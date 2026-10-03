import asyncio
import os

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import indicators as ind
from .providers import SyntheticProvider, YahooProvider, load_universe
from .scoring import combine, technical_component

app = FastAPI(title="Nifty 500 Analyzer")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

# DATA_SOURCE=synthetic runs fully offline.
provider = SyntheticProvider() if os.getenv("DATA_SOURCE") == "synthetic" else YahooProvider()
_universe: list[str] | None = None


def universe() -> list[str]:
    global _universe
    if _universe is None:
        _universe = load_universe()
    return _universe


def analyze(symbol: str) -> dict:
    symbol = symbol.upper()
    try:
        df = provider.history(symbol)
    except LookupError:
        raise HTTPException(404, f"No data for {symbol}")
    result = combine(technical_component(df))
    support, resistance = ind.support_resistance(df)
    return {
        "symbol": symbol,
        "price": round(float(df["close"].iloc[-1]), 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "disclaimer": "Informational signals only; not investment advice.",
        **result,
    }


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/universe")
def get_universe():
    return {"count": len(universe()), "symbols": universe()}


@app.get("/api/stocks/{symbol}/analysis")
def stock_analysis(symbol: str):
    return analyze(symbol)


@app.get("/api/stocks/{symbol}/candles")
def candles(symbol: str, days: int = 180):
    df = provider.history(symbol.upper(), days).tail(days)
    return [{"t": i.isoformat(), **{c: float(r[c]) for c in df.columns}} for i, r in df.iterrows()]


@app.get("/api/screener")
def screener(limit: int = 25, signal: str | None = None):
    rows = []
    for sym in universe()[:limit]:
        try:
            rows.append(analyze(sym))
        except Exception:
            continue
    if signal:
        rows = [r for r in rows if r["signal"].lower() == signal.lower()]
    return sorted(rows, key=lambda r: r["score"] or 0, reverse=True)


@app.websocket("/ws/quotes/{symbol}")
async def quotes(ws: WebSocket, symbol: str, interval: float = 5.0):
    """Pushes the latest price every `interval` seconds."""
    await ws.accept()
    try:
        while True:
            price = await asyncio.to_thread(provider.last_price, symbol.upper())
            await ws.send_json({"symbol": symbol.upper(), "price": round(price, 2)})
            await asyncio.sleep(max(interval, 1.0))
    except (WebSocketDisconnect, LookupError):
        pass
