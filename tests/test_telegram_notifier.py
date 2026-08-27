from unittest.mock import MagicMock

from app import telegram_notifier
from app.config import StrategyConfig, TelegramConfig
from app.schemas import OrderResult


def _strategy(telegram=None, **overrides):
    payload = {
        "price": 1,
        "deviation": 200,
        "magic": 100001,
        "comment": "ETH Strategy 01",
        "mt5": {"login": 1, "server": "TestServer"},
    }
    payload.update(overrides)
    return StrategyConfig.model_validate({**payload, "telegram": telegram})


def _result(**overrides):
    payload = dict(
        success=True,
        dry_run=False,
        strategy="eth_strategy_01",
        symbol="ETHUSD",
        action="openLong",
        volume=1.0,
        price=4000.0,
        order_ticket=555,
        message="Request executed",
    )
    payload.update(overrides)
    return OrderResult(**payload)


def test_format_number_uses_dot_thousands_separator():
    assert telegram_notifier._format_number(12996.0) == "12.996"
    assert telegram_notifier._format_number(4125.1) == "4.125,10"
    assert telegram_notifier._format_number(998) == "998"


def test_display_symbol_strips_perpetual_suffix():
    assert telegram_notifier._display_symbol("ETHUSDT.P") == "ETHUSDT"
    assert telegram_notifier._display_symbol("ETHUSD") == "ETHUSD"


def test_format_message_header_matches_expected_style():
    result = _result(symbol="ETHUSDT.P", action="closeLong", price=12996.0, success=True)
    message = telegram_notifier._format_message(result)
    assert message.startswith("✅ ETHUSDT-closeLong: 12.996")


def test_no_notification_when_telegram_not_configured(monkeypatch):
    post_mock = MagicMock()
    monkeypatch.setattr(telegram_notifier.httpx, "post", post_mock)

    strategy = _strategy(telegram=None)
    telegram_notifier.notify_order_result(strategy, _result())

    post_mock.assert_not_called()


def test_no_notification_when_disabled(monkeypatch):
    post_mock = MagicMock()
    monkeypatch.setattr(telegram_notifier.httpx, "post", post_mock)

    strategy = _strategy(telegram={"enabled": False, "chatId": "123"})
    telegram_notifier.notify_order_result(strategy, _result())

    post_mock.assert_not_called()


def test_no_notification_when_token_missing(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN_ETH_STRATEGY_01", raising=False)
    post_mock = MagicMock()
    monkeypatch.setattr(telegram_notifier.httpx, "post", post_mock)

    strategy = _strategy(telegram={"enabled": True, "chatId": "123"})
    telegram_notifier.notify_order_result(strategy, _result())

    post_mock.assert_not_called()


def test_sends_message_using_config_bot_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    post_mock = MagicMock(return_value=MagicMock(raise_for_status=MagicMock()))
    monkeypatch.setattr(telegram_notifier.httpx, "post", post_mock)

    strategy = _strategy(
        telegram={"enabled": True, "chatId": "-100123", "botToken": "config-token"}
    )
    result = _result()
    telegram_notifier.notify_order_result(strategy, result)

    post_mock.assert_called_once()
    url = post_mock.call_args[0][0]
    kwargs = post_mock.call_args[1]
    assert url == "https://api.telegram.org/botconfig-token/sendMessage"
    assert kwargs["json"]["chat_id"] == "-100123"
    assert "eth_strategy_01" in kwargs["json"]["text"]
    assert "ETHUSD" in kwargs["json"]["text"]


def test_config_bot_token_overrides_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    post_mock = MagicMock(return_value=MagicMock(raise_for_status=MagicMock()))
    monkeypatch.setattr(telegram_notifier.httpx, "post", post_mock)

    strategy = _strategy(
        telegram={"enabled": True, "chatId": "-100123", "botToken": "config-token"}
    )
    telegram_notifier.notify_order_result(strategy, _result())

    url = post_mock.call_args[0][0]
    assert url == "https://api.telegram.org/botconfig-token/sendMessage"


def test_falls_back_to_env_token_when_config_has_none(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    post_mock = MagicMock(return_value=MagicMock(raise_for_status=MagicMock()))
    monkeypatch.setattr(telegram_notifier.httpx, "post", post_mock)

    strategy = _strategy(telegram={"enabled": True, "chatId": "-100123"})
    telegram_notifier.notify_order_result(strategy, _result())

    url = post_mock.call_args[0][0]
    assert url == "https://api.telegram.org/botenv-token/sendMessage"


def test_per_strategy_env_token_overrides_global_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "global-token")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_ETH_STRATEGY_01", "specific-token")
    post_mock = MagicMock(return_value=MagicMock(raise_for_status=MagicMock()))
    monkeypatch.setattr(telegram_notifier.httpx, "post", post_mock)

    strategy = _strategy(telegram={"enabled": True, "chatId": "-100123"})
    telegram_notifier.notify_order_result(strategy, _result())

    url = post_mock.call_args[0][0]
    assert url == "https://api.telegram.org/botspecific-token/sendMessage"


def test_notification_failure_does_not_raise(monkeypatch):
    import httpx as real_httpx

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    def boom(*args, **kwargs):
        raise real_httpx.ConnectError("boom")

    monkeypatch.setattr(telegram_notifier.httpx, "post", boom)

    strategy = _strategy(telegram={"enabled": True, "chatId": "-100123"})
    # Should not raise.
    telegram_notifier.notify_order_result(strategy, _result())
