import copy
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from webull_lab.exports import write_company_artifacts, write_json_atomic
from webull_lab.financials import OUTPUT_COLUMNS, build_financial_statements
from webull_lab.market_data import BAR_COLUMNS, normalize_stock_bars
from webull_lab.metrics import METRIC_COLUMNS, build_financial_metrics

STATEMENT_NAMES = ("income_statement", "balance_sheet", "cash_flow")
FIXTURE_ROOT = Path("tests/fixtures")
DECIMAL_SCHEMA = pa.decimal256(76, 30)
STATEMENT_SCHEMA = pa.schema(
    [
        pa.field("ticker", pa.string()),
        pa.field("cik", pa.string()),
        pa.field("statement", pa.string()),
        pa.field("canonical_metric", pa.string()),
        pa.field("source_taxonomy", pa.string()),
        pa.field("source_tag", pa.string()),
        pa.field("value", DECIMAL_SCHEMA),
        pa.field("unit", pa.string()),
        pa.field("start_date", pa.date32()),
        pa.field("end_date", pa.date32()),
        pa.field("form", pa.string()),
        pa.field("fiscal_year", pa.int64()),
        pa.field("fiscal_period", pa.string()),
        pa.field("filed_date", pa.date32()),
        pa.field("frame", pa.string()),
        pa.field("accession_number", pa.string()),
        pa.field("period_type", pa.string()),
        pa.field("derived", pa.bool_()),
        pa.field("superseded_accessions", pa.string()),
    ]
)
PRICE_SCHEMA = pa.schema(
    [
        pa.field("symbol", pa.string()),
        pa.field("date", pa.date32()),
        pa.field("open", pa.decimal128(20, 8)),
        pa.field("high", pa.decimal128(20, 8)),
        pa.field("low", pa.decimal128(20, 8)),
        pa.field("close", pa.decimal128(20, 8)),
        pa.field("volume", pa.int64()),
    ]
)
METRIC_SCHEMA = pa.schema(
    [
        pa.field("ticker", pa.string()),
        pa.field("metric", pa.string()),
        pa.field("value", DECIMAL_SCHEMA),
        pa.field("status", pa.string()),
        pa.field("formula", pa.string()),
        pa.field("current_period", pa.int64()),
        pa.field("comparison_period", pa.int64()),
        pa.field("available_date", pa.date32()),
        pa.field("price_date", pa.date32()),
    ]
)


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
    price_history = {
        "status": "partial",
        "requested_start_date": "2020-01-02",
        "requested_end_date": "2025-01-02",
        "observed_start_date": "2025-01-02",
        "observed_end_date": "2025-01-02",
        "observed_bar_count": 1,
        "pages_requested": 1,
        "pagination_complete": True,
    }
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
        price_history=price_history,
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
    assert manifest["price_history"] == price_history


def test_write_company_artifacts_rejects_price_history_that_disagrees_with_prices(
    tmp_path,
):
    with pytest.raises(ValueError, match="price history metadata is invalid"):
        write_company_artifacts(
            tmp_path,
            "AAPL",
            "0000320193",
            _statements(),
            _prices(),
            _metrics(),
            "available",
            price_history={
                "status": "partial",
                "requested_start_date": "2020-01-02",
                "requested_end_date": "2025-01-02",
                "observed_start_date": "2024-01-02",
                "observed_end_date": "2025-01-02",
                "observed_bar_count": 252,
                "pages_requested": 1,
                "pagination_complete": True,
            },
        )


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
    assert list(pd.read_csv(tmp_path / "income_statement.csv").columns) == OUTPUT_COLUMNS
    assert list(pd.read_csv(tmp_path / "prices.csv").columns) == BAR_COLUMNS
    assert list(pd.read_csv(tmp_path / "financial_metrics.csv").columns) == METRIC_COLUMNS
    assert pq.read_schema(tmp_path / "income_statement.parquet").remove_metadata() == (
        STATEMENT_SCHEMA
    )
    assert pq.read_schema(tmp_path / "prices.parquet").remove_metadata() == PRICE_SCHEMA
    assert pq.read_schema(tmp_path / "financial_metrics.parquet").remove_metadata() == (
        METRIC_SCHEMA
    )


