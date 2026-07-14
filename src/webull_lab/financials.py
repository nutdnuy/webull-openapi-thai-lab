from __future__ import annotations

import json
import math
import re
from datetime import date
from numbers import Real
from typing import Any

import pandas as pd

from webull_lab.sec_client import normalize_cik


class FinancialDataError(ValueError):
    """Raised when SEC Company Facts data is not safe to normalize."""


CANONICAL_TAGS = {
    "income_statement": {
        "revenue": [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
        ],
        "gross_profit": ["GrossProfit"],
        "operating_income": ["OperatingIncomeLoss"],
        "net_income": ["NetIncomeLoss", "ProfitLoss"],
        "basic_eps": ["EarningsPerShareBasic"],
        "diluted_eps": ["EarningsPerShareDiluted"],
    },
    "balance_sheet": {
        "cash": [
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ],
        "current_assets": ["AssetsCurrent"],
        "total_assets": ["Assets"],
        "current_liabilities": ["LiabilitiesCurrent"],
        "total_liabilities": ["Liabilities"],
        "debt": [
            "LongTermDebtAndFinanceLeaseObligationsCurrent",
            "LongTermDebtCurrent",
            "LongTermDebtNoncurrent",
        ],
        "stockholders_equity": ["StockholdersEquity"],
    },
    "cash_flow": {
        "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "capital_expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment"],
        "investing_cash_flow": ["NetCashProvidedByUsedInInvestingActivities"],
        "financing_cash_flow": ["NetCashProvidedByUsedInFinancingActivities"],
        "dividends_paid": ["PaymentsOfDividends"],
    },
}

OUTPUT_COLUMNS = [
    "ticker",
    "cik",
    "statement",
    "canonical_metric",
    "source_taxonomy",
    "source_tag",
    "value",
    "unit",
    "start_date",
    "end_date",
    "form",
    "fiscal_year",
    "fiscal_period",
    "filed_date",
    "frame",
    "accession_number",
    "period_type",
    "derived",
    "superseded_accessions",
]

_SUPPORTED_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}
_DISCRETE_QUARTER_FRAME = re.compile(r"^CY\d{4}Q[1-4]$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _financial_error(message: str) -> FinancialDataError:
    return FinancialDataError(message)


def _validate_inputs(
    ticker: str, cik: str, payload: dict, years: int | None
) -> tuple[str, str, dict]:
    if not isinstance(ticker, str) or not ticker.strip():
        raise _financial_error("ticker must be a nonblank string")
    try:
        normalized_cik = normalize_cik(cik)
    except (TypeError, ValueError):
        raise _financial_error("CIK is invalid") from None
    if years is not None and (isinstance(years, bool) or not isinstance(years, int) or years <= 0):
        raise ValueError("years must be a positive integer or None")
    if not isinstance(payload, dict):
        raise _financial_error("Company Facts payload must be an object")
    if "cik" in payload:
        try:
            payload_cik = normalize_cik(payload["cik"])
        except (TypeError, ValueError):
            raise _financial_error("Company Facts payload CIK is invalid") from None
        if payload_cik != normalized_cik:
            raise _financial_error("Company Facts payload CIK does not match supplied CIK")
    facts = payload.get("facts")
    if not isinstance(facts, dict):
        raise _financial_error("Company Facts payload is missing a facts object")
    us_gaap = facts.get("us-gaap")
    if not isinstance(us_gaap, dict):
        raise _financial_error("Company Facts payload is missing a us-gaap object")
    _validate_us_gaap(us_gaap)
    return ticker.strip().upper(), normalized_cik, us_gaap


def _validate_us_gaap(us_gaap: dict) -> None:
    for tag, fact in us_gaap.items():
        if not isinstance(tag, str) or not isinstance(fact, dict):
            raise _financial_error("Company Facts contains a malformed tag")
        units = fact.get("units")
        if not isinstance(units, dict):
            raise _financial_error("Company Facts contains malformed units")
        for unit, observations in units.items():
            if not isinstance(unit, str) or not unit or not isinstance(observations, list):
                raise _financial_error("Company Facts contains a malformed unit")
            for item in observations:
                if not isinstance(item, dict):
                    raise _financial_error("Company Facts contains a malformed observation")
                value = item.get("val")
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or (isinstance(value, float) and not math.isfinite(value))
                ):
                    raise _financial_error("Company Facts observation value must be numeric")
                form = item.get("form")
                if not isinstance(form, str) or not form.strip():
                    raise _financial_error("Company Facts observation form must be nonblank")
                if form in _SUPPORTED_FORMS:
                    _validate_supported_metadata(item)


def _validate_iso_date(value: Any, field: str, *, required: bool = False) -> None:
    if value is None:
        if required:
            raise _financial_error(f"Company Facts observation {field} is required")
        return
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        raise _financial_error(f"Company Facts observation {field} must be an ISO date")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise _financial_error(f"Company Facts observation {field} must be an ISO date") from None


