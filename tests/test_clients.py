import io
import logging
import sys
from pathlib import Path

import pytest

from webull_lab.clients import build_api_client, build_data_client, build_trade_client
from webull_lab.config import Settings


class FakeApiClient:
    def __init__(self, app_key, app_secret, region):
        self.app_key = app_key
        self.app_secret = app_secret
        self.region = region
        self.endpoints = []
        self.token_dir = None

    def add_endpoint(self, region, endpoint):
        self.endpoints.append((region, endpoint))

    def set_token_dir(self, token_dir):
        self.token_dir = token_dir


class FakeTradeClient:
    def __init__(self, api_client):
        self.api_client = api_client


class FakeDataClient:
    def __init__(self, api_client):
        self.api_client = api_client


class LoggingSdkClient:
    marker = ""
    log_filename = ""

    def __init__(self, api_client):
        if not getattr(api_client, "_stream_logger_set", False) and not getattr(
            api_client, "_file_logger_set", False
        ):
            api_client.set_stream_logger()
            api_client.set_file_logger(self.log_filename)
        self._emit_logs()

    def emit_request_log(self):
        self._emit_logs()

    def _emit_logs(self):
        print(f"stdout {self.marker}")
        print(f"stderr {self.marker}", file=sys.stderr)
        logging.getLogger("webull.core.client").error(
            "signed request app_key=%s signature=%s", self.marker, self.marker
        )


class FailingLoggingSdkClient(LoggingSdkClient):
    def __init__(self, api_client):
        super().__init__(api_client)
        raise RuntimeError(self.marker)
        logging.getLogger("webull.core.http.response").debug(
            "x-app-key=%s x-signature=%s", self.marker, self.marker
        )


def make_settings() -> Settings:
    return Settings(
        env="uat",
        region="us",
        app_key="key_123",
        app_secret="secret_456",
        account_id="acct_789",
        token_dir=Path(".webull-token"),
    )


def test_build_api_client_sets_endpoint_and_token_dir():
    api_client = build_api_client(make_settings(), api_client_cls=FakeApiClient)

    assert api_client.app_key == "key_123"
    assert api_client.region == "us"
    assert api_client.endpoints == [("us", "api.sandbox.webull.com")]
    assert api_client.token_dir == ".webull-token"


def test_build_trade_client_wraps_api_client():
    trade_client = build_trade_client(
        make_settings(),
        api_client_cls=FakeApiClient,
        trade_client_cls=FakeTradeClient,
    )

    assert isinstance(trade_client, FakeTradeClient)
    assert trade_client.api_client.endpoints == [("us", "api.sandbox.webull.com")]


def test_build_data_client_wraps_api_client():
    data_client = build_data_client(
        make_settings(),
        api_client_cls=FakeApiClient,
        data_client_cls=FakeDataClient,
    )

    assert isinstance(data_client, FakeDataClient)
    assert data_client.api_client.endpoints == [("us", "api.sandbox.webull.com")]


@pytest.mark.parametrize(
    ("builder", "client_class_argument", "log_filename", "client_class"),
    [
        (build_data_client, "data_client_cls", "webull_data_sdk.log", LoggingSdkClient),
        (build_trade_client, "trade_client_cls", "webull_trade_sdk.log", LoggingSdkClient),
        (
            build_data_client,
            "data_client_cls",
            "webull_data_sdk.log",
            FailingLoggingSdkClient,
        ),
        (
            build_trade_client,
            "trade_client_cls",
            "webull_trade_sdk.log",
            FailingLoggingSdkClient,
        ),
    ],
)
def test_sdk_client_build_scope_restores_logging_and_stream_state(
    monkeypatch,
    tmp_path,
    capsys,
    builder,
    client_class_argument,
    log_filename,
    client_class,
):
    marker = "MARKER_KEY_AND_SIGNATURE_MUST_NOT_LEAK"
    monkeypatch.chdir(tmp_path)
    webull_logger = logging.getLogger("webull")
    response_logger = logging.getLogger("webull.core.http.response")
    webull_handler = logging.StreamHandler(io.StringIO())
    response_handler = logging.StreamHandler(io.StringIO())
    monkeypatch.setattr(webull_logger, "handlers", [webull_handler])
    monkeypatch.setattr(webull_logger, "level", logging.WARNING)
    monkeypatch.setattr(webull_logger, "disabled", False)
    monkeypatch.setattr(webull_logger, "propagate", True)
    monkeypatch.setattr(response_logger, "handlers", [response_handler])
    monkeypatch.setattr(response_logger, "level", logging.DEBUG)
    monkeypatch.setattr(response_logger, "disabled", True)
    monkeypatch.setattr(response_logger, "propagate", False)
    monkeypatch.setattr(logging.root.manager, "disable", 17)
    expected_webull_state = (
        tuple(webull_logger.handlers),
        webull_logger.level,
        webull_logger.disabled,
        webull_logger.propagate,
    )
    expected_response_state = (
        tuple(response_logger.handlers),
        response_logger.level,
        response_logger.disabled,
        response_logger.propagate,
    )
    stdout_before = sys.stdout
    stderr_before = sys.stderr
    client_class.marker = marker
    client_class.log_filename = log_filename

    for _ in range(2):
        if client_class is FailingLoggingSdkClient:
            with pytest.raises(RuntimeError, match=marker):
                builder(make_settings(), **{client_class_argument: client_class})
        else:
            builder(make_settings(), **{client_class_argument: client_class})

    captured = capsys.readouterr()
    assert marker not in captured.out
    assert marker not in captured.err
    assert not (tmp_path / log_filename).exists()
    assert logging.root.manager.disable == 17
    assert sys.stdout is stdout_before
    assert sys.stderr is stderr_before
    assert (
        tuple(webull_logger.handlers),
        webull_logger.level,
        webull_logger.disabled,
        webull_logger.propagate,
    ) == expected_webull_state
    assert (
        tuple(response_logger.handlers),
        response_logger.level,
        response_logger.disabled,
        response_logger.propagate,
    ) == expected_response_state