def test_empty_and_minimal_tables_export_canonical_csv_headers_and_parquet_schemas(
    tmp_path,
):
    write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        _statements(),
        _prices(),
        _metrics(),
        "available",
    )

    assert list(pd.read_csv(tmp_path / "income_statement.csv").columns) == OUTPUT_COLUMNS
    assert list(pd.read_csv(tmp_path / "prices.csv").columns) == BAR_COLUMNS
    assert list(pd.read_csv(tmp_path / "financial_metrics.csv").columns) == METRIC_COLUMNS
    assert pq.read_schema(tmp_path / "income_statement.parquet").remove_metadata() == (
        STATEMENT_SCHEMA
    )
    assert pq.read_schema(tmp_path / "prices.parquet").remove_metadata() == PRICE_SCHEMA
    assert pq.read_schema(tmp_path / "financial_metrics.parquet").remove_metadata() == (
        METRIC_SCHEMA
    )

    empty_dir = tmp_path / "empty"
    write_company_artifacts(
        empty_dir,
        "AAPL",
        "0000320193",
        {name: pd.DataFrame(columns=OUTPUT_COLUMNS, dtype="object") for name in STATEMENT_NAMES},
        normalize_stock_bars([]),
        pd.DataFrame(columns=METRIC_COLUMNS, dtype="object"),
        "unavailable",
    )

    assert pq.read_schema(empty_dir / "income_statement.parquet").remove_metadata() == (
        STATEMENT_SCHEMA
    )
    assert pq.read_schema(empty_dir / "prices.parquet").remove_metadata() == PRICE_SCHEMA
    assert pq.read_schema(empty_dir / "financial_metrics.parquet").remove_metadata() == (
        METRIC_SCHEMA
    )


def test_real_financial_metric_and_price_outputs_use_canonical_export_schemas(tmp_path):
    companyfacts = json.loads(
        (FIXTURE_ROOT / "sec" / "aapl_companyfacts_sample.json").read_text()
    )
    bar_payload = json.loads(
        (FIXTURE_ROOT / "webull" / "aapl_daily_bars_sample.json").read_text()
    )
    statements = build_financial_statements("AAPL", "320193", companyfacts, years=5)
    prices = normalize_stock_bars(bar_payload)
    metrics = build_financial_metrics(statements, prices)

    write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        statements,
        prices,
        metrics,
        "available",
    )

    for name in STATEMENT_NAMES:
        assert pq.read_schema(tmp_path / f"{name}.parquet").remove_metadata() == (
            STATEMENT_SCHEMA
        )
    assert pq.read_schema(tmp_path / "prices.parquet").remove_metadata() == PRICE_SCHEMA
    assert pq.read_schema(tmp_path / "financial_metrics.parquet").remove_metadata() == (
        METRIC_SCHEMA
    )


def test_companyfacts_float_fiscal_year_exports_end_to_end(tmp_path):
    companyfacts = {
        "cik": 320193,
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "val": 100,
                                "start": "2022-10-01",
                                "end": "2023-09-30",
                                "accn": "0000320193-23-000106",
                                "fy": 2023.0,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                                "frame": "CY2023",
                            }
                        ]
                    }
                }
            }
        },
    }
    statements = build_financial_statements("AAPL", "320193", companyfacts)

    write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        statements,
        pd.DataFrame(),
        pd.DataFrame(),
        "unavailable",
    )

    assert pq.read_table(tmp_path / "income_statement.parquet")["fiscal_year"].to_pylist() == [
        2023
    ]


def test_numpy_integral_float_fiscal_year_exports_as_int64(tmp_path):
    statements = _statements()
    statements["income_statement"]["fiscal_year"] = np.float64(2023.0)

    write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        statements,
        pd.DataFrame(),
        pd.DataFrame(),
        "unavailable",
    )

    assert pq.read_table(tmp_path / "income_statement.parquet")["fiscal_year"].to_pylist() == [
        2023
    ]


