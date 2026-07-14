from __future__ import annotations

from typing import Any

from webull_lab.clients import suppress_webull_sdk_output


class ResponseError(RuntimeError):
    pass


def response_json_or_raise(response: Any) -> Any:
    if response.status_code != 200:
        raise ResponseError(f"HTTP {response.status_code}: {response.text}")
    return response.json()


def get_account_list(trade_client: Any) -> Any:
    with suppress_webull_sdk_output():
        response = trade_client.account_v2.get_account_list()
    return response_json_or_raise(response)


def get_account_balance(trade_client: Any, account_id: str) -> Any:
    with suppress_webull_sdk_output():
        response = trade_client.account_v2.get_account_balance(account_id)
    return response_json_or_raise(response)
