"""Real-time BTC market data via ccxt (Binance public endpoints)."""

from __future__ import annotations

import logging
from typing import Optional

import ccxt
import pandas as pd

from config import CONFIG

log = logging.getLogger(__name__)


class DataCollector:
    """Thin ccxt wrapper that returns an OHLCV DataFrame."""

    def __init__(self, exchange_id: str = CONFIG.exchange_id):
        exchange_cls = getattr(ccxt, exchange_id)
        self.exchange = exchange_cls({"enableRateLimit": True})

    def fetch_ohlcv(
        self,
        symbol: str = CONFIG.symbol,
        timeframe: str = CONFIG.timeframe,
        limit: int = CONFIG.candles_limit,
    ) -> pd.DataFrame:
        raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp").astype(float)
        return df

    def fetch_last_price(self, symbol: str = CONFIG.symbol) -> Optional[float]:
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker["last"])
        except Exception as e:
            log.warning("fetch_ticker failed: %s", e)
            return None
