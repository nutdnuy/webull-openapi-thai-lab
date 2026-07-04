from __future__ import annotations

from typing import Any

from webull_lab.account import response_json_or_raise

US_STOCK = "US_STOCK"


def get_stock_snapshot(data_client: Any, symbol: str) -> Any:
    response = data_client.market_data.get_snapshot(
        symbol.upper(),
        US_STOCK,
        extend_hour_required=True,
        overnight_required=True,
    )
    return response_json_or_raise(response)


def get_stock_bars(data_client: Any, symbol: str, timespan: str = "M1") -> Any:
    response = data_client.market_data.get_history_bar(symbol.upper(), US_STOCK, timespan)
    return response_json_or_raise(response)
