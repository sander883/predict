"""Probability model: rule-based default, ML-ready wrapper for mlmodelpoly."""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from config import CONFIG

log = logging.getLogger(__name__)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class RuleBasedModel:
    """Simple, interpretable baseline used until an ML model is trained."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.w = weights or CONFIG.rule_weights

    def predict_proba(self, features: Dict[str, float]) -> float:
        prob = 0.5
        rsi = features.get("rsi", 50.0)
        ema9 = features.get("ema9", 0.0)
        ema21 = features.get("ema21", 0.0)
        ret_1m = features.get("ret_1m", 0.0)

        if rsi < 30:
            prob += self.w["rsi_oversold"]
        if rsi > 70:
            prob -= self.w["rsi_overbought"]
        if ema9 > ema21:
            prob += self.w["ema_bull_cross"]
        else:
            prob -= self.w["ema_bull_cross"]
        if ret_1m > 0:
            prob += self.w["ret1_positive"]
        else:
            prob -= self.w["ret1_positive"]

        return _clamp(prob)


class MLModel:
    """Wrapper compatible with mlmodelpoly-style sklearn estimators.

    Expects an estimator exposing `predict_proba(X)` returning [[p_down, p_up]].
    """

    FEATURE_ORDER = (
        "ret_1m", "ret_3m", "ret_5m",
        "vol_std", "volume_z",
        "rsi", "ema_spread",
    )

    def __init__(self, model_path: str = CONFIG.ml_model_path):
        self.model_path = model_path
        self.model = None

    def load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"ML model not found at {self.model_path}")
        try:
            import joblib
            self.model = joblib.load(self.model_path)
        except ImportError:
            import pickle
            with open(self.model_path, "rb") as f:
                self.model = pickle.load(f)
        log.info("Loaded ML model from %s", self.model_path)
        return self

    def predict_proba(self, features: Dict[str, float]) -> float:
        if self.model is None:
            self.load_model()
        x = [[features.get(k, 0.0) for k in self.FEATURE_ORDER]]
        proba = self.model.predict_proba(x)[0]
        # assume positive class = "up" at index 1
        p_up = float(proba[1]) if len(proba) > 1 else float(proba[0])
        return _clamp(p_up)


def get_model():
    """Factory honoring the CONFIG.use_ml_model toggle, with rule-based fallback."""
    if CONFIG.use_ml_model:
        try:
            return MLModel().load_model()
        except Exception as e:
            log.warning("ML model unavailable (%s); falling back to rule-based", e)
    return RuleBasedModel()
