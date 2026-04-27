"""CSV logger and post-hoc evaluator for predictions."""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import pandas as pd

from config import CONFIG

log = logging.getLogger(__name__)

_FIELDS = ["timestamp", "price", "prob_up", "rsi", "ema_spread", "ret_1m"]


def log_signal(signal: Dict, path: str = CONFIG.log_csv_path) -> None:
    write_header = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(signal)


def _bucket(p: float) -> str:
    edges = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]
    for i in range(len(edges) - 1):
        if edges[i] <= p < edges[i + 1]:
            return f"[{edges[i]:.1f},{edges[i+1]:.1f})"
    return "n/a"


def evaluate(
    path: str = CONFIG.log_csv_path,
    horizon_min: int = CONFIG.forecast_horizon_min,
    decision_threshold: float = 0.5,
) -> Optional[Dict]:
    """Compare each prediction to the price `horizon_min` later.

    Returns dict with accuracy, winrate (when model takes a side), and calibration buckets.
    """
    if not os.path.exists(path):
        log.warning("No log file at %s", path)
        return None

    df = pd.read_csv(path)
    if df.empty:
        return None
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    horizon = timedelta(minutes=horizon_min)
    correct: List[int] = []
    sides_correct: List[int] = []
    bucket_data: Dict[str, List[int]] = {}

    for i, row in df.iterrows():
        target_t = row["timestamp"] + horizon
        future = df[df["timestamp"] >= target_t]
        if future.empty:
            continue
        future_price = float(future.iloc[0]["price"])
        went_up = int(future_price > row["price"])
        pred_up = int(row["prob_up"] >= decision_threshold)

        correct.append(int(pred_up == went_up))
        if abs(row["prob_up"] - 0.5) > 1e-9:
            sides_correct.append(int(pred_up == went_up))

        bucket_data.setdefault(_bucket(row["prob_up"]), []).append(went_up)

    if not correct:
        log.warning("Not enough horizon-matched samples to evaluate")
        return None

    calibration = {
        b: {"avg_actual_up": sum(v) / len(v), "n": len(v)}
        for b, v in sorted(bucket_data.items())
    }

    return {
        "n_samples": len(correct),
        "accuracy": sum(correct) / len(correct),
        "winrate": (sum(sides_correct) / len(sides_correct)) if sides_correct else None,
        "calibration": calibration,
    }
