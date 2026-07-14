from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import Any

from webull_lab.config import Settings


class _DiscardLogStream:
    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


_DISCARD_LOG_STREAM = _DiscardLogStream()
_WEBULL_LOGGER_NAMES = ("webull", "webull.core.http.response")


@contextmanager
def suppress_webull_sdk_output() -> Iterator[None]:
    """Suppress one SDK call and restore state; the lab CLI invokes this synchronously."""
    previous_disable_level = logging.root.manager.disable
    logger_states = []
    for name in _WEBULL_LOGGER_NAMES:
        logger = logging.getLogger(name)
        logger_states.append(
            (
                logger,
                logger.handlers,
                tuple(logger.handlers),
                logger.level,
                logger.disabled,
                logger.propagate,
            )
        )
    with redirect_stdout(_DISCARD_LOG_STREAM), redirect_stderr(_DISCARD_LOG_STREAM):
        logging.disable(max(previous_disable_level, logging.CRITICAL))
        try:
            yield
        finally:
            logging.disable(previous_disable_level)
            for logger, handler_list, handlers, level, disabled, propagate in logger_states:
                for handler in logger.handlers:
                    if handler not in handlers:
                        handler.close()
                handler_list[:] = handlers
                logger.handlers = handler_list
                logger.setLevel(level)
                logger.disabled = disabled
                logger.propagate = propagate


def _prevent_default_sdk_loggers(api_client: Any) -> None:
    # Webull has no public no-logging constructor option. Its DataClient and
    # TradeClient inspect these compatibility flags before installing console/file handlers.
    api_client._stream_logger_set = True
    api_client._file_logger_set = True


def build_api_client(settings: Settings, api_client_cls: type[Any] | None = None) -> Any:
    with suppress_webull_sdk_output():
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
    with suppress_webull_sdk_output():
        if trade_client_cls is None:
            from webull.trade.trade_client import TradeClient

            trade_client_cls = TradeClient

    api_client = build_api_client(settings, api_client_cls=api_client_cls)
    _prevent_default_sdk_loggers(api_client)
    with suppress_webull_sdk_output():
        return trade_client_cls(api_client)


def build_data_client(
    settings: Settings,
    api_client_cls: type[Any] | None = None,
    data_client_cls: type[Any] | None = None,
) -> Any:
    with suppress_webull_sdk_output():
        if data_client_cls is None:
            from webull.data.data_client import DataClient

            data_client_cls = DataClient

    api_client = build_api_client(settings, api_client_cls=api_client_cls)
    _prevent_default_sdk_loggers(api_client)
    with suppress_webull_sdk_output():
        return data_client_cls(api_client)
