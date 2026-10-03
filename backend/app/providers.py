"""Data providers. Swap implementations (e.g. a broker API) without touching analysis code."""
import io
from typing import Protocol

import numpy as np
import pandas as pd

NSE_NIFTY500_CSV = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
FALLBACK_UNIVERSE = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "ITC", "LT"]


class PriceProvider(Protocol):
    def history(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """Daily OHLCV, lowercase columns, DatetimeIndex ascending."""

    def last_price(self, symbol: str) -> float: ...


def load_universe() -> list[str]:
    """Nifty 500 symbols from NSE; falls back to a small list when offline."""
    try:
        import httpx

        r = httpx.get(NSE_NIFTY500_CSV, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text))["Symbol"].dropna().tolist()
    except Exception:
        return list(FALLBACK_UNIVERSE)


class YahooProvider:
    """Free, delayed (~15 min) NSE data via yfinance. Unofficial; may rate-limit."""

    def history(self, symbol: str, days: int = 365) -> pd.DataFrame:
        import yfinance as yf

        df = yf.Ticker(f"{symbol}.NS").history(period=f"{max(days, 30)}d", auto_adjust=True)
        if df.empty:
            raise LookupError(f"No data for {symbol}")
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df

    def last_price(self, symbol: str) -> float:
        return float(self.history(symbol, 30)["close"].iloc[-1])


class SyntheticProvider:
    """Deterministic random-walk data for tests and offline demos."""

    def history(self, symbol: str, days: int = 365) -> pd.DataFrame:
        rng = np.random.default_rng(sum(map(ord, symbol)))
        n = max(days, 30)
        close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n)))
        open_ = np.r_[close[0], close[:-1]]
        high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n))
        low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n))
        vol = rng.integers(500_000, 2_000_000, n)
        idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
        return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)

    def last_price(self, symbol: str) -> float:
        return float(self.history(symbol, 30)["close"].iloc[-1])
