from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from math import isfinite
from time import sleep
from typing import Any

import pandas as pd
import pyarrow as pa

from webull_lab.account import response_json_or_raise
from webull_lab.clients import suppress_webull_sdk_output

US_STOCK = "US_STOCK"
BAR_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
PRICE_PRECISION = 20
PRICE_SCALE = 8
MAX_PRICE_INTEGER_DIGITS = PRICE_PRECISION - PRICE_SCALE
MAX_TIMESTAMP_MS = 253402300799999
MAX_VOLUME = 2**63 - 1
MAX_BAR_COUNT = 1200
MAX_HISTORY_PAGES = 25
BAR_REQUEST_INTERVAL_SECONDS = 1.0
BAR_DTYPES = {
    "symbol": pd.ArrowDtype(pa.string()),
    "date": pd.ArrowDtype(pa.date32()),
    "open": pd.ArrowDtype(pa.decimal128(PRICE_PRECISION, PRICE_SCALE)),
    "high": pd.ArrowDtype(pa.decimal128(PRICE_PRECISION, PRICE_SCALE)),
    "low": pd.ArrowDtype(pa.decimal128(PRICE_PRECISION, PRICE_SCALE)),
    "close": pd.ArrowDtype(pa.decimal128(PRICE_PRECISION, PRICE_SCALE)),
    "volume": pd.ArrowDtype(pa.int64()),
}


def get_stock_snapshot(data_client: Any, symbol: str) -> Any:
    with suppress_webull_sdk_output():
        response = data_client.market_data.get_snapshot(
            symbol.strip().upper(),
            US_STOCK,
            extend_hour_required=True,
            overnight_required=True,
        )
    return response_json_or_raise(response)


def get_stock_bars(data_client: Any, symbol: str, timespan: str = "M1") -> Any:
    with suppress_webull_sdk_output():
        response = data_client.market_data.get_history_bar(
            symbol.strip().upper(), US_STOCK, timespan
        )
    return response_json_or_raise(response)


def get_daily_stock_bars(data_client: Any, symbol: str) -> Any:
    return get_stock_bars(data_client, symbol, "D")


@dataclass(frozen=True)
class PriceHistoryFetch:
    payload: list[Mapping[str, Any]]
    requested_start_date: date
    requested_end_date: date
    pages_requested: int
    pagination_complete: bool


def price_history_metadata(
    years: int,
    prices: pd.DataFrame,
    *,
    fetch: PriceHistoryFetch | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    if isinstance(years, bool) or not isinstance(years, int) or years <= 0:
        raise ValueError("years must be a positive integer")
    if fetch is None:
        requested_end = as_of or datetime.now(UTC).date()
        requested_start = _years_before(requested_end, years)
        pages_requested = 0
        pagination_complete = False
    else:
        requested_start = fetch.requested_start_date
        requested_end = fetch.requested_end_date
        pages_requested = fetch.pages_requested
        pagination_complete = fetch.pagination_complete

    observed_dates = prices["date"].dropna().tolist() if "date" in prices else []
    observed_start = min(observed_dates) if observed_dates else None
    observed_end = max(observed_dates) if observed_dates else None
    if observed_start is None or observed_end is None:
        status = "unavailable"
    else:
        boundary_tolerance = timedelta(days=7)
        status = (
            "range_observed"
            if pagination_complete
            and observed_start <= requested_start + boundary_tolerance
            and observed_end >= requested_end - boundary_tolerance
            else "partial"
        )
    return {
        "status": status,
        "requested_start_date": requested_start.isoformat(),
        "requested_end_date": requested_end.isoformat(),
        "observed_start_date": observed_start.isoformat() if observed_start else None,
        "observed_end_date": observed_end.isoformat() if observed_end else None,
        "observed_bar_count": len(prices),
        "pages_requested": pages_requested,
        "pagination_complete": pagination_complete,
    }


def _years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)


def _day_start_ms(day: date) -> int:
    return int(datetime.combine(day, time(), tzinfo=UTC).timestamp() * 1000)