def _validate_supported_metadata(item: dict) -> None:
    _validate_iso_date(item.get("start"), "start")
    for field in ("end", "filed"):
        _validate_iso_date(item.get(field), field, required=True)
    frame = item.get("frame")
    if frame is not None and not isinstance(frame, str):
        raise _financial_error("Company Facts observation frame must be a string")
    accession = item.get("accn")
    if not isinstance(accession, str) or not accession.strip():
        raise _financial_error("Company Facts observation accession must be nonblank")
    fiscal_year = item.get("fy")
    if (
        fiscal_year is not None
        and (
            isinstance(fiscal_year, bool)
            or not isinstance(fiscal_year, Real)
            or (not isinstance(fiscal_year, int) and not math.isfinite(fiscal_year))
        )
    ):
        raise _financial_error("Company Facts observation fiscal year must be numeric")
    fiscal_period = item.get("fp")
    if not isinstance(fiscal_period, str) or not fiscal_period.strip():
        raise _financial_error("Company Facts observation fiscal period must be nonblank")


def _period_type(statement: str, observation: dict) -> str:
    fiscal_period = observation.get("fp")
    frame = observation.get("frame")
    if statement == "balance_sheet" and observation.get("start") is None:
        return "annual" if fiscal_period == "FY" else "quarterly"
    if isinstance(frame, str) and _DISCRETE_QUARTER_FRAME.fullmatch(frame):
        return "quarterly"
    if fiscal_period == "FY":
        return "annual"
    return "ytd"


def _candidate_rows(ticker: str, cik: str, us_gaap: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for statement, metrics in CANONICAL_TAGS.items():
        for canonical_metric, tags in metrics.items():
            for tag_priority, tag in enumerate(tags):
                fact = us_gaap.get(tag)
                if fact is None:
                    continue
                for unit, observations in fact["units"].items():
                    for observation in observations:
                        if observation.get("form") not in _SUPPORTED_FORMS:
                            continue
                        if statement != "balance_sheet" and observation.get("start") is None:
                            raise _financial_error(
                                "Company Facts duration observation start is required"
                            )
                        rows.append(
                            {
                                "ticker": ticker,
                                "cik": cik,
                                "statement": statement,
                                "canonical_metric": canonical_metric,
                                "source_taxonomy": "us-gaap",
                                "source_tag": tag,
                                "value": observation["val"],
                                "unit": unit,
                                "start_date": observation.get("start"),
                                "end_date": observation.get("end"),
                                "form": observation.get("form"),
                                "fiscal_year": observation.get("fy"),
                                "fiscal_period": observation.get("fp"),
                                "filed_date": observation.get("filed"),
                                "frame": observation.get("frame"),
                                "accession_number": observation.get("accn"),
                                "period_type": _period_type(statement, observation),
                                "derived": False,
                                "superseded_accessions": "[]",
                                "tag_priority": tag_priority,
                            }
                        )
    return rows


def _selection_key(row: dict[str, Any]) -> tuple[str, int]:
    filed_date = row["filed_date"] if isinstance(row["filed_date"], str) else ""
    return filed_date, -row["tag_priority"]


def _select_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            row["statement"],
            row["canonical_metric"],
            row["start_date"],
            row["end_date"],
            row["period_type"],
            row["unit"],
        )
        groups.setdefault(key, []).append(row)

    selected: list[dict[str, Any]] = []
    for candidates in groups.values():
        selected_candidate = max(candidates, key=_selection_key)
        winner = selected_candidate.copy()
        displaced = sorted(
            {
                candidate["accession_number"]
                for candidate in candidates
                if candidate is not selected_candidate
                and isinstance(candidate["accession_number"], str)
                and candidate["accession_number"] != winner["accession_number"]
            }
        )
        winner["superseded_accessions"] = json.dumps(displaced)
        winner.pop("tag_priority")
        selected.append(winner)
    return selected


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    fiscal_year = row["fiscal_year"]
    sortable_year = (
        fiscal_year
        if isinstance(fiscal_year, Real) and not isinstance(fiscal_year, bool)
        else -1
    )
    return (
        list(CANONICAL_TAGS).index(row["statement"]),
        sortable_year,
        row["end_date"] or "",
        list(CANONICAL_TAGS[row["statement"]]).index(row["canonical_metric"]),
        row["unit"],
    )


def _filter_years(rows: list[dict[str, Any]], years: int | None) -> list[dict[str, Any]]:
    if years is None:
        return rows
    economic_years = {int(row["end_date"][:4]) for row in rows}
    latest_years = set(sorted(economic_years, reverse=True)[:years])
    return [row for row in rows if int(row["end_date"][:4]) in latest_years]


