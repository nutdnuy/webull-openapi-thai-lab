from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any

import pandas as pd

from webull_lab.account import response_json_or_raise

US_STOCK = "US_STOCK"
BAR_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]


def get_stock_snapshot(data_client: Any, symbol: str) -> Any:
    response = data_client.market_data.get_snapshot(
        symbol.strip().upper(),
        US_STOCK,
        extend_hour_required=True,
        overnight_required=True,
    )
    return response_json_or_raise(response)


def get_stock_bars(data_client: Any, symbol: str, timespan: str = "M1") -> Any:
    response = data_client.market_data.get_history_bar(
        symbol.strip().upper(), US_STOCK, timespan
    )
    return response_json_or_raise(response)


def get_daily_stock_bars(data_client: Any, symbol: str) -> Any:
    return get_stock_bars(data_client, symbol, "D")


def normalize_stock_bars(payload: object) -> pd.DataFrame:
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

    return (
        pd.DataFrame(rows, columns=BAR_COLUMNS)
        .sort_values(["symbol", "date"])
        .reset_index(drop=True)
    )


def _required_field(item: Mapping[Any, Any], field: str, index: int) -> Any:
    if field not in item:
        raise ValueError(f"Webull bar row {index} is missing field '{field}'")
    return item[field]


def _parse_symbol(value: Any, index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Webull bar row {index} field 'symbol' is invalid")
    return value.strip().upper()


def _parse_timestamp(value: Any, index: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Webull bar row {index} field 'time' is invalid")
    if isinstance(value, int):
        timestamp_ms = value
    elif isinstance(value, str) and value.isdigit():
        timestamp_ms = int(value)
    else:
        raise ValueError(f"Webull bar row {index} field 'time' is invalid")
    if timestamp_ms < 0:
        raise ValueError(f"Webull bar row {index} field 'time' is invalid")
    return timestamp_ms


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
    return price


def _parse_volume(value: Any, index: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Webull bar row {index} field 'volume' is invalid")
    if isinstance(value, int):
        volume = value
    elif isinstance(value, str) and value.isdigit():
        volume = int(value)
    else:
        raise ValueError(f"Webull bar row {index} field 'volume' is invalid")
    if volume < 0:
        raise ValueError(f"Webull bar row {index} field 'volume' is invalid")
    return volume
