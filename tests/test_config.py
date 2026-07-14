import pytest

from webull_lab.config import Settings, load_settings, redact_secret

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


def test_load_settings_uses_uat_endpoint_by_default(monkeypatch, tmp_path):
    clear_webull_env(monkeypatch)
    monkeypatch.setenv("WEBULL_APP_KEY", "key_123")
    monkeypatch.setenv("WEBULL_APP_SECRET", "secret_456")
    monkeypatch.setenv("WEBULL_TOKEN_DIR", str(tmp_path / "token"))

    settings = load_settings(env_file=None)

    assert settings.env == "uat"
    assert settings.region == "us"
    assert settings.trading_endpoint == "api.sandbox.webull.com"
    assert settings.app_key == "key_123"
    assert settings.app_secret == "secret_456"
    assert settings.token_dir == tmp_path / "token"


def test_load_settings_rejects_missing_credentials(monkeypatch):
    clear_webull_env(monkeypatch)

    with pytest.raises(RuntimeError, match="WEBULL_APP_KEY"):
        load_settings(env_file=None)


def test_load_settings_rejects_unknown_environment(monkeypatch):
    clear_webull_env(monkeypatch)
    monkeypatch.setenv("WEBULL_ENV", "paper")
    monkeypatch.setenv("WEBULL_APP_KEY", "key_123")
    monkeypatch.setenv("WEBULL_APP_SECRET", "secret_456")

    with pytest.raises(ValueError, match="WEBULL_ENV"):
        load_settings(env_file=None)


def test_load_settings_reads_explicit_env_file(monkeypatch, tmp_path):
    clear_webull_env(monkeypatch)
    env_file = tmp_path / ".env"
    token_dir = tmp_path / "tokens"
    env_file.write_text(
        "\n".join(
            [
                "WEBULL_ENV=prod",
                "WEBULL_REGION=us",
                "WEBULL_APP_KEY=file_key",
                "WEBULL_APP_SECRET=file_secret",
                f"WEBULL_TOKEN_DIR={token_dir}",
                "WEBULL_ACCOUNT_ID=account_123456789",
                "WEBULL_ALLOW_LIVE_ORDERS=I_UNDERSTAND",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.env == "prod"
    assert settings.trading_endpoint == "api.webull.com"
    assert settings.app_key == "file_key"
    assert settings.app_secret == "file_secret"
    assert settings.token_dir == token_dir
    assert settings.account_id == "account_123456789"
    assert settings.live_orders_enabled is True


def test_load_settings_treats_blank_account_id_as_missing(monkeypatch):
    clear_webull_env(monkeypatch)
    monkeypatch.setenv("WEBULL_APP_KEY", "key_123")
    monkeypatch.setenv("WEBULL_APP_SECRET", "secret_456")
    monkeypatch.setenv("WEBULL_ACCOUNT_ID", "   ")

    settings = load_settings(env_file=None)

    assert settings.account_id is None


def test_load_settings_strips_account_id(monkeypatch):
    clear_webull_env(monkeypatch)
    monkeypatch.setenv("WEBULL_APP_KEY", "key_123")
    monkeypatch.setenv("WEBULL_APP_SECRET", "secret_456")
    monkeypatch.setenv("WEBULL_ACCOUNT_ID", "  acct_1  ")

    settings = load_settings(env_file=None)

    assert settings.account_id == "acct_1"


def test_redact_secret_keeps_logs_safe():
    assert redact_secret("abcd1234efgh5678") == "abcd...5678"
    assert redact_secret("short") == "*****"


def test_settings_repr_does_not_expose_secret():
    settings = Settings(
        env="uat",
        region="us",
        app_key="key_123",
        app_secret="secret_456",
        account_id="account_123456789",
        token_dir=None,
    )

    rendered = repr(settings)

    assert "secret_456" not in rendered
    assert "account_123456789" not in rendered
    assert "secr..._456" in rendered
    assert "acco...6789" in rendered


def test_live_orders_enabled_is_snapshot(monkeypatch):
    clear_webull_env(monkeypatch)
    monkeypatch.setenv("WEBULL_APP_KEY", "key_123")
    monkeypatch.setenv("WEBULL_APP_SECRET", "secret_456")
    monkeypatch.setenv("WEBULL_ALLOW_LIVE_ORDERS", "I_UNDERSTAND")

    settings = load_settings(env_file=None)
    monkeypatch.setenv("WEBULL_ALLOW_LIVE_ORDERS", "NO")

    assert settings.live_orders_enabled is True
