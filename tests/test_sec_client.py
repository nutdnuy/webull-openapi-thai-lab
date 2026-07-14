import json
import traceback
from pathlib import Path

import pytest
import requests

import webull_lab.sec_client as sec_client_module
from webull_lab.sec_client import (
    COMPANYFACTS_URL,
    SUBMISSIONS_URL,
    TICKERS_URL,
    SecClient,
    SecNotFoundError,
    normalize_cik,
)
from webull_lab.sec_config import SecSettings

FIXTURES = Path(__file__).parent / "fixtures" / "sec"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text="RAW-CANARY"):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}: {self.text}")


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def make_settings(tmp_path, max_attempts=3):
    return SecSettings(
        contact_email="researcher@example.com",
        cache_dir=tmp_path / "cache",
        timeout_seconds=12.5,
        max_attempts=max_attempts,
    )


def test_sec_client_constructs_requests_session_by_default(tmp_path, monkeypatch):
    expected_session = object()
    monkeypatch.setattr(sec_client_module.requests, "Session", lambda: expected_session)

    client = SecClient(make_settings(tmp_path))

    assert client.session is expected_session
    assert client.cache_hits == 0
    assert client.network_requests == 0


def test_normalize_cik_zero_pads_digits():
    assert normalize_cik(320193) == "0000320193"
    assert normalize_cik(" 320193 ") == "0000320193"


@pytest.mark.parametrize("cik", ["32A193", "１２３", "12345678901", "", "   "])
def test_normalize_cik_rejects_invalid_values(cik):
    with pytest.raises(ValueError, match="CIK"):
        normalize_cik(cik)


def test_get_json_sends_headers_and_timeout_then_reuses_written_cache(tmp_path):
    session = FakeSession(FakeResponse(payload={"ok": True}))
    client = SecClient(make_settings(tmp_path), session=session)

    first = client.get_json("https://example.test/data", "nested/data.json")
    second = client.get_json("https://example.test/data", "nested/data.json")

    assert first == second == {"ok": True}
    assert session.calls == [
        (
            "https://example.test/data",
            {
                "headers": {
                    "User-Agent": "webull-openapi-thai-lab researcher@example.com",
                    "Accept-Encoding": "gzip, deflate",
                },
                "timeout": 12.5,
            },
        )
    ]
    assert json.loads((tmp_path / "cache/nested/data.json").read_text()) == {"ok": True}
    assert client.network_requests == 1
    assert client.cache_hits == 1


def test_get_json_returns_preexisting_object_cache_without_network(tmp_path):
    cache_path = tmp_path / "cache/data.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text('{"cached": true}', encoding="utf-8")
    session = FakeSession()
    client = SecClient(make_settings(tmp_path), session=session)

    assert client.get_json("https://example.test/data", "data.json") == {"cached": True}
    assert client.cache_hits == 1
    assert client.network_requests == 0
    assert session.calls == []


def test_get_json_rejects_preexisting_non_object_cache_without_network(tmp_path):
    cache_path = tmp_path / "cache/data.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("[]", encoding="utf-8")
    session = FakeSession()
    client = SecClient(make_settings(tmp_path), session=session)

    with pytest.raises(sec_client_module.SecDataError, match="JSON object"):
        client.get_json("https://example.test/data", "data.json")

    assert client.cache_hits == 0
    assert client.network_requests == 0
    assert session.calls == []


def test_resolve_cik_normalizes_ticker_and_finds_fixture_company(tmp_path):
    companies = json.loads((FIXTURES / "company_tickers_sample.json").read_text())
    session = FakeSession(FakeResponse(payload=companies))
    client = SecClient(make_settings(tmp_path), session=session)

    assert client.resolve_cik(" aapl ") == "0000320193"
    assert session.calls[0][0] == TICKERS_URL
    assert (tmp_path / "cache/company_tickers.json").exists()


def test_resolve_cik_rejects_blank_ticker_without_network(tmp_path):
    session = FakeSession()
    client = SecClient(make_settings(tmp_path), session=session)

    with pytest.raises(SecNotFoundError, match="ticker ''"):
        client.resolve_cik("   ")

    assert session.calls == []


def test_resolve_cik_rejects_unknown_normalized_ticker(tmp_path):
    companies = json.loads((FIXTURES / "company_tickers_sample.json").read_text())
    client = SecClient(
        make_settings(tmp_path), session=FakeSession(FakeResponse(payload=companies))
    )

    with pytest.raises(SecNotFoundError, match="ticker 'NOPE'"):
        client.resolve_cik(" nope ")


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_get_json_retries_required_status_then_succeeds_with_backoff(
    tmp_path, monkeypatch, status_code
):
    sleeps = []
    monkeypatch.setattr(sec_client_module.time, "sleep", sleeps.append)
    monkeypatch.setattr(sec_client_module.random, "uniform", lambda _start, _end: 0.0)
    session = FakeSession(
        FakeResponse(status_code=status_code, payload={"error": "busy"}),
        FakeResponse(payload={"ok": True}),
    )
    client = SecClient(make_settings(tmp_path), session=session)

    assert client.get_json("https://example.test/data", "data.json") == {"ok": True}
    assert sleeps == [1.0]
    assert client.network_requests == 2