@pytest.mark.parametrize(
    "fiscal_year",
    [True, 2023.5, np.float64("nan"), np.float64("inf"), 2**63],
)
def test_invalid_or_out_of_range_fiscal_year_is_rejected(tmp_path, fiscal_year):
    statements = _statements()
    statements["income_statement"]["fiscal_year"] = fiscal_year

    with pytest.raises(ValueError, match="field 'fiscal_year' is invalid"):
        write_company_artifacts(
            tmp_path,
            "AAPL",
            "0000320193",
            statements,
            pd.DataFrame(),
            pd.DataFrame(),
            "unavailable",
        )

    assert not (tmp_path / "run_manifest.json").exists()


def test_optional_numpy_nan_cells_export_as_null_without_mutating_frame(tmp_path):
    statements = _statements()
    income = statements["income_statement"]
    income["start_date"] = np.nan
    income["end_date"] = np.nan
    income["frame"] = np.nan
    original = income.copy(deep=True)

    write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        statements,
        pd.DataFrame(),
        pd.DataFrame(),
        "unavailable",
    )

    row = pq.read_table(tmp_path / "income_statement.parquet").to_pylist()[0]
    assert row["start_date"] is None
    assert row["end_date"] is None
    assert row["frame"] is None
    pd.testing.assert_frame_equal(income, original)


def test_nonscalar_optional_cell_rejects_safely(tmp_path):
    statements = _statements()
    statements["income_statement"]["frame"] = [["secret-nonscalar"]]

    with pytest.raises(ValueError) as error:
        write_company_artifacts(
            tmp_path,
            "AAPL",
            "0000320193",
            statements,
            pd.DataFrame(),
            pd.DataFrame(),
            "unavailable",
        )

    assert "secret-nonscalar" not in str(error.value)
    assert not (tmp_path / "run_manifest.json").exists()


def test_nonfinite_statement_value_is_rejected_instead_of_exported_as_null(tmp_path):
    statements = _statements()
    statements["income_statement"]["value"] = np.nan

    with pytest.raises(ValueError, match="field 'value' is invalid"):
        write_company_artifacts(
            tmp_path,
            "AAPL",
            "0000320193",
            statements,
            pd.DataFrame(),
            pd.DataFrame(),
            "unavailable",
        )

    assert not (tmp_path / "run_manifest.json").exists()


def test_staging_failure_leaves_previous_run_artifacts_untouched(tmp_path):
    write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        _statements(),
        _prices(),
        _metrics(),
        "available",
        raw_payloads={"sec_companyfacts": {"facts": {}}},
    )
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    with pytest.raises(TypeError):
        write_company_artifacts(
            tmp_path,
            "MSFT",
            "0000789019",
            _statements(),
            _prices(),
            _metrics(),
            "available",
            raw_payloads={"bad_payload": {"not_json": {1, 2}}},
        )

    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert json.loads((tmp_path / "run_manifest.json").read_text())["ticker"] == "AAPL"


def test_publish_failure_invalidates_manifest(tmp_path, monkeypatch):
    write_company_artifacts(
        tmp_path,
        "AAPL",
        "0000320193",
        _statements(),
        _prices(),
        _metrics(),
        "available",
    )
    publish_calls = 0

    def fail_during_publish(source, target):
        nonlocal publish_calls
        publish_calls += 1
        if publish_calls == 2:
            raise OSError("simulated publish failure")
        source.replace(target)

    monkeypatch.setattr(
        "webull_lab.exports._publish_staged_file", fail_during_publish, raising=False
    )

    with pytest.raises(OSError, match="simulated publish failure"):
        write_company_artifacts(
            tmp_path,
            "MSFT",
            "0000789019",
            _statements(),
            _prices(),
            _metrics(),
            "available",
        )

    assert not (tmp_path / "run_manifest.json").exists()


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


def test_atomic_json_update_preserves_old_file_and_cleans_temp_on_replace_failure(
    tmp_path, monkeypatch
):
    manifest_path = tmp_path / "run_manifest.json"
    original = '{"status":"old"}\n'
    manifest_path.write_text(original, encoding="utf-8")
    original_replace = Path.replace

    def fail_manifest_replace(source, target):
        if Path(target) == manifest_path:
            raise OSError("injected atomic replace failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_manifest_replace)

    with pytest.raises(OSError, match="injected atomic replace failure"):
        write_json_atomic(manifest_path, {"status": "new"})

    assert manifest_path.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".run_manifest.json.*.tmp")) == []
