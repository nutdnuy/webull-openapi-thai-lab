from typer.testing import CliRunner

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
