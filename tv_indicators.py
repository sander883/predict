"""TradingView indicator fetcher with a local fallback.

Primary path: tradingview-ta (https://github.com/Mathieu2301/TradingView-API parity).
Fallback: compute RSI/EMA locally from the OHLCV DataFrame.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

from config import CONFIG

log = logging.getLogger(__name__)

_TV_INTERVAL_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1d",
}


def fetch_tv_indicators(
    symbol: str = CONFIG.tv_symbol,
    screener: str = CONFIG.tv_screener,
    interval: str = CONFIG.tv_interval,
    timeout: float = CONFIG.tv_timeout_s,
) -> Optional[Dict[str, float]]:
    """Return {'rsi','ema9','ema21','close'} from TradingView, or None on failure."""
    try:
        from tradingview_ta import TA_Handler, Interval
    except ImportError:
        log.warning("tradingview_ta not installed; skipping TV fetch")
        return None

    interval_map = {
        "1m": Interval.INTERVAL_1_MINUTE,
        "5m": Interval.INTERVAL_5_MINUTES,
        "15m": Interval.INTERVAL_15_MINUTES,
        "1h": Interval.INTERVAL_1_HOUR,
        "4h": Interval.INTERVAL_4_HOURS,
        "1d": Interval.INTERVAL_1_DAY,
    }
    tv_interval = interval_map.get(interval, Interval.INTERVAL_1_MINUTE)

    if ":" in symbol:
        exchange, ticker = symbol.split(":", 1)
    else:
        exchange, ticker = "BINANCE", symbol

    try:
        handler = TA_Handler(
            symbol=ticker,
            screener=screener,
            exchange=exchange,
            interval=tv_interval,
            timeout=timeout,
        )
        analysis = handler.get_analysis()
        ind = analysis.indicators
        return {
            "rsi": float(ind.get("RSI")) if ind.get("RSI") is not None else None,
            "ema9": float(ind.get("EMA9")) if ind.get("EMA9") is not None else None,
            "ema21": float(ind.get("EMA21")) if ind.get("EMA21") is not None else None,
            "close": float(ind.get("close")) if ind.get("close") is not None else None,
        }
    except Exception as e:
        log.warning("TradingView fetch failed: %s", e)
        return None


# ---------- Local fallback ----------

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def compute_local_indicators(ohlcv: pd.DataFrame) -> Dict[str, float]:
    close = ohlcv["close"]
    return {
        "rsi": float(_rsi(close, 14).iloc[-1]),
        "ema9": float(_ema(close, 9).iloc[-1]),
        "ema21": float(_ema(close, 21).iloc[-1]),
        "close": float(close.iloc[-1]),
    }


def get_indicators(ohlcv: pd.DataFrame) -> Dict[str, float]:
    """Use TradingView if enabled and available, else local computation."""
    if CONFIG.use_tradingview:
        tv = fetch_tv_indicators()
        if tv and all(v is not None for v in tv.values()):
            return tv
        log.info("Falling back to local indicators")
    return compute_local_indicators(ohlcv)
