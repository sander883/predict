"""Main loop: fetch -> features -> signal -> log."""

from __future__ import annotations

import argparse
import json
import logging
import time

from config import CONFIG
from data_collector import DataCollector
from edge import generate_action
from logger import evaluate, log_signal
from model import get_model
from polymarket_client import PolymarketClient, fetch_yes_price
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

    if CONFIG.use_polymarket:
        yes_book = fetch_yes_price()
        report = generate_action(signal["prob_up"], yes_book)
        if report is not None:
            signal.update({
                "yes_bid": report.yes_bid,
                "yes_ask": report.yes_ask,
                "yes_mid": report.yes_mid,
                "edge_yes": report.edge_yes,
                "edge_no": report.edge_no,
                "action": report.action,
                "size": report.size,
            })
            log.info(
                "price=%.2f prob_up=%.3f yes_mid=%.3f edge_yes=%+.4f edge_no=%+.4f -> %s size=%.4f",
                signal["price"], signal["prob_up"], report.yes_mid,
                report.edge_yes, report.edge_no, report.action, report.size,
            )
        else:
            signal["action"] = "NO_MARKET"
            log.info("price=%.2f prob_up=%.3f (no Polymarket book)",
                     signal["price"], signal["prob_up"])
    else:
        log.info(
            "price=%.2f prob_up=%.3f rsi=%.1f ema_spread=%.5f ret_1m=%.5f",
            signal["price"], signal["prob_up"], signal["rsi"],
            signal["ema_spread"], signal["ret_1m"],
        )

    log_signal(signal)
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
    parser.add_argument("--find-market", action="store_true",
                        help="List active markets matching CONFIG.poly_search_query and exit")
    args = parser.parse_args()

    if args.find_market:
        client = PolymarketClient(timeout=CONFIG.poly_timeout_s)
        markets = client.list_btc_5m_markets(query=CONFIG.poly_search_query)
        out = []
        for m in markets[:20]:
            out.append({
                "slug": m.get("slug"),
                "question": m.get("question") or m.get("title"),
                "endDate": m.get("endDate") or m.get("end_date_iso"),
                "yes_token_id": PolymarketClient._yes_token_from_market(m),
            })
        print(json.dumps(out, indent=2, default=str))
        return

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
