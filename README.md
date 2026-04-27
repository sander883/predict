# BTC 5-Minute Signal Generator (Polymarket)

Production-ready Python system that predicts the probability BTC/USDT moves up
over the next 5 minutes, designed to feed Polymarket short-horizon markets.

## Stack

- **ccxt** — real-time BTC/USDT 1m OHLCV from Binance
- **tradingview-ta** — RSI(14), EMA(9), EMA(21) from TradingView (with local fallback)
- **mlmodelpoly** — optional ML wrapper (rule-based baseline ships by default)
- **Polymarket CLOB** — YES price book → edge → action (BUY_YES / BUY_NO / HOLD)

## Layout

```
predict/
├── config.py             # parameters & toggles
├── data_collector.py     # ccxt OHLCV
├── tv_indicators.py      # TradingView + local fallback
├── feature_engineering.py
├── model.py              # RuleBasedModel + MLModel
├── signal_generator.py
├── logger.py             # CSV log + evaluator
├── main.py               # loop / --once / --evaluate
└── requirements.txt
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
# Single iteration
python main.py --once

# Continuous loop (every 30s by default)
python main.py

# Evaluate accuracy / winrate / calibration on the log
python main.py --evaluate
```

## Toggles (`config.py`)

| Setting | Default | Notes |
|---|---|---|
| `use_tradingview` | `True` | When `False` (or on TV failure) indicators are computed locally |
| `use_ml_model` | `False` | When `True` and `ml_model.pkl` exists, MLModel is used; falls back to rules |
| `use_polymarket` | `True` | Fetch YES book and compute edge/action |
| `poly_market_slug` | `""` | Gamma slug, e.g. `"bitcoin-up-or-down-april-27-12pm-et"` |
| `poly_token_id` | `""` | YES CLOB token_id (overrides slug) |
| `edge_threshold` | `0.03` | Min edge to take a side |
| `kelly_fraction` | `0.25` | Fractional Kelly multiplier on size |
| `poll_interval_s` | `30` | Loop cadence |
| `forecast_horizon_min` | `5` | Used by the evaluator |

## Rule-based model

```
base = 0.5
RSI < 30 -> +0.10
RSI > 70 -> -0.10
EMA9 > EMA21 -> +0.10 (else -0.10)
ret_1m > 0 -> +0.05 (else -0.05)
clamp to [0, 1]
```

## Plugging in an ML model (`mlmodelpoly`)

`MLModel` in `model.py` loads any pickle/joblib estimator exposing
`predict_proba(X)` with the positive class = "up". Feature order:

```
ret_1m, ret_3m, ret_5m, vol_std, volume_z, rsi, ema_spread
```

Train upstream (e.g. with mlmodelpoly), save as `ml_model.pkl`, set
`use_ml_model = True` and run.

## Polymarket integration

`polymarket_client.py` resolves a market via the public Gamma API and reads the
best YES bid/ask from the CLOB:

```
GET https://gamma-api.polymarket.com/markets?slug=<slug>
GET https://clob.polymarket.com/price?token_id=<id>&side=buy|sell
```

`edge.py` then computes:

```
edge_yes = prob_up - yes_ask
edge_no  = (1 - prob_up) - (1 - yes_bid)
```

Action selection (whichever side wins, if its edge clears `edge_threshold`):

- `BUY_YES` — model is more bullish than the market ask
- `BUY_NO`  — model is more bearish than the implied NO ask
- `HOLD`    — neither side clears the threshold

Size = `kelly_fraction * fractional_Kelly(p, price)`, clamped to `[0, 1]`.

Configure either by slug or directly by token_id:

```python
# config.py
poly_market_slug = "bitcoin-up-or-down-april-27-12pm-et"
# or
poly_token_id = "71321045679252212594626385532706912750332728571942165818289...."
```

## Example output

```json
{
  "timestamp": "2026-04-27T12:34:56.789+00:00",
  "price": 67421.45,
  "prob_up": 0.65,
  "rsi": 42.7,
  "ema_spread": 0.00031,
  "ret_1m": 0.00012,
  "yes_bid": 0.53, "yes_ask": 0.55, "yes_mid": 0.54,
  "edge_yes": 0.10, "edge_no": -0.08,
  "action": "BUY_YES", "size": 0.0556
}
```

`predictions.csv`:

```
timestamp,price,prob_up,rsi,ema_spread,ret_1m
2026-04-27T12:34:56.789+00:00,67421.45,0.55,42.7,0.00031,0.00012
```

`python main.py --evaluate`:

```json
{
  "n_samples": 240,
  "accuracy": 0.54,
  "winrate": 0.56,
  "calibration": {
    "[0.4,0.5)": {"avg_actual_up": 0.47, "n": 60},
    "[0.5,0.6)": {"avg_actual_up": 0.55, "n": 92},
    "[0.6,0.7)": {"avg_actual_up": 0.61, "n": 38}
  }
}
```

## References

- ccxt — https://github.com/ccxt/ccxt
- TradingView API — https://github.com/Mathieu2301/TradingView-API
- mlmodelpoly — https://github.com/txbabaxyz/mlmodelpoly
- Polymarket agents — https://github.com/polymarket/agents
