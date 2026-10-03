import os

os.environ["DATA_SOURCE"] = "synthetic"

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import indicators as ind
from app.main import app
from app.providers import SyntheticProvider
from app.scoring import combine, technical_component, Component


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1, 60, dtype=float))
    assert ind.rsi(up).iloc[-1] == 100
    down = pd.Series(np.arange(60, 1, -1, dtype=float))
    assert ind.rsi(down).iloc[-1] < 5
    r = ind.rsi(SyntheticProvider().history("TCS")["close"]).dropna()
    assert r.between(0, 100).all()


def test_macd_hist_is_line_minus_signal():
    c = SyntheticProvider().history("INFY")["close"]
    m = ind.macd(c)
    assert np.allclose(m["hist"], m["macd"] - m["signal"])


def test_bollinger_ordering():
    b = ind.bollinger(SyntheticProvider().history("SBIN")["close"]).dropna()
    assert (b["upper"] >= b["mid"]).all() and (b["mid"] >= b["lower"]).all()


def test_support_resistance():
    df = SyntheticProvider().history("ITC")
    s, r = ind.support_resistance(df)
    assert s < r


def test_uptrend_scores_bullish():
    close = pd.Series(np.linspace(100, 200, 120))
    df = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close,
                       "volume": 1_000_000})
    comp = technical_component(df)
    assert comp.score > 0 and combine(comp)["signal"] in {"Bullish", "Neutral"}


def test_insufficient_history():
    df = SyntheticProvider().history("TCS", 30).head(10)
    assert technical_component(df).score is None
    assert combine(technical_component(df))["signal"] == "Unknown"


def test_combine_renormalises_missing_components():
    out = combine(Component(1.0), None, Component(-1.0))
    # technical 0.5, sentiment 0.2 -> (0.5 - 0.2) / 0.7
    assert out["score"] == pytest.approx(0.429, abs=1e-3)


client = TestClient(app)


def test_api_analysis():
    r = client.get("/api/stocks/TCS/analysis")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "TCS" and body["signal"] in {"Bullish", "Neutral", "Bearish"}
    assert body["support"] < body["resistance"]


def test_api_screener_and_candles():
    assert len(client.get("/api/screener?limit=3").json()) == 3
    assert len(client.get("/api/stocks/TCS/candles?days=50").json()) == 50


def test_websocket_quote():
    with client.websocket_connect("/ws/quotes/TCS?interval=1") as ws:
        assert ws.receive_json()["symbol"] == "TCS"
