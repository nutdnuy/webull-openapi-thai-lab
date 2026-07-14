from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from webull_lab.financials import (
    CANONICAL_TAGS,
    OUTPUT_COLUMNS,
    FinancialDataError,
    build_financial_statements,
    derive_discrete_quarter,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sec" / "aapl_companyfacts_sample.json"


@pytest.fixture
def companyfacts() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def observation(
    value: int | float,
    *,
    start: str | None = "2024-01-01",
    end: str = "2024-12-31",
    accession: str = "acc-current",
    fiscal_year: int | None = 2024,
    fiscal_period: str | None = "FY",
    form: str = "10-K",
    filed: str = "2025-02-01",
    frame: str | None = "CY2024",
) -> dict:
    result = {
        "end": end,
        "val": value,
        "accn": accession,
        "fy": fiscal_year,
        "fp": fiscal_period,
        "form": form,
        "filed": filed,
    }
    if start is not None:
        result["start"] = start
    if frame is not None:
        result["frame"] = frame
    return result


def payload_for(tag: str, observations: list[dict], unit: str = "USD") -> dict:
    return {"facts": {"us-gaap": {tag: {"units": {unit: observations}}}}}


def test_canonical_tags_exactly_match_approved_mapping():
    assert CANONICAL_TAGS == {
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


def test_schema_keys_columns_and_fixture_provenance_are_stable(companyfacts):
    result = build_financial_statements(" aapl ", "320193", companyfacts)

    assert list(result) == ["income_statement", "balance_sheet", "cash_flow"]
    assert list(CANONICAL_TAGS) == ["income_statement", "balance_sheet", "cash_flow"]
    assert all(list(frame.columns) == OUTPUT_COLUMNS for frame in result.values())
    revenue = result["income_statement"].query("canonical_metric == 'revenue'")
    amended = revenue.query("fiscal_year == 2024").iloc[0]
    assert amended.to_dict() == {
        "ticker": "AAPL",
        "cik": "0000320193",
        "statement": "income_statement",
        "canonical_metric": "revenue",
        "source_taxonomy": "us-gaap",
        "source_tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "value": 1010,
        "unit": "USD",
        "start_date": "2023-10-01",
        "end_date": "2024-09-28",
        "form": "10-K/A",
        "fiscal_year": 2024,
        "fiscal_period": "FY",
        "filed_date": "2024-11-15",
        "frame": "CY2024",
        "accession_number": "0000320193-24-000002",
        "period_type": "annual",
        "derived": False,
        "superseded_accessions": '["0000320193-24-000001"]',
    }
    assert set(result["income_statement"]["canonical_metric"]) == {"revenue", "net_income"}
    assert set(result["balance_sheet"]["canonical_metric"]) == {
        "total_assets",
        "stockholders_equity",
    }


def test_duration_period_classification_from_fixture(companyfacts):
    revenue = build_financial_statements("AAPL", "320193", companyfacts)[
        "income_statement"
    ].query("canonical_metric == 'revenue'")

    by_period = revenue.set_index("fiscal_period")["period_type"].to_dict()
    assert by_period == {"FY": "annual", "Q1": "quarterly", "Q2": "ytd"}


def test_duration_discrete_quarter_frame_takes_precedence_over_fy():
    payload = payload_for(
        "Revenues",
        [
            observation(
                90,
                start="2008-09-28",
                end="2008-12-27",
                fiscal_year=2009,
                fiscal_period="FY",
                form="10-K",
                filed="2009-10-27",
                frame="CY2008Q4",
            )
        ],
    )

    row = build_financial_statements("AAPL", "320193", payload)["income_statement"].iloc[0]

    assert row["period_type"] == "quarterly"


def test_quarterly_instant_balance_fact_is_not_ytd():
    payload = payload_for(
        "Assets",
        [
            observation(
                5500,
                start=None,
                end="2025-03-31",
                fiscal_year=2025,
                fiscal_period="Q2",
                form="10-Q",
                frame="CY2025Q1I",
            )
        ],
    )

    row = build_financial_statements("AAPL", "320193", payload)["balance_sheet"].iloc[0]
    assert row["period_type"] == "quarterly"
    assert row["start_date"] is None


def test_q4_instant_balance_fact_is_quarterly():
    payload = payload_for(
        "Assets",
        [
            observation(
                5600,
                start=None,
                fiscal_period="Q4",
                form="10-Q/A",
                frame="CY2024Q4I",
            )
        ],
    )

    row = build_financial_statements("AAPL", "320193", payload)["balance_sheet"].iloc[0]

    assert row["period_type"] == "quarterly"


def test_quarterly_instant_balance_without_frame_is_quarterly():
    payload = payload_for(
        "Assets",
        [
            observation(
                5700,
                start=None,
                fiscal_period="Q2",
                form="10-Q",
                frame=None,
            )
        ],
    )

    row = build_financial_statements("AAPL", "320193", payload)["balance_sheet"].iloc[0]

    assert row["period_type"] == "quarterly"


def test_candidate_tags_cover_different_periods_and_priority_breaks_filed_date_tie():
    first = observation(100, end="2023-12-31", fiscal_year=2023, accession="first-2023")
    first_tie = observation(110, fiscal_year=2024, accession="first-2024")
    fallback_tie = observation(999, fiscal_year=2024, accession="fallback-2024")
    fallback_new_period = observation(
        120, end="2025-12-31", fiscal_year=2025, accession="fallback-2025"
    )
    payload = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [first, first_tie]}
                },
                "Revenues": {"units": {"USD": [fallback_tie, fallback_new_period]}},
            }
        }
    }

    rows = build_financial_statements("AAPL", "320193", payload)["income_statement"]

    assert rows["fiscal_year"].tolist() == [2023, 2024, 2025]
    tie = rows.query("fiscal_year == 2024").iloc[0]
    assert tie["source_tag"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert tie["value"] == 110
    assert tie["superseded_accessions"] == '["fallback-2024"]'


def test_same_economic_period_deduplicates_across_changed_filing_metadata():
    original = observation(
        100,
        accession="original",
        fiscal_year=2024,
        fiscal_period="Q2",
        filed="2024-08-01",
        frame=None,
    )
    later = observation(
        101,
        accession="later",
        fiscal_year=2025,
        fiscal_period="Q3",
        filed="2025-08-01",
        frame=None,
    )
    payload = payload_for("NetIncomeLoss", [original, later])

    rows = build_financial_statements("AAPL", "320193", payload)["income_statement"]

    assert len(rows) == 1
    assert rows.iloc[0]["accession_number"] == "later"
    assert rows.iloc[0]["fiscal_year"] == 2025
    assert rows.iloc[0]["fiscal_period"] == "Q3"
    assert rows.iloc[0]["superseded_accessions"] == '["original"]'


def test_units_are_separate_and_unsupported_forms_are_excluded():
    supported = observation(100, accession="usd")
    unsupported = observation(200, accession="eight-k", form="8-K")
    shares = observation(10, accession="shares")
    payload = {
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {"USD": [supported, unsupported], "shares": [shares]}
                }
            }
        }
    }

    rows = build_financial_statements("AAPL", "320193", payload)["income_statement"]

    assert rows["unit"].tolist() == ["USD", "shares"]
    assert "eight-k" not in rows["accession_number"].tolist()


