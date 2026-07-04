from __future__ import annotations

import json

from webull_lab.clients import build_data_client
from webull_lab.config import load_settings
from webull_lab.market_data import get_stock_snapshot


def main() -> None:
    settings = load_settings()
    data_client = build_data_client(settings)
    snapshot = get_stock_snapshot(data_client, "AAPL")
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
