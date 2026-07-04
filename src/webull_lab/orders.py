from __future__ import annotations

import uuid
from typing import Any

from webull_lab.account import response_json_or_raise
from webull_lab.config import Settings


class LiveOrderBlocked(RuntimeError):
    pass


def build_stock_limit_buy(symbol: str, limit_price: str, quantity: str) -> dict[str, str]:
    return {
        "client_order_id": uuid.uuid4().hex,
        "symbol": symbol.upper(),
        "instrument_type": "EQUITY",
        "market": "US",
        "order_type": "LIMIT",
        "limit_price": limit_price,
        "quantity": quantity,
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
    return response_json_or_raise(trade_client.order_v2.preview_order(account_id, [order]))


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
    return response_json_or_raise(trade_client.order_v2.place_order(settings.account_id, [order]))
