from __future__ import annotations

import json

from webull_lab.clients import build_trade_client
from webull_lab.config import load_settings
from webull_lab.orders import preview_stock_limit_buy


def main() -> None:
    settings = load_settings()
    if settings.account_id is None:
        raise SystemExit("Set WEBULL_ACCOUNT_ID in .env before running this example.")

    trade_client = build_trade_client(settings)
    preview = preview_stock_limit_buy(
        trade_client,
        account_id=settings.account_id,
        symbol="AAPL",
        limit_price="100",
        quantity="1",
    )
    print(json.dumps(preview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
