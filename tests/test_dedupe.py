import time

from app import dedupe
from app.schemas import TradingViewAlert


def _alert(**overrides):
    payload = {
        "symbol": "ETHUSD",
        "price": "4000",
        "order_id": "openLong",
        "order_ratio": 1,
        "strategy": "eth_strategy_01",
        "comment": "openLong",
        "timenow": "2026-08-27T00:00:00Z",
    }
    payload.update(overrides)
    return TradingViewAlert.model_validate(payload)


def setup_function(_):
    dedupe._seen.clear()


def test_first_sighting_is_not_duplicate():
    assert dedupe.is_duplicate(_alert()) is False


def test_repeat_within_window_is_duplicate():
    alert = _alert()
    assert dedupe.is_duplicate(alert) is False
    assert dedupe.is_duplicate(alert) is True


def test_different_timenow_is_not_duplicate():
    assert dedupe.is_duplicate(_alert(timenow="2026-08-27T00:00:00Z")) is False
    assert dedupe.is_duplicate(_alert(timenow="2026-08-27T00:05:00Z")) is False


def test_different_order_id_is_not_duplicate():
    assert dedupe.is_duplicate(_alert(order_id="openLong")) is False
    assert dedupe.is_duplicate(_alert(order_id="closeLong")) is False


def test_expired_entry_is_not_duplicate(monkeypatch):
    alert = _alert()
    assert dedupe.is_duplicate(alert) is False

    real_time = time.monotonic() + dedupe._DEDUPE_WINDOW_SECONDS + 1
    monkeypatch.setattr(dedupe.time, "monotonic", lambda: real_time)

    assert dedupe.is_duplicate(alert) is False
