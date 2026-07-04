from typer.testing import CliRunner

from webull_lab.account import ResponseError
from webull_lab.cli import app

WEBULL_ENV_VARS = [
    "WEBULL_ENV",
    "WEBULL_REGION",
    "WEBULL_APP_KEY",
    "WEBULL_APP_SECRET",
    "WEBULL_ACCOUNT_ID",
    "WEBULL_TOKEN_DIR",
    "WEBULL_ALLOW_LIVE_ORDERS",
]


def clear_webull_env(monkeypatch):
    for key in WEBULL_ENV_VARS:
        monkeypatch.delenv(key, raising=False)


def test_doctor_redacts_account_id_and_secret(monkeypatch):
    clear_webull_env(monkeypatch)
    account_id = "J6HA4EBQRQFJD2J6NQH0F7M649"
    app_secret = "secret_456789"
    monkeypatch.setenv("WEBULL_APP_KEY", "key_123456")
    monkeypatch.setenv("WEBULL_APP_SECRET", app_secret)
    monkeypatch.setenv("WEBULL_ACCOUNT_ID", account_id)

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert account_id not in result.output
    assert "J6HA...M649" in result.output
    assert app_secret not in result.output


def test_stock_snapshot_prints_json_payload(monkeypatch):
    calls = []
    settings = object()
    data_client = object()

    def fake_build_data_client(received_settings):
        calls.append(("build_data_client", received_settings))
        return data_client

    def fake_get_stock_snapshot(received_data_client, symbol):
        calls.append(("get_stock_snapshot", received_data_client, symbol))
        return {"symbol": symbol, "last_price": "200.00"}

    monkeypatch.setattr("webull_lab.cli.load_settings", lambda: settings)
    monkeypatch.setattr("webull_lab.cli.build_data_client", fake_build_data_client)
    monkeypatch.setattr("webull_lab.cli.get_stock_snapshot", fake_get_stock_snapshot)

    result = CliRunner().invoke(app, ["stock-snapshot", "AAPL"])

    assert result.exit_code == 0
    assert '"symbol": "AAPL"' in result.output
    assert '"last_price": "200.00"' in result.output
    assert calls == [
        ("build_data_client", settings),
        ("get_stock_snapshot", data_client, "AAPL"),
    ]


def test_stock_snapshot_prints_error_without_traceback(monkeypatch):
    monkeypatch.setattr("webull_lab.cli.load_settings", lambda: object())
    monkeypatch.setattr("webull_lab.cli.build_data_client", lambda settings: object())

    def fake_get_stock_snapshot(data_client, symbol):
        raise ResponseError("HTTP 401: bad signature")

    monkeypatch.setattr("webull_lab.cli.get_stock_snapshot", fake_get_stock_snapshot)

    result = CliRunner().invoke(app, ["stock-snapshot", "AAPL"])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "HTTP 401" in result.output
    assert "Traceback" not in result.output


def test_account_list_prints_error_without_traceback(monkeypatch):
    monkeypatch.setattr("webull_lab.cli.load_settings", lambda: object())
    monkeypatch.setattr("webull_lab.cli.build_trade_client", lambda settings: object())

    def fake_get_account_list(trade_client):
        raise ResponseError("HTTP 401: bad signature")

    monkeypatch.setattr("webull_lab.cli.get_account_list", fake_get_account_list)

    result = CliRunner().invoke(app, ["account-list"])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "HTTP 401" in result.output
    assert "Traceback" not in result.output
