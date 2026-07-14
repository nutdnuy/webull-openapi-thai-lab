from __future__ import annotations

import json
import math
import re
import tempfile
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from numbers import Integral
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from webull_lab.financials import OUTPUT_COLUMNS
from webull_lab.market_data import BAR_COLUMNS
from webull_lab.metrics import METRIC_COLUMNS

STATEMENT_NAMES = ("income_statement", "balance_sheet", "cash_flow")
WEBULL_STATUSES = frozenset({"available", "unavailable"})
CACHE_STATUSES = frozenset({"hit", "miss", "unknown"})
_RAW_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_DECIMAL_TYPE = pa.decimal256(76, 30)
_PRICE_DECIMAL_TYPE = pa.decimal128(20, 8)


def _schema(
    columns: list[str], type_overrides: Mapping[str, pa.DataType]
) -> pa.Schema:
    return pa.schema(
        [pa.field(column, type_overrides.get(column, pa.string())) for column in columns]
    )


STATEMENT_SCHEMA = _schema(
    OUTPUT_COLUMNS,
    {
        "value": _DECIMAL_TYPE,
        "start_date": pa.date32(),
        "end_date": pa.date32(),
        "fiscal_year": pa.int64(),
        "filed_date": pa.date32(),
        "derived": pa.bool_(),
    },
)
PRICE_SCHEMA = _schema(
    BAR_COLUMNS,
    {
        "date": pa.date32(),
        "open": _PRICE_DECIMAL_TYPE,
        "high": _PRICE_DECIMAL_TYPE,
        "low": _PRICE_DECIMAL_TYPE,
        "close": _PRICE_DECIMAL_TYPE,
        "volume": pa.int64(),
    },
)
METRIC_SCHEMA = _schema(
    METRIC_COLUMNS,
    {
        "value": _DECIMAL_TYPE,
        "current_period": pa.int64(),
        "comparison_period": pa.int64(),
        "available_date": pa.date32(),
        "price_date": pa.date32(),
    },
)


def _validate_inputs(
    ticker: str,
    cik: str,
    statements: Mapping[str, pd.DataFrame],
    prices: pd.DataFrame,
    metrics: pd.DataFrame,
    webull_status: str,
    years: int,
    warnings: Sequence[str] | None,
    raw_payloads: Mapping[str, Mapping[str, Any]] | None,
    cache_status: str,
) -> tuple[list[str], dict[str, Mapping[str, Any]]]:
    if (
        not isinstance(ticker, str)
        or not ticker.strip()
        or ticker != ticker.strip().upper()
    ):
        raise ValueError("ticker must be a nonblank uppercase string")
    if not isinstance(cik, str) or not cik.strip():
        raise ValueError("cik must be a nonblank string")
    if isinstance(years, bool) or not isinstance(years, int) or years <= 0:
        raise ValueError("years must be a positive integer")
    if webull_status not in WEBULL_STATUSES:
        raise ValueError("webull_status is invalid")
    if cache_status not in CACHE_STATUSES:
        raise ValueError("cache_status is invalid")
    if (
        not isinstance(statements, Mapping)
        or set(statements) != set(STATEMENT_NAMES)
        or any(not isinstance(statements[name], pd.DataFrame) for name in STATEMENT_NAMES)
        or not isinstance(prices, pd.DataFrame)
        or not isinstance(metrics, pd.DataFrame)
    ):
        raise ValueError("artifact tables are invalid")

    sanitized_warnings: list[str] = []
    if warnings is not None:
        if isinstance(warnings, str) or not isinstance(warnings, Sequence):
            raise ValueError("warnings are invalid")
        for warning in warnings:
            if not isinstance(warning, str):
                raise ValueError("warnings are invalid")
            sanitized = " ".join(warning.split())
            if sanitized and sanitized not in sanitized_warnings:
                sanitized_warnings.append(sanitized)

    validated_raw: dict[str, Mapping[str, Any]] = {}
    if raw_payloads is not None:
        if not isinstance(raw_payloads, Mapping):
            raise ValueError("raw payloads are invalid")
        for name, payload in raw_payloads.items():
            if not isinstance(name, str) or _RAW_NAME.fullmatch(name) is None:
                raise ValueError("raw payload name is invalid")
            if not isinstance(payload, Mapping):
                raise ValueError("raw payloads are invalid")
            validated_raw[name] = payload
    return sanitized_warnings, validated_raw


def _is_null(value: object) -> bool:
    return value is None or value is pd.NA or value is pd.NaT


def _as_string(value: object) -> str | None:
    if _is_null(value):
        return None
    if not isinstance(value, str):
        raise ValueError("string field is invalid")
    return value


def _as_date(value: object) -> date | None:
    if _is_null(value):
        return None
    if type(value) is date:
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError("date field is invalid")


def _as_int(value: object) -> int | None:
    if _is_null(value):
        return None
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError("integer field is invalid")
    return int(value)


def _as_bool(value: object) -> bool | None:
    if _is_null(value):
        return None
    if not isinstance(value, bool):
        raise ValueError("boolean field is invalid")
    return value


def _as_decimal(value: object) -> Decimal | None:
    if _is_null(value):
        return None
    if isinstance(value, bool) or not isinstance(value, Decimal | int | float | str):
        raise ValueError("decimal field is invalid")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("decimal field is invalid")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("decimal field is invalid") from None
    if not parsed.is_finite():
        raise ValueError("decimal field is invalid")
    return parsed


