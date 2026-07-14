from __future__ import annotations

import logging
from typing import Any

from webull_lab.config import Settings

SILENT_LOG_LEVEL = logging.CRITICAL + 1
WEBULL_RESPONSE_LOGGER = "webull.core.http.response"


class _DiscardLogStream:
    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


_DISCARD_LOG_STREAM = _DiscardLogStream()


def _configure_secret_safe_sdk_logging(api_client: Any) -> None:
    webull_logger = logging.getLogger("webull")
    webull_logger.handlers.clear()
    webull_logger.setLevel(SILENT_LOG_LEVEL)
    webull_logger.propagate = False

    response_logger = logging.getLogger(WEBULL_RESPONSE_LOGGER)
    response_logger.handlers.clear()
    response_logger.disabled = True
    response_logger.propagate = False

    set_stream_logger = getattr(api_client, "set_stream_logger", None)
    if callable(set_stream_logger):
        set_stream_logger(
            log_level=SILENT_LOG_LEVEL,
            logger_name="webull",
            stream=_DISCARD_LOG_STREAM,
            format_string="%(message)s",
        )
    set_logger = getattr(api_client, "set_logger", None)
    if callable(set_logger):
        set_logger(webull_logger)


def build_api_client(settings: Settings, api_client_cls: type[Any] | None = None) -> Any:
    if api_client_cls is None:
        from webull.core.client import ApiClient

        api_client_cls = ApiClient

    api_client = api_client_cls(settings.app_key, settings.app_secret, settings.region)
    _configure_secret_safe_sdk_logging(api_client)
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
