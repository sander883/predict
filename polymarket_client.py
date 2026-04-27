"""Polymarket YES price fetcher.

Reads the best YES (and NO) prices for a market from the public CLOB API.
Reference: https://github.com/polymarket/agents
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import urllib.parse
import urllib.request
import json

from config import CONFIG

log = logging.getLogger(__name__)


class PolymarketClient:
    """Read-only client over Polymarket's public CLOB endpoints.

    Two ways to identify the YES outcome:
      - `token_id`: CLOB token_id of the YES outcome (preferred, exact)
      - `market_slug`: Gamma slug, e.g. "btc-up-or-down-2026-04-27-12pm-et"
    """

    GAMMA_BASE = "https://gamma-api.polymarket.com"
    CLOB_BASE = "https://clob.polymarket.com"

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    # ---------- HTTP helpers ----------
    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "btc-signal/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    # ---------- Resolution ----------
    def resolve_yes_token_id(self, market_slug: str) -> Optional[str]:
        """Return the YES outcome's CLOB token_id for a Gamma market slug."""
        data = self._get(f"{self.GAMMA_BASE}/markets", {"slug": market_slug})
        markets = data if isinstance(data, list) else data.get("data", [])
        if not markets:
            log.warning("No market found for slug=%s", market_slug)
            return None
        m = markets[0]
        outcomes = m.get("outcomes")
        token_ids = m.get("clobTokenIds")
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        if isinstance(token_ids, str):
            token_ids = json.loads(token_ids)
        if not outcomes or not token_ids:
            return None
        for name, tid in zip(outcomes, token_ids):
            if str(name).strip().lower() == "yes":
                return str(tid)
        return str(token_ids[0])

    # ---------- Pricing ----------
    def get_yes_price(self, token_id: str) -> Optional[Dict[str, float]]:
        """Return {'yes_bid','yes_ask','yes_mid','spread'} or None on failure.

        Uses CLOB best-of-book.
        """
        try:
            bid = self._get(f"{self.CLOB_BASE}/price", {"token_id": token_id, "side": "buy"})
            ask = self._get(f"{self.CLOB_BASE}/price", {"token_id": token_id, "side": "sell"})
            yes_bid = float(bid.get("price", 0.0))
            yes_ask = float(ask.get("price", 0.0))
            if yes_bid <= 0 or yes_ask <= 0:
                return None
            yes_mid = (yes_bid + yes_ask) / 2.0
            return {
                "yes_bid": yes_bid,
                "yes_ask": yes_ask,
                "yes_mid": yes_mid,
                "spread": yes_ask - yes_bid,
            }
        except Exception as e:
            log.warning("Polymarket price fetch failed: %s", e)
            return None


def fetch_yes_price() -> Optional[Dict[str, float]]:
    """Convenience: resolve via config and return YES price book."""
    client = PolymarketClient(timeout=CONFIG.poly_timeout_s)
    token_id = CONFIG.poly_token_id
    if not token_id and CONFIG.poly_market_slug:
        token_id = client.resolve_yes_token_id(CONFIG.poly_market_slug)
    if not token_id:
        log.warning("No Polymarket token_id resolved (slug=%s)", CONFIG.poly_market_slug)
        return None
    return client.get_yes_price(token_id)
