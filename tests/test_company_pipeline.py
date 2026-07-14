import copy
import json
from decimal import Decimal

import pandas as pd
import pytest
from webull.core.exception.exceptions import ClientException, ServerException

from webull_lab.company_pipeline import run_company_pipeline
from webull_lab.financials import OUTPUT_COLUMNS
from webull_lab.sec_client import SecDataError

STATEMENT_NAMES = ("income_statement", "balance_sheet", "cash_flow")
SAFE_WEBULL_WARNING = (
    "Webull market data unavailable; SEC financial outputs were still generated."
)


class FakeSecClient:
    def __init__(self, *, cache_hits=0, cache_hit_increment=0):
        self.cache_hits = cache_hits
        self.cache_hit_increment = cache_hit_increment
        self.calls = []
        self.submissions = {"name": "Apple Inc.", "filings": {}}
        self.companyfacts = {"cik": 320193, "facts": {"us-gaap": {}}}

    def resolve_cik(self, ticker):
        self.calls.append(("resolve_cik", ticker))
        return "0000320193"

    def get_submissions(self, cik):
        self.calls.append(("get_submissions", cik))
        return self.submissions

    def get_companyfacts(self, cik):
        self.calls.append(("get_companyfacts", cik))
        if hasattr(self, "cache_hits"):
            self.cache_hits += self.cache_hit_increment
        return self.companyfacts


def _empty_statements():
    return {name: pd.DataFrame(columns=OUTPUT_COLUMNS) for name in STATEMENT_NAMES}


def test_pipeline_completes_sec_only_when_webull_is_absent(tmp_path):
    sec_client = FakeSecClient()

    result = run_company_pipeline(" aapl ", 5, tmp_path, sec_client, data_client=None)

    assert result["ticker"] == "AAPL"
    assert result["webull_status"] == "unavailable"
    assert result["warnings"] == []
    assert result["cache_status"] == "miss"
    assert sec_client.calls == [
        ("resolve_cik", "AAPL"),
        ("get_submissions", "0000320193"),
        ("get_companyfacts", "0000320193"),
    ]
    assert (tmp_path / "run_manifest.json").exists()
    assert (tmp_path / "raw" / "sec_submissions.json").exists()
    assert (tmp_path / "raw" / "sec_companyfacts.json").exists()


def test_pipeline_successfully_normalizes_webull_bars_and_computes_metrics(
    tmp_path, monkeypatch
):
    sec_client = FakeSecClient(cache_hits=2, cache_hit_increment=1)
    raw_bars = [
        {
            "symbol": "AAPL",
            "time": "1730419200000",
            "open": "220.97",
            "high": "225.35",
            "low": "220.27",
            "close": "222.91",
            "volume": "65276700",
        }
    ]
    captured = {}
    monkeypatch.setattr(
        "webull_lab.company_pipeline.get_daily_stock_bars",
        lambda client, symbol: raw_bars,
    )

    def fake_metrics(statements, prices):
        captured["statements"] = statements
        captured["prices"] = prices.copy(deep=True)
        return pd.DataFrame(
            [{"ticker": "AAPL", "metric": "pe", "status": "available", "value": 1}]
        )

    monkeypatch.setattr("webull_lab.company_pipeline.build_financial_metrics", fake_metrics)

    result = run_company_pipeline("AAPL", 3, tmp_path, sec_client, data_client=object())

    assert result["webull_status"] == "available"
    assert result["cache_status"] == "hit"
    assert captured["prices"].loc[0, "close"] == Decimal("222.91")
    assert captured["statements"].keys() == set(STATEMENT_NAMES)
    assert json.loads((tmp_path / "run_manifest.json").read_text())["years"] == 3


def test_pipeline_ignores_stale_cache_hits_from_prior_runs(tmp_path):
    result = run_company_pipeline(
        "AAPL", 5, tmp_path, FakeSecClient(cache_hits=4), data_client=None
    )

    assert result["cache_status"] == "miss"


def test_pipeline_reports_unknown_cache_status_without_valid_client_signal(tmp_path):
    client = FakeSecClient()
    del client.cache_hits

    result = run_company_pipeline("AAPL", 5, tmp_path, client, data_client=None)

    assert result["cache_status"] == "unknown"


@pytest.mark.parametrize("exception_type", [RuntimeError, ValueError])
def test_pipeline_turns_expected_webull_failure_into_safe_partial_result(
    tmp_path, monkeypatch, exception_type
):
    secret = "WEBULL_APP_SECRET=do-not-leak-this"
    monkeypatch.setattr(
        "webull_lab.company_pipeline.get_daily_stock_bars",
        lambda *args: (_ for _ in ()).throw(exception_type(secret)),
    )

    result = run_company_pipeline("AAPL", 5, tmp_path, FakeSecClient(), data_client=object())

    assert result["webull_status"] == "unavailable"
    assert result["warnings"] == [SAFE_WEBULL_WARNING]
    assert secret not in str(result)
    assert secret not in (tmp_path / "run_manifest.json").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "sdk_error",
    [
        ClientException("SDK_HTTP_ERROR", "WEBULL_MARKER_SECRET"),
        ServerException("SERVER_ERROR", "WEBULL_MARKER_SECRET", 500, "request-id"),
    ],
)
def test_pipeline_turns_sdk_fetch_failure_into_safe_partial_result(
    tmp_path, monkeypatch, capsys, sdk_error
):
    marker = "WEBULL_MARKER_SECRET"
    monkeypatch.setattr(
        "webull_lab.company_pipeline.get_daily_stock_bars",
        lambda *args: (_ for _ in ()).throw(sdk_error),
    )

    result = run_company_pipeline("AAPL", 5, tmp_path, FakeSecClient(), data_client=object())

    captured = capsys.readouterr()
    manifest_text = (tmp_path / "run_manifest.json").read_text(encoding="utf-8")
    assert result["webull_status"] == "unavailable"
    assert result["warnings"] == [SAFE_WEBULL_WARNING]
    assert marker not in str(result)
    assert marker not in manifest_text
    assert marker not in captured.out
    assert marker not in captured.err