def build_financial_statements(
    ticker: str,
    cik: str,
    payload: dict,
    years: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Normalize SEC Company Facts into three schema-stable financial statements."""
    normalized_ticker, normalized_cik, us_gaap = _validate_inputs(ticker, cik, payload, years)
    rows = _filter_years(
        _select_rows(_candidate_rows(normalized_ticker, normalized_cik, us_gaap)), years
    )
    rows.sort(key=_sort_key)
    statements: dict[str, pd.DataFrame] = {}
    for statement in CANONICAL_TAGS:
        statement_rows = [row for row in rows if row["statement"] == statement]
        if not statement_rows:
            statements[statement] = pd.DataFrame(columns=OUTPUT_COLUMNS)
            continue
        statements[statement] = pd.DataFrame(
            {
                column: pd.Series(
                    [row[column] for row in statement_rows],
                    dtype="object",
                )
                for column in OUTPUT_COLUMNS
            }
        )
    return statements


def _numeric(value: Any) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and (isinstance(value, int) or math.isfinite(value))
    )


def _provenance_accessions(row: pd.Series) -> list[str]:
    accessions: list[str] = []
    accession = row.get("accession_number")
    if isinstance(accession, str):
        accessions.append(accession)
    serialized = row.get("superseded_accessions", "[]")
    try:
        prior_accessions = json.loads(serialized)
    except (TypeError, ValueError):
        raise ValueError("superseded_accessions must be a JSON list") from None
    if not isinstance(prior_accessions, list) or any(
        not isinstance(item, str) for item in prior_accessions
    ):
        raise ValueError("superseded_accessions must be a JSON list of strings")
    return accessions + prior_accessions


def derive_discrete_quarter(current_ytd: pd.Series, prior_ytd: pd.Series) -> pd.Series:
    """Derive one discrete quarter by subtracting compatible cumulative observations."""
    if not isinstance(current_ytd, pd.Series) or not isinstance(prior_ytd, pd.Series):
        raise ValueError("current_ytd and prior_ytd must be pandas Series")
    for field in (
        "ticker",
        "statement",
        "source_taxonomy",
        "canonical_metric",
        "unit",
        "fiscal_year",
        "start_date",
    ):
        if current_ytd.get(field) != prior_ytd.get(field):
            raise ValueError(f"financial rows have incompatible {field}")
    for field in (
        "ticker",
        "statement",
        "source_taxonomy",
        "canonical_metric",
        "unit",
        "start_date",
    ):
        if not isinstance(current_ytd.get(field), str) or not current_ytd.get(field):
            raise ValueError(f"financial rows require {field}")
    if current_ytd["statement"] not in {"income_statement", "cash_flow"}:
        raise ValueError("financial rows must be duration statements")
    current_cik = current_ytd.get("cik")
    prior_cik = prior_ytd.get("cik")
    try:
        normalized_current_cik = normalize_cik(current_cik)
        normalized_prior_cik = normalize_cik(prior_cik)
    except (TypeError, ValueError):
        raise ValueError("financial rows require normalized CIK values") from None
    if (
        not isinstance(current_cik, str)
        or not isinstance(prior_cik, str)
        or current_cik != normalized_current_cik
        or prior_cik != normalized_prior_cik
        or current_cik != prior_cik
    ):
        raise ValueError("financial rows require matching normalized CIK values")
    if current_ytd.get("derived") is not False or prior_ytd.get("derived") is not False:
        raise ValueError("financial rows must not already be derived")
    current_period = current_ytd.get("fiscal_period")
    prior_period = prior_ytd.get("fiscal_period")
    expected_prior = {"Q2": "Q1", "Q3": "Q2", "Q4": "Q3"}.get(current_period)
    if expected_prior is None or prior_period != expected_prior:
        raise ValueError("financial rows have incompatible fiscal-period progression")
    if current_ytd.get("period_type") != "ytd":
        raise ValueError("current financial row must be ytd")
    expected_prior_type = "quarterly" if prior_period == "Q1" else "ytd"
    if prior_ytd.get("period_type") != expected_prior_type:
        raise ValueError("prior financial row has incompatible period type")
    fiscal_year = current_ytd.get("fiscal_year")
    if (
        not isinstance(fiscal_year, Real)
        or isinstance(fiscal_year, bool)
        or (not isinstance(fiscal_year, int) and not math.isfinite(fiscal_year))
    ):
        raise ValueError("financial rows require fiscal_year")
    current_value = current_ytd.get("value")
    prior_value = prior_ytd.get("value")
    if not _numeric(current_value) or not _numeric(prior_value):
        raise ValueError("financial row values must be numeric")
    try:
        fiscal_year_start = pd.Timestamp(current_ytd.get("start_date"))
        current_end = pd.Timestamp(current_ytd.get("end_date"))
        prior_end = pd.Timestamp(prior_ytd.get("end_date"))
    except (TypeError, ValueError):
        raise ValueError("financial row dates must be valid") from None
    if (
        pd.isna(fiscal_year_start)
        or pd.isna(current_end)
        or pd.isna(prior_end)
        or fiscal_year_start >= prior_end
        or prior_end >= current_end
    ):
        raise ValueError("prior end date must precede current end date")

    result = current_ytd.copy(deep=True)
    result["value"] = current_value - prior_value
    result["start_date"] = (prior_end + pd.Timedelta(days=1)).date().isoformat()
    result["period_type"] = "quarterly"
    result["derived"] = True
    provenance = sorted(
        set(_provenance_accessions(current_ytd) + _provenance_accessions(prior_ytd))
    )
    result["superseded_accessions"] = json.dumps(provenance)
    return result
