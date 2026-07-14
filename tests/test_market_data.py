import copy
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from webull_lab.market_data import (
    get_daily_stock_bars,
    get_stock_bars,
    get_stock_snapshot,
    normalize_stock_bars,
)

BAR_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
FIXTURE_PATH = Path("tests/fixtures/webull/aapl_daily_bars_sample.json")


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


def test_get_stock_snapshot_normalizes_symbol_whitespace_and_case():
    client = FakeDataClient()

    payload = get_stock_snapshot(client, " aapl ")

    assert payload == {"symbol": "AAPL", "last_price": "200.00"}
    assert client.market_data.calls == [("snapshot", "AAPL", "US_STOCK", True, True)]


def test_get_stock_bars_normalizes_symbol_whitespace_and_case():
    client = FakeDataClient()

    payload = get_stock_bars(client, " aapl ", "M5")

    assert payload == [{"symbol": "AAPL", "close": "200.00"}]
    assert client.market_data.calls == [("bars", "AAPL", "US_STOCK", "M5")]


def test_get_daily_stock_bars_requests_daily_timespan():
    client = FakeDataClient()

    payload = get_daily_stock_bars(client, " aapl ")

    assert payload == [{"symbol": "AAPL", "close": "200.00"}]
    assert client.market_data.calls == [("bars", "AAPL", "US_STOCK", "D")]


def test_normalize_stock_bars_parses_fixture_without_losing_precision():
    payload = json.loads(FIXTURE_PATH.read_text())

    frame = normalize_stock_bars(payload)

    assert list(frame.columns) == BAR_COLUMNS
    assert frame.to_dict("records") == [
        {
            "symbol": "AAPL",
            "date": date(2024, 11, 1),
            "open": Decimal("220.97"),
            "high": Decimal("225.35"),
            "low": Decimal("220.27"),
            "close": Decimal("222.91"),
            "volume": 65276700,
        },
        {
            "symbol": "AAPL",
            "date": date(2024, 11, 4),
            "open": Decimal("220.99"),
            "high": Decimal("222.79"),
            "low": Decimal("219.71"),
            "close": Decimal("222.01"),
            "volume": 44944500,
        },
    ]
    assert all(
        isinstance(value, Decimal)
        for column in ("open", "high", "low", "close")
        for value in frame[column]
    )
    assert all(isinstance(value, int) for value in frame["volume"])


def test_normalize_stock_bars_accepts_supported_numeric_representations():
    payload = [
        {
            "symbol": " aapl ",
            "time": "1730419200000",
            "open": 220,
            "high": 225.35,
            "low": "220.2700",
            "close": 222.0,
            "volume": 0,
        }
    ]

    frame = normalize_stock_bars(payload)

    assert frame.loc[0].to_dict() == {
        "symbol": "AAPL",
        "date": date(2024, 11, 1),
        "open": Decimal("220"),
        "high": Decimal("225.35"),
        "low": Decimal("220.2700"),
        "close": Decimal("222.0"),
        "volume": 0,
    }


@pytest.mark.parametrize("payload", [None, {}, (), "not-a-list"])
def test_normalize_stock_bars_rejects_non_list_payload(payload):
    with pytest.raises(ValueError, match="payload must be a list"):
        normalize_stock_bars(payload)


@pytest.mark.parametrize("row", [None, [], "not-a-row", 1])
def test_normalize_stock_bars_rejects_non_mapping_rows(row):
    with pytest.raises(ValueError, match="row 0 must be a mapping"):
        normalize_stock_bars([row])


@pytest.mark.parametrize("symbol", [None, "", "   ", 123])
def test_normalize_stock_bars_rejects_invalid_symbols(symbol):
    row = _valid_bar(symbol=symbol)

    with pytest.raises(ValueError, match="row 0 field 'symbol'"):
        normalize_stock_bars([row])


@pytest.mark.parametrize(
    "timestamp",
    [True, False, -1, "-1", 1730419200000.0, "1730419200000.5", "", None],
)
def test_normalize_stock_bars_rejects_invalid_timestamps(timestamp):
    row = _valid_bar(time=timestamp)

    with pytest.raises(ValueError, match="row 0 field 'time'"):
        normalize_stock_bars([row])


def test_normalize_stock_bars_rejects_out_of_range_timestamp_safely():
    row = _valid_bar(time="9" * 100)

    with pytest.raises(ValueError) as exc_info:
        normalize_stock_bars([row])

    assert str(exc_info.value) == "Webull bar row 0 field 'time' is invalid"
    assert "999999" not in str(exc_info.value)


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
@pytest.mark.parametrize("value", [True, -1, "-0.01", float("nan"), float("inf"), "bad"])
def test_normalize_stock_bars_rejects_invalid_prices(field, value):
    row = _valid_bar(**{field: value})

    with pytest.raises(ValueError, match=rf"row 0 field '{field}'"):
        normalize_stock_bars([row])


@pytest.mark.parametrize("volume", [True, -1, "-1", 1.0, "1.5", "", None])
def test_normalize_stock_bars_rejects_invalid_volume(volume):
    row = _valid_bar(volume=volume)

    with pytest.raises(ValueError, match="row 0 field 'volume'"):
        normalize_stock_bars([row])


def test_normalize_stock_bars_rejects_missing_fields_without_echoing_row_data():
    row = _valid_bar()
    row.pop("close")
    row["private_note"] = "do-not-leak-this"

    with pytest.raises(ValueError) as exc_info:
        normalize_stock_bars([row])

    assert str(exc_info.value) == "Webull bar row 0 is missing field 'close'"
    assert "do-not-leak-this" not in str(exc_info.value)


def test_normalize_stock_bars_rejects_duplicate_symbol_dates():
    first = _valid_bar(symbol="aapl", time=1730419200000)
    duplicate = _valid_bar(symbol=" AAPL ", time=1730422800000)

    with pytest.raises(ValueError, match="duplicate symbol and date"):
        normalize_stock_bars([first, duplicate])


def test_normalize_stock_bars_sorts_by_symbol_then_date():
    payload = [
        _valid_bar(symbol="msft", time="1730678400000"),
        _valid_bar(symbol="aapl", time="1730678400000"),
        _valid_bar(symbol="AAPL", time="1730419200000"),
    ]

    frame = normalize_stock_bars(payload)

    assert list(zip(frame["symbol"], frame["date"], strict=True)) == [
        ("AAPL", date(2024, 11, 1)),
        ("AAPL", date(2024, 11, 4)),
        ("MSFT", date(2024, 11, 4)),
    ]


def test_normalize_stock_bars_does_not_mutate_input():
    payload = [_valid_bar(symbol=" aapl ", time="1730419200000")]
    original = copy.deepcopy(payload)

    normalize_stock_bars(payload)

    assert payload == original


def test_normalize_stock_bars_empty_list_has_stable_schema():
    frame = normalize_stock_bars([])

    assert frame.empty
    assert list(frame.columns) == BAR_COLUMNS


def _valid_bar(**overrides):
    row = {
        "symbol": "AAPL",
        "time": 1730419200000,
        "open": "220.97",
        "high": "225.35",
        "low": "220.27",
        "close": "222.91",
        "volume": "65276700",
    }
    row.update(overrides)
    return row