def test_arbitrarily_large_integer_value_is_retained():
    large_value = 10**1000
    payload = payload_for("NetIncomeLoss", [observation(large_value)])

    row = build_financial_statements("AAPL", "320193", payload)["income_statement"].iloc[0]

    assert row["value"] == large_value


def test_missing_metrics_are_absent_and_empty_us_gaap_is_schema_stable():
    one_metric = build_financial_statements(
        "AAPL", "320193", payload_for("Assets", [observation(1, start=None)])
    )
    empty = build_financial_statements("AAPL", "320193", {"facts": {"us-gaap": {}}})

    assert one_metric["income_statement"].empty
    assert one_metric["cash_flow"].empty
    assert set(one_metric["balance_sheet"]["canonical_metric"]) == {"total_assets"}
    assert all(frame.empty and list(frame.columns) == OUTPUT_COLUMNS for frame in empty.values())


def test_years_filter_keeps_latest_n_fiscal_years_across_statements():
    payload = {
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            observation(1, fiscal_year=2022, end="2022-12-31"),
                            observation(2, fiscal_year=2023, end="2023-12-31"),
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            observation(3, start=None, fiscal_year=2024, end="2024-12-31")
                        ]
                    }
                },
            }
        }
    }

    result = build_financial_statements("AAPL", "320193", payload, years=1)

    assert result["income_statement"].empty
    assert result["balance_sheet"]["fiscal_year"].tolist() == [2024]


def test_years_filter_uses_latest_distinct_values_for_sparse_years():
    payload = payload_for(
        "NetIncomeLoss",
        [
            observation(1, fiscal_year=2020, end="2020-12-31"),
            observation(2, fiscal_year=2024, end="2024-12-31"),
        ],
    )

    latest_two = build_financial_statements("AAPL", "320193", payload, years=2)[
        "income_statement"
    ]
    latest_one = build_financial_statements("AAPL", "320193", payload, years=1)[
        "income_statement"
    ]

    assert latest_two["fiscal_year"].tolist() == [2020, 2024]
    assert latest_one["fiscal_year"].tolist() == [2024]