def test_pipeline_does_not_catch_sdk_exception_from_normalization(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "webull_lab.company_pipeline.get_daily_stock_bars", lambda *args: [{"raw": "bar"}]
    )

    def fail_normalization(payload):
        if payload:
            raise ServerException("NORMALIZER_BUG", "not a fetch failure")
        return pd.DataFrame()

    monkeypatch.setattr("webull_lab.company_pipeline.normalize_stock_bars", fail_normalization)

    with pytest.raises(ServerException):
        run_company_pipeline("AAPL", 5, tmp_path, FakeSecClient(), data_client=object())

    assert not (tmp_path / "run_manifest.json").exists()


def test_pipeline_turns_malformed_webull_payload_into_safe_partial_result(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "webull_lab.company_pipeline.get_daily_stock_bars", lambda *args: {"bad": "shape"}
    )

    result = run_company_pipeline("AAPL", 5, tmp_path, FakeSecClient(), data_client=object())

    assert result["webull_status"] == "unavailable"
    assert result["warnings"] == [SAFE_WEBULL_WARNING]


def test_pipeline_propagates_unexpected_runtime_error_from_normalization(
    tmp_path, monkeypatch
):
    calls = 0

    def fail_on_fetched_payload(payload):
        nonlocal calls
        calls += 1
        if calls == 1:
            return pd.DataFrame()
        raise RuntimeError("normalizer bug")

    monkeypatch.setattr(
        "webull_lab.company_pipeline.get_daily_stock_bars", lambda *args: [{"raw": "bar"}]
    )
    monkeypatch.setattr(
        "webull_lab.company_pipeline.normalize_stock_bars",
        fail_on_fetched_payload,
    )

    with pytest.raises(RuntimeError, match="normalizer bug"):
        run_company_pipeline("AAPL", 5, tmp_path, FakeSecClient(), data_client=object())

    assert not (tmp_path / "run_manifest.json").exists()


def test_pipeline_propagates_sec_failure_without_writing_manifest(tmp_path):
    class FailingSecClient(FakeSecClient):
        def get_companyfacts(self, cik):
            raise SecDataError("SEC unavailable")

    with pytest.raises(SecDataError, match="SEC unavailable"):
        run_company_pipeline("AAPL", 5, tmp_path, FailingSecClient(), data_client=None)

    assert not (tmp_path / "run_manifest.json").exists()


def test_pipeline_propagates_unexpected_webull_programming_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "webull_lab.company_pipeline.get_daily_stock_bars",
        lambda *args: (_ for _ in ()).throw(TypeError("programming bug")),
    )

    with pytest.raises(TypeError, match="programming bug"):
        run_company_pipeline("AAPL", 5, tmp_path, FakeSecClient(), data_client=object())

    assert not (tmp_path / "run_manifest.json").exists()


def test_pipeline_does_not_mutate_sec_payloads(tmp_path):
    client = FakeSecClient()
    original_submissions = copy.deepcopy(client.submissions)
    original_companyfacts = copy.deepcopy(client.companyfacts)

    run_company_pipeline("AAPL", 5, tmp_path, client, data_client=None)

    assert client.submissions == original_submissions
    assert client.companyfacts == original_companyfacts


@pytest.mark.parametrize("ticker", [None, "", "   ", 123])
def test_pipeline_rejects_invalid_ticker_before_calling_sec(tmp_path, ticker):
    client = FakeSecClient()

    with pytest.raises(ValueError, match="ticker must be a nonblank string"):
        run_company_pipeline(ticker, 5, tmp_path, client, data_client=None)

    assert client.calls == []


@pytest.mark.parametrize("years", [True, 0, -1, 1.5, "5", None])
def test_pipeline_rejects_nonpositive_or_noninteger_years_before_calling_sec(
    tmp_path, years
):
    client = FakeSecClient()

    with pytest.raises(ValueError, match="years must be a positive integer"):
        run_company_pipeline("AAPL", years, tmp_path, client, data_client=None)

    assert client.calls == []


def test_pipeline_validates_generated_statement_mapping_before_artifact_writes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "webull_lab.company_pipeline.build_financial_statements", lambda *args, **kwargs: []
    )

    with pytest.raises(ValueError, match="artifact tables are invalid"):
        run_company_pipeline("AAPL", 5, tmp_path, FakeSecClient(), data_client=None)

    assert not (tmp_path / "run_manifest.json").exists()