def _converter(data_type: pa.DataType):
    if pa.types.is_string(data_type):
        return _as_string
    if pa.types.is_date32(data_type):
        return _as_date
    if pa.types.is_int64(data_type):
        return _as_int
    if pa.types.is_boolean(data_type):
        return _as_bool
    if pa.types.is_decimal(data_type):
        return _as_decimal
    raise RuntimeError("unsupported artifact field type")


def _canonical_table(frame: pd.DataFrame, schema: pa.Schema, name: str) -> pa.Table:
    if not frame.columns.is_unique or not set(frame.columns).issubset(schema.names):
        raise ValueError(f"{name} table columns are invalid")
    arrays: list[pa.Array] = []
    for field in schema:
        values = frame[field.name].tolist() if field.name in frame else [None] * len(frame)
        try:
            converted = [_converter(field.type)(value) for value in values]
            arrays.append(pa.array(converted, type=field.type))
        except (ValueError, TypeError, OverflowError, pa.ArrowException):
            raise ValueError(f"{name} table field {field.name!r} is invalid") from None
    return pa.Table.from_arrays(arrays, schema=schema)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")


def _write_table(table: pa.Table, output_dir: Path, name: str) -> None:
    csv_path = output_dir / f"{name}.csv"
    parquet_path = output_dir / f"{name}.parquet"
    table.to_pandas().to_csv(csv_path, index=False)
    pq.write_table(table, parquet_path)


def _missing_metrics(metrics: pd.DataFrame) -> list[str]:
    if metrics.empty or not {"metric", "status"}.issubset(metrics.columns):
        return []
    missing = metrics.loc[metrics["status"] != "available", "metric"].tolist()
    if any(not isinstance(metric, str) or not metric.strip() for metric in missing):
        raise ValueError("artifact metrics are invalid")
    return sorted({metric.strip() for metric in missing})


def _validate_publish_destination(directory: Path) -> None:
    if directory.exists() and not directory.is_dir():
        raise ValueError("output directory is invalid")
    raw_dir = directory / "raw"
    if raw_dir.is_symlink() or (raw_dir.exists() and not raw_dir.is_dir()):
        raise ValueError("raw output directory is invalid")


def _publish_staged_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source.replace(target)


def _publish_staged_run(staging_dir: Path, directory: Path, files: list[str]) -> None:
    _validate_publish_destination(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "run_manifest.json"
    manifest_path.unlink(missing_ok=True)

    for relative in files:
        if relative == "run_manifest.json":
            continue
        _publish_staged_file(staging_dir / relative, directory / relative)

    expected_raw = {relative for relative in files if relative.startswith("raw/")}
    raw_dir = directory / "raw"
    if raw_dir.exists():
        for path in raw_dir.glob("*.json"):
            relative = path.relative_to(directory).as_posix()
            if relative not in expected_raw:
                path.unlink()
        if not any(raw_dir.iterdir()):
            raw_dir.rmdir()

    _publish_staged_file(staging_dir / "run_manifest.json", manifest_path)


def write_company_artifacts(
    output_dir: Path,
    ticker: str,
    cik: str,
    statements: dict[str, pd.DataFrame],
    prices: pd.DataFrame,
    metrics: pd.DataFrame,
    webull_status: str,
    years: int = 5,
    warnings: list[str] | None = None,
    raw_payloads: dict[str, dict[str, Any]] | None = None,
    cache_status: str = "unknown",
) -> dict[str, Any]:
    sanitized_warnings, validated_raw = _validate_inputs(
        ticker,
        cik,
        statements,
        prices,
        metrics,
        webull_status,
        years,
        warnings,
        raw_payloads,
        cache_status,
    )
    canonical_statements = {
        name: _canonical_table(statements[name], STATEMENT_SCHEMA, name)
        for name in STATEMENT_NAMES
    }
    canonical_prices = _canonical_table(prices, PRICE_SCHEMA, "prices")
    canonical_metrics = _canonical_table(metrics, METRIC_SCHEMA, "financial_metrics")
    missing_metrics = _missing_metrics(metrics)
    directory = Path(output_dir)
    directory.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(
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
            *(f"raw/{name}.json" for name in sorted(validated_raw)),
            "run_manifest.json",
        ]
    )
    manifest = {
        "ticker": ticker,
        "cik": cik,
        "run_timestamp": datetime.now(UTC).isoformat(),
        "sec_status": "available",
        "webull_status": webull_status,
        "years": years,
        "cache_status": cache_status,
        "warnings": sanitized_warnings,
        "missing_metrics": missing_metrics,
        "files": files,
    }

    with tempfile.TemporaryDirectory(
        prefix=".company-artifacts-", dir=directory.parent
    ) as temporary:
        staging_dir = Path(temporary)
        for name in STATEMENT_NAMES:
            _write_table(canonical_statements[name], staging_dir, name)
        _write_table(canonical_prices, staging_dir, "prices")
        _write_table(canonical_metrics, staging_dir, "financial_metrics")
        _write_json(
            staging_dir / "company_snapshot.json",
            {"ticker": ticker, "cik": cik, "webull_status": webull_status},
        )
        for name in sorted(validated_raw):
            _write_json(staging_dir / "raw" / f"{name}.json", validated_raw[name])
        _write_json(staging_dir / "run_manifest.json", manifest)
        _publish_staged_run(staging_dir, directory, files)
    return manifest