def test_years_filter_uses_economic_end_year_not_recent_filing_metadata():
    payload = payload_for(
        "NetIncomeLoss",
        [
            observation(
                1,
                start="2020-01-01",
                end="2020-12-31",
                fiscal_year=2025,
                accession="old-repeated",
                filed="2025-02-01",
            ),
            observation(
                2,
                start="2024-01-01",
                end="2024-12-31",
                fiscal_year=2024,
                accession="latest-economic",
                filed="2025-02-02",
            ),
        ],
    )

    rows = build_financial_statements("AAPL", "320193", payload, years=1)[
        "income_statement"
    ]

    assert rows["accession_number"].tolist() == ["latest-economic"]


@pytest.mark.parametrize("years", [0, -1, 1.5, "1", True])
def test_years_rejects_non_positive_non_integer_and_bool(years):
    with pytest.raises(ValueError, match="years"):
        build_financial_statements("AAPL", "320193", {"facts": {"us-gaap": {}}}, years=years)


def test_all_null_fiscal_years_are_retained_when_filtering():
    payload = payload_for("NetIncomeLoss", [observation(1, fiscal_year=None)])

    result = build_financial_statements("AAPL", "320193", payload, years=1)

    assert len(result["income_statement"]) == 1
    assert pd.isna(result["income_statement"].iloc[0]["fiscal_year"])


@pytest.mark.parametrize(
    "ticker,cik,payload",
    [
        (" ", "320193", {"facts": {"us-gaap": {}}}),
        ("AAPL", "not-a-cik", {"facts": {"us-gaap": {}}}),
        ("AAPL", "320193", []),
        ("AAPL", "320193", {}),
        ("AAPL", "320193", {"facts": []}),
        ("AAPL", "320193", {"facts": {"us-gaap": []}}),
        ("AAPL", "320193", {"facts": {"us-gaap": {"Assets": []}}}),
        ("AAPL", "320193", {"facts": {"us-gaap": {"Assets": {"units": []}}}}),
        (
            "AAPL",
            "320193",
            {"facts": {"us-gaap": {"Assets": {"units": {"USD": {}}}}}},
        ),
        (
            "AAPL",
            "320193",
            {"facts": {"us-gaap": {"Assets": {"units": {"USD": ["secret"]}}}}},
        ),
        (
            "AAPL",
            "320193",
            {"facts": {"us-gaap": {"Assets": {"units": {"USD": [observation(True)]}}}}},
        ),
        (
            "AAPL",
            "320193",
            {"facts": {"us-gaap": {"Assets": {"units": {"USD": [observation("secret")]}}}}},
        ),
    ],
)
def test_malformed_inputs_raise_safe_error_without_payload_content(ticker, cik, payload):
    with pytest.raises(FinancialDataError) as exc_info:
        build_financial_statements(ticker, cik, payload)

    assert "secret" not in str(exc_info.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("fy", []),
        ("fy", True),
        ("fy", float("inf")),
        ("start", []),
        ("start", "2024/01/01"),
        ("end", 20241231),
        ("end", "2024-13-01"),
        ("filed", []),
        ("filed", "2025-02-30"),
        ("frame", []),
        ("accn", {}),
        ("fp", []),
        ("fp", ""),
        ("form", []),
        ("form", ""),
    ],
)
def test_supported_observation_rejects_malformed_metadata_safely(field, value):
    item = observation(100)
    item[field] = value
    payload = payload_for("NetIncomeLoss", [item])

    with pytest.raises(FinancialDataError) as exc_info:
        build_financial_statements("AAPL", "320193", payload)

    assert repr(value) not in str(exc_info.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("end", None),
        ("end", ""),
        ("filed", None),
        ("filed", ""),
        ("accn", None),
        ("accn", ""),
    ],
)
def test_supported_observation_requires_auditable_fields(field, value):
    item = observation(100)
    item[field] = value

    with pytest.raises(FinancialDataError):
        build_financial_statements(
            "AAPL", "320193", payload_for("NetIncomeLoss", [item])
        )


def test_duration_observation_requires_start_date():
    item = observation(100)
    item.pop("start")

    with pytest.raises(FinancialDataError):
        build_financial_statements(
            "AAPL", "320193", payload_for("NetIncomeLoss", [item])
        )


