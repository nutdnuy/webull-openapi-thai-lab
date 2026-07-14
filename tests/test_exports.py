import copy
import json
from datetime import date
from decimal import Decimal

import pandas as pd
import pyarrow.parquet as pq
import pytest

from webull_lab.exports import write_company_artifacts

STATEMENT_NAMES = ("income_statement", "balance_sheet", "cash_flow")


def _statements() -> dict[str, pd.DataFrame]:
    return {
        name: pd.DataFrame(
            [
                {
                    "ticker": "AAPL",
                    "value": Decimal(str(index)),
                    "filed_date": date(2025, 1, index),
                }
            ],
            dtype="object",
        )
        for index, name in enumerate(STATEMENT_NAMES, start=1)
    }


def _prices() -> pd.DataFrame:
    return pd.DataFrame(
        [{"symbol": "AAPL", "date": date(2025, 1, 2), "close": Decimal("100.25")}],
        dtype="object",
    )


def _metrics() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "metric": "net_margin",
                "value": Decimal("0.2"),
                "status": "available",
            },
            {
                "ticker": "AAPL",
                "metric": "pe",
                "value": None,
                "status": "missing_input",
            },
            {
                "ticker": "AAPL",
                "metric": "pe",
                "value": None,
                "status": "missing_input",
            },
        ],
        dtype="object",
    )


def test_write_company_artifacts_writes_exact_portable_artifact_set(tmp_path):
    manifest = write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        _statements(),
        _prices(),
        _metrics(),
        "available",
        raw_payloads={
            "sec_submissions": {"name": "Apple Inc."},
            "sec_companyfacts": {"facts": {}},
        },
    )

    expected = sorted(
        [
            *(
                f"{name}.{extension}"
                for name in STATEMENT_NAMES
                for extension in ("csv", "parquet")
            ),
            "prices.csv",
            "prices.parquet",
            "financial_metrics.csv",
            "financial_metrics.parquet",
            "company_snapshot.json",
            "raw/sec_submissions.json",
            "raw/sec_companyfacts.json",
            "run_manifest.json",
        ]
    )
    actual = sorted(
        str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_file()
    )

    assert actual == expected
    assert manifest["files"] == expected
    assert all(not path.startswith(str(tmp_path)) for path in manifest["files"])
    assert json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8")) == manifest
    assert manifest["ticker"] == "AAPL"
    assert manifest["webull_status"] == "available"
    assert manifest["sec_status"] == "available"
    assert manifest["missing_metrics"] == ["pe"]
    assert manifest["run_timestamp"].endswith("+00:00")


def test_write_company_artifacts_preserves_decimal_and_date_in_parquet_and_csv(tmp_path):
    write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        _statements(),
        _prices(),
        _metrics(),
        "available",
    )

    parquet_row = pq.read_table(tmp_path / "prices.parquet").to_pylist()[0]
    csv_text = (tmp_path / "prices.csv").read_text(encoding="utf-8")

    assert parquet_row["date"] == date(2025, 1, 2)
    assert parquet_row["close"] == Decimal("100.25")
    assert "2025-01-02" in csv_text
    assert "100.25" in csv_text


def test_write_company_artifacts_exports_empty_tables_without_crashing(tmp_path):
    empty_statements = {name: pd.DataFrame() for name in STATEMENT_NAMES}

    manifest = write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        empty_statements,
        pd.DataFrame(),
        pd.DataFrame(),
        "unavailable",
    )

    assert len(manifest["files"]) == 12
    assert pq.read_table(tmp_path / "income_statement.parquet").num_rows == 0


