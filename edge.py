"""Edge calculation and action generation for Polymarket binary markets.

Edge = model probability - market-implied probability.
Action = BUY_YES / BUY_NO / HOLD, sized by edge magnitude vs threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from config import CONFIG


@dataclass
class EdgeReport:
    prob_up: float          # model probability of YES (BTC up)
    yes_mid: float          # market YES mid
    yes_ask: float          # cost to BUY YES
    yes_bid: float          # cost to BUY NO = 1 - yes_bid
    no_ask: float           # = 1 - yes_bid
    edge_yes: float         # prob_up - yes_ask (buying YES)
    edge_no: float          # (1 - prob_up) - no_ask (buying NO)
    action: str             # BUY_YES | BUY_NO | HOLD
    size: float             # fractional Kelly-ish sizing in [0, 1]
    reason: str

    def as_dict(self) -> Dict:
        return self.__dict__.copy()


def _kelly_fraction(p: float, price: float) -> float:
    """Fractional Kelly for a binary YES/NO bet at the given price.

    Payoff per $1 stake on YES = (1 / price) - 1 if YES wins, else -1.
    f* = p - (1 - p) / b, where b = (1 - price) / price.
    Clamped to [0, 1].
    """
    if price <= 0 or price >= 1:
        return 0.0
    b = (1.0 - price) / price
    f = p - (1.0 - p) / b
    return max(0.0, min(1.0, f))


def compute_edge(prob_up: float, yes_book: Dict[str, float]) -> EdgeReport:
    yes_bid = float(yes_book["yes_bid"])
    yes_ask = float(yes_book["yes_ask"])
    yes_mid = float(yes_book.get("yes_mid", (yes_bid + yes_ask) / 2.0))
    no_ask = 1.0 - yes_bid  # buying NO crosses the YES bid

    edge_yes = prob_up - yes_ask
    edge_no = (1.0 - prob_up) - no_ask

    threshold = CONFIG.edge_threshold
    kelly_scale = CONFIG.kelly_fraction

    if edge_yes >= threshold and edge_yes >= edge_no:
        size = kelly_scale * _kelly_fraction(prob_up, yes_ask)
        action, reason = "BUY_YES", f"edge={edge_yes:.4f} >= {threshold}"
    elif edge_no >= threshold:
        size = kelly_scale * _kelly_fraction(1.0 - prob_up, no_ask)
        action, reason = "BUY_NO", f"edge={edge_no:.4f} >= {threshold}"
    else:
        size = 0.0
        action = "HOLD"
        reason = f"edge_yes={edge_yes:.4f} edge_no={edge_no:.4f} < {threshold}"

    return EdgeReport(
        prob_up=prob_up,
        yes_mid=yes_mid,
        yes_ask=yes_ask,
        yes_bid=yes_bid,
        no_ask=no_ask,
        edge_yes=edge_yes,
        edge_no=edge_no,
        action=action,
        size=round(size, 6),
        reason=reason,
    )


def generate_action(prob_up: float, yes_book: Optional[Dict[str, float]]) -> Optional[EdgeReport]:
    if yes_book is None:
        return None
    return compute_edge(prob_up, yes_book)
