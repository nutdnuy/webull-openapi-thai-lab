from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from webull_lab.financials import build_financial_statements
from webull_lab.metrics import (
    FORMULAS,
    METRIC_COLUMNS,
    MetricResult,
    align_price_on_or_after,
    build_financial_metrics,
    growth_rate,
    safe_ratio,
)


def _fact(
    metric: str,
    value: object,
    fiscal_year: int,
    filed_date: str,
    *,
    ticker: str = "AAPL",
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "canonical_metric": metric,
        "value": value,
        "unit": "USD",
        "fiscal_year": fiscal_year,
        "period_type": "annual",
        "end_date": f"{fiscal_year}-09-30",
        "filed_date": filed_date,
    }


def test_safe_ratio_returns_available_result():
    result = safe_ratio("net_margin", Decimal("25"), Decimal("100"), date(2025, 2, 1))

    assert result == MetricResult(
        "net_margin", Decimal("0.25"), "available", date(2025, 2, 1)
    )


def test_safe_ratio_marks_zero_denominator_not_meaningful():
    result = safe_ratio("roe", Decimal("10"), Decimal("0"), date(2025, 2, 1))

    assert result.status == "not_meaningful"
    assert result.value is None


def test_ratio_and_growth_statuses_distinguish_missing_from_zero_denominator():
    available_date = date(2025, 2, 1)

    assert safe_ratio("net_margin", None, Decimal("10"), available_date).status == (
        "missing_input"
    )
    assert growth_rate("revenue_growth", Decimal("10"), None, available_date).status == (
        "missing_input"
    )
    assert growth_rate(
        "revenue_growth", Decimal("10"), Decimal("0"), available_date
    ).status == "not_meaningful"


@pytest.mark.parametrize(
    "constructor",
    [
        lambda: MetricResult("roe", Decimal("1"), "missing_input", date(2025, 1, 1)),
        lambda: MetricResult("roe", None, "available", date(2025, 1, 1)),
        lambda: MetricResult("roe", None, "unexpected", date(2025, 1, 1)),
    ],
)
def test_metric_result_rejects_inconsistent_status_semantics(constructor):
    with pytest.raises(ValueError, match="MetricResult is invalid"):
        constructor()


@pytest.mark.parametrize(
    ("numerator", "denominator"),
    [
        (Decimal("NaN"), Decimal("1")),
        (Decimal("1"), Decimal("Infinity")),
        ("secret-row-value", Decimal("1")),
        (True, Decimal("1")),
    ],
)
def test_safe_ratio_rejects_invalid_numeric_inputs_without_echoing_them(
    numerator, denominator
):
    with pytest.raises(ValueError, match="metric numeric input is invalid") as error:
        safe_ratio("roe", numerator, denominator, date(2025, 1, 1))

    assert "secret-row-value" not in str(error.value)


def test_align_price_uses_first_trading_date_on_or_after_filing():
    prices = pd.DataFrame(
        {
            "date": [date(2025, 1, 31), date(2025, 2, 3)],
            "close": [Decimal("100"), Decimal("103")],
        }
    )

    aligned = align_price_on_or_after(prices, date(2025, 2, 1))

    assert aligned["date"] == date(2025, 2, 3)
    assert aligned["close"] == Decimal("103")


def test_align_price_sorts_without_mutating_input():
    prices = pd.DataFrame(
        {
            "date": [date(2025, 2, 4), date(2025, 2, 3), date(2025, 1, 31)],
            "close": [Decimal("104"), Decimal("103"), Decimal("100")],
        }
    )
    original = prices.copy(deep=True)

    aligned = align_price_on_or_after(prices, date(2025, 2, 1))

    assert aligned.to_dict() == {"date": date(2025, 2, 3), "close": Decimal("103")}
    pd.testing.assert_frame_equal(prices, original)


@pytest.mark.parametrize(
    "prices",
    [
        pd.DataFrame({"date": [date(2025, 1, 1)]}),
        pd.DataFrame({"close": [Decimal("10")]}),
        pd.DataFrame({"date": ["2025-01-01"], "close": [Decimal("10")]}),
        pd.DataFrame({"date": [date(2025, 1, 1)], "close": [float("nan")]}),
        pd.DataFrame(
            {
                "date": [date(2025, 1, 1), date(2025, 1, 1)],
                "close": [Decimal("10"), Decimal("11")],
            }
        ),
    ],
)
def test_align_price_rejects_malformed_or_ambiguous_data(prices):
    with pytest.raises(ValueError, match="price data is invalid"):
        align_price_on_or_after(prices, date(2025, 1, 1))