def test_write_company_artifacts_does_not_mutate_inputs_and_copies_warnings(tmp_path):
    statements = _statements()
    prices = _prices()
    metrics = _metrics()
    raw_payloads = {"sec_submissions": {"name": "Apple Inc."}}
    warnings = ["  SEC-only output generated.  ", "SEC-only output generated."]
    originals = (
        {name: frame.copy(deep=True) for name, frame in statements.items()},
        prices.copy(deep=True),
        metrics.copy(deep=True),
        copy.deepcopy(raw_payloads),
        warnings.copy(),
    )

    manifest = write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        statements,
        prices,
        metrics,
        "unavailable",
        warnings=warnings,
        raw_payloads=raw_payloads,
    )
    warnings.append("changed later")

    for name, frame in statements.items():
        pd.testing.assert_frame_equal(frame, originals[0][name])
    pd.testing.assert_frame_equal(prices, originals[1])
    pd.testing.assert_frame_equal(metrics, originals[2])
    assert raw_payloads == originals[3]
    assert manifest["warnings"] == ["SEC-only output generated."]


def test_repeated_run_removes_stale_raw_json_and_manifest_reference(tmp_path):
    write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        _statements(),
        _prices(),
        _metrics(),
        "available",
        raw_payloads={"old_payload": {"secret": "stale"}},
    )

    manifest = write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        _statements(),
        _prices(),
        _metrics(),
        "unavailable",
        raw_payloads={"sec_companyfacts": {"facts": {}}},
    )

    assert not (tmp_path / "raw" / "old_payload.json").exists()
    assert "raw/old_payload.json" not in manifest["files"]
    assert "stale" not in (tmp_path / "run_manifest.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("ticker", ["", "   ", "aapl", 123])
def test_write_company_artifacts_rejects_invalid_or_nonuppercase_ticker(tmp_path, ticker):
    with pytest.raises(ValueError, match="ticker must be a nonblank uppercase string"):
        write_company_artifacts(
            tmp_path,
            ticker,
            "0000320193",
            _statements(),
            _prices(),
            _metrics(),
            "available",
        )


@pytest.mark.parametrize("years", [True, 0, -1, 1.5, "5"])
def test_write_company_artifacts_rejects_invalid_years(tmp_path, years):
    with pytest.raises(ValueError, match="years must be a positive integer"):
        write_company_artifacts(
            tmp_path,
            "AAPL",
            "0000320193",
            _statements(),
            _prices(),
            _metrics(),
            "available",
            years=years,
        )


@pytest.mark.parametrize("webull_status", ["", "partial", None])
def test_write_company_artifacts_rejects_unknown_webull_status(tmp_path, webull_status):
    with pytest.raises(ValueError, match="webull_status is invalid"):
        write_company_artifacts(
            tmp_path,
            "AAPL",
            "0000320193",
            _statements(),
            _prices(),
            _metrics(),
            webull_status,
        )


@pytest.mark.parametrize(
    ("statements", "prices", "metrics"),
    [
        ([], pd.DataFrame(), pd.DataFrame()),
        ({"income_statement": pd.DataFrame()}, pd.DataFrame(), pd.DataFrame()),
        ({name: [] for name in STATEMENT_NAMES}, pd.DataFrame(), pd.DataFrame()),
        ({name: pd.DataFrame() for name in STATEMENT_NAMES}, [], pd.DataFrame()),
        ({name: pd.DataFrame() for name in STATEMENT_NAMES}, pd.DataFrame(), {}),
    ],
)
def test_write_company_artifacts_rejects_malformed_table_inputs(
    tmp_path, statements, prices, metrics
):
    with pytest.raises(ValueError, match="artifact tables are invalid"):
        write_company_artifacts(
            tmp_path,
            "AAPL",
            "0000320193",
            statements,
            prices,
            metrics,
            "available",
        )


@pytest.mark.parametrize("raw_name", ["../secret", "a/b", "/absolute", ".", "name.json"])
def test_write_company_artifacts_rejects_raw_name_path_traversal(tmp_path, raw_name):
    with pytest.raises(ValueError, match="raw payload name is invalid"):
        write_company_artifacts(
            tmp_path,
            "AAPL",
            "0000320193",
            _statements(),
            _prices(),
            _metrics(),
            "available",
            raw_payloads={raw_name: {}},
        )

    assert not (tmp_path / "run_manifest.json").exists()