@pytest.mark.parametrize("payload_cik", [789019, [], "secret-cik"])
def test_payload_cik_must_be_valid_and_match_supplied_cik(payload_cik):
    payload = payload_for("NetIncomeLoss", [observation(100)])
    payload["cik"] = payload_cik

    with pytest.raises(FinancialDataError) as exc_info:
        build_financial_statements("AAPL", "320193", payload)

    assert "secret-cik" not in str(exc_info.value)


def test_build_does_not_mutate_caller_payload(companyfacts):
    original = copy.deepcopy(companyfacts)

    build_financial_statements("AAPL", "320193", companyfacts)

    assert companyfacts == original


def series_for_derivation(**overrides) -> pd.Series:
    values = {
        "ticker": "AAPL",
        "cik": "0000320193",
        "statement": "income_statement",
        "canonical_metric": "revenue",
        "source_taxonomy": "us-gaap",
        "source_tag": "Revenues",
        "value": 650,
        "unit": "USD",
        "start_date": "2024-09-29",
        "end_date": "2025-03-29",
        "form": "10-Q",
        "fiscal_year": 2025,
        "fiscal_period": "Q2",
        "filed_date": "2025-05-01",
        "frame": None,
        "accession_number": "current",
        "period_type": "ytd",
        "derived": False,
        "superseded_accessions": "[]",
    }
    values.update(overrides)
    return pd.Series(values)


def test_derive_discrete_quarter_subtracts_ytd_and_preserves_inputs():
    current = series_for_derivation()
    prior = series_for_derivation(
        value=300,
        end_date="2024-12-28",
        fiscal_period="Q1",
        accession_number="prior",
        period_type="quarterly",
    )
    current_before = current.copy(deep=True)
    prior_before = prior.copy(deep=True)

    result = derive_discrete_quarter(current, prior)

    assert result["value"] == 350
    assert result["start_date"] == "2024-12-29"
    assert result["period_type"] == "quarterly"
    assert result["derived"] is True
    assert result["accession_number"] == "current"
    assert result["superseded_accessions"] == '["current", "prior"]'
    pd.testing.assert_series_equal(current, current_before)
    pd.testing.assert_series_equal(prior, prior_before)


@pytest.mark.parametrize(
    "current_change,prior_change",
    [
        ({"unit": "EUR"}, {}),
        ({"canonical_metric": "net_income"}, {}),
        ({"fiscal_year": 2024}, {}),
        ({"start_date": "2024-10-01"}, {}),
        ({"end_date": "2024-12-01"}, {}),
        ({"value": "650"}, {}),
        ({}, {"value": True}),
        ({"unit": None}, {"unit": None}),
        ({"canonical_metric": None}, {"canonical_metric": None}),
        ({"fiscal_year": None}, {"fiscal_year": None}),
        ({"start_date": None}, {"start_date": None}),
        ({"start_date": "not-a-date"}, {"start_date": "not-a-date"}),
        ({"end_date": "not-a-date"}, {}),
    ],
)
def test_derive_discrete_quarter_rejects_incompatible_rows(current_change, prior_change):
    current = series_for_derivation(**current_change)
    prior_values = {
        "value": 300,
        "end_date": "2024-12-28",
        "fiscal_period": "Q1",
        "accession_number": "prior",
        **prior_change,
    }
    prior = series_for_derivation(**prior_values)

    with pytest.raises(ValueError):
        derive_discrete_quarter(current, prior)


@pytest.mark.parametrize(
    "current_change,prior_change",
    [
        ({"ticker": "MSFT"}, {}),
        ({"ticker": ""}, {"ticker": ""}),
        ({"cik": "0000789019"}, {}),
        ({"cik": "320193"}, {"cik": "320193"}),
        ({"statement": "cash_flow"}, {}),
        ({"statement": "balance_sheet"}, {"statement": "balance_sheet"}),
        ({"source_taxonomy": "ifrs-full"}, {}),
        ({"source_taxonomy": ""}, {"source_taxonomy": ""}),
        ({"fiscal_period": "Q3"}, {}),
        ({"period_type": "quarterly"}, {}),
        ({}, {"period_type": "ytd"}),
        ({"derived": True}, {}),
        ({}, {"derived": True}),
    ],
)
def test_derive_discrete_quarter_rejects_identity_progression_and_state_errors(
    current_change, prior_change
):
    current = series_for_derivation(**current_change)
    prior_values = {
        "value": 300,
        "end_date": "2024-12-28",
        "fiscal_period": "Q1",
        "accession_number": "prior",
        "period_type": "quarterly",
        **prior_change,
    }
    prior = series_for_derivation(**prior_values)

    with pytest.raises(ValueError):
        derive_discrete_quarter(current, prior)
