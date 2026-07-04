from __future__ import annotations

import json

from webull_lab.account import get_account_list
from webull_lab.clients import build_trade_client
from webull_lab.config import load_settings


def main() -> None:
    settings = load_settings()
    trade_client = build_trade_client(settings)
    accounts = get_account_list(trade_client)
    print(json.dumps(accounts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