def test_get_json_respects_numeric_retry_after(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(sec_client_module.time, "sleep", sleeps.append)
    monkeypatch.setattr(sec_client_module.random, "uniform", lambda _start, _end: 0.0)
    session = FakeSession(
        FakeResponse(status_code=503, payload={}, headers={"Retry-After": "7.5"}),
        FakeResponse(payload={"ok": True}),
    )
    client = SecClient(make_settings(tmp_path), session=session)

    client.get_json("https://example.test/data", "data.json")

    assert sleeps == [7.5]


def test_get_json_exhausted_retry_raises_safe_error(tmp_path, monkeypatch):
    monkeypatch.setattr(sec_client_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(sec_client_module.random, "uniform", lambda _start, _end: 0.0)
    session = FakeSession(
        FakeResponse(status_code=500),
        FakeResponse(status_code=500),
    )
    client = SecClient(make_settings(tmp_path, max_attempts=2), session=session)

    with pytest.raises(sec_client_module.SecDataError) as error:
        client.get_json("https://example.test/data", "data.json")

    assert "RAW-CANARY" not in str(error.value)
    assert client.network_requests == 2


def test_get_json_non_retryable_http_error_is_safe(tmp_path):
    client = SecClient(
        make_settings(tmp_path), session=FakeSession(FakeResponse(status_code=404))
    )

    with pytest.raises(sec_client_module.SecDataError) as error:
        client.get_json("https://example.test/data", "data.json")

    assert "RAW-CANARY" not in str(error.value)
    assert client.network_requests == 1


@pytest.mark.parametrize("payload", [[1, 2], "text", None])
def test_get_json_rejects_non_object_json_without_caching(tmp_path, payload):
    client = SecClient(make_settings(tmp_path), session=FakeSession(FakeResponse(payload=payload)))

    with pytest.raises(sec_client_module.SecDataError, match="JSON object"):
        client.get_json("https://example.test/data", "data.json")

    assert not (tmp_path / "cache/data.json").exists()


def test_get_json_rejects_invalid_response_json_safely(tmp_path):
    client = SecClient(
        make_settings(tmp_path),
        session=FakeSession(FakeResponse(payload=ValueError("RAW-CANARY"))),
    )

    with pytest.raises(sec_client_module.SecDataError) as error:
        client.get_json("https://example.test/data", "data.json")

    assert "RAW-CANARY" not in str(error.value)
    assert "RAW-CANARY" not in "".join(traceback.format_exception(error.value))


def test_get_json_corrupt_cache_raises_without_network(tmp_path):
    cache_path = tmp_path / "cache/data.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("not-json RAW-CANARY")
    session = FakeSession(FakeResponse(payload={"should": "not fetch"}))
    client = SecClient(make_settings(tmp_path), session=session)

    with pytest.raises(sec_client_module.SecDataError) as error:
        client.get_json("https://example.test/data", "data.json")

    assert "RAW-CANARY" not in str(error.value)
    assert "RAW-CANARY" not in "".join(traceback.format_exception(error.value))
    assert session.calls == []
    assert client.network_requests == 0


def test_get_json_cache_read_exception_traceback_is_safe(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache/data.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("{}", encoding="utf-8")

    def raise_read_error(_path, **_kwargs):
        raise OSError("RAW-CANARY")

    monkeypatch.setattr(Path, "read_text", raise_read_error)
    client = SecClient(make_settings(tmp_path), session=FakeSession())

    with pytest.raises(sec_client_module.SecDataError) as error:
        client.get_json("https://example.test/data", "data.json")

    assert "RAW-CANARY" not in "".join(traceback.format_exception(error.value))
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True
    assert client.network_requests == 0


def test_get_json_request_exception_is_safe_and_counted(tmp_path):
    class RaisingSession:
        def get(self, _url, **_kwargs):
            raise requests.RequestException("RAW-CANARY")

    client = SecClient(make_settings(tmp_path), session=RaisingSession())

    with pytest.raises(sec_client_module.SecDataError) as error:
        client.get_json("https://example.test/data", "data.json")

    assert "RAW-CANARY" not in "".join(traceback.format_exception(error.value))
    assert client.network_requests == 1


def test_get_submissions_returns_valid_fixture_and_uses_normalized_cik(tmp_path):
    submissions = json.loads((FIXTURES / "aapl_submissions_sample.json").read_text())
    session = FakeSession(FakeResponse(payload=submissions))
    client = SecClient(make_settings(tmp_path), session=session)

    assert client.get_submissions(320193) == submissions
    assert session.calls[0][0] == SUBMISSIONS_URL.format(cik="0000320193")
    assert (tmp_path / "cache/0000320193-submissions.json").exists()


def test_get_submissions_rejects_missing_filings(tmp_path):
    client = SecClient(
        make_settings(tmp_path), session=FakeSession(FakeResponse(payload={"cik": "0000320193"}))
    )

    with pytest.raises(sec_client_module.SecDataError, match="submissions missing"):
        client.get_submissions("320193")


def test_get_companyfacts_accepts_facts_object(tmp_path):
    payload = {"cik": 320193, "facts": {"us-gaap": {}}}
    session = FakeSession(FakeResponse(payload=payload))
    client = SecClient(make_settings(tmp_path), session=session)

    assert client.get_companyfacts(" 320193 ") == payload
    assert session.calls[0][0] == COMPANYFACTS_URL.format(cik="0000320193")
    assert (tmp_path / "cache/0000320193-companyfacts.json").exists()


def test_get_companyfacts_rejects_missing_facts(tmp_path):
    client = SecClient(
        make_settings(tmp_path), session=FakeSession(FakeResponse(payload={"cik": 320193}))
    )

    with pytest.raises(sec_client_module.SecDataError, match="company facts missing"):
        client.get_companyfacts(320193)
