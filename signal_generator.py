"""Glue layer that turns OHLCV + indicators + model into a signal dict."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

import pandas as pd

from feature_engineering import build_features


class SignalGenerator:
    def __init__(self, model):
        self.model = model

    def generate(self, ohlcv: pd.DataFrame, indicators: Dict[str, float]) -> Dict:
        features = build_features(ohlcv, indicators)
        prob_up = float(self.model.predict_proba(features))
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price": features["price"],
            "prob_up": prob_up,
            "rsi": features["rsi"],
            "ema_spread": features["ema_spread"],
            "ret_1m": features["ret_1m"],
        }
