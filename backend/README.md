# Nifty 500 Analyzer – backend

FastAPI service that pulls NSE price data, computes technical indicators and
produces a Bullish / Neutral / Bearish signal with reasons. Signals are
informational only, not investment advice.

## Run
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # live data via yfinance (delayed ~15 min)
DATA_SOURCE=synthetic uvicorn app.main:app --reload   # offline demo data
pytest
```

## Endpoints
- `GET /api/universe` – Nifty 500 symbols (NSE CSV, small fallback list offline)
- `GET /api/stocks/{symbol}/analysis` – price, support/resistance, signal, score, reasons
- `GET /api/stocks/{symbol}/candles?days=180` – OHLCV for charting
- `GET /api/screener?limit=25&signal=Bullish` – ranked list
- `WS /ws/quotes/{symbol}?interval=5` – live price pushes

## Roadmap
1. ✅ Data providers, indicators, technical scoring, API, tests
2. Fundamentals component (P/E, ROE, debt/equity, growth)
3. News sentiment component
4. Backtesting of the scoring rules
5. React dashboard (screener, candlestick charts, live ticker)
6. Broker feed (Zerodha/Upstox) behind the `PriceProvider` interface
