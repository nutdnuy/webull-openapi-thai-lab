from pathlib import Path

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
    assert api_client.endpoints == [("us", "us-openapi-alb.uat.webullbroker.com")]
    assert api_client.token_dir == ".webull-token"


def test_build_trade_client_wraps_api_client():
    trade_client = build_trade_client(
        make_settings(),
        api_client_cls=FakeApiClient,
        trade_client_cls=FakeTradeClient,
    )

    assert isinstance(trade_client, FakeTradeClient)
    assert trade_client.api_client.endpoints == [("us", "us-openapi-alb.uat.webullbroker.com")]


def test_build_data_client_wraps_api_client():
    data_client = build_data_client(
        make_settings(),
        api_client_cls=FakeApiClient,
        data_client_cls=FakeDataClient,
    )

    assert isinstance(data_client, FakeDataClient)
    assert data_client.api_client.endpoints == [("us", "us-openapi-alb.uat.webullbroker.com")]