def test_align_price_raises_controlled_error_when_no_price_is_eligible():
    prices = pd.DataFrame(
        {"date": [date(2025, 1, 1)], "close": [Decimal("10")]}
    )

    with pytest.raises(ValueError, match="No price on or after filing date 2025-01-02"):
        align_price_on_or_after(prices, date(2025, 1, 2))


def test_build_financial_metrics_records_formulas_and_timing():
    income = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "canonical_metric": "revenue",
                "value": 100,
                "unit": "USD",
                "fiscal_year": 2023,
                "period_type": "annual",
                "end_date": "2023-09-30",
                "filed_date": "2023-11-03",
            },
            {
                "ticker": "AAPL",
                "canonical_metric": "revenue",
                "value": 120,
                "unit": "USD",
                "fiscal_year": 2024,
                "period_type": "annual",
                "end_date": "2024-09-28",
                "filed_date": "2024-11-01",
            },
            {
                "ticker": "AAPL",
                "canonical_metric": "net_income",
                "value": 24,
                "unit": "USD",
                "fiscal_year": 2024,
                "period_type": "annual",
                "end_date": "2024-09-28",
                "filed_date": "2024-11-01",
            },
            {
                "ticker": "AAPL",
                "canonical_metric": "diluted_eps",
                "value": "6.00",
                "unit": "USD/shares",
                "fiscal_year": 2024,
                "period_type": "annual",
                "end_date": "2024-09-28",
                "filed_date": "2024-11-01",
            },
        ]
    )
    balance = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "canonical_metric": "stockholders_equity",
                "value": 50,
                "unit": "USD",
                "fiscal_year": 2023,
                "period_type": "annual",
                "end_date": "2023-09-30",
                "filed_date": "2023-11-03",
            },
            {
                "ticker": "AAPL",
                "canonical_metric": "stockholders_equity",
                "value": 70,
                "unit": "USD",
                "fiscal_year": 2024,
                "period_type": "annual",
                "end_date": "2024-09-28",
                "filed_date": "2024-11-01",
            },
        ]
    )
    prices = pd.DataFrame(
        {
            "date": [date(2024, 11, 1), date(2024, 11, 4)],
            "close": [Decimal("222"), Decimal("224")],
        }
    )

    result = build_financial_metrics(
        {
            "income_statement": income,
            "balance_sheet": balance,
            "cash_flow": pd.DataFrame(),
        },
        prices,
    ).set_index("metric")

    assert result.loc["revenue_growth", "value"] == Decimal("0.2")
    assert result.loc["net_margin", "value"] == Decimal("0.2")
    assert result.loc["roe", "value"] == Decimal("0.4")
    assert result.loc["pe", "value"] == Decimal("37")
    assert result.loc["pe", "price_date"] == "2024-11-01"
    assert result.loc["price_to_book", "status"] == "missing_input"
    assert (
        result.loc["revenue_growth", "formula"]
        == "current_revenue / prior_revenue - 1"
    )


def test_metric_schema_and_formulas_are_exactly_stable():
    assert METRIC_COLUMNS == [
        "ticker",
        "metric",
        "value",
        "status",
        "formula",
        "current_period",
        "comparison_period",
        "available_date",
        "price_date",
    ]
    assert FORMULAS == {
        "revenue_growth": "current_revenue / prior_revenue - 1",
        "diluted_eps_growth": "current_diluted_eps / prior_diluted_eps - 1",
        "gross_margin": "gross_profit / revenue",
        "operating_margin": "operating_income / revenue",
        "net_margin": "net_income / revenue",
        "roe": "net_income / average_stockholders_equity",
        "debt_to_equity": "debt / stockholders_equity",
        "operating_cash_flow_growth": (
            "current_operating_cash_flow / prior_operating_cash_flow - 1"
        ),
        "free_cash_flow": "operating_cash_flow - capital_expenditure",
        "pe": "filed_date_aligned_close / diluted_eps",
        "price_to_book": "filed_date_aligned_market_cap / stockholders_equity",
    }