def fetch_daily_stock_history(
    data_client: Any,
    symbol: str,
    years: int,
    *,
    as_of: date | None = None,
) -> PriceHistoryFetch:
    """Fetch a bounded daily history, paging backward across the SDK's bar cap."""
    if isinstance(years, bool) or not isinstance(years, int) or years <= 0:
        raise ValueError("years must be a positive integer")
    if as_of is not None and type(as_of) is not date:
        raise ValueError("as_of must be a date or None")

    requested_end = as_of or datetime.now(UTC).date()
    requested_start = _years_before(requested_end, years)
    start_ms = _day_start_ms(requested_start)
    page_end_ms = _day_start_ms(requested_end + timedelta(days=1)) - 1
    normalized_symbol = symbol.strip().upper()
    rows: list[Mapping[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    pages_requested = 0
    pagination_complete = False

    for page_index in range(MAX_HISTORY_PAGES):
        if page_index:
            sleep(BAR_REQUEST_INTERVAL_SECONDS)
        with suppress_webull_sdk_output():
            response = data_client.market_data.get_history_bar(
                normalized_symbol,
                US_STOCK,
                "D",
                count=str(MAX_BAR_COUNT),
                start_time=start_ms,
                end_time=page_end_ms,
            )
        page = response_json_or_raise(response)
        pages_requested += 1
        if not isinstance(page, list):
            raise ValueError("Webull bars payload must be a list")
        if not page:
            pagination_complete = True
            break

        timestamps: list[int] = []
        for index, item in enumerate(page):
            if not isinstance(item, Mapping):
                raise ValueError(f"Webull bar row {index} must be a mapping")
            timestamp_ms = _parse_timestamp(_required_field(item, "time", index), index)
            timestamps.append(timestamp_ms)
            if start_ms <= timestamp_ms <= page_end_ms:
                item_symbol = item.get("symbol")
                dedupe_symbol = (
                    item_symbol.strip().upper()
                    if isinstance(item_symbol, str)
                    else normalized_symbol
                )
                key = (dedupe_symbol, timestamp_ms)
                if key not in seen:
                    seen.add(key)
                    rows.append(item)

        earliest_ms = min(timestamps)
        if earliest_ms <= start_ms or len(page) < MAX_BAR_COUNT:
            pagination_complete = True
            break
        next_end_ms = earliest_ms - 1
        if next_end_ms >= page_end_ms:
            break
        page_end_ms = next_end_ms

    return PriceHistoryFetch(
        payload=rows,
        requested_start_date=requested_start,
        requested_end_date=requested_end,
        pages_requested=pages_requested,
        pagination_complete=pagination_complete,
    )


def normalize_stock_bars(payload: object) -> pd.DataFrame:
    """Normalize bars to an Arrow-stable schema suitable for Parquet.

    Prices are nonnegative decimal128(20, 8): at most 12 integer and 8 fractional
    digits, without rounding. Volume is a nonnegative signed int64.
    """
    if not isinstance(payload, list):
        raise ValueError("Webull bars payload must be a list")

    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, object]] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"Webull bar row {index} must be a mapping")

        symbol = _parse_symbol(_required_field(item, "symbol", index), index)
        timestamp_ms = _parse_timestamp(_required_field(item, "time", index), index)
        bar_date = _timestamp_to_utc_date(timestamp_ms, index)
        row = {
            "symbol": symbol,
            "date": bar_date,
            "open": _parse_price(_required_field(item, "open", index), "open", index),
            "high": _parse_price(_required_field(item, "high", index), "high", index),
            "low": _parse_price(_required_field(item, "low", index), "low", index),
            "close": _parse_price(_required_field(item, "close", index), "close", index),
            "volume": _parse_volume(_required_field(item, "volume", index), index),
        }

        key = (symbol, bar_date)
        if key in seen_keys:
            raise ValueError("Webull bars payload contains a duplicate symbol and date")
        seen_keys.add(key)
        rows.append(row)

    frame = pd.DataFrame(
        {
            column: pd.Series([row[column] for row in rows], dtype=BAR_DTYPES[column])
            for column in BAR_COLUMNS
        }
    )
    return frame.sort_values(["symbol", "date"]).reset_index(drop=True)


def _required_field(item: Mapping[Any, Any], field: str, index: int) -> Any:
    if field not in item:
        raise ValueError(f"Webull bar row {index} is missing field '{field}'")
    return item[field]


def _parse_symbol(value: Any, index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Webull bar row {index} field 'symbol' is invalid")
    return value.strip().upper()


def _parse_timestamp(value: Any, index: int) -> int:
    return _parse_bounded_integer(value, "time", index, MAX_TIMESTAMP_MS)


def _timestamp_to_utc_date(timestamp_ms: int, index: int) -> date:
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).date()
    except (OverflowError, OSError, ValueError):
        raise ValueError(f"Webull bar row {index} field 'time' is invalid") from None


def _parse_price(value: Any, field: str, index: int) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"Webull bar row {index} field '{field}' is invalid")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"Webull bar row {index} field '{field}' is invalid")
    try:
        price = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"Webull bar row {index} field '{field}' is invalid") from None
    if not price.is_finite() or price < 0:
        raise ValueError(f"Webull bar row {index} field '{field}' is invalid")
    _, digits, exponent = price.as_tuple()
    integer_digits = max(len(digits) + exponent, 0)
    scale = max(-exponent, 0)
    if integer_digits > MAX_PRICE_INTEGER_DIGITS or scale > PRICE_SCALE:
        raise ValueError(f"Webull bar row {index} field '{field}' is invalid")
    return price


def _parse_volume(value: Any, index: int) -> int:
    return _parse_bounded_integer(value, "volume", index, MAX_VOLUME)


def _parse_bounded_integer(value: Any, field: str, index: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Webull bar row {index} field '{field}' is invalid")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.isascii() and value.isdecimal():
        normalized = value.lstrip("0") or "0"
        if len(normalized) > len(str(maximum)):
            raise ValueError(f"Webull bar row {index} field '{field}' is invalid")
        parsed = int(normalized)
    else:
        raise ValueError(f"Webull bar row {index} field '{field}' is invalid")
    if parsed < 0 or parsed > maximum:
        raise ValueError(f"Webull bar row {index} field '{field}' is invalid")
    return parsed
