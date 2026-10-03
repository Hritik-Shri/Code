"""Combine technical, fundamental and sentiment views into a signal with reasons.

Each component score is in [-1, 1] (bearish -> bullish) or None when unavailable.
Missing components are dropped and the remaining weights renormalised.
"""
from dataclasses import dataclass, field

import pandas as pd

from . import indicators as ind

WEIGHTS = {"technical": 0.5, "fundamental": 0.3, "sentiment": 0.2}
MIN_BARS = 30


@dataclass
class Component:
    score: float | None
    reasons: list[str] = field(default_factory=list)


def _clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))


def technical_component(df: pd.DataFrame) -> Component:
    if len(df) < MIN_BARS:
        return Component(None, ["Not enough price history"])
    close = df["close"]
    last = float(close.iloc[-1])
    votes: list[float] = []
    reasons: list[str] = []

    r = float(ind.rsi(close).iloc[-1])
    if r < 30:
        votes.append(1.0); reasons.append(f"RSI {r:.0f}: oversold")
    elif r > 70:
        votes.append(-1.0); reasons.append(f"RSI {r:.0f}: overbought")
    else:
        votes.append((r - 50) / 40); reasons.append(f"RSI {r:.0f}: neutral")

    m = ind.macd(close)
    hist = float(m["hist"].iloc[-1])
    votes.append(1.0 if hist > 0 else -1.0)
    reasons.append("MACD histogram positive" if hist > 0 else "MACD histogram negative")

    s20 = float(ind.sma(close, 20).iloc[-1])
    votes.append(1.0 if last > s20 else -1.0)
    reasons.append("Price above 20-day average" if last > s20 else "Price below 20-day average")

    if len(df) >= 50:
        s50 = float(ind.sma(close, 50).iloc[-1])
        votes.append(1.0 if s20 > s50 else -1.0)
        reasons.append("20-day average above 50-day" if s20 > s50 else "20-day average below 50-day")

    vr = ind.volume_ratio(df["volume"]).iloc[-1]
    if pd.notna(vr) and vr > 1.5:
        direction = 1.0 if close.iloc[-1] >= close.iloc[-2] else -1.0
        votes.append(direction)
        reasons.append(f"Volume {vr:.1f}x average on {'up' if direction > 0 else 'down'} day")

    return Component(_clamp(sum(votes) / len(votes)), reasons)


def combine(technical: Component, fundamental: Component | None = None,
            sentiment: Component | None = None) -> dict:
    parts = {"technical": technical, "fundamental": fundamental, "sentiment": sentiment}
    avail = {k: v for k, v in parts.items() if v is not None and v.score is not None}
    if not avail:
        return {"signal": "Unknown", "score": None, "components": {}, "reasons": technical.reasons}
    total_w = sum(WEIGHTS[k] for k in avail)
    score = sum(WEIGHTS[k] * v.score for k, v in avail.items()) / total_w
    signal = "Bullish" if score > 0.25 else "Bearish" if score < -0.25 else "Neutral"
    return {
        "signal": signal,
        "score": round(score, 3),
        "components": {k: round(v.score, 3) for k, v in avail.items()},
        "reasons": [r for v in avail.values() for r in v.reasons],
    }
