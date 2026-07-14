import copy
import io
import json
import logging
import sys
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from webull_lab.market_data import (
    PriceHistoryFetch,
    fetch_daily_stock_history,
    get_daily_stock_bars,
    get_stock_bars,
    get_stock_snapshot,
    normalize_stock_bars,
    price_history_metadata,
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


class LoggingMarketData(FakeMarketData):
    marker = "MARKER_REQUEST_SECRET_MUST_NOT_LEAK"

    def _emit_secret_logs(self):
        print(f"stdout {self.marker}")
        print(f"stderr {self.marker}", file=sys.stderr)
        logging.getLogger("webull").critical(self.marker)
        logging.getLogger("webull.core.http.response").critical(self.marker)

    def get_snapshot(self, *args, **kwargs):
        self._emit_secret_logs()
        return super().get_snapshot(*args, **kwargs)

    def get_history_bar(self, *args, **kwargs):
        self._emit_secret_logs()
        return super().get_history_bar(*args, **kwargs)


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


def _bar(symbol, day):
    timestamp = int(datetime.combine(day, time(), tzinfo=UTC).timestamp() * 1000)
    return {
        "symbol": symbol,
        "time": str(timestamp),
        "open": "1",
        "high": "1",
        "low": "1",
        "close": "1",
        "volume": "1",
    }


class PaginatedMarketData:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get_history_bar(self, symbol, category, timespan, **kwargs):
        self.calls.append((symbol, category, timespan, kwargs))
        return FakeResponse(self.pages.pop(0))


def test_fetch_daily_stock_history_paginates_to_requested_year_boundary(monkeypatch):
    monkeypatch.setattr("webull_lab.market_data.MAX_BAR_COUNT", 2)
    monkeypatch.setattr("webull_lab.market_data.sleep", lambda _seconds: None)
    pages = [
        [_bar("AAPL", date(2025, 1, 10)), _bar("AAPL", date(2024, 6, 1))],
        [_bar("AAPL", date(2024, 1, 10)), _bar("AAPL", date(2024, 1, 9))],
    ]
    client = FakeDataClient()
    client.market_data = PaginatedMarketData(pages)

    result = fetch_daily_stock_history(
        client, " aapl ", years=1, as_of=date(2025, 1, 10)
    )

    assert isinstance(result, PriceHistoryFetch)
    assert result.requested_start_date == date(2024, 1, 10)
    assert result.requested_end_date == date(2025, 1, 10)
    assert result.pages_requested == 2
    assert result.pagination_complete is True
    assert [row["time"] for row in result.payload] == [
        _bar("AAPL", date(2025, 1, 10))["time"],
        _bar("AAPL", date(2024, 6, 1))["time"],
        _bar("AAPL", date(2024, 1, 10))["time"],
    ]
    first = client.market_data.calls[0]
    second = client.market_data.calls[1]
    assert first[:3] == ("AAPL", "US_STOCK", "D")
    assert first[3]["count"] == "2"
    assert first[3]["start_time"] == int(
        datetime(2024, 1, 10, tzinfo=UTC).timestamp() * 1000
    )
    assert first[3]["end_time"] == int(
        datetime(2025, 1, 11, tzinfo=UTC).timestamp() * 1000
    ) - 1
    assert second[3]["end_time"] == int(
        datetime(2024, 6, 1, tzinfo=UTC).timestamp() * 1000
    ) - 1


def test_fetch_daily_stock_history_stops_on_short_page_and_deduplicates(monkeypatch):
    monkeypatch.setattr("webull_lab.market_data.MAX_BAR_COUNT", 3)
    page = [
        _bar("MSFT", date(2025, 1, 10)),
        _bar("MSFT", date(2025, 1, 10)),
    ]
    client = FakeDataClient()
    client.market_data = PaginatedMarketData([page])

    result = fetch_daily_stock_history(
        client, "MSFT", years=5, as_of=date(2025, 1, 10)
    )

    assert len(result.payload) == 1
    assert result.pages_requested == 1
    assert result.pagination_complete is True


@pytest.mark.parametrize("years", [True, 0, -1, 1.5, "5"])
def test_fetch_daily_stock_history_rejects_invalid_years(years):
    with pytest.raises(ValueError, match="years must be a positive integer"):
        fetch_daily_stock_history(FakeDataClient(), "AAPL", years=years)


def test_price_history_metadata_reports_observed_range_boundaries():
    fetch = PriceHistoryFetch(
        payload=[],
        requested_start_date=date(2024, 1, 10),
        requested_end_date=date(2025, 1, 10),
        pages_requested=2,
        pagination_complete=True,
    )
    prices = normalize_stock_bars(
        [_bar("AAPL", date(2024, 1, 10)), _bar("AAPL", date(2025, 1, 10))]
    )

    metadata = price_history_metadata(1, prices, fetch=fetch)

    assert metadata == {
        "status": "range_observed",
        "requested_start_date": "2024-01-10",
        "requested_end_date": "2025-01-10",
        "observed_start_date": "2024-01-10",
        "observed_end_date": "2025-01-10",
        "observed_bar_count": 2,
        "pages_requested": 2,
        "pagination_complete": True,
    }


def test_price_history_metadata_does_not_call_short_history_complete():
    fetch = PriceHistoryFetch(
        payload=[],
        requested_start_date=date(2020, 1, 10),
        requested_end_date=date(2025, 1, 10),
        pages_requested=1,
        pagination_complete=True,
    )
    prices = normalize_stock_bars([_bar("NEW", date(2024, 6, 1))])

    metadata = price_history_metadata(5, prices, fetch=fetch)

    assert metadata["status"] == "partial"
    assert metadata["observed_start_date"] == "2024-06-01"
    assert metadata["observed_bar_count"] == 1


def test_price_history_metadata_reports_unavailable_without_prices():
    metadata = price_history_metadata(
        5,
        normalize_stock_bars([]),
        as_of=date(2025, 1, 10),
    )

    assert metadata["status"] == "unavailable"
    assert metadata["requested_start_date"] == "2020-01-10"
    assert metadata["requested_end_date"] == "2025-01-10"
    assert metadata["observed_start_date"] is None
    assert metadata["observed_end_date"] is None
    assert metadata["observed_bar_count"] == 0
    assert metadata["pages_requested"] == 0
    assert metadata["pagination_complete"] is False


def test_market_data_sdk_calls_suppress_output_and_restore_logging_state(
    monkeypatch, capsys
):
    marker = LoggingMarketData.marker
    client = FakeDataClient()
    client.market_data = LoggingMarketData()
    webull_logger = logging.getLogger("webull")
    response_logger = logging.getLogger("webull.core.http.response")
    webull_handler = logging.StreamHandler(io.StringIO())
    response_handler = logging.StreamHandler(io.StringIO())
    monkeypatch.setattr(webull_logger, "handlers", [webull_handler])
    monkeypatch.setattr(webull_logger, "level", logging.INFO)
    monkeypatch.setattr(webull_logger, "disabled", False)
    monkeypatch.setattr(webull_logger, "propagate", False)
    monkeypatch.setattr(response_logger, "handlers", [response_handler])
    monkeypatch.setattr(response_logger, "level", logging.DEBUG)
    monkeypatch.setattr(response_logger, "disabled", False)
    monkeypatch.setattr(response_logger, "propagate", True)
    monkeypatch.setattr(logging.root.manager, "disable", 9)
    expected_states = {
        "webull": (
            tuple(webull_logger.handlers),
            webull_logger.level,
            webull_logger.disabled,
            webull_logger.propagate,
        ),
        "response": (
            tuple(response_logger.handlers),
            response_logger.level,
            response_logger.disabled,
            response_logger.propagate,
        ),
    }

    get_stock_snapshot(client, "AAPL")
    get_stock_bars(client, "AAPL")

    captured = capsys.readouterr()
    assert marker not in captured.out
    assert marker not in captured.err
    assert logging.root.manager.disable == 9
    assert (
        tuple(webull_logger.handlers),
        webull_logger.level,
        webull_logger.disabled,
        webull_logger.propagate,
    ) == expected_states["webull"]
    assert (
        tuple(response_logger.handlers),
        response_logger.level,
        response_logger.disabled,
        response_logger.propagate,
    ) == expected_states["response"]
    assert marker not in webull_handler.stream.getvalue()
    assert marker not in response_handler.stream.getvalue()


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


def test_normalize_stock_bars_has_consistent_arrow_schema_for_parquet(tmp_path):
    sample = normalize_stock_bars(json.loads(FIXTURE_PATH.read_text()))
    empty = normalize_stock_bars([])
    sample_path = tmp_path / "sample.parquet"
    empty_path = tmp_path / "empty.parquet"

    sample.to_parquet(sample_path, index=False)
    empty.to_parquet(empty_path, index=False)

    expected = pa.schema(
        [
            pa.field("symbol", pa.string()),
            pa.field("date", pa.date32()),
            pa.field("open", pa.decimal128(20, 8)),
            pa.field("high", pa.decimal128(20, 8)),
            pa.field("low", pa.decimal128(20, 8)),
            pa.field("close", pa.decimal128(20, 8)),
            pa.field("volume", pa.int64()),
        ]
    )
    assert pq.read_schema(sample_path).remove_metadata() == expected
    assert pq.read_schema(empty_path).remove_metadata() == expected


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


def test_normalize_stock_bars_rejects_unicode_numeric_timestamp_safely():
    row = _valid_bar(time="²")

    with pytest.raises(ValueError) as exc_info:
        normalize_stock_bars([row])

    assert str(exc_info.value) == "Webull bar row 0 field 'time' is invalid"
    assert "²" not in str(exc_info.value)


def test_normalize_stock_bars_rejects_oversized_timestamp_string_safely():
    row = _valid_bar(time="9" * 5000)

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


@pytest.mark.parametrize("value", ["1000000000000", "0.000000001", "9" * 5000])
def test_normalize_stock_bars_rejects_prices_outside_decimal_schema_safely(value):
    row = _valid_bar(open=value)

    with pytest.raises(ValueError) as exc_info:
        normalize_stock_bars([row])

    assert str(exc_info.value) == "Webull bar row 0 field 'open' is invalid"
    assert value not in str(exc_info.value)


@pytest.mark.parametrize("volume", [True, -1, "-1", 1.0, "1.5", "", None])
def test_normalize_stock_bars_rejects_invalid_volume(volume):
    row = _valid_bar(volume=volume)

    with pytest.raises(ValueError, match="row 0 field 'volume'"):
        normalize_stock_bars([row])


def test_normalize_stock_bars_rejects_unicode_numeric_volume_safely():
    row = _valid_bar(volume="²")

    with pytest.raises(ValueError) as exc_info:
        normalize_stock_bars([row])

    assert str(exc_info.value) == "Webull bar row 0 field 'volume' is invalid"
    assert "²" not in str(exc_info.value)


@pytest.mark.parametrize("volume", [2**63, str(2**63), "9" * 5000])
def test_normalize_stock_bars_rejects_volume_outside_int64_safely(volume):
    row = _valid_bar(volume=volume)

    with pytest.raises(ValueError) as exc_info:
        normalize_stock_bars([row])

    assert str(exc_info.value) == "Webull bar row 0 field 'volume' is invalid"
    assert str(volume) not in str(exc_info.value)


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
