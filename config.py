"""Central configuration for the BTC signal generator."""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Config:
    # --- Market data (ccxt) ---
    exchange_id: str = "binance"
    symbol: str = "BTC/USDT"
    timeframe: str = "1m"
    candles_limit: int = 200

    # --- TradingView ---
    tv_symbol: str = "BINANCE:BTCUSDT"
    tv_screener: str = "crypto"
    tv_interval: str = "1m"
    tv_timeout_s: float = 5.0

    # --- Feature engineering ---
    return_lookbacks: tuple = (1, 3, 5)
    volatility_window: int = 10
    forecast_horizon_min: int = 5

    # --- Rule-based weights (clamped to [0,1]) ---
    rule_weights: Dict[str, float] = field(default_factory=lambda: {
        "rsi_oversold": 0.10,    # RSI < 30 -> +
        "rsi_overbought": 0.10,  # RSI > 70 -> -
        "ema_bull_cross": 0.10,  # EMA9 > EMA21 -> +
        "ret1_positive": 0.05,   # last 1m return > 0 -> +
    })

    # --- Toggles ---
    use_tradingview: bool = True       # if False, compute indicators locally
    use_ml_model: bool = False          # if False, use rule-based model
    ml_model_path: str = "ml_model.pkl"
    use_polymarket: bool = True         # fetch YES price + compute edge/action

    # --- Polymarket ---
    poly_market_slug: str = ""          # e.g. "bitcoin-up-or-down-april-27-12pm-et"
    poly_token_id: str = ""             # YES outcome CLOB token_id (overrides slug)
    poly_timeout_s: float = 5.0
    edge_threshold: float = 0.03        # min edge to take a side
    kelly_fraction: float = 0.25        # fractional Kelly multiplier

    # --- Loop / Runtime ---
    poll_interval_s: int = 30

    # --- Logging ---
    log_csv_path: str = "predictions.csv"


CONFIG = Config()
