from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

STATEMENT_NAMES = ("income_statement", "balance_sheet", "cash_flow")
WEBULL_STATUSES = frozenset({"available", "unavailable"})
CACHE_STATUSES = frozenset({"hit", "miss", "unknown"})
_RAW_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


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


def _atomic_write(path: Path, writer: Callable[[Path], None]) -> None:
    temporary_path: Path | None = None
    replaced = False
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
        writer(temporary_path)
        temporary_path.replace(path)
        replaced = True
    finally:
        if temporary_path is not None and not replaced:
            temporary_path.unlink(missing_ok=True)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    _atomic_write(path, lambda temporary: temporary.write_text(serialized, encoding="utf-8"))


def _write_table(frame: pd.DataFrame, output_dir: Path, name: str) -> list[str]:
    csv_path = output_dir / f"{name}.csv"
    parquet_path = output_dir / f"{name}.parquet"
    _atomic_write(csv_path, lambda temporary: frame.to_csv(temporary, index=False))
    _atomic_write(parquet_path, lambda temporary: frame.to_parquet(temporary, index=False))
    return [csv_path.name, parquet_path.name]


def _missing_metrics(metrics: pd.DataFrame) -> list[str]:
    if metrics.empty or not {"metric", "status"}.issubset(metrics.columns):
        return []
    missing = metrics.loc[metrics["status"] != "available", "metric"].tolist()
    if any(not isinstance(metric, str) or not metric.strip() for metric in missing):
        raise ValueError("artifact metrics are invalid")
    return sorted({metric.strip() for metric in missing})


def _remove_stale_raw_json(raw_dir: Path) -> None:
    if raw_dir.is_symlink():
        raise ValueError("raw output directory is invalid")
    if not raw_dir.exists():
        return
    if not raw_dir.is_dir():
        raise ValueError("raw output directory is invalid")
    for path in raw_dir.glob("*.json"):
        path.unlink()


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
    missing_metrics = _missing_metrics(metrics)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    files: list[str] = []
    for name in STATEMENT_NAMES:
        files.extend(_write_table(statements[name], directory, name))
    files.extend(_write_table(prices, directory, "prices"))
    files.extend(_write_table(metrics, directory, "financial_metrics"))

    snapshot = {"ticker": ticker, "cik": cik, "webull_status": webull_status}
    snapshot_path = directory / "company_snapshot.json"
    _write_json(snapshot_path, snapshot)
    files.append(snapshot_path.name)

    raw_dir = directory / "raw"
    _remove_stale_raw_json(raw_dir)
    if validated_raw:
        raw_dir.mkdir(exist_ok=True)
        for name in sorted(validated_raw):
            raw_path = raw_dir / f"{name}.json"
            _write_json(raw_path, validated_raw[name])
            files.append(raw_path.relative_to(directory).as_posix())
    elif raw_dir.exists() and not any(raw_dir.iterdir()):
        raw_dir.rmdir()

    files.append("run_manifest.json")
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
        "files": sorted(files),
    }
    _write_json(directory / "run_manifest.json", manifest)
    return manifest
