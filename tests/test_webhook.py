import json

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import OrderResult

client = TestClient(app)


def _tv_body(**overrides):
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
    return json.dumps(payload)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_accepts_raw_text_plain(tmp_config, monkeypatch):
    def fake_execute_order(alert, strategy):
        return OrderResult(
            success=True,
            dry_run=True,
            strategy=alert.strategy,
            symbol=alert.symbol,
            action=alert.order_id.value,
            volume=1.0,
            price=alert.price,
            message="Dry run: no order sent to MT5",
        )

    monkeypatch.setattr("app.main.execute_order", fake_execute_order)

    resp = client.post(
        "/api/order",
        content=_tv_body(),
        headers={"Content-Type": "text/plain"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["dry_run"] is True
    assert body["symbol"] == "ETHUSDT.P"


def test_webhook_rejects_malformed_json(tmp_config):
    resp = client.post(
        "/api/order",
        content="not-json-at-all{{",
        headers={"Content-Type": "text/plain"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_json"


def test_webhook_rejects_invalid_payload_schema(tmp_config):
    resp = client.post(
        "/api/order",
        content=_tv_body(order_id="notAValidAction"),
        headers={"Content-Type": "text/plain"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


def test_webhook_rejects_unknown_strategy(tmp_config):
    resp = client.post(
        "/api/order",
        content=_tv_body(strategy="does_not_exist"),
        headers={"Content-Type": "text/plain"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "unknown_strategy"


def test_webhook_ignores_duplicate_alert(tmp_config, monkeypatch):
    call_count = {"n": 0}

    def fake_execute_order(alert, strategy):
        call_count["n"] += 1
        return OrderResult(
            success=True,
            dry_run=True,
            strategy=alert.strategy,
            symbol=alert.symbol,
            action=alert.order_id.value,
            volume=1.0,
            price=alert.price,
            message="Dry run: no order sent to MT5",
        )

    monkeypatch.setattr("app.main.execute_order", fake_execute_order)

    body = _tv_body()
    first = client.post(
        "/api/order", content=body, headers={"Content-Type": "text/plain"}
    )
    second = client.post(
        "/api/order", content=body, headers={"Content-Type": "text/plain"}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "Duplicate" in second.json()["message"]
    assert call_count["n"] == 1
