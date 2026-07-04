from __future__ import annotations

from typing import Any

from webull_lab.config import Settings


def build_api_client(settings: Settings, api_client_cls: type[Any] | None = None) -> Any:
    if api_client_cls is None:
        from webull.core.client import ApiClient

        api_client_cls = ApiClient

    api_client = api_client_cls(settings.app_key, settings.app_secret, settings.region)
    api_client.add_endpoint(settings.region, settings.trading_endpoint)
    if settings.token_dir is not None:
        api_client.set_token_dir(str(settings.token_dir))
    return api_client


def build_trade_client(
    settings: Settings,
    api_client_cls: type[Any] | None = None,
    trade_client_cls: type[Any] | None = None,
) -> Any:
    if trade_client_cls is None:
        from webull.trade.trade_client import TradeClient

        trade_client_cls = TradeClient

    return trade_client_cls(build_api_client(settings, api_client_cls=api_client_cls))


def build_data_client(
    settings: Settings,
    api_client_cls: type[Any] | None = None,
    data_client_cls: type[Any] | None = None,
) -> Any:
    if data_client_cls is None:
        from webull.data.data_client import DataClient

        data_client_cls = DataClient

    return data_client_cls(build_api_client(settings, api_client_cls=api_client_cls))
