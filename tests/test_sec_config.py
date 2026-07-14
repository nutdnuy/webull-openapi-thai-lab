import pytest

from webull_lab.sec_config import load_sec_settings


def test_load_sec_settings_reads_environment(monkeypatch, tmp_path):
    cache_dir = tmp_path / "sec-cache"
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")
    monkeypatch.setenv("SEC_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("SEC_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("SEC_MAX_ATTEMPTS", raising=False)

    settings = load_sec_settings()

    assert settings.user_agent == "webull-openapi-thai-lab researcher@example.com"
    assert settings.cache_dir == cache_dir
    assert settings.timeout_seconds == 20.0
    assert settings.max_attempts == 3


def test_load_sec_settings_rejects_missing_contact_email(monkeypatch):
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)

    with pytest.raises(RuntimeError, match="SEC_CONTACT_EMAIL"):
        load_sec_settings()


def test_load_sec_settings_rejects_non_positive_timeout(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")
    monkeypatch.setenv("SEC_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValueError, match="positive"):
        load_sec_settings()


@pytest.mark.parametrize("contact_email", ["not-an-email", "user@example.com@invalid"])
def test_load_sec_settings_rejects_invalid_contact_email(monkeypatch, contact_email):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", contact_email)

    with pytest.raises(RuntimeError, match="SEC_CONTACT_EMAIL"):
        load_sec_settings()


def test_load_sec_settings_rejects_non_positive_max_attempts(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")
    monkeypatch.setenv("SEC_MAX_ATTEMPTS", "0")

    with pytest.raises(ValueError, match="positive"):
        load_sec_settings()
