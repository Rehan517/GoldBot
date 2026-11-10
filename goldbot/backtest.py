"""Bar-by-bar backtester.

For every bar, in this order:
  1. ENTER at this bar's open if the previous closed bar produced a signal.
  2. EXIT if this bar reached the stop loss or take profit.
  3. RECORD equity at this bar's close (including open profit/loss).
  4. ASK the strategy for a signal on this (now closed) bar; only if no trade is open.

Price conventions: MT5 bars are BID prices.
  Buy  -> enter at ask (bid + spread), exit at bid.
  Sell -> enter at bid,               exit at ask (bid + spread).

Pessimistic rules (see docs/ROADMAP.md, Step 5):
  - Spread = max(bar's spread, min_spread_points). Slippage on entries and stop exits.
  - If the stop AND the target are both inside one bar, assume the STOP was hit first.
  - Gap through the stop -> fill at the (worse) open. Gap through the target -> fill at the target.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pandas as pd

from goldbot.risk import position_size
from goldbot.strategy import Signal

# A signal function receives (previous bar, current bar, current bar's time) and returns a
# Signal or None. Normally it's strategy.evaluate_bar with the params filled in, but tests can
# pass a scripted one ("buy on bar 3"), so the engine can be tested on its own.
SignalFn = Callable[[Mapping, Mapping, pd.Timestamp], Signal | None]


@dataclass(frozen=True)
class Costs:
    min_spread_points: float
    slippage_points: float
    commission_per_lot: float
    swap_long_points: float    # per lot per night; negative = you pay
    swap_short_points: float

    @classmethod
    def from_settings(cls, settings: dict) -> "Costs":
        bt, sym = settings["backtest"], settings["symbol"]
        return cls(bt["min_spread_points"], bt["slippage_points"], bt["commission_per_lot"],
                   sym["swap_long"], sym["swap_short"])


@dataclass(frozen=True)
class OpenTrade:
    direction: str
    lots: float
    signal_bar: pd.Timestamp
    entry_index: int
    entry_time: pd.Timestamp
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_money: float       # $ planned loss if the stop is hit (= 1R)
    sizing_note: str


@dataclass
class BacktestResult:
    trades: pd.DataFrame     # one row per closed trade
    equity: pd.Series        # account value at every bar's close
    skipped: pd.DataFrame    # signals we did NOT take, and why
    initial_equity: float


def swap_nights(entry_time: pd.Timestamp, exit_time: pd.Timestamp) -> int:
    """How many nights of swap a position pays (rollover at server midnight).

    MT5 convention: Wednesday night counts 3x (covering the weekend), Saturday and
    Sunday nights count 0. So a full week Mon-Fri = 1 + 1 + 3 + 1 + 1 = 7 nights.
    """
    nights = 0
    for midnight in pd.date_range(entry_time.normalize() + pd.Timedelta(days=1),
                                  exit_time.normalize(), freq="D"):
        day_before = (midnight - pd.Timedelta(days=1)).day_of_week   # Mon=0 ... Sun=6
        if day_before == 2:
            nights += 3
        elif day_before <= 4:
            nights += 1
    return nights


def _money(price_move: float, lots: float, symbol: dict) -> float:
    """$ value of a price move on `lots` (positive move = profit)."""
    return price_move / symbol["tick_size"] * symbol["tick_value"] * lots


def _open_trade(signal: Signal, index: int, time: pd.Timestamp, bar: Mapping, spread: float,
                slip: float, balance: float, symbol: dict, risk: dict) -> tuple[OpenTrade | None, str]:
    if signal.direction == "buy":
        entry = bar["open"] + spread + slip   # buy at the ask, plus slippage
    else:
        entry = bar["open"] - slip            # sell at the bid, minus slippage

    size = position_size(balance, signal.stop_distance, symbol,
                         risk["risk_per_trade_pct"], risk["max_risk_per_trade_pct"])
    if size.lots == 0:
        return None, size.note

    trade = OpenTrade(
        direction=signal.direction, lots=size.lots, signal_bar=signal.signal_bar,
        entry_index=index, entry_time=time, entry_price=entry,
        stop_loss=signal.stop_loss_price(entry), take_profit=signal.take_profit_price(entry),
        risk_money=size.risk_money, sizing_note=size.note,
    )
    return trade, size.note


def _check_exit(pos: OpenTrade, bar: Mapping, spread: float, slip: float) -> tuple[float | None, str]:
    """Did this bar hit the stop or the target? Returns (exit price, reason) or (None, "")."""
    if pos.direction == "buy":   # a buy closes by SELLING at the bid (the bar's own prices)
        if bar["open"] <= pos.stop_loss:
            return bar["open"] - slip, "stop_gap"     # gapped through the stop: worse fill
        if bar["low"] <= pos.stop_loss:
            return pos.stop_loss - slip, "stop"       # checked BEFORE target: pessimistic
        if bar["high"] >= pos.take_profit:
            return pos.take_profit, "target"
    else:                        # a sell closes by BUYING at the ask (bid + spread)
        ask_open, ask_high, ask_low = bar["open"] + spread, bar["high"] + spread, bar["low"] + spread
        if ask_open >= pos.stop_loss:
            return ask_open + slip, "stop_gap"
        if ask_high >= pos.stop_loss:
            return pos.stop_loss + slip, "stop"
        if ask_low <= pos.take_profit:
            return pos.take_profit, "target"
    return None, ""


def _close_trade(pos: OpenTrade, index: int, time: pd.Timestamp, exit_price: float, reason: str,
                 symbol: dict, costs: Costs) -> dict:
    move = exit_price - pos.entry_price if pos.direction == "buy" else pos.entry_price - exit_price
    gross = _money(move, pos.lots, symbol)
    commission = costs.commission_per_lot * pos.lots
    swap_points = costs.swap_long_points if pos.direction == "buy" else costs.swap_short_points
    swap = swap_nights(pos.entry_time, time) * swap_points * symbol["tick_value"] * pos.lots
    pnl = gross - commission + swap
    return {
        "signal_bar": pos.signal_bar, "entry_time": pos.entry_time, "exit_time": time,
        "direction": pos.direction, "lots": pos.lots,
        "entry": round(pos.entry_price, 2), "stop_loss": round(pos.stop_loss, 2),
        "take_profit": round(pos.take_profit, 2), "exit": round(exit_price, 2),
        "exit_reason": reason, "bars_held": index - pos.entry_index,
        "gross": round(gross, 2), "commission": round(commission, 2), "swap": round(swap, 2),
        "pnl": round(pnl, 2), "r": round(pnl / pos.risk_money, 3), "risk_money": pos.risk_money,
        "sizing_note": pos.sizing_note,
    }


def run_backtest(bars: pd.DataFrame, signal_fn: SignalFn, symbol: dict, risk: dict,
                 costs: Costs, initial_equity: float) -> BacktestResult:
    """Simulate trading over `bars` (CLOSED bars with open/high/low/close/spread columns)."""
    tick = symbol["tick_size"]
    rows, times = bars.to_dict("records"), bars.index
    last = len(rows) - 1

    balance = initial_equity
    position: OpenTrade | None = None
    pending: Signal | None = None          # signal waiting for the next bar's open
    trades, skipped, equity = [], [], []

    for i, (time, bar) in enumerate(zip(times, rows)):
        spread = max(bar["spread"], costs.min_spread_points) * tick
        slip = costs.slippage_points * tick

        # 1. ENTER at this bar's open, if the previous bar signalled.
        if pending is not None:
            position, note = _open_trade(pending, i, time, bar, spread, slip, balance, symbol, risk)
            if position is None:
                skipped.append({"signal_bar": pending.signal_bar, "direction": pending.direction,
                                "reason": note})
            pending = None

        # 2. EXIT if the stop or target was reached during this bar.
        if position is not None:
            exit_price, reason = _check_exit(position, bar, spread, slip)
            if exit_price is not None:
                trade = _close_trade(position, i, time, exit_price, reason, symbol, costs)
                balance += trade["pnl"]
                trades.append(trade)
                position = None

        # 3. RECORD equity at the close (bid for buys, ask for sells).
        open_pnl = 0.0
        if position is not None:
            if position.direction == "buy":
                open_pnl = _money(bar["close"] - position.entry_price, position.lots, symbol)
            else:
                open_pnl = _money(position.entry_price - (bar["close"] + spread), position.lots, symbol)
        equity.append(balance + open_pnl)

        # 4. ASK for a signal on this closed bar (needs a previous bar, and a next bar to enter on).
        if 1 <= i < last:
            signal = signal_fn(rows[i - 1], bar, time)
            if signal is not None:
                if position is not None:
                    skipped.append({"signal_bar": time, "direction": signal.direction,
                                    "reason": "skip: position already open"})
                else:
                    pending = signal

    # Data ran out with a trade still open: close it at the last close.
    if position is not None:
        bar = rows[last]
        spread = max(bar["spread"], costs.min_spread_points) * tick
        exit_price = bar["close"] if position.direction == "buy" else bar["close"] + spread
        trade = _close_trade(position, last, times[last], exit_price, "end_of_data", symbol, costs)
        balance += trade["pnl"]
        trades.append(trade)
        equity[-1] = balance

    return BacktestResult(
        trades=pd.DataFrame(trades),
        equity=pd.Series(equity, index=times, name="equity"),
        skipped=pd.DataFrame(skipped, columns=["signal_bar", "direction", "reason"]),
        initial_equity=initial_equity,
    )
