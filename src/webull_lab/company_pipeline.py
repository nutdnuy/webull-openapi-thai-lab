from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd
from webull.core.exception.exceptions import ClientException, ServerException

from webull_lab.account import ResponseError
from webull_lab.exports import STATEMENT_NAMES, write_company_artifacts
from webull_lab.financials import build_financial_statements
from webull_lab.market_data import get_daily_stock_bars, normalize_stock_bars
from webull_lab.metrics import build_financial_metrics

SAFE_WEBULL_WARNING = (
    "Webull market data unavailable; SEC financial outputs were still generated."
)


def _cache_hits(client: Any) -> int | None:
    value = getattr(client, "cache_hits", None)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _validate_statements(statements: object) -> None:
    if (
        not isinstance(statements, Mapping)
        or set(statements) != set(STATEMENT_NAMES)
        or any(not isinstance(statements[name], pd.DataFrame) for name in STATEMENT_NAMES)
    ):
        raise ValueError("artifact tables are invalid")


def run_company_pipeline(
    ticker: str,
    years: int,
    output_dir: Path,
    sec_client: Any,
    data_client: Any | None,
) -> dict[str, Any]:
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("ticker must be a nonblank string")
    if isinstance(years, bool) or not isinstance(years, int) or years <= 0:
        raise ValueError("years must be a positive integer")

    symbol = ticker.strip().upper()
    cache_hits_before = _cache_hits(sec_client)
    cik = sec_client.resolve_cik(symbol)
    submissions = sec_client.get_submissions(cik)
    companyfacts = sec_client.get_companyfacts(cik)
    cache_hits_after = _cache_hits(sec_client)
    cache_status = (
        "unknown"
        if cache_hits_before is None or cache_hits_after is None
        else "hit"
        if cache_hits_after > cache_hits_before
        else "miss"
    )
    statements = build_financial_statements(symbol, cik, companyfacts, years=years)
    _validate_statements(statements)

    warnings: list[str] = []
    prices = normalize_stock_bars([])
    webull_status = "unavailable"
    if data_client is not None:
        try:
            payload = get_daily_stock_bars(data_client, symbol)
        except (ResponseError, ClientException, ServerException, RuntimeError, ValueError):
            warnings.append(SAFE_WEBULL_WARNING)
        else:
            try:
                prices = normalize_stock_bars(payload)
            except ValueError:
                warnings.append(SAFE_WEBULL_WARNING)
            else:
                webull_status = "available"

    metrics = build_financial_metrics(statements, prices)
    return write_company_artifacts(
        output_dir,
        symbol,
        cik,
        statements,
        prices,
        metrics,
        webull_status,
        years=years,
        warnings=warnings,
        raw_payloads={
            "sec_submissions": submissions,
            "sec_companyfacts": companyfacts,
        },
        cache_status=cache_status,
    )
