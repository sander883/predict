"""Combine OHLCV + indicators into a feature vector."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from config import CONFIG


def build_features(ohlcv: pd.DataFrame, indicators: Dict[str, float]) -> Dict[str, float]:
    if len(ohlcv) < max(CONFIG.return_lookbacks) + CONFIG.volatility_window + 1:
        raise ValueError("Not enough candles to compute features")

    close = ohlcv["close"]
    volume = ohlcv["volume"]

    feats: Dict[str, float] = {}
    for n in CONFIG.return_lookbacks:
        feats[f"ret_{n}m"] = float(close.iloc[-1] / close.iloc[-1 - n] - 1.0)

    log_ret = np.log(close / close.shift(1))
    feats["vol_std"] = float(log_ret.rolling(CONFIG.volatility_window).std().iloc[-1])

    feats["volume_z"] = float(
        (volume.iloc[-1] - volume.tail(CONFIG.volatility_window).mean())
        / (volume.tail(CONFIG.volatility_window).std() + 1e-9)
    )

    feats["price"] = float(close.iloc[-1])
    feats["rsi"] = float(indicators.get("rsi", 50.0))
    feats["ema9"] = float(indicators.get("ema9", feats["price"]))
    feats["ema21"] = float(indicators.get("ema21", feats["price"]))
    feats["ema_spread"] = (feats["ema9"] - feats["ema21"]) / feats["price"]

    return feats
