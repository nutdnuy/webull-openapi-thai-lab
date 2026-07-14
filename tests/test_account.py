import io
import logging
import sys

import pytest

from webull_lab.account import ResponseError, get_account_balance, get_account_list


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeAccountV2:
    def get_account_list(self):
        return FakeResponse(200, [{"account_id": "acct_1"}])

    def get_account_balance(self, account_id):
        return FakeResponse(200, {"account_id": account_id, "buying_power": "1000"})


class FailingAccountV2:
    def get_account_list(self):
        return FakeResponse(401, {"message": "bad signature"})


class FakeTradeClient:
    account_v2 = FakeAccountV2()


class FailingTradeClient:
    account_v2 = FailingAccountV2()


class LoggingAccountV2(FakeAccountV2):
    marker = "MARKER_ACCOUNT_SECRET_MUST_NOT_LEAK"

    def _emit_secret_output(self):
        print(f"stdout x-app-key={self.marker}")
        print(f"stderr x-signature={self.marker}", file=sys.stderr)
        logging.getLogger("webull").critical("x-app-key=%s", self.marker)
        logging.getLogger("webull.core.http.response").critical(
            "x-signature=%s", self.marker
        )

    def get_account_list(self):
        self._emit_secret_output()
        return super().get_account_list()

    def get_account_balance(self, account_id):
        self._emit_secret_output()
        return super().get_account_balance(account_id)


def test_get_account_list_returns_json_payload():
    assert get_account_list(FakeTradeClient()) == [{"account_id": "acct_1"}]


def test_get_account_balance_returns_json_payload():
    assert get_account_balance(FakeTradeClient(), "acct_1") == {
        "account_id": "acct_1",
        "buying_power": "1000",
    }


def test_get_account_list_raises_response_error_on_non_200():
    with pytest.raises(ResponseError, match="HTTP 401"):
        get_account_list(FailingTradeClient())


def test_account_sdk_calls_suppress_secrets_and_restore_process_state(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    marker = LoggingAccountV2.marker
    client = FakeTradeClient()
    client.account_v2 = LoggingAccountV2()
    webull_logger = logging.getLogger("webull")
    response_logger = logging.getLogger("webull.core.http.response")
    webull_handler = logging.StreamHandler(io.StringIO())
    response_handler = logging.StreamHandler(io.StringIO())
    monkeypatch.setattr(webull_logger, "handlers", [webull_handler])
    monkeypatch.setattr(webull_logger, "level", logging.INFO)
    monkeypatch.setattr(webull_logger, "disabled", False)
    monkeypatch.setattr(webull_logger, "propagate", True)
    monkeypatch.setattr(response_logger, "handlers", [response_handler])
    monkeypatch.setattr(response_logger, "level", logging.DEBUG)
    monkeypatch.setattr(response_logger, "disabled", False)
    monkeypatch.setattr(response_logger, "propagate", False)
    monkeypatch.setattr(logging.root.manager, "disable", 11)
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

    assert get_account_list(client) == [{"account_id": "acct_1"}]
    assert get_account_balance(client, "acct_1")["buying_power"] == "1000"

    captured = capsys.readouterr()
    assert marker not in captured.out
    assert marker not in captured.err
    assert marker not in webull_handler.stream.getvalue()
    assert marker not in response_handler.stream.getvalue()
    assert not (tmp_path / "webull_trade_sdk.log").exists()
    assert logging.root.manager.disable == 11
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