def test_build_financial_metrics_calculates_all_supported_non_price_metrics():
    income = pd.DataFrame(
        [
            _fact("revenue", 100, 2023, "2023-11-01"),
            _fact("revenue", 120, 2024, "2024-11-01"),
            _fact("diluted_eps", "4", 2023, "2023-11-01"),
            _fact("diluted_eps", "6", 2024, "2024-11-01"),
            _fact("gross_profit", 48, 2024, "2024-11-01"),
            _fact("operating_income", 30, 2024, "2024-11-01"),
            _fact("net_income", 24, 2024, "2024-11-01"),
        ]
    )
    balance = pd.DataFrame(
        [
            _fact("stockholders_equity", 50, 2023, "2023-11-01"),
            _fact("stockholders_equity", 70, 2024, "2024-11-01"),
            _fact("debt", 35, 2024, "2024-11-01"),
        ]
    )
    cash_flow = pd.DataFrame(
        [
            _fact("operating_cash_flow", 40, 2023, "2023-11-01"),
            _fact("operating_cash_flow", 50, 2024, "2024-11-01"),
            _fact("capital_expenditure", 12, 2024, "2024-11-01"),
        ]
    )

    result = build_financial_metrics(
        {
            "income_statement": income,
            "balance_sheet": balance,
            "cash_flow": cash_flow,
        },
        pd.DataFrame(),
    ).set_index("metric")

    assert result["value"].to_dict() == {
        "revenue_growth": Decimal("0.2"),
        "diluted_eps_growth": Decimal("0.5"),
        "gross_margin": Decimal("0.4"),
        "operating_margin": Decimal("0.25"),
        "net_margin": Decimal("0.2"),
        "debt_to_equity": Decimal("0.5"),
        "operating_cash_flow_growth": Decimal("0.25"),
        "roe": Decimal("0.4"),
        "free_cash_flow": Decimal("38"),
        "pe": None,
        "price_to_book": None,
    }
    assert result.loc["free_cash_flow", "status"] == "available"


def test_builder_handles_missing_statement_keys_and_no_annual_input():
    result = build_financial_metrics({}, pd.DataFrame())

    assert result.empty
    assert list(result.columns) == METRIC_COLUMNS


def test_builder_returns_empty_when_only_non_income_statements_have_annual_rows():
    balance = pd.DataFrame(
        [_fact("stockholders_equity", 70, 2024, "2024-11-01")]
    )

    result = build_financial_metrics(
        {"balance_sheet": balance, "cash_flow": pd.DataFrame()}, pd.DataFrame()
    )

    assert result.empty
    assert list(result.columns) == METRIC_COLUMNS


def test_balance_year_newer_than_income_does_not_shift_metric_period():
    income = pd.DataFrame(
        [
            _fact("revenue", 100, 2023, "2023-11-01"),
            _fact("revenue", 120, 2024, "2024-11-01"),
        ]
    )
    balance = pd.DataFrame(
        [
            _fact("stockholders_equity", 70, 2024, "2024-11-01"),
            _fact("stockholders_equity", 80, 2025, "2025-11-01"),
        ]
    )

    result = build_financial_metrics(
        {"income_statement": income, "balance_sheet": balance}, pd.DataFrame()
    ).set_index("metric")

    assert result.loc["revenue_growth", "current_period"] == 2024
    assert result.loc["revenue_growth", "comparison_period"] == 2023
    assert result.loc["revenue_growth", "value"] == Decimal("0.2")


@pytest.mark.parametrize("fiscal_year", [2024.0, np.float64(2024.0), np.int64(2024)])
def test_builder_normalizes_integral_real_fiscal_years(fiscal_year):
    income = pd.DataFrame(
        [
            _fact("revenue", 100, 2023.0, "2023-11-01"),
            _fact("revenue", 120, fiscal_year, "2024-11-01"),
        ]
    )

    result = build_financial_metrics(
        {"income_statement": income}, pd.DataFrame()
    ).set_index("metric")

    assert result.loc["revenue_growth", "current_period"] == 2024
    assert result.loc["revenue_growth", "comparison_period"] == 2023
    assert result.loc["revenue_growth", "value"] == Decimal("0.2")


