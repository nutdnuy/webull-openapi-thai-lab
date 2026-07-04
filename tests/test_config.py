import pytest

from webull_lab.config import Settings, load_settings, redact_secret


def test_load_settings_uses_uat_endpoint_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBULL_APP_KEY", "key_123")
    monkeypatch.setenv("WEBULL_APP_SECRET", "secret_456")
    monkeypatch.setenv("WEBULL_TOKEN_DIR", str(tmp_path / "token"))

    settings = load_settings()

    assert settings.env == "uat"
    assert settings.region == "us"
    assert settings.trading_endpoint == "us-openapi-alb.uat.webullbroker.com"
    assert settings.app_key == "key_123"
    assert settings.app_secret == "secret_456"
    assert settings.token_dir == tmp_path / "token"


def test_load_settings_rejects_missing_credentials(monkeypatch):
    monkeypatch.delenv("WEBULL_APP_KEY", raising=False)
    monkeypatch.delenv("WEBULL_APP_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="WEBULL_APP_KEY"):
        load_settings()


def test_load_settings_rejects_unknown_environment(monkeypatch):
    monkeypatch.setenv("WEBULL_ENV", "paper")
    monkeypatch.setenv("WEBULL_APP_KEY", "key_123")
    monkeypatch.setenv("WEBULL_APP_SECRET", "secret_456")

    with pytest.raises(ValueError, match="WEBULL_ENV"):
        load_settings()


def test_redact_secret_keeps_logs_safe():
    assert redact_secret("abcd1234efgh5678") == "abcd...5678"
    assert redact_secret("short") == "*****"


def test_settings_repr_does_not_expose_secret():
    settings = Settings(
        env="uat",
        region="us",
        app_key="key_123",
        app_secret="secret_456",
        account_id=None,
        token_dir=None,
    )

    rendered = repr(settings)

    assert "secret_456" not in rendered
    assert "secr..._456" in rendered
