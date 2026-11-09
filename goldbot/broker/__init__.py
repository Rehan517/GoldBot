"""Broker layer: the only part of GoldBot that talks to MetaTrader 5.

Built in Step 8. Keeping it isolated here means the strategy, risk and
backtest code never depends on MT5 and can be tested on the Mac.
"""