@pytest.mark.parametrize("fiscal_year", [True, float("nan"), float("inf"), 2024.5])
def test_builder_rejects_invalid_fiscal_years_safely(fiscal_year):
    income = pd.DataFrame(
        [_fact("revenue", 120, fiscal_year, "2024-11-01")]
    )

    with pytest.raises(ValueError, match="financial facts are invalid"):
        build_financial_metrics({"income_statement": income}, pd.DataFrame())


def test_metrics_compose_with_financial_statement_real_fiscal_years():
    def observation(value, fiscal_year, end, filed, accession):
        return {
            "start": f"{int(fiscal_year) - 1}-10-01",
            "end": end,
            "val": value,
            "accn": accession,
            "fy": fiscal_year,
            "fp": "FY",
            "form": "10-K",
            "filed": filed,
            "frame": f"CY{int(fiscal_year)}",
        }

    payload = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            observation(100, 2023.0, "2023-09-30", "2023-11-01", "a"),
                            observation(120, 2024.0, "2024-09-28", "2024-11-01", "b"),
                        ]
                    }
                }
            }
        }
    }
    statements = build_financial_statements("AAPL", "320193", payload)

    result = build_financial_metrics(statements, pd.DataFrame()).set_index("metric")

    assert result.loc["revenue_growth", "value"] == Decimal("0.2")
    assert result.loc["revenue_growth", "current_period"] == 2024


def test_builder_rejects_mixed_statement_tickers():
    income = pd.DataFrame(
        [
            _fact("revenue", 100, 2023, "2023-11-01"),
            _fact("revenue", 120, 2024, "2024-11-01", ticker="MSFT"),
        ]
    )

    with pytest.raises(ValueError, match="financial statements contain mixed tickers"):
        build_financial_metrics({"income_statement": income}, pd.DataFrame())


def test_builder_rejects_ambiguous_duplicate_facts():
    income = pd.DataFrame(
        [
            _fact("revenue", 120, 2024, "2024-11-01"),
            _fact("revenue", 121, 2024, "2024-11-01"),
        ]
    )

    with pytest.raises(ValueError, match="financial facts are ambiguous"):
        build_financial_metrics({"income_statement": income}, pd.DataFrame())


def test_metric_timing_ignores_irrelevant_and_future_filed_facts():
    income = pd.DataFrame(
        [
            _fact("revenue", 100, 2023, "2023-11-01"),
            _fact("revenue", 80, 2023, "2024-12-01"),
            _fact("revenue", 120, 2024, "2024-11-01"),
            _fact("gross_profit", 60, 2024, "2024-12-15"),
        ]
    )

    result = build_financial_metrics(
        {"income_statement": income}, pd.DataFrame()
    ).set_index("metric")

    assert result.loc["revenue_growth", "value"] == Decimal("0.2")
    assert result.loc["revenue_growth", "available_date"] == "2024-11-01"


def test_pe_uses_latest_eps_filing_and_matching_ticker_price():
    income = pd.DataFrame(
        [
            _fact("revenue", 100, 2023, "2023-11-01"),
            _fact("revenue", 120, 2024, "2024-11-01"),
            _fact("diluted_eps", 6, 2024, "2024-11-01"),
            _fact("diluted_eps", 5, 2024, "2024-11-15"),
        ]
    )
    prices = pd.DataFrame(
        {
            "symbol": ["MSFT", "AAPL", "AAPL"],
            "date": [date(2024, 11, 15), date(2024, 11, 1), date(2024, 11, 15)],
            "close": [Decimal("500"), Decimal("222"), Decimal("200")],
        }
    )

    pe = build_financial_metrics(
        {"income_statement": income}, prices
    ).set_index("metric").loc["pe"]

    assert pe["value"] == Decimal("40")
    assert pe["available_date"] == "2024-11-15"
    assert pe["price_date"] == "2024-11-15"


def test_pe_is_missing_without_eps_even_if_prices_end_before_filing():
    income = pd.DataFrame(
        [
            _fact("revenue", 100, 2023, "2023-11-01"),
            _fact("revenue", 120, 2024, "2024-11-01"),
        ]
    )
    prices = pd.DataFrame(
        {"date": [date(2024, 10, 31)], "close": [Decimal("220")]}
    )

    pe = build_financial_metrics(
        {"income_statement": income}, prices
    ).set_index("metric").loc["pe"]

    assert pe["status"] == "missing_input"
    assert pe["price_date"] is None
