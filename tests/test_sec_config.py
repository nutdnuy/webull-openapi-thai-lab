from pathlib import Path

import pytest

from webull_lab.sec_config import load_sec_settings

SEC_ENV_VARS = [
    "SEC_CONTACT_EMAIL",
    "SEC_CACHE_DIR",
    "SEC_TIMEOUT_SECONDS",
    "SEC_MAX_ATTEMPTS",
]


@pytest.fixture(autouse=True)
def clear_sec_env(monkeypatch):
    for key in SEC_ENV_VARS:
        monkeypatch.delenv(key, raising=False)
    yield
    for key in SEC_ENV_VARS:
        monkeypatch.delenv(key, raising=False)


def test_load_sec_settings_reads_environment(monkeypatch, tmp_path):
    cache_dir = tmp_path / "sec-cache"
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")
    monkeypatch.setenv("SEC_CACHE_DIR", str(cache_dir))
    settings = load_sec_settings(env_file=None)

    assert settings.user_agent == "webull-openapi-thai-lab researcher@example.com"
    assert settings.cache_dir == cache_dir
    assert settings.timeout_seconds == 20.0
    assert settings.max_attempts == 3


def test_load_sec_settings_rejects_missing_contact_email(monkeypatch):
    with pytest.raises(RuntimeError, match="SEC_CONTACT_EMAIL"):
        load_sec_settings(env_file=None)


@pytest.mark.parametrize("timeout", ["nan", "inf", "-inf", "0"])
def test_load_sec_settings_rejects_non_finite_or_non_positive_timeout(monkeypatch, timeout):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")
    monkeypatch.setenv("SEC_TIMEOUT_SECONDS", timeout)

    with pytest.raises(ValueError, match="positive"):
        load_sec_settings(env_file=None)


@pytest.mark.parametrize("contact_email", ["not-an-email", "user@example.com@invalid"])
def test_load_sec_settings_rejects_invalid_contact_email(monkeypatch, contact_email):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", contact_email)

    with pytest.raises(RuntimeError, match="SEC_CONTACT_EMAIL"):
        load_sec_settings(env_file=None)


def test_load_sec_settings_rejects_non_positive_max_attempts(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")
    monkeypatch.setenv("SEC_MAX_ATTEMPTS", "0")

    with pytest.raises(ValueError, match="positive"):
        load_sec_settings(env_file=None)


def test_load_sec_settings_reads_explicit_env_file(tmp_path):
    env_file = tmp_path / ".env.sec"
    cache_dir = tmp_path / "cache"
    env_file.write_text(
        "\n".join(
            [
                "SEC_CONTACT_EMAIL=researcher@example.com",
                f"SEC_CACHE_DIR={cache_dir}",
                "SEC_TIMEOUT_SECONDS=15",
                "SEC_MAX_ATTEMPTS=4",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_sec_settings(env_file=env_file)

    assert settings.contact_email == "researcher@example.com"
    assert settings.cache_dir == cache_dir
    assert settings.timeout_seconds == 15.0
    assert settings.max_attempts == 4


def test_load_sec_settings_env_file_none_does_not_load_dotenv(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "SEC_CONTACT_EMAIL=researcher@example.com\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="SEC_CONTACT_EMAIL"):
        load_sec_settings(env_file=None)


def test_load_sec_settings_uses_default_cache_dir_when_environment_is_blank(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")
    monkeypatch.setenv("SEC_CACHE_DIR", "   ")

    settings = load_sec_settings(env_file=None)

    assert settings.cache_dir == Path("data/private/sec-cache")


def test_load_sec_settings_rejects_example_placeholder_email(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "your_monitored_email@example.com")

    with pytest.raises(RuntimeError, match="SEC_CONTACT_EMAIL"):
        load_sec_settings(env_file=None)
