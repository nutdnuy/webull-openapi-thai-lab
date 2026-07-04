from webull_lab.market_data import get_stock_bars, get_stock_snapshot


class FakeResponse:
    status_code = 200
    text = "ok"

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeMarketData:
    def __init__(self):
        self.calls = []

    def get_snapshot(self, symbol, category, extend_hour_required, overnight_required):
        self.calls.append(
            ("snapshot", symbol, category, extend_hour_required, overnight_required)
        )
        return FakeResponse({"symbol": symbol, "last_price": "200.00"})

    def get_history_bar(self, symbol, category, timespan):
        self.calls.append(("bars", symbol, category, timespan))
        return FakeResponse([{"symbol": symbol, "close": "200.00"}])


class FakeDataClient:
    def __init__(self):
        self.market_data = FakeMarketData()


def test_get_stock_snapshot_uses_us_stock_category():
    client = FakeDataClient()

    payload = get_stock_snapshot(client, "AAPL")

    assert payload == {"symbol": "AAPL", "last_price": "200.00"}
    assert client.market_data.calls == [("snapshot", "AAPL", "US_STOCK", True, True)]


def test_get_stock_bars_uses_requested_timespan():
    client = FakeDataClient()

    payload = get_stock_bars(client, "AAPL", "M1")

    assert payload == [{"symbol": "AAPL", "close": "200.00"}]
    assert client.market_data.calls == [("bars", "AAPL", "US_STOCK", "M1")]
