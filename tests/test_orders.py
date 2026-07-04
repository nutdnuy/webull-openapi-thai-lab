import pytest

from webull_lab.config import Settings
from webull_lab.orders import (
    LiveOrderBlocked,
    build_stock_limit_buy,
    place_stock_limit_buy,
    preview_stock_limit_buy,
)


class FakeResponse:
    def __init__(self, payload, status_code=200, text="ok"):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


class FakeOrderV2:
    def __init__(self, preview_response=None, place_response=None):
        self.preview_calls = []
        self.place_calls = []
        self.preview_response = preview_response
        self.place_response = place_response

    def preview_order(self, account_id, orders):
        self.preview_calls.append((account_id, orders))
        if self.preview_response is not None:
            return self.preview_response
        return FakeResponse({"preview": "ok", "orders": orders})

    def place_order(self, account_id, orders):
        self.place_calls.append((account_id, orders))
        if self.place_response is not None:
            return self.place_response
        return FakeResponse({"place": "ok", "orders": orders})


class FakeTradeClient:
    def __init__(self, order_v2=None):
        self.order_v2 = order_v2 or FakeOrderV2()


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
    order = build_stock_limit_buy(symbol=" aapl ", limit_price="100", quantity="1")

    assert order["symbol"] == "AAPL"
    assert order["instrument_type"] == "EQUITY"
    assert order["market"] == "US"
    assert order["order_type"] == "LIMIT"
    assert order["side"] == "BUY"
    assert order["time_in_force"] == "DAY"
    assert order["support_trading_session"] == "CORE"
    assert order["entrust_type"] == "QTY"
    assert len(order["client_order_id"]) == 32


@pytest.mark.parametrize(
    ("symbol", "limit_price", "quantity", "message"),
    [
        (" ", "100", "1", "symbol"),
        ("AAPL", " ", "1", "limit_price"),
        ("AAPL", "100", " ", "quantity"),
        ("AAPL", "abc", "1", "limit_price"),
        ("AAPL", "0", "1", "limit_price"),
        ("AAPL", "100", "-1", "quantity"),
    ],
)
def test_build_stock_limit_buy_rejects_invalid_inputs(symbol, limit_price, quantity, message):
    with pytest.raises(ValueError, match=message):
        build_stock_limit_buy(symbol=symbol, limit_price=limit_price, quantity=quantity)


def test_preview_stock_limit_buy_calls_preview_only():
    client = FakeTradeClient()

    payload = preview_stock_limit_buy(client, "acct_1", "AAPL", "100", "1")

    assert payload["preview"] == "ok"
    assert len(client.order_v2.preview_calls) == 1
    assert client.order_v2.place_calls == []


@pytest.mark.parametrize(
    ("symbol", "limit_price", "quantity", "message"),
    [
        (" ", "100", "1", "symbol"),
        ("AAPL", " ", "1", "limit_price"),
        ("AAPL", "100", " ", "quantity"),
        ("AAPL", "abc", "1", "limit_price"),
        ("AAPL", "0", "1", "limit_price"),
        ("AAPL", "100", "-1", "quantity"),
    ],
)
def test_preview_stock_limit_buy_rejects_invalid_inputs_without_sdk_call(
    symbol, limit_price, quantity, message
):
    client = FakeTradeClient()

    with pytest.raises(ValueError, match=message):
        preview_stock_limit_buy(client, "acct_1", symbol, limit_price, quantity)

    assert client.order_v2.preview_calls == []
    assert client.order_v2.place_calls == []


def test_preview_stock_limit_buy_raises_on_non_200_response():
    client = FakeTradeClient(
        FakeOrderV2(preview_response=FakeResponse({}, status_code=400, text="bad order"))
    )

    with pytest.raises(RuntimeError, match="HTTP 400: bad order"):
        preview_stock_limit_buy(client, "acct_1", "AAPL", "100", "1")

    assert len(client.order_v2.preview_calls) == 1
    assert client.order_v2.place_calls == []


def test_place_stock_limit_buy_is_blocked_by_default():
    client = FakeTradeClient()
    settings = make_settings()

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

    assert client.order_v2.place_calls == []
