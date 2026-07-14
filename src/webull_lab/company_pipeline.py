from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from webull_lab.account import ResponseError
from webull_lab.exports import STATEMENT_NAMES, write_company_artifacts
from webull_lab.financials import build_financial_statements
from webull_lab.market_data import get_daily_stock_bars, normalize_stock_bars
from webull_lab.metrics import build_financial_metrics

SAFE_WEBULL_WARNING = (
    "Webull market data unavailable; SEC financial outputs were still generated."
)


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
    cik = sec_client.resolve_cik(symbol)
    submissions = sec_client.get_submissions(cik)
    companyfacts = sec_client.get_companyfacts(cik)
    statements = build_financial_statements(symbol, cik, companyfacts, years=years)
    _validate_statements(statements)

    warnings: list[str] = []
    prices = normalize_stock_bars([])
    webull_status = "unavailable"
    if data_client is not None:
        try:
            prices = normalize_stock_bars(get_daily_stock_bars(data_client, symbol))
            webull_status = "available"
        except (ResponseError, RuntimeError, ValueError):
            warnings.append(SAFE_WEBULL_WARNING)

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
        cache_status="hit" if getattr(sec_client, "cache_hits", 0) else "miss",
    )
