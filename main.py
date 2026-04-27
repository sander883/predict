"""Main loop: fetch -> features -> signal -> log."""

from __future__ import annotations

import argparse
import json
import logging
import time

from config import CONFIG
from data_collector import DataCollector
from logger import evaluate, log_signal
from model import get_model
from signal_generator import SignalGenerator
from tv_indicators import get_indicators

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("btc-signal")


def run_once(collector: DataCollector, generator: SignalGenerator) -> dict:
    ohlcv = collector.fetch_ohlcv()
    indicators = get_indicators(ohlcv)
    signal = generator.generate(ohlcv, indicators)
    log_signal(signal)
    log.info(
        "price=%.2f prob_up=%.3f rsi=%.1f ema_spread=%.5f ret_1m=%.5f",
        signal["price"], signal["prob_up"], signal["rsi"],
        signal["ema_spread"], signal["ret_1m"],
    )
    return signal


def loop():
    collector = DataCollector()
    model = get_model()
    generator = SignalGenerator(model)
    log.info("Started loop: poll=%ss model=%s tv=%s",
             CONFIG.poll_interval_s, type(model).__name__, CONFIG.use_tradingview)

    while True:
        start = time.time()
        try:
            run_once(collector, generator)
        except Exception as e:
            log.exception("Iteration failed: %s", e)
        sleep_for = max(0.0, CONFIG.poll_interval_s - (time.time() - start))
        time.sleep(sleep_for)


def main():
    parser = argparse.ArgumentParser(description="BTC 5-min direction signal generator")
    parser.add_argument("--once", action="store_true", help="Run a single iteration and exit")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate predictions log and exit")
    args = parser.parse_args()

    if args.evaluate:
        report = evaluate()
        print(json.dumps(report, indent=2, default=str))
        return

    if args.once:
        collector = DataCollector()
        generator = SignalGenerator(get_model())
        signal = run_once(collector, generator)
        print(json.dumps(signal, indent=2))
        return

    loop()


if __name__ == "__main__":
    main()
