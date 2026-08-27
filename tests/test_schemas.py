import pytest
from pydantic import ValidationError

from app.schemas import OrderId, TradingViewAlert


def _base_payload(**overrides):
    payload = {
        "symbol": "ETHUSDT.P",
        "price": "4123.45",
        "alert_name": "ETH Long",
        "timenow": "2026-08-27T00:00:00Z",
        "order_id": "openLong",
        "order_action": "buy",
        "comment": "eth_strategy_01",
        "alert_message": None,
        "order_ratio": 1,
        "strategy": "eth_strategy_01",
    }
    payload.update(overrides)
    return payload


def test_parses_string_price_and_ratio():
    alert = TradingViewAlert.model_validate(_base_payload())
    assert alert.price == pytest.approx(4123.45)
    assert alert.order_ratio == pytest.approx(1.0)
    assert alert.order_id == OrderId.OPEN_LONG


def test_accepts_numeric_price_and_ratio():
    alert = TradingViewAlert.model_validate(
        _base_payload(price=100.5, order_ratio=2)
    )
    assert alert.price == 100.5
    assert alert.order_ratio == 2


@pytest.mark.parametrize(
    "order_id,expected",
    [
        ("openLong", OrderId.OPEN_LONG),
        ("closeLong", OrderId.CLOSE_LONG),
        ("openShort", OrderId.OPEN_SHORT),
        ("closeShort", OrderId.CLOSE_SHORT),
    ],
)
def test_all_order_ids_accepted(order_id, expected):
    alert = TradingViewAlert.model_validate(_base_payload(order_id=order_id))
    assert alert.order_id == expected


def test_rejects_invalid_order_id():
    with pytest.raises(ValidationError):
        TradingViewAlert.model_validate(_base_payload(order_id="doNothing"))


def test_rejects_non_numeric_price():
    with pytest.raises(ValidationError):
        TradingViewAlert.model_validate(_base_payload(price="not-a-number"))


def test_rejects_zero_or_negative_price():
    with pytest.raises(ValidationError):
        TradingViewAlert.model_validate(_base_payload(price="0"))
    with pytest.raises(ValidationError):
        TradingViewAlert.model_validate(_base_payload(price="-5"))


def test_rejects_zero_order_ratio():
    with pytest.raises(ValidationError):
        TradingViewAlert.model_validate(_base_payload(order_ratio=0))


def test_rejects_blank_strategy():
    with pytest.raises(ValidationError):
        TradingViewAlert.model_validate(_base_payload(strategy="  "))


def test_rejects_missing_required_field():
    payload = _base_payload()
    del payload["strategy"]
    with pytest.raises(ValidationError):
        TradingViewAlert.model_validate(payload)
