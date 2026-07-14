from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from math import isfinite
from numbers import Integral, Real

import pandas as pd

METRIC_COLUMNS = [
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

FORMULAS = {
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

_STATEMENT_KEYS = ("income_statement", "balance_sheet", "cash_flow")
_FACT_COLUMNS = {
    "ticker",
    "canonical_metric",
    "value",
    "fiscal_year",
    "period_type",
    "filed_date",
    "unit",
}
_STATUSES = {"available", "missing_input", "not_meaningful", "incompatible_unit"}
# SEC Company Facts normalizes diluted EPS to this canonical USD-per-share unit.
_SEC_USD_PER_SHARE_UNITS = frozenset({"USD/shares"})


class _NoEligiblePriceError(ValueError):
    pass


@dataclass(frozen=True)
class MetricResult:
    metric: str
    value: Decimal | None
    status: str
    available_date: date

    def __post_init__(self) -> None:
        valid_value = (
            isinstance(self.value, Decimal)
            and self.value.is_finite()
            and self.status == "available"
        )
        valid_missing = self.value is None and self.status in {
            "missing_input",
            "not_meaningful",
            "incompatible_unit",
        }
        if (
            not isinstance(self.metric, str)
            or not self.metric.strip()
            or self.status not in _STATUSES
            or not isinstance(self.available_date, date)
            or not (valid_value or valid_missing)
        ):
            raise ValueError("MetricResult is invalid")


@dataclass(frozen=True)
class _Fact:
    value: Decimal
    filed_date: date
    unit: str


def _validate_decimal_input(value: Decimal | None) -> None:
    if value is not None and (
        not isinstance(value, Decimal) or not value.is_finite()
    ):
        raise ValueError("metric numeric input is invalid")


def safe_ratio(
    metric: str,
    numerator: Decimal | None,
    denominator: Decimal | None,
    available_date: date,
) -> MetricResult:
    _validate_decimal_input(numerator)
    _validate_decimal_input(denominator)
    if numerator is None or denominator is None:
        return MetricResult(metric, None, "missing_input", available_date)
    if denominator == 0:
        return MetricResult(metric, None, "not_meaningful", available_date)
    return MetricResult(metric, numerator / denominator, "available", available_date)


def growth_rate(
    metric: str,
    current: Decimal | None,
    previous: Decimal | None,
    available_date: date,
) -> MetricResult:
    _validate_decimal_input(current)
    _validate_decimal_input(previous)
    if current is None or previous is None:
        return MetricResult(metric, None, "missing_input", available_date)
    if previous == 0:
        return MetricResult(metric, None, "not_meaningful", available_date)
    return MetricResult(
        metric, current / previous - Decimal("1"), "available", available_date
    )


def align_price_on_or_after(prices: pd.DataFrame, filed_date: date) -> pd.Series:
    if (
        not isinstance(prices, pd.DataFrame)
        or not isinstance(filed_date, date)
        or not {"date", "close"}.issubset(prices.columns)
    ):
        raise ValueError("price data is invalid")
    dates = prices["date"].tolist()
    closes = prices["close"].tolist()
    if (
        any(type(item) is not date for item in dates)
        or any(
            not isinstance(item, Decimal) or not item.is_finite() or item < 0
            for item in closes
        )
        or prices["date"].duplicated().any()
    ):
        raise ValueError("price data is invalid")

    eligible = prices.loc[prices["date"] >= filed_date].sort_values(
        "date", kind="stable"
    )
    if eligible.empty:
        raise _NoEligiblePriceError(
            f"No price on or after filing date {filed_date.isoformat()}"
        )
    return eligible.iloc[0].copy(deep=True)


def _parse_date(value: object) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError("financial facts are invalid")


def _parse_decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int | float | str):
        raise ValueError("financial facts are invalid")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("financial facts are invalid") from None
    if not parsed.is_finite():
        raise ValueError("financial facts are invalid")
    return parsed


def _parse_fiscal_year(value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or (not isinstance(value, Integral) and not isfinite(value))
    ):
        raise ValueError("financial facts are invalid")
    normalized = int(value)
    if value != normalized:
        raise ValueError("financial facts are invalid")
    return normalized


def _validated_annual_frames(
    statements: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    if not isinstance(statements, dict):
        raise ValueError("financial statements are invalid")
    annual_frames: dict[str, pd.DataFrame] = {}
    for key in _STATEMENT_KEYS:
        frame = statements.get(key, pd.DataFrame())
        if not isinstance(frame, pd.DataFrame):
            raise ValueError("financial statements are invalid")
        if frame.empty:
            annual_frames[key] = pd.DataFrame()
            continue
        if not _FACT_COLUMNS.issubset(frame.columns):
            raise ValueError("financial statements are invalid")
        annual = frame.loc[frame["period_type"] == "annual"].copy(deep=True)
        fiscal_years: list[int] = []
        for row in annual.to_dict("records"):
            if (
                not isinstance(row["ticker"], str)
                or not row["ticker"].strip()
                or not isinstance(row["canonical_metric"], str)
                or not row["canonical_metric"].strip()
                or not isinstance(row["unit"], str)
                or not row["unit"].strip()
            ):
                raise ValueError("financial facts are invalid")
            fiscal_years.append(_parse_fiscal_year(row["fiscal_year"]))
            _parse_date(row["filed_date"])
            _parse_decimal(row["value"])
        annual["fiscal_year"] = fiscal_years
        annual_frames[key] = annual
    return annual_frames


def _fact(
    frame: pd.DataFrame,
    metric: str,
    fiscal_year: int,
) -> _Fact | None:
    if frame.empty:
        return None
    rows = frame.loc[
        (frame["canonical_metric"] == metric)
        & (frame["fiscal_year"] == fiscal_year)
    ].copy(deep=True)
    if rows.empty:
        return None
    rows["_filed_date"] = rows["filed_date"].map(_parse_date)
    selected_date = max(rows["_filed_date"])
    selected = rows.loc[rows["_filed_date"] == selected_date]
    identities = {
        (
            _parse_decimal(row["value"]),
            row.get("unit"),
            row.get("end_date"),
        )
        for row in selected.to_dict("records")
    }
    if len(identities) != 1:
        raise ValueError("financial facts are ambiguous")
    value, unit, _ = next(iter(identities))
    return _Fact(value, selected_date, unit)


def _availability(base: date, *facts: _Fact | None) -> date:
    dates = [fact.filed_date for fact in facts if fact is not None]
    return max(dates, default=base)


def _ratio_result(
    metric: str, numerator: _Fact | None, denominator: _Fact | None, base: date
) -> MetricResult:
    available = _availability(base, numerator, denominator)
    if numerator is not None and denominator is not None and numerator.unit != denominator.unit:
        return MetricResult(metric, None, "incompatible_unit", available)
    return safe_ratio(
        metric,
        numerator.value if numerator else None,
        denominator.value if denominator else None,
        available,
    )


def _growth_result(
    metric: str,
    current: _Fact | None,
    frame: pd.DataFrame,
    source_metric: str,
    prior_year: int,
    base: date,
) -> MetricResult:
    prior = _fact(frame, source_metric, prior_year) if current else None
    available = _availability(base, current, prior)
    if current is not None and prior is not None and current.unit != prior.unit:
        return MetricResult(metric, None, "incompatible_unit", available)
    return growth_rate(
        metric,
        current.value if current else None,
        prior.value if prior else None,
        available,
    )


def _ticker_and_years(
    annual_frames: dict[str, pd.DataFrame],
) -> tuple[str, list[int], date] | None:
    frames = [frame for frame in annual_frames.values() if not frame.empty]
    income = annual_frames["income_statement"]
    if income.empty:
        return None
    tickers = {
        str(value).strip().upper()
        for frame in frames
        for value in frame["ticker"].tolist()
    }
    if len(tickers) != 1:
        raise ValueError("financial statements contain mixed tickers")
    years = sorted(set(income["fiscal_year"].tolist()))
    current_year = years[-1]
    current_dates = [
        _parse_date(row["filed_date"])
        for row in income.loc[income["fiscal_year"] == current_year].to_dict("records")
    ]
    return next(iter(tickers)), years, max(current_dates)


def _prices_for_ticker(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if not isinstance(prices, pd.DataFrame):
        raise ValueError("price data is invalid")
    if prices.empty or "symbol" not in prices.columns:
        return prices.copy(deep=True)
    symbols = prices["symbol"].tolist()
    if any(not isinstance(symbol, str) or not symbol.strip() for symbol in symbols):
        raise ValueError("price data is invalid")
    normalized = prices["symbol"].map(lambda symbol: symbol.strip().upper())
    return prices.loc[normalized == ticker].copy(deep=True)


def build_financial_metrics(
    statements: dict[str, pd.DataFrame], prices: pd.DataFrame
) -> pd.DataFrame:
    annual_frames = _validated_annual_frames(statements)
    identity = _ticker_and_years(annual_frames)
    if identity is None:
        return pd.DataFrame(columns=METRIC_COLUMNS)
    ticker, fiscal_years, base_date = identity
    current_year = fiscal_years[-1]
    prior_year = fiscal_years[-2] if len(fiscal_years) > 1 else current_year - 1
    income = annual_frames["income_statement"]
    balance = annual_frames["balance_sheet"]
    cash_flow = annual_frames["cash_flow"]

    revenue = _fact(income, "revenue", current_year)
    diluted_eps = _fact(income, "diluted_eps", current_year)
    gross_profit = _fact(income, "gross_profit", current_year)
    operating_income = _fact(income, "operating_income", current_year)
    net_income = _fact(income, "net_income", current_year)
    equity = _fact(balance, "stockholders_equity", current_year)
    debt = _fact(balance, "debt", current_year)
    operating_cash_flow = _fact(cash_flow, "operating_cash_flow", current_year)
    capital_expenditure = _fact(cash_flow, "capital_expenditure", current_year)

    rows: list[dict[str, object]] = []

    def add(
        result: MetricResult,
        comparison_period: int | None = None,
        price_date: str | None = None,
    ) -> None:
        rows.append(
            {
                "ticker": ticker,
                "metric": result.metric,
                "value": result.value,
                "status": result.status,
                "formula": FORMULAS[result.metric],
                "current_period": current_year,
                "comparison_period": comparison_period,
                "available_date": result.available_date.isoformat(),
                "price_date": price_date,
            }
        )

    add(
        _growth_result(
            "revenue_growth", revenue, income, "revenue", prior_year, base_date
        ),
        prior_year,
    )
    add(
        _growth_result(
            "diluted_eps_growth",
            diluted_eps,
            income,
            "diluted_eps",
            prior_year,
            base_date,
        ),
        prior_year,
    )
    add(_ratio_result("gross_margin", gross_profit, revenue, base_date))
    add(_ratio_result("operating_margin", operating_income, revenue, base_date))
    add(_ratio_result("net_margin", net_income, revenue, base_date))
    add(_ratio_result("debt_to_equity", debt, equity, base_date))
    add(
        _growth_result(
            "operating_cash_flow_growth",
            operating_cash_flow,
            cash_flow,
            "operating_cash_flow",
            prior_year,
            base_date,
        ),
        prior_year,
    )

    prior_equity = (
        _fact(balance, "stockholders_equity", prior_year)
        if equity and net_income
        else None
    )
    roe_date = _availability(base_date, net_income, equity, prior_equity)
    average_equity = None
    roe_units_compatible = (
        net_income is not None
        and equity is not None
        and prior_equity is not None
        and len({net_income.unit, equity.unit, prior_equity.unit}) == 1
    )
    if roe_units_compatible:
        average_equity = (equity.value + prior_equity.value) / Decimal("2")
    roe = (
        MetricResult("roe", None, "incompatible_unit", roe_date)
        if net_income is not None
        and equity is not None
        and prior_equity is not None
        and not roe_units_compatible
        else safe_ratio(
            "roe",
            net_income.value if net_income else None,
            average_equity,
            roe_date,
        )
    )
    add(roe, prior_year)

    fcf_date = _availability(base_date, operating_cash_flow, capital_expenditure)
    free_cash_flow = None
    fcf_units_compatible = (
        operating_cash_flow is not None
        and capital_expenditure is not None
        and operating_cash_flow.unit == capital_expenditure.unit
    )
    if fcf_units_compatible:
        free_cash_flow = operating_cash_flow.value - capital_expenditure.value
    add(
        MetricResult(
            "free_cash_flow",
            free_cash_flow,
            (
                "available"
                if free_cash_flow is not None
                else "incompatible_unit"
                if operating_cash_flow is not None and capital_expenditure is not None
                else "missing_input"
            ),
            fcf_date,
        )
    )

    pe_date = _availability(base_date, diluted_eps)
    price_date = None
    aligned_close = None
    ticker_prices = _prices_for_ticker(prices, ticker)
    if diluted_eps is not None and not ticker_prices.empty:
        try:
            aligned = align_price_on_or_after(ticker_prices, pe_date)
        except _NoEligiblePriceError:
            pass
        else:
            price_date = aligned["date"].isoformat()
            aligned_close = aligned["close"]
    pe = (
        MetricResult("pe", None, "incompatible_unit", pe_date)
        if aligned_close is not None
        and diluted_eps is not None
        and diluted_eps.unit not in _SEC_USD_PER_SHARE_UNITS
        else safe_ratio(
            "pe",
            aligned_close,
            diluted_eps.value if diluted_eps else None,
            pe_date,
        )
    )
    add(
        pe,
        price_date=price_date,
    )
    price_to_book_date = _availability(base_date, equity)
    add(
        MetricResult("price_to_book", None, "missing_input", price_to_book_date),
    )
    return pd.DataFrame(
        {
            column: pd.Series([row[column] for row in rows], dtype="object")
            for column in METRIC_COLUMNS
        }
    )
