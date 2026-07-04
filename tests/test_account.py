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
