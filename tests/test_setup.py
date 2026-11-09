"""Smoke tests: prove the environment is wired up correctly.

If these pass, pytest can find our tests, import our package,
and import the libraries we installed into the virtual environment.
"""

import sys


def test_goldbot_package_imports():
    import goldbot

    assert goldbot.__version__ == "0.1.0"


def test_core_libraries_import():
    import matplotlib
    import numpy
    import pandas

    # A tiny DataFrame, the shape our price bars will take from Step 1.
    bars = pandas.DataFrame({"close": [2650.10, 2651.35, 2649.80]})
    assert len(bars) == 3


def test_running_inside_virtualenv():
    # In a venv, sys.prefix points at .venv while sys.base_prefix points at
    # the system Python. If they're equal, we're using the wrong Python.
    assert sys.prefix != sys.base_prefix, "Activate the venv: source .venv/bin/activate"
