"""Polymarket YES price fetcher.

Reads the best YES (and NO) prices for a market from the public CLOB API.
Includes auto-discovery for the active "BTC Up or Down 5m" market.
Reference: https://github.com/polymarket/agents
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import urllib.parse
import urllib.request
import json

from config import CONFIG

log = logging.getLogger(__name__)


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


class PolymarketClient:
    """Read-only client over Polymarket's public CLOB endpoints.

    Three ways to identify a market:
      - `token_id`: CLOB token_id of the YES outcome (preferred, exact)
      - `market_slug`: Gamma slug, e.g. "btc-up-or-down-2026-04-27-12pm-et"
      - auto-discovery via `find_active_btc_market(query="BTC Up or Down 5m")`
    """

    GAMMA_BASE = "https://gamma-api.polymarket.com"
    CLOB_BASE = "https://clob.polymarket.com"

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    # ---------- HTTP helpers ----------
    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
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
        return self._yes_token_from_market(markets[0])

    @staticmethod
    def _yes_token_from_market(m: Dict) -> Optional[str]:
        outcomes = m.get("outcomes")
        token_ids = m.get("clobTokenIds")
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        if isinstance(token_ids, str):
            token_ids = json.loads(token_ids)
        if not outcomes or not token_ids:
            return None
        for name, tid in zip(outcomes, token_ids):
            if str(name).strip().lower() in ("yes", "up"):
                return str(tid)
        return str(token_ids[0])

    # ---------- Auto-discovery ----------
    def list_btc_5m_markets(self, query: str = "BTC Up or Down 5m", limit: int = 50) -> List[Dict]:
        """List active markets matching `query`, sorted by soonest end time."""
        data = self._get(f"{self.GAMMA_BASE}/markets", {
            "active": "true",
            "closed": "false",
            "limit": str(limit),
            "order": "endDate",
            "ascending": "true",
        })
        markets = data if isinstance(data, list) else data.get("data", [])
        q = query.lower()
        return [
            m for m in markets
            if q in str(m.get("question", "")).lower()
            or q in str(m.get("title", "")).lower()
            or q in str(m.get("slug", "")).lower()
        ]

    def find_active_btc_market(
        self,
        query: str = "BTC Up or Down 5m",
    ) -> Optional[Tuple[str, Dict]]:
        """Return (yes_token_id, market_dict) for the soonest-ending active match."""
        candidates = self.list_btc_5m_markets(query=query)
        now = datetime.now(timezone.utc)

        scored = []
        for m in candidates:
            end = _parse_dt(m.get("endDate") or m.get("end_date_iso"))
            if end and end <= now:
                continue
            scored.append((end or datetime.max.replace(tzinfo=timezone.utc), m))
        if not scored:
            return None
        scored.sort(key=lambda x: x[0])
        chosen = scored[0][1]
        tid = self._yes_token_from_market(chosen)
        if not tid:
            return None
        return tid, chosen

    # ---------- Pricing ----------
    def get_yes_price(self, token_id: str) -> Optional[Dict[str, float]]:
        """Return {'yes_bid','yes_ask','yes_mid','spread'} or None on failure."""
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


# ---------- Cached auto-discovery for the live loop ----------
_DISCOVERY_CACHE: Dict[str, object] = {"token_id": None, "slug": None, "expires": 0.0}


def _resolve_token_id(client: PolymarketClient) -> Optional[str]:
    if CONFIG.poly_token_id:
        return CONFIG.poly_token_id
    if CONFIG.poly_market_slug:
        return client.resolve_yes_token_id(CONFIG.poly_market_slug)
    if not CONFIG.poly_auto_discover:
        return None

    now = time.time()
    if _DISCOVERY_CACHE["token_id"] and now < float(_DISCOVERY_CACHE["expires"]):
        return _DISCOVERY_CACHE["token_id"]  # type: ignore[return-value]

    found = client.find_active_btc_market(query=CONFIG.poly_search_query)
    if not found:
        log.warning("Auto-discovery: no active market for %r", CONFIG.poly_search_query)
        return None
    tid, market = found
    _DISCOVERY_CACHE.update({
        "token_id": tid,
        "slug": market.get("slug"),
        "expires": now + CONFIG.poly_discovery_ttl_s,
    })
    log.info("Auto-discovered market: slug=%s end=%s",
             market.get("slug"), market.get("endDate"))
    return tid


def fetch_yes_price() -> Optional[Dict[str, float]]:
    """Convenience: resolve via config (or auto-discover) and return YES price book."""
    client = PolymarketClient(timeout=CONFIG.poly_timeout_s)
    token_id = _resolve_token_id(client)
    if not token_id:
        return None
    return client.get_yes_price(token_id)

