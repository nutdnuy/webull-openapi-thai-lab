import pytest

from webull_lab.config import Settings
from webull_lab.orders import (
    LiveOrderBlocked,
    build_stock_limit_buy,
    place_stock_limit_buy,
    preview_stock_limit_buy,
)


class FakeResponse:
    status_code = 200
    text = "ok"

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeOrderV2:
    def __init__(self):
        self.preview_calls = []
        self.place_calls = []

    def preview_order(self, account_id, orders):
        self.preview_calls.append((account_id, orders))
        return FakeResponse({"preview": "ok", "orders": orders})

    def place_order(self, account_id, orders):
        self.place_calls.append((account_id, orders))
        return FakeResponse({"place": "ok", "orders": orders})


class FakeTradeClient:
    def __init__(self):
        self.order_v2 = FakeOrderV2()


def make_settings() -> Settings:
    return Settings(
        env="uat",
        region="us",
        app_key="key_123",
        app_secret="secret_456",
        account_id="acct_1",
        token_dir=None,
    )


def test_build_stock_limit_buy_has_safe_default_shape():
    order = build_stock_limit_buy(symbol="AAPL", limit_price="100", quantity="1")

    assert order["symbol"] == "AAPL"
    assert order["instrument_type"] == "EQUITY"
    assert order["market"] == "US"
    assert order["order_type"] == "LIMIT"
    assert order["side"] == "BUY"
    assert order["time_in_force"] == "DAY"
    assert order["support_trading_session"] == "CORE"
    assert order["entrust_type"] == "QTY"
    assert len(order["client_order_id"]) == 32


def test_preview_stock_limit_buy_calls_preview_only():
    client = FakeTradeClient()

    payload = preview_stock_limit_buy(client, "acct_1", "AAPL", "100", "1")

    assert payload["preview"] == "ok"
    assert len(client.order_v2.preview_calls) == 1
    assert client.order_v2.place_calls == []


def test_place_stock_limit_buy_is_blocked_by_default(monkeypatch):
    client = FakeTradeClient()
    settings = make_settings()
    monkeypatch.setenv("WEBULL_ALLOW_LIVE_ORDERS", "NO")

    with pytest.raises(LiveOrderBlocked, match="WEBULL_ALLOW_LIVE_ORDERS"):
        place_stock_limit_buy(client, settings, "AAPL", "100", "1")

    assert client.order_v2.place_calls == []


def test_place_stock_limit_buy_requires_account_id(monkeypatch):
    client = FakeTradeClient()
    settings = Settings(
        env="uat",
        region="us",
        app_key="key_123",
        app_secret="secret_456",
        account_id=None,
        token_dir=None,
        live_orders_enabled=True,
    )
    monkeypatch.setenv("WEBULL_ALLOW_LIVE_ORDERS", "I_UNDERSTAND")

    with pytest.raises(ValueError, match="WEBULL_ACCOUNT_ID"):
        place_stock_limit_buy(client, settings, "AAPL", "100", "1")
