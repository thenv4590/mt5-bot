"""Duplicate-webhook guard.

TradingView retries a webhook delivery if it doesn't get a prompt 2xx
response (slow network, brief downtime, etc.), which can otherwise cause
the exact same signal to open/close a position twice. This tracks
recently-seen alerts by their identifying fields and flags repeats within
a short window so the caller can skip re-executing the order.
"""
import threading
import time
from typing import Dict

from app.schemas import TradingViewAlert

_DEDUPE_WINDOW_SECONDS = 30

_lock = threading.Lock()
_seen: Dict[str, float] = {}


def _alert_key(alert: TradingViewAlert) -> str:
    return "|".join(
        [
            alert.strategy,
            alert.order_id.value,
            alert.symbol,
            str(alert.order_ratio),
            alert.comment or "",
            alert.timenow or "",
        ]
    )


def _prune(now: float) -> None:
    expired = [k for k, ts in _seen.items() if now - ts > _DEDUPE_WINDOW_SECONDS]
    for k in expired:
        del _seen[k]


def is_duplicate(alert: TradingViewAlert) -> bool:
    """Returns True (and remembers it) if an identical alert was already
    seen within the dedupe window; False (and remembers it) otherwise."""
    key = _alert_key(alert)
    now = time.monotonic()
    with _lock:
        _prune(now)
        if key in _seen:
            return True
        _seen[key] = now
        return False
