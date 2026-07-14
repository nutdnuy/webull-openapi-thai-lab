from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from webull_lab.account import response_json_or_raise
from webull_lab.clients import suppress_webull_sdk_output
from webull_lab.config import Settings


class LiveOrderBlocked(RuntimeError):
    pass


def _require_not_blank(field_name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _require_positive_decimal(field_name: str, value: str) -> str:
    normalized = _require_not_blank(field_name, value)
    try:
        decimal_value = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(f"{field_name} must be a positive decimal number") from error

    if not decimal_value.is_finite() or decimal_value <= 0:
        raise ValueError(f"{field_name} must be a positive decimal number")
    return normalized


def build_stock_limit_buy(symbol: str, limit_price: str, quantity: str) -> dict[str, str]:
    normalized_symbol = _require_not_blank("symbol", symbol).upper()
    normalized_limit_price = _require_positive_decimal("limit_price", limit_price)
    normalized_quantity = _require_positive_decimal("quantity", quantity)

    return {
        "client_order_id": uuid.uuid4().hex,
        "symbol": normalized_symbol,
        "instrument_type": "EQUITY",
        "market": "US",
        "order_type": "LIMIT",
        "limit_price": normalized_limit_price,
        "quantity": normalized_quantity,
        "support_trading_session": "CORE",
        "side": "BUY",
        "time_in_force": "DAY",
        "entrust_type": "QTY",
    }


def preview_stock_limit_buy(
    trade_client: Any,
    account_id: str,
    symbol: str,
    limit_price: str,
    quantity: str,
) -> Any:
    order = build_stock_limit_buy(symbol=symbol, limit_price=limit_price, quantity=quantity)
    with suppress_webull_sdk_output():
        response = trade_client.order_v2.preview_order(account_id, [order])
    return response_json_or_raise(response)


def place_stock_limit_buy(
    trade_client: Any,
    settings: Settings,
    symbol: str,
    limit_price: str,
    quantity: str,
) -> Any:
    if not settings.live_orders_enabled:
        raise LiveOrderBlocked(
            "Live order placement is blocked. Set WEBULL_ALLOW_LIVE_ORDERS=I_UNDERSTAND "
            "only after checking the account, symbol, price, quantity, and environment."
        )
    if settings.account_id is None:
        raise ValueError("WEBULL_ACCOUNT_ID is required before placing an order")

    order = build_stock_limit_buy(symbol=symbol, limit_price=limit_price, quantity=quantity)
    with suppress_webull_sdk_output():
        response = trade_client.order_v2.place_order(settings.account_id, [order])
    return response_json_or_raise(response)
