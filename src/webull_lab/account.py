from __future__ import annotations

from typing import Any


class ResponseError(RuntimeError):
    pass


def response_json_or_raise(response: Any) -> Any:
    if response.status_code != 200:
        raise ResponseError(f"HTTP {response.status_code}: {response.text}")
    return response.json()


def get_account_list(trade_client: Any) -> Any:
    return response_json_or_raise(trade_client.account_v2.get_account_list())


def get_account_balance(trade_client: Any, account_id: str) -> Any:
    return response_json_or_raise(trade_client.account_v2.get_account_balance(account_id))
