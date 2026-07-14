# SEC EDGAR + Webull Financial Data MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only, single-ticker pipeline that exports auditable SEC financial statements, optional Webull daily prices, timing-safe metrics, and one Thai beginner notebook.

**Architecture:** Keep SEC transport, XBRL normalization, Webull price normalization, metrics, exports, and orchestration in separate modules. SEC output must work without Webull credentials; Webull enriches the result when configured. All tests and the beginner notebook run offline by default with reduced fixtures.

**Tech Stack:** Python 3.11+, Typer, requests, pandas, PyArrow, Plotly, official Webull Python SDK, pytest, Ruff, GitHub Actions

---

## Preflight

Implement in a dedicated worktree created from the commit containing this plan. Keep the existing
`main` checkout clean and do not push until local verification passes.

```bash
git worktree add ../webull-openapi-thai-lab-sec-mvp -b sec-webull-financial-data-mvp
cd ../webull-openapi-thai-lab-sec-mvp
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
```

Expected baseline: the existing test suite and Ruff both pass before implementation.

## File Map

### Create

- `src/webull_lab/sec_config.py` — SEC identity, timeout, retry, and cache settings.
- `src/webull_lab/sec_client.py` — SEC JSON transport, caching, ticker/CIK resolution, errors.
- `src/webull_lab/financials.py` — canonical XBRL mapping, period selection, provenance.
- `src/webull_lab/metrics.py` — pure financial and valuation calculations.
- `src/webull_lab/exports.py` — deterministic CSV, Parquet, JSON, and manifest writing.
- `src/webull_lab/company_pipeline.py` — single-ticker orchestration and partial-result behavior.
- `src/webull_lab/tutorial_fixtures.py` — offline adapters used only by the beginner notebook.
- `scripts/build_sec_webull_financials_notebook.py` — deterministic notebook builder.
- `notebooks/sec_webull_financials_beginner.ipynb` — generated Thai beginner notebook.
- `docs/06-sec-webull-financials-th.md` — Thai concepts and usage guide.
- `tests/fixtures/sec/company_tickers_sample.json` — reduced ticker-to-CIK fixture.
- `tests/fixtures/sec/aapl_submissions_sample.json` — reduced filing metadata fixture.
- `tests/fixtures/sec/aapl_companyfacts_sample.json` — reduced XBRL fixture.
- `tests/fixtures/webull/aapl_daily_bars_sample.json` — reduced daily OHLCV fixture.
- `tests/test_sec_config.py` — SEC configuration tests.
- `tests/test_sec_client.py` — transport, cache, retry, and CIK tests.
- `tests/test_financials.py` — statement selection and provenance tests.
- `tests/test_metrics.py` — financial metric and timing tests.
- `tests/test_exports.py` — artifact schema and determinism tests.
- `tests/test_company_pipeline.py` — orchestration and partial-result tests.
- `tests/test_sec_webull_financials_notebook.py` — notebook contract and execution tests.
- `.github/workflows/sec-webull-live-smoke.yml` — manual, secret-gated live smoke test.

### Modify

- `pyproject.toml` — add runtime data/export dependencies.
- `.env.example` — add SEC identity, cache, and tutorial mode settings.
- `src/webull_lab/config.py` — use Webull's current official sandbox host.
- `src/webull_lab/market_data.py` — normalize daily Webull bars into a DataFrame.
- `src/webull_lab/cli.py` — add the `company-data` command.
- `.gitignore` — confirm all generated private data and cache paths are ignored.
- `README.md` — add the combined SEC + Webull quick start.
- `notebooks/README.md` — add the new beginner path.
- `docs/00-learning-path-th.md` — add the financial-data lesson.
- `AGENTS.md`, `CLAUDE.md`, `llms.txt` — document module boundaries and safety rules.
- `.github/workflows/ci.yml` — run the new offline checks through the existing test command.
- `tests/test_market_data.py`, `tests/test_cli.py`, `tests/test_repository_contract.py`,
  `tests/test_docs_links.py` — cover the new public behavior and documentation links.

---

### Task 1: Add SEC Configuration and Runtime Dependencies

**Files:**
- Create: `src/webull_lab/sec_config.py`
- Create: `tests/test_sec_config.py`
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `src/webull_lab/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing SEC configuration tests**

```python
# tests/test_sec_config.py
from pathlib import Path

import pytest

from webull_lab.sec_config import load_sec_settings


def test_load_sec_settings_builds_descriptive_user_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")
    monkeypatch.setenv("SEC_CACHE_DIR", str(tmp_path / "sec-cache"))

    settings = load_sec_settings()

    assert settings.user_agent == "webull-openapi-thai-lab researcher@example.com"
    assert settings.cache_dir == tmp_path / "sec-cache"
    assert settings.timeout_seconds == 20.0
    assert settings.max_attempts == 3


def test_load_sec_settings_requires_contact_email(monkeypatch):
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)

    with pytest.raises(RuntimeError, match="SEC_CONTACT_EMAIL"):
        load_sec_settings()


def test_load_sec_settings_rejects_non_positive_timeout(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")
    monkeypatch.setenv("SEC_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValueError, match="positive"):
        load_sec_settings()
```

Also change the existing assertion in
`tests/test_config.py::test_load_settings_uses_uat_endpoint_by_default` to:

```python
assert settings.trading_endpoint == "api.sandbox.webull.com"
```

- [ ] **Step 2: Run the focused test and confirm the expected failure**

Run:

```bash
python -m pytest tests/test_sec_config.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'webull_lab.sec_config'`.

- [ ] **Step 3: Add runtime dependencies and implement SEC settings**

In `pyproject.toml`, make the runtime dependency list exactly include these additions while
retaining the existing entries:

```toml
dependencies = [
    "pandas>=2.2.0",
    "pyarrow>=16.1.0",
    "python-dotenv>=1.0.1",
    "requests>=2.32.0",
    "rich>=13.7.1",
    "typer>=0.12.3",
    "webull-openapi-python-sdk>=2.0.12",
]
```

Create:

```python
# src/webull_lab/sec_config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SecSettings:
    contact_email: str
    cache_dir: Path
    timeout_seconds: float = 20.0
    max_attempts: int = 3

    @property
    def user_agent(self) -> str:
        return f"webull-openapi-thai-lab {self.contact_email}"


def load_sec_settings() -> SecSettings:
    contact_email = os.getenv("SEC_CONTACT_EMAIL", "").strip()
    if not contact_email or "@" not in contact_email:
        raise RuntimeError("Set SEC_CONTACT_EMAIL to a monitored contact email.")

    timeout_seconds = float(os.getenv("SEC_TIMEOUT_SECONDS", "20"))
    max_attempts = int(os.getenv("SEC_MAX_ATTEMPTS", "3"))
    if timeout_seconds <= 0 or max_attempts <= 0:
        raise ValueError("SEC timeout and max attempts must be positive.")

    return SecSettings(
        contact_email=contact_email,
        cache_dir=Path(os.getenv("SEC_CACHE_DIR", "data/private/sec-cache")),
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
    )
```

Append to `.env.example`:

```dotenv
SEC_CONTACT_EMAIL=your_monitored_email@example.com
SEC_CACHE_DIR=data/private/sec-cache
SEC_TIMEOUT_SECONDS=20
SEC_MAX_ATTEMPTS=3
SEC_WEBULL_TUTORIAL_LIVE=0
SEC_WEBULL_TUTORIAL_OUTPUT_DIR=outputs/sec-webull-financials
```

Update the test-environment host in `src/webull_lab/config.py` to the current official sandbox
host published in the Webull SDK documentation and 2026-07-08 changelog:

```python
TRADING_ENDPOINTS = {
    "uat": "api.sandbox.webull.com",
    "prod": "api.webull.com",
}
```

- [ ] **Step 4: Install the updated package and run the focused tests**

Run:

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/test_sec_config.py tests/test_config.py -v
python -m ruff check src/webull_lab/sec_config.py tests/test_sec_config.py
```

Expected: all SEC configuration tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 5: Commit SEC configuration**

```bash
git add pyproject.toml .env.example src/webull_lab/sec_config.py src/webull_lab/config.py tests/test_sec_config.py tests/test_config.py
git commit -m "feat: add SEC data configuration"
```

---

### Task 2: Build the SEC JSON Client, Cache, and Ticker-to-CIK Resolver

**Files:**
- Create: `src/webull_lab/sec_client.py`
- Create: `tests/test_sec_client.py`
- Create: `tests/fixtures/sec/company_tickers_sample.json`
- Create: `tests/fixtures/sec/aapl_submissions_sample.json`

- [ ] **Step 1: Add reduced SEC fixtures**

`tests/fixtures/sec/company_tickers_sample.json`:

```json
{
  "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
  "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"}
}
```

`tests/fixtures/sec/aapl_submissions_sample.json`:

```json
{
  "cik": "0000320193",
  "name": "Apple Inc.",
  "tickers": ["AAPL"],
  "filings": {
    "recent": {
      "accessionNumber": ["0000320193-24-000123"],
      "filingDate": ["2024-11-01"],
      "reportDate": ["2024-09-28"],
      "form": ["10-K"]
    }
  }
}
```

- [ ] **Step 2: Write failing tests for headers, cache, retry, and CIK lookup**

```python
# tests/test_sec_client.py
import json
from pathlib import Path

import pytest

from webull_lab.sec_client import SecClient, SecDataError, SecNotFoundError, normalize_cik
from webull_lab.sec_config import SecSettings


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers, timeout):
        self.calls.append((url, headers, timeout))
        return self.responses.pop(0)


def settings(tmp_path):
    return SecSettings("researcher@example.com", tmp_path / "cache", 2.0, 3)


def test_normalize_cik_zero_pads_to_ten_digits():
    assert normalize_cik(320193) == "0000320193"


def test_resolve_cik_uses_ticker_fixture(tmp_path):
    payload = json.loads(Path("tests/fixtures/sec/company_tickers_sample.json").read_text())
    client = SecClient(settings(tmp_path), session=FakeSession([FakeResponse(200, payload)]))

    assert client.resolve_cik(" aapl ") == "0000320193"


def test_resolve_cik_rejects_unknown_ticker(tmp_path):
    payload = json.loads(Path("tests/fixtures/sec/company_tickers_sample.json").read_text())
    client = SecClient(settings(tmp_path), session=FakeSession([FakeResponse(200, payload)]))

    with pytest.raises(SecNotFoundError, match="ZZZZ"):
        client.resolve_cik("ZZZZ")


def test_get_json_sends_identity_and_reuses_cache(tmp_path):
    session = FakeSession([FakeResponse(200, {"ok": True})])
    client = SecClient(settings(tmp_path), session=session)

    first = client.get_json("https://data.sec.gov/example.json", "example.json")
    second = client.get_json("https://data.sec.gov/example.json", "example.json")

    assert first == second == {"ok": True}
    assert len(session.calls) == 1
    assert session.calls[0][1]["User-Agent"] == "webull-openapi-thai-lab researcher@example.com"
    assert client.cache_hits == 1
    assert client.network_requests == 1


def test_get_json_retries_429_then_succeeds(tmp_path, monkeypatch):
    session = FakeSession([FakeResponse(429, {}), FakeResponse(200, {"ok": True})])
    monkeypatch.setattr("webull_lab.sec_client.time.sleep", lambda seconds: None)
    client = SecClient(settings(tmp_path), session=session)

    assert client.get_json("https://data.sec.gov/example.json", "retry.json") == {"ok": True}
    assert len(session.calls) == 2


def test_get_companyfacts_rejects_missing_facts_object(tmp_path):
    client = SecClient(settings(tmp_path), session=FakeSession([FakeResponse(200, {"cik": 320193})]))

    with pytest.raises(SecDataError, match="company facts missing"):
        client.get_companyfacts("0000320193")
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_sec_client.py -v
```

Expected: collection fails because `webull_lab.sec_client` does not exist.

- [ ] **Step 4: Implement the SEC client**

```python
# src/webull_lab/sec_client.py
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

import requests

from webull_lab.sec_config import SecSettings

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class SecDataError(RuntimeError):
    pass


class SecNotFoundError(SecDataError):
    pass


def normalize_cik(cik: int | str) -> str:
    digits = str(cik).strip()
    if not digits.isdigit() or len(digits) > 10:
        raise ValueError(f"Invalid CIK: {cik!r}")
    return digits.zfill(10)


class SecClient:
    def __init__(self, settings: SecSettings, session: Any | None = None):
        self.settings = settings
        self.session = session or requests.Session()
        self.cache_hits = 0
        self.network_requests = 0

    def get_json(self, url: str, cache_name: str) -> dict[str, Any]:
        cache_path = self.settings.cache_dir / cache_name
        if cache_path.exists():
            self.cache_hits += 1
            return json.loads(cache_path.read_text(encoding="utf-8"))

        headers = {"User-Agent": self.settings.user_agent, "Accept-Encoding": "gzip, deflate"}
        for attempt in range(1, self.settings.max_attempts + 1):
            self.network_requests += 1
            response = self.session.get(url, headers=headers, timeout=self.settings.timeout_seconds)
            if response.status_code not in {429, 500, 502, 503, 504}:
                try:
                    response.raise_for_status()
                    payload = response.json()
                except Exception as error:
                    raise SecDataError(f"SEC request failed for {url}") from error
                if not isinstance(payload, dict):
                    raise SecDataError(f"SEC response is not a JSON object: {url}")
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                return payload
            if attempt < self.settings.max_attempts:
                time.sleep((0.5 * (2 ** (attempt - 1))) + random.uniform(0.0, 0.2))
        raise SecDataError(f"SEC request exhausted retries for {url}")

    def resolve_cik(self, ticker: str) -> str:
        normalized = ticker.strip().upper()
        payload = self.get_json(TICKERS_URL, "company_tickers.json")
        for company in payload.values():
            if str(company.get("ticker", "")).upper() == normalized:
                return normalize_cik(company["cik_str"])
        raise SecNotFoundError(f"SEC ticker not found: {normalized}")

    def get_submissions(self, cik: str) -> dict[str, Any]:
        normalized = normalize_cik(cik)
        return self.get_json(SUBMISSIONS_URL.format(cik=normalized), f"{normalized}-submissions.json")

    def get_companyfacts(self, cik: str) -> dict[str, Any]:
        normalized = normalize_cik(cik)
        payload = self.get_json(COMPANYFACTS_URL.format(cik=normalized), f"{normalized}-companyfacts.json")
        if not isinstance(payload.get("facts"), dict):
            raise SecDataError(f"SEC company facts missing for CIK {normalized}")
        return payload
```

- [ ] **Step 5: Run focused tests and lint**

```bash
python -m pytest tests/test_sec_client.py -v
python -m ruff check src/webull_lab/sec_client.py tests/test_sec_client.py
```

Expected: all SEC client tests pass and Ruff passes.

- [ ] **Step 6: Commit the SEC client**

```bash
git add src/webull_lab/sec_client.py tests/test_sec_client.py tests/fixtures/sec
git commit -m "feat: add cached SEC EDGAR client"
```

---

### Task 3: Normalize SEC Company Facts into Auditable Statements

**Files:**
- Create: `src/webull_lab/financials.py`
- Create: `tests/test_financials.py`
- Create: `tests/fixtures/sec/aapl_companyfacts_sample.json`

- [ ] **Step 1: Add a reduced Company Facts fixture with annual, YTD, and amended observations**

Create `tests/fixtures/sec/aapl_companyfacts_sample.json` with this exact reduced shape. The
four included tags are sufficient for the normalization tests in this task:

```json
{
  "cik": 320193,
  "entityName": "Apple Inc.",
  "facts": {
    "us-gaap": {
      "RevenueFromContractWithCustomerExcludingAssessedTax": {
        "label": "Revenue",
        "units": {
          "USD": [
            {"start": "2023-10-01", "end": "2024-09-28", "val": 391035, "accn": "A", "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-11-01", "frame": "CY2024"},
            {"start": "2024-09-29", "end": "2024-12-28", "val": 124300, "accn": "B", "fy": 2025, "fp": "Q1", "form": "10-Q", "filed": "2025-01-31", "frame": "CY2024Q4"},
            {"start": "2024-09-29", "end": "2025-03-29", "val": 219700, "accn": "C", "fy": 2025, "fp": "Q2", "form": "10-Q", "filed": "2025-05-02"}
          ]
        }
      },
      "NetIncomeLoss": {"label": "Net Income", "units": {"USD": [{"start": "2023-10-01", "end": "2024-09-28", "val": 93736, "accn": "D", "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-11-01", "frame": "CY2024"}]}},
      "Assets": {"label": "Assets", "units": {"USD": [{"end": "2024-09-28", "val": 364980, "accn": "E", "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-11-01", "frame": "CY2024Q3I"}]}},
      "StockholdersEquity": {"label": "Equity", "units": {"USD": [{"end": "2024-09-28", "val": 56950, "accn": "F", "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-11-01", "frame": "CY2024Q3I"}]}}
    }
  }
}
```

- [ ] **Step 2: Write failing normalization tests**

```python
# tests/test_financials.py
import json
from pathlib import Path

from webull_lab.financials import build_financial_statements


def fixture():
    return json.loads(Path("tests/fixtures/sec/aapl_companyfacts_sample.json").read_text())


def test_build_financial_statements_retains_provenance():
    statements = build_financial_statements("AAPL", "0000320193", fixture())
    revenue = statements["income_statement"].query("canonical_metric == 'revenue'").iloc[0]

    assert revenue["value"] == 391035
    assert revenue["source_tag"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert revenue["accession_number"] == "A"
    assert revenue["filed_date"] == "2024-11-01"
    assert revenue["period_type"] == "annual"
    assert bool(revenue["derived"]) is False


def test_build_financial_statements_keeps_ytd_separate():
    statements = build_financial_statements("AAPL", "0000320193", fixture())
    revenue = statements["income_statement"].query("canonical_metric == 'revenue'")

    assert set(revenue["period_type"]) == {"annual", "quarterly", "ytd"}


def test_build_financial_statements_does_not_invent_missing_metrics():
    statements = build_financial_statements("AAPL", "0000320193", fixture())

    assert "gross_profit" not in set(statements["income_statement"]["canonical_metric"])


def test_build_financial_statements_limits_requested_fiscal_years():
    statements = build_financial_statements("AAPL", "0000320193", fixture(), years=1)

    assert set(statements["income_statement"]["fiscal_year"]) == {2025}
```

- [ ] **Step 3: Run tests to confirm failure**

```bash
python -m pytest tests/test_financials.py -v
```

Expected: collection fails because `webull_lab.financials` does not exist.

- [ ] **Step 4: Implement canonical mappings and normalization**

```python
# src/webull_lab/financials.py
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

CANONICAL_TAGS = {
    "income_statement": {
        "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
        "gross_profit": ["GrossProfit"],
        "operating_income": ["OperatingIncomeLoss"],
        "net_income": ["NetIncomeLoss", "ProfitLoss"],
        "basic_eps": ["EarningsPerShareBasic"],
        "diluted_eps": ["EarningsPerShareDiluted"],
    },
    "balance_sheet": {
        "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
        "current_assets": ["AssetsCurrent"],
        "total_assets": ["Assets"],
        "current_liabilities": ["LiabilitiesCurrent"],
        "total_liabilities": ["Liabilities"],
        "debt": ["LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtCurrent", "LongTermDebtNoncurrent"],
        "stockholders_equity": ["StockholdersEquity"],
    },
    "cash_flow": {
        "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "capital_expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment"],
        "investing_cash_flow": ["NetCashProvidedByUsedInInvestingActivities"],
        "financing_cash_flow": ["NetCashProvidedByUsedInFinancingActivities"],
        "dividends_paid": ["PaymentsOfDividends"]
    },
}

OUTPUT_COLUMNS = [
    "ticker", "cik", "statement", "canonical_metric", "source_tag", "value", "unit",
    "start_date", "end_date", "form", "fiscal_year", "fiscal_period", "filed_date",
    "frame", "accession_number", "period_type", "derived",
]


def _period_type(item: dict[str, Any]) -> str:
    if item.get("fp") == "FY":
        return "annual"
    if item.get("frame") and item.get("fp", "").startswith("Q"):
        return "quarterly"
    return "ytd"


def _facts_for_metric(us_gaap: dict[str, Any], tags: Iterable[str]):
    for tag in tags:
        fact = us_gaap.get(tag)
        if fact:
            yield tag, fact


def build_financial_statements(
    ticker: str,
    cik: str,
    payload: dict[str, Any],
    years: int | None = None,
) -> dict[str, pd.DataFrame]:
    if years is not None and years <= 0:
        raise ValueError("years must be positive")
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    rows: list[dict[str, Any]] = []
    for statement, metrics in CANONICAL_TAGS.items():
        for canonical_metric, tags in metrics.items():
            selected = next(_facts_for_metric(us_gaap, tags), None)
            if selected is None:
                continue
            source_tag, fact = selected
            for unit, observations in fact.get("units", {}).items():
                for item in observations:
                    if item.get("form") not in {"10-K", "10-K/A", "10-Q", "10-Q/A"}:
                        continue
                    rows.append({
                        "ticker": ticker.strip().upper(), "cik": cik, "statement": statement,
                        "canonical_metric": canonical_metric, "source_tag": source_tag,
                        "value": item["val"], "unit": unit, "start_date": item.get("start"),
                        "end_date": item.get("end"), "form": item.get("form"),
                        "fiscal_year": item.get("fy"), "fiscal_period": item.get("fp"),
                        "filed_date": item.get("filed"), "frame": item.get("frame"),
                        "accession_number": item.get("accn"), "period_type": _period_type(item),
                        "derived": False,
                    })
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if not frame.empty:
        key = ["statement", "canonical_metric", "end_date", "period_type", "unit"]
        frame = frame.sort_values("filed_date").drop_duplicates(key, keep="last")
        if years is not None:
            latest_year = int(frame["fiscal_year"].dropna().max())
            frame = frame.loc[frame["fiscal_year"] > latest_year - years]
    return {
        name: frame.loc[frame["statement"] == name].reset_index(drop=True)
        for name in CANONICAL_TAGS
    }
```

- [ ] **Step 5: Add explicit derived-quarter coverage**

Extend `tests/test_financials.py` with a pure-function test and add this function to
`financials.py`:

```python
def derive_discrete_quarter(current_ytd: pd.Series, prior_ytd: pd.Series) -> pd.Series:
    if current_ytd["unit"] != prior_ytd["unit"] or current_ytd["start_date"] != prior_ytd["start_date"]:
        raise ValueError("YTD observations must share unit and fiscal-year start")
    derived = current_ytd.copy()
    derived["value"] = current_ytd["value"] - prior_ytd["value"]
    derived["start_date"] = prior_ytd["end_date"]
    derived["period_type"] = "quarterly"
    derived["derived"] = True
    return derived
```

```python
def test_derive_discrete_quarter_marks_provenance():
    import pandas as pd
    from webull_lab.financials import derive_discrete_quarter

    prior = pd.Series({"value": 100, "unit": "USD", "start_date": "2025-01-01", "end_date": "2025-03-31"})
    current = pd.Series({"value": 230, "unit": "USD", "start_date": "2025-01-01", "end_date": "2025-06-30"})

    result = derive_discrete_quarter(current, prior)

    assert result["value"] == 130
    assert result["derived"] is True
    assert result["period_type"] == "quarterly"
```

- [ ] **Step 6: Run tests and commit statement normalization**

```bash
python -m pytest tests/test_financials.py -v
python -m ruff check src/webull_lab/financials.py tests/test_financials.py
git add src/webull_lab/financials.py tests/test_financials.py tests/fixtures/sec/aapl_companyfacts_sample.json
git commit -m "feat: normalize SEC financial statements"
```

Expected: all financial statement tests and Ruff pass.

---

### Task 4: Normalize Webull Daily Bars Without Requiring Webull

**Files:**
- Create: `tests/fixtures/webull/aapl_daily_bars_sample.json`
- Modify: `src/webull_lab/market_data.py`
- Modify: `tests/test_market_data.py`

- [ ] **Step 1: Add a reduced Webull daily-bar fixture**

```json
[
  {"symbol": "AAPL", "time": 1730419200000, "open": "220.97", "high": "225.35", "low": "220.27", "close": "222.91", "volume": "65276700"},
  {"symbol": "AAPL", "time": 1730678400000, "open": "220.99", "high": "222.79", "low": "219.71", "close": "222.01", "volume": "44944500"}
]
```

- [ ] **Step 2: Write failing tests for daily retrieval and precision-safe normalization**

Append to `tests/test_market_data.py`:

```python
import json
from decimal import Decimal
from pathlib import Path

from webull_lab.market_data import get_daily_stock_bars, normalize_stock_bars


def test_get_daily_stock_bars_requests_daily_timespan():
    client = FakeDataClient()

    get_daily_stock_bars(client, "aapl")

    assert client.market_data.calls == [("bars", "AAPL", "US_STOCK", "D")]


def test_normalize_stock_bars_parses_utc_dates_and_decimal_prices():
    payload = json.loads(Path("tests/fixtures/webull/aapl_daily_bars_sample.json").read_text())

    frame = normalize_stock_bars(payload)

    assert frame.loc[0, "date"].isoformat() == "2024-11-01"
    assert frame.loc[0, "close"] == Decimal("222.91")
    assert frame.loc[0, "volume"] == 65276700
```

- [ ] **Step 3: Run the focused tests and confirm failure**

```bash
python -m pytest tests/test_market_data.py -v
```

Expected: import fails because the two new functions do not exist.

- [ ] **Step 4: Implement daily retrieval and normalization**

Append to `src/webull_lab/market_data.py`:

```python
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd


def get_daily_stock_bars(data_client: Any, symbol: str) -> Any:
    return get_stock_bars(data_client, symbol, "D")


def normalize_stock_bars(payload: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in payload:
        timestamp_ms = int(item["time"])
        rows.append({
            "symbol": str(item["symbol"]).upper(),
            "date": datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).date(),
            "open": Decimal(str(item["open"])),
            "high": Decimal(str(item["high"])),
            "low": Decimal(str(item["low"])),
            "close": Decimal(str(item["close"])),
            "volume": int(item["volume"]),
        })
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
```

- [ ] **Step 5: Run tests and commit market-data normalization**

```bash
python -m pytest tests/test_market_data.py -v
python -m ruff check src/webull_lab/market_data.py tests/test_market_data.py
git add src/webull_lab/market_data.py tests/test_market_data.py tests/fixtures/webull/aapl_daily_bars_sample.json
git commit -m "feat: normalize Webull daily bars"
```

---

### Task 5: Add Timing-Safe Financial Metrics

**Files:**
- Create: `src/webull_lab/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write failing tests for formulas, missing inputs, and filed-date alignment**

```python
# tests/test_metrics.py
from datetime import date
from decimal import Decimal

import pandas as pd

from webull_lab.metrics import MetricResult, align_price_on_or_after, safe_ratio


def test_safe_ratio_returns_available_result():
    result = safe_ratio("net_margin", Decimal("25"), Decimal("100"), date(2025, 2, 1))

    assert result == MetricResult("net_margin", Decimal("0.25"), "available", date(2025, 2, 1))


def test_safe_ratio_marks_zero_denominator_not_meaningful():
    result = safe_ratio("roe", Decimal("10"), Decimal("0"), date(2025, 2, 1))

    assert result.status == "not_meaningful"
    assert result.value is None


def test_align_price_uses_first_trading_date_on_or_after_filing():
    prices = pd.DataFrame({
        "date": [date(2025, 1, 31), date(2025, 2, 3)],
        "close": [Decimal("100"), Decimal("103")],
    })

    aligned = align_price_on_or_after(prices, date(2025, 2, 1))

    assert aligned["date"] == date(2025, 2, 3)
    assert aligned["close"] == Decimal("103")
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/test_metrics.py -v
```

Expected: collection fails because `webull_lab.metrics` does not exist.

- [ ] **Step 3: Implement typed metric primitives**

```python
# src/webull_lab/metrics.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd


@dataclass(frozen=True)
class MetricResult:
    metric: str
    value: Decimal | None
    status: str
    available_date: date


def safe_ratio(metric: str, numerator: Decimal | None, denominator: Decimal | None, available_date: date) -> MetricResult:
    if numerator is None or denominator is None:
        return MetricResult(metric, None, "missing_input", available_date)
    if denominator == 0:
        return MetricResult(metric, None, "not_meaningful", available_date)
    return MetricResult(metric, numerator / denominator, "available", available_date)


def growth_rate(metric: str, current: Decimal | None, previous: Decimal | None, available_date: date) -> MetricResult:
    if current is None or previous is None:
        return MetricResult(metric, None, "missing_input", available_date)
    if previous == 0:
        return MetricResult(metric, None, "not_meaningful", available_date)
    return MetricResult(metric, (current / previous) - Decimal("1"), "available", available_date)


def align_price_on_or_after(prices: pd.DataFrame, filed_date: date) -> pd.Series:
    eligible = prices.loc[prices["date"] >= filed_date].sort_values("date")
    if eligible.empty:
        raise ValueError(f"No price on or after filing date {filed_date.isoformat()}")
    return eligible.iloc[0]
```

- [ ] **Step 4: Add the table-level metric builder test**

Append this exact test to `tests/test_metrics.py`:

```python
def test_build_financial_metrics_records_formulas_and_timing():
    from webull_lab.metrics import build_financial_metrics

    income = pd.DataFrame([
        {"ticker": "AAPL", "canonical_metric": "revenue", "value": 100, "unit": "USD", "fiscal_year": 2023, "period_type": "annual", "end_date": "2023-09-30", "filed_date": "2023-11-03"},
        {"ticker": "AAPL", "canonical_metric": "revenue", "value": 120, "unit": "USD", "fiscal_year": 2024, "period_type": "annual", "end_date": "2024-09-28", "filed_date": "2024-11-01"},
        {"ticker": "AAPL", "canonical_metric": "net_income", "value": 24, "unit": "USD", "fiscal_year": 2024, "period_type": "annual", "end_date": "2024-09-28", "filed_date": "2024-11-01"},
        {"ticker": "AAPL", "canonical_metric": "diluted_eps", "value": "6.00", "unit": "USD/shares", "fiscal_year": 2024, "period_type": "annual", "end_date": "2024-09-28", "filed_date": "2024-11-01"},
    ])
    balance = pd.DataFrame([
        {"ticker": "AAPL", "canonical_metric": "stockholders_equity", "value": 50, "unit": "USD", "fiscal_year": 2023, "period_type": "annual", "end_date": "2023-09-30", "filed_date": "2023-11-03"},
        {"ticker": "AAPL", "canonical_metric": "stockholders_equity", "value": 70, "unit": "USD", "fiscal_year": 2024, "period_type": "annual", "end_date": "2024-09-28", "filed_date": "2024-11-01"},
    ])
    prices = pd.DataFrame({
        "date": [date(2024, 11, 1), date(2024, 11, 4)],
        "close": [Decimal("222"), Decimal("224")],
    })

    result = build_financial_metrics(
        {"income_statement": income, "balance_sheet": balance, "cash_flow": pd.DataFrame()},
        prices,
    ).set_index("metric")

    assert result.loc["revenue_growth", "value"] == Decimal("0.2")
    assert result.loc["net_margin", "value"] == Decimal("0.2")
    assert result.loc["roe", "value"] == Decimal("0.4")
    assert result.loc["pe", "value"] == Decimal("37")
    assert result.loc["pe", "price_date"] == "2024-11-01"
    assert result.loc["price_to_book", "status"] == "missing_input"
    assert result.loc["revenue_growth", "formula"] == "current_revenue / prior_revenue - 1"
```

- [ ] **Step 5: Implement the table-level metric builder**

Append this code to `src/webull_lab/metrics.py`:

```python
from typing import Any


METRIC_COLUMNS = [
    "ticker", "metric", "value", "status", "formula", "current_period",
    "comparison_period", "available_date", "price_date",
]

```python
METRIC_COLUMNS = [
    "ticker", "metric", "value", "status", "formula", "current_period",
    "comparison_period", "available_date", "price_date",
]
```

The initial formulas are:

```python
FORMULAS = {
    "revenue_growth": "current_revenue / prior_revenue - 1",
    "diluted_eps_growth": "current_diluted_eps / prior_diluted_eps - 1",
    "gross_margin": "gross_profit / revenue",
    "operating_margin": "operating_income / revenue",
    "net_margin": "net_income / revenue",
    "roe": "net_income / average_stockholders_equity",
    "debt_to_equity": "debt / stockholders_equity",
    "operating_cash_flow_growth": "current_operating_cash_flow / prior_operating_cash_flow - 1",
    "free_cash_flow": "operating_cash_flow - capital_expenditure",
    "pe": "filed_date_aligned_close / diluted_eps",
    "price_to_book": "filed_date_aligned_market_cap / stockholders_equity",
}


def _annual(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame.loc[
        (frame["canonical_metric"] == metric) & (frame["period_type"] == "annual")
    ].sort_values(["fiscal_year", "filed_date"])


def _decimal_value(frame: pd.DataFrame, metric: str, fiscal_year: int) -> Decimal | None:
    rows = _annual(frame, metric)
    if rows.empty:
        return None
    rows = rows.loc[rows["fiscal_year"] == fiscal_year]
    if rows.empty:
        return None
    return Decimal(str(rows.iloc[-1]["value"]))


def _metric_row(
    ticker: str,
    result: MetricResult,
    current_period: int,
    comparison_period: int | None,
    price_date: str | None = None,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "metric": result.metric,
        "value": result.value,
        "status": result.status,
        "formula": FORMULAS[result.metric],
        "current_period": current_period,
        "comparison_period": comparison_period,
        "available_date": result.available_date.isoformat(),
        "price_date": price_date,
    }


def build_financial_metrics(
    statements: dict[str, pd.DataFrame], prices: pd.DataFrame
) -> pd.DataFrame:
    income = statements["income_statement"]
    balance = statements["balance_sheet"]
    cash_flow = statements["cash_flow"]
    fiscal_years = (
        sorted(set(income.loc[income["period_type"] == "annual", "fiscal_year"]))
        if not income.empty
        else []
    )
    if not fiscal_years:
        return pd.DataFrame(columns=METRIC_COLUMNS)

    current_year = int(fiscal_years[-1])
    prior_year = int(fiscal_years[-2]) if len(fiscal_years) > 1 else current_year - 1
    filed_values = pd.concat([income, balance, cash_flow], ignore_index=True)
    current_filed = filed_values.loc[filed_values["fiscal_year"] == current_year, "filed_date"]
    available_date = date.fromisoformat(str(current_filed.max()))
    ticker = str(income.iloc[0]["ticker"])

    revenue = _decimal_value(income, "revenue", current_year)
    prior_revenue = _decimal_value(income, "revenue", prior_year)
    net_income = _decimal_value(income, "net_income", current_year)
    gross_profit = _decimal_value(income, "gross_profit", current_year)
    operating_income = _decimal_value(income, "operating_income", current_year)
    diluted_eps = _decimal_value(income, "diluted_eps", current_year)
    prior_eps = _decimal_value(income, "diluted_eps", prior_year)
    equity = _decimal_value(balance, "stockholders_equity", current_year)
    prior_equity = _decimal_value(balance, "stockholders_equity", prior_year)
    debt = _decimal_value(balance, "debt", current_year)
    operating_cash_flow = _decimal_value(cash_flow, "operating_cash_flow", current_year)
    prior_operating_cash_flow = _decimal_value(cash_flow, "operating_cash_flow", prior_year)
    capital_expenditure = _decimal_value(cash_flow, "capital_expenditure", current_year)

    rows = [
        _metric_row(ticker, growth_rate("revenue_growth", revenue, prior_revenue, available_date), current_year, prior_year),
        _metric_row(ticker, growth_rate("diluted_eps_growth", diluted_eps, prior_eps, available_date), current_year, prior_year),
        _metric_row(ticker, safe_ratio("gross_margin", gross_profit, revenue, available_date), current_year, None),
        _metric_row(ticker, safe_ratio("operating_margin", operating_income, revenue, available_date), current_year, None),
        _metric_row(ticker, safe_ratio("net_margin", net_income, revenue, available_date), current_year, None),
        _metric_row(ticker, safe_ratio("debt_to_equity", debt, equity, available_date), current_year, None),
        _metric_row(ticker, growth_rate("operating_cash_flow_growth", operating_cash_flow, prior_operating_cash_flow, available_date), current_year, prior_year),
    ]

    average_equity = None
    if equity is not None and prior_equity is not None:
        average_equity = (equity + prior_equity) / Decimal("2")
    rows.append(_metric_row(ticker, safe_ratio("roe", net_income, average_equity, available_date), current_year, prior_year))

    free_cash_flow = None
    fcf_status = "missing_input"
    if operating_cash_flow is not None and capital_expenditure is not None:
        free_cash_flow = operating_cash_flow - capital_expenditure
        fcf_status = "available"
    rows.append(_metric_row(ticker, MetricResult("free_cash_flow", free_cash_flow, fcf_status, available_date), current_year, None))

    price_date = None
    aligned_close = None
    if not prices.empty:
        aligned = align_price_on_or_after(prices, available_date)
        price_date = aligned["date"].isoformat()
        aligned_close = Decimal(str(aligned["close"]))
    rows.append(_metric_row(ticker, safe_ratio("pe", aligned_close, diluted_eps, available_date), current_year, None, price_date))
    rows.append(_metric_row(ticker, MetricResult("price_to_book", None, "missing_input", available_date), current_year, None, price_date))
    return pd.DataFrame(rows, columns=METRIC_COLUMNS)
```

`price_to_book` deliberately returns `missing_input` until shares outstanding is part of the
canonical statement input; the implementation must not infer market capitalization.

- [ ] **Step 6: Run tests and commit metrics**

```bash
python -m pytest tests/test_metrics.py -v
python -m ruff check src/webull_lab/metrics.py tests/test_metrics.py
git add src/webull_lab/metrics.py tests/test_metrics.py
git commit -m "feat: add timing-safe financial metrics"
```

---

### Task 6: Export Artifacts and Orchestrate Partial SEC/Webull Runs

**Files:**
- Create: `src/webull_lab/exports.py`
- Create: `src/webull_lab/company_pipeline.py`
- Create: `tests/test_exports.py`
- Create: `tests/test_company_pipeline.py`

- [ ] **Step 1: Write failing export tests**

```python
# tests/test_exports.py
import json

import pandas as pd

from webull_lab.exports import write_company_artifacts


def test_write_company_artifacts_writes_csv_parquet_json_and_manifest(tmp_path):
    statements = {
        "income_statement": pd.DataFrame([{"ticker": "AAPL", "value": 1}]),
        "balance_sheet": pd.DataFrame([{"ticker": "AAPL", "value": 2}]),
        "cash_flow": pd.DataFrame([{"ticker": "AAPL", "value": 3}]),
    }
    prices = pd.DataFrame([{"symbol": "AAPL", "close": "100"}])
    metrics = pd.DataFrame([{"ticker": "AAPL", "metric": "net_margin", "value": "0.2"}])

    manifest = write_company_artifacts(tmp_path, "AAPL", "0000320193", statements, prices, metrics, "available")

    assert (tmp_path / "income_statement.csv").exists()
    assert (tmp_path / "income_statement.parquet").exists()
    assert (tmp_path / "prices.parquet").exists()
    assert json.loads((tmp_path / "run_manifest.json").read_text())["webull_status"] == "available"
    assert manifest["ticker"] == "AAPL"
```

- [ ] **Step 2: Run the export test and confirm failure**

```bash
python -m pytest tests/test_exports.py -v
```

Expected: collection fails because `webull_lab.exports` does not exist.

- [ ] **Step 3: Implement deterministic artifact writing**

```python
# src/webull_lab/exports.py
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


def _write_table(frame: pd.DataFrame, output_dir: Path, name: str) -> list[str]:
    csv_path = output_dir / f"{name}.csv"
    parquet_path = output_dir / f"{name}.parquet"
    frame.to_csv(csv_path, index=False)
    frame.to_parquet(parquet_path, index=False)
    return [str(csv_path), str(parquet_path)]


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
    output_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    for name, frame in statements.items():
        files.extend(_write_table(frame, output_dir, name))
    files.extend(_write_table(prices, output_dir, "prices"))
    files.extend(_write_table(metrics, output_dir, "financial_metrics"))
    snapshot = {"ticker": ticker, "cik": cik, "webull_status": webull_status}
    snapshot_path = output_dir / "company_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    files.append(str(snapshot_path))
    if raw_payloads:
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        for name, payload in raw_payloads.items():
            raw_path = raw_dir / f"{name}.json"
            raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            files.append(str(raw_path))
    missing_metrics = []
    if not metrics.empty and {"metric", "status"}.issubset(metrics.columns):
        missing_metrics = sorted(metrics.loc[metrics["status"] != "available", "metric"].tolist())
    manifest = {
        "ticker": ticker,
        "cik": cik,
        "run_timestamp": datetime.now(UTC).isoformat(),
        "sec_status": "available",
        "webull_status": webull_status,
        "years": years,
        "cache_status": cache_status,
        "warnings": warnings or [],
        "missing_metrics": missing_metrics,
        "files": sorted(files),
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
```

- [ ] **Step 4: Write failing orchestration tests with injected boundaries**

```python
# tests/test_company_pipeline.py
from pathlib import Path

import pandas as pd

from webull_lab.company_pipeline import run_company_pipeline


class FakeSecClient:
    def resolve_cik(self, ticker):
        return "0000320193"

    def get_submissions(self, cik):
        return {"name": "Apple Inc."}

    def get_companyfacts(self, cik):
        return {"facts": {"us-gaap": {}}}


def test_pipeline_completes_sec_only_when_webull_is_absent(tmp_path, monkeypatch):
    empty_statements = {name: pd.DataFrame() for name in ("income_statement", "balance_sheet", "cash_flow")}
    monkeypatch.setattr("webull_lab.company_pipeline.build_financial_statements", lambda *args: empty_statements)
    monkeypatch.setattr("webull_lab.company_pipeline.build_financial_metrics", lambda *args: pd.DataFrame())

    result = run_company_pipeline("AAPL", 5, tmp_path, FakeSecClient(), data_client=None)

    assert result["webull_status"] == "unavailable"
    assert (tmp_path / "run_manifest.json").exists()
    assert (tmp_path / "raw" / "sec_submissions.json").exists()
    assert (tmp_path / "raw" / "sec_companyfacts.json").exists()


def test_pipeline_turns_webull_failure_into_safe_partial_result(tmp_path, monkeypatch):
    empty_statements = {name: pd.DataFrame() for name in ("income_statement", "balance_sheet", "cash_flow")}
    monkeypatch.setattr("webull_lab.company_pipeline.build_financial_statements", lambda *args: empty_statements)
    monkeypatch.setattr("webull_lab.company_pipeline.build_financial_metrics", lambda *args: pd.DataFrame())
    monkeypatch.setattr("webull_lab.company_pipeline.get_daily_stock_bars", lambda *args: (_ for _ in ()).throw(RuntimeError("secret upstream detail")))

    result = run_company_pipeline("AAPL", 5, tmp_path, FakeSecClient(), data_client=object())

    assert result["webull_status"] == "unavailable"
    assert result["warnings"] == ["Webull market data unavailable; SEC financial outputs were still generated."]
    assert "secret upstream detail" not in str(result)
```

- [ ] **Step 5: Implement the orchestrator**

```python
# src/webull_lab/company_pipeline.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from webull_lab.account import ResponseError
from webull_lab.exports import write_company_artifacts
from webull_lab.financials import build_financial_statements
from webull_lab.market_data import get_daily_stock_bars, normalize_stock_bars
from webull_lab.metrics import build_financial_metrics


def run_company_pipeline(
    ticker: str,
    years: int,
    output_dir: Path,
    sec_client: Any,
    data_client: Any | None,
) -> dict[str, Any]:
    if years <= 0:
        raise ValueError("years must be positive")
    symbol = ticker.strip().upper()
    cik = sec_client.resolve_cik(symbol)
    submissions = sec_client.get_submissions(cik)
    companyfacts = sec_client.get_companyfacts(cik)
    statements = build_financial_statements(symbol, cik, companyfacts, years=years)

    warnings: list[str] = []
    prices = pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])
    webull_status = "unavailable"
    if data_client is not None:
        try:
            prices = normalize_stock_bars(get_daily_stock_bars(data_client, symbol))
            webull_status = "available"
        except (ResponseError, RuntimeError, ValueError):
            warnings.append("Webull market data unavailable; SEC financial outputs were still generated.")

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
        raw_payloads={"sec_submissions": submissions, "sec_companyfacts": companyfacts},
        cache_status="hit" if getattr(sec_client, "cache_hits", 0) else "miss",
    )
```

- [ ] **Step 6: Run focused tests and commit pipeline/export work**

```bash
python -m pytest tests/test_exports.py tests/test_company_pipeline.py -v
python -m ruff check src/webull_lab/exports.py src/webull_lab/company_pipeline.py tests/test_exports.py tests/test_company_pipeline.py
git add src/webull_lab/exports.py src/webull_lab/company_pipeline.py tests/test_exports.py tests/test_company_pipeline.py
git commit -m "feat: orchestrate SEC and Webull company data"
```

---

### Task 7: Add the `company-data` CLI Command

**Files:**
- Modify: `src/webull_lab/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests for full and SEC-only runs**

Append to `tests/test_cli.py`:

```python
def test_company_data_prints_manifest_without_webull_credentials(monkeypatch, tmp_path):
    manifest = {"ticker": "AAPL", "sec_status": "available", "webull_status": "unavailable"}
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")
    monkeypatch.delenv("WEBULL_APP_KEY", raising=False)
    monkeypatch.delenv("WEBULL_APP_SECRET", raising=False)
    monkeypatch.setattr("webull_lab.cli.run_company_pipeline", lambda *args, **kwargs: manifest)

    result = CliRunner().invoke(app, ["company-data", "AAPL", "--years", "5", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert '"ticker": "AAPL"' in result.output
    assert '"webull_status": "unavailable"' in result.output


def test_company_data_rejects_zero_years(monkeypatch, tmp_path):
    result = CliRunner().invoke(app, ["company-data", "AAPL", "--years", "0", "--output-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "years" in result.output.lower()
```

- [ ] **Step 2: Run the CLI tests and confirm failure**

```bash
python -m pytest tests/test_cli.py -v
```

Expected: the command is missing and Typer reports `No such command 'company-data'`.

- [ ] **Step 3: Implement optional Webull configuration and the CLI command**

Add these imports and command to `src/webull_lab/cli.py`:

```python
import os
from pathlib import Path

from webull_lab.company_pipeline import run_company_pipeline
from webull_lab.sec_client import SecClient, SecDataError
from webull_lab.sec_config import load_sec_settings


def build_optional_data_client():
    if not os.getenv("WEBULL_APP_KEY", "").strip() or not os.getenv("WEBULL_APP_SECRET", "").strip():
        return None
    return build_data_client(load_settings())


@app.command("company-data")
def company_data(
    symbol: str = typer.Argument("AAPL"),
    years: int = typer.Option(5, min=1, max=20),
    output_dir: Path = typer.Option(Path("data/private/company-data")),
) -> None:
    try:
        sec_client = SecClient(load_sec_settings())
        manifest = run_company_pipeline(
            symbol,
            years,
            output_dir,
            sec_client,
            build_optional_data_client(),
        )
        console.print(json.dumps(manifest, ensure_ascii=False, indent=2))
    except (ResponseError, SecDataError, RuntimeError, ValueError, OSError) as error:
        print_error_and_exit(error)
```

- [ ] **Step 4: Run CLI and regression tests**

```bash
python -m pytest tests/test_cli.py tests/test_orders.py tests/test_account.py -v
python -m ruff check src/webull_lab/cli.py tests/test_cli.py
```

Expected: the new CLI tests pass and existing order/account guardrail tests remain green.

- [ ] **Step 5: Commit the CLI**

```bash
git add src/webull_lab/cli.py tests/test_cli.py
git commit -m "feat: add company financial data CLI"
```

---

### Task 8: Build the Thai Offline-First Beginner Notebook

**Files:**
- Create: `src/webull_lab/tutorial_fixtures.py`
- Create: `scripts/build_sec_webull_financials_notebook.py`
- Create: `notebooks/sec_webull_financials_beginner.ipynb`
- Create: `tests/test_sec_webull_financials_notebook.py`

- [ ] **Step 1: Write the failing notebook contract test**

```python
# tests/test_sec_webull_financials_notebook.py
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_sec_webull_financials_notebook.py"
NOTEBOOK = ROOT / "notebooks" / "sec_webull_financials_beginner.ipynb"
REQUIRED_HEADINGS = [
    "SEC EDGAR + Webull", "Step 1 - Setup", "Step 2 - Ticker to CIK",
    "Step 3 - Financial Statements", "Step 4 - Webull Prices",
    "Step 5 - Metrics", "Step 6 - Charts", "Step 7 - Export",
    "Common Mistakes", "Exercise", "Checklist",
]


def source(cell):
    value = cell.get("source", "")
    return "".join(value) if isinstance(value, list) else value


def load(path=NOTEBOOK):
    return json.loads(path.read_text(encoding="utf-8"))


def test_builder_is_deterministic_and_notebook_compiles(tmp_path):
    output = tmp_path / NOTEBOOK.name
    result = subprocess.run([sys.executable, str(BUILDER), "--out", str(output)], cwd=ROOT, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert load(output) == load()
    text = "\n".join(source(cell) for cell in load()["cells"])
    for heading in REQUIRED_HEADINGS:
        assert heading in text
    for index, cell in enumerate(load()["cells"]):
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None
            ast.parse(source(cell), filename=f"notebook cell {index}")
```

- [ ] **Step 2: Run the notebook test and confirm failure**

```bash
python -m pytest tests/test_sec_webull_financials_notebook.py -v
```

Expected: the builder path is missing.

- [ ] **Step 3: Implement offline fixture adapters**

```python
# src/webull_lab/tutorial_fixtures.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FixtureResponse:
    status_code = 200
    text = "offline fixture"

    def __init__(self, payload: Any):
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class FixtureMarketData:
    def __init__(self, bars_path: Path):
        self.bars_path = bars_path

    def get_history_bar(self, symbol: str, category: str, timespan: str) -> FixtureResponse:
        if symbol != "AAPL" or category != "US_STOCK" or timespan != "D":
            raise ValueError("Offline fixture supports AAPL daily US stock bars only")
        return FixtureResponse(json.loads(self.bars_path.read_text(encoding="utf-8")))


class FixtureDataClient:
    def __init__(self, bars_path: Path):
        self.market_data = FixtureMarketData(bars_path)


class FixtureSecClient:
    def __init__(self, fixture_dir: Path):
        self.fixture_dir = fixture_dir

    def resolve_cik(self, ticker: str) -> str:
        if ticker.strip().upper() != "AAPL":
            raise ValueError("Offline fixture supports AAPL only")
        return "0000320193"

    def get_submissions(self, cik: str) -> dict[str, Any]:
        return json.loads((self.fixture_dir / "aapl_submissions_sample.json").read_text(encoding="utf-8"))

    def get_companyfacts(self, cik: str) -> dict[str, Any]:
        return json.loads((self.fixture_dir / "aapl_companyfacts_sample.json").read_text(encoding="utf-8"))
```

- [ ] **Step 4: Implement the deterministic builder**

Create the builder with this complete implementation:

```python
# scripts/build_sec_webull_financials_notebook.py
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "notebooks" / "sec_webull_financials_beginner.ipynb"


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(source).strip() + "\n"}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dedent(source).strip() + "\n",
    }


def explanation(action: str, expected: str, mistake: str) -> dict:
    return markdown(f"""
    ### โค้ดช่องถัดไปทำอะไร
    - สิ่งที่จะทำ: {action}
    - ผลลัพธ์ที่ควรเห็น: {expected}
    - ข้อผิดพลาดที่พบบ่อย: {mistake}
    """)


def build_notebook() -> dict:
    cells = [
        markdown("""
        # SEC EDGAR + Webull Financial Data for Newbies

        Notebook ภาษาไทยสำหรับดึงงบ 10-K/10-Q จาก SEC EDGAR เชื่อมกับราคาหุ้นรายวันจาก
        Webull และคำนวณ metrics โดยใช้ filed date เพื่อป้องกัน look-ahead bias.

        Goal: สร้าง Income Statement, Balance Sheet, Cash Flow, ราคา และ metrics ที่ตรวจสอบ
        source tag, unit, period และวันที่ข้อมูลพร้อมใช้ได้.
        """),
        markdown("""
        ## Step 1 - Setup

        เริ่มด้วย offline fixture เพื่อให้รันได้โดยไม่มี key. ตั้ง
        `SEC_WEBULL_TUTORIAL_LIVE=1` เฉพาะเมื่อมี SEC contact email และ Webull permission.
        """),
        explanation("โหลด library และเลือก offline/live mode", "เห็น ticker, mode และ output directory", "อย่าเขียน Webull secret ลงใน notebook"),
        code("""
        import os
        from pathlib import Path

        import pandas as pd
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        from webull_lab.clients import build_data_client
        from webull_lab.company_pipeline import run_company_pipeline
        from webull_lab.config import load_settings
        from webull_lab.financials import build_financial_statements
        from webull_lab.market_data import get_daily_stock_bars, normalize_stock_bars
        from webull_lab.metrics import build_financial_metrics
        from webull_lab.sec_client import SecClient
        from webull_lab.sec_config import load_sec_settings
        from webull_lab.tutorial_fixtures import FixtureDataClient, FixtureSecClient

        LIVE_MODE = os.getenv("SEC_WEBULL_TUTORIAL_LIVE", "0") == "1"
        TICKER = os.getenv("SEC_WEBULL_TUTORIAL_TICKER", "AAPL").strip().upper()
        OUTPUT_DIR = Path(os.getenv("SEC_WEBULL_TUTORIAL_OUTPUT_DIR", "outputs/sec-webull-financials"))
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        FIXTURE_ROOT = Path("tests/fixtures")

        if LIVE_MODE:
            sec_client = SecClient(load_sec_settings())
            try:
                data_client = build_data_client(load_settings())
            except RuntimeError:
                data_client = None
        else:
            sec_client = FixtureSecClient(FIXTURE_ROOT / "sec")
            data_client = FixtureDataClient(FIXTURE_ROOT / "webull/aapl_daily_bars_sample.json")

        print({"ticker": TICKER, "live_mode": LIVE_MODE, "output_dir": str(OUTPUT_DIR)})
        """),
        markdown("## Step 2 - Ticker to CIK\n\nSEC ใช้ CIK 10 หลักเป็นรหัสบริษัท ส่วน ticker เป็นชื่อย่อในตลาด."),
        explanation("แปลง AAPL เป็น CIK", "ได้ 0000320193", "อย่าตัดเลขศูนย์ด้านหน้า CIK"),
        code("""
        CIK = sec_client.resolve_cik(TICKER)
        print({"ticker": TICKER, "cik": CIK})
        """),
        markdown("## Step 3 - Financial Statements\n\nดึง Company Facts แล้วแยก annual, quarterly และ YTD โดยเก็บ provenance."),
        explanation("สร้างงบการเงินสามชุด", "เห็นจำนวนแถวของแต่ละงบ", "อย่าแทน missing fact ด้วยศูนย์"),
        code("""
        companyfacts = sec_client.get_companyfacts(CIK)
        statements = build_financial_statements(TICKER, CIK, companyfacts)
        {name: len(frame) for name, frame in statements.items()}
        """),
        markdown("## Step 4 - Webull Prices\n\nWebull ให้ daily OHLCV; ราคาเป็นข้อมูลเสริมและ pipeline SEC ยังทำงานได้เมื่อ Webull ไม่พร้อม."),
        explanation("ดึงและ normalize daily bars", "เห็น date, close และ volume", "HTTP 403 มักหมายถึงยังไม่มี OpenAPI market-data permission"),
        code("""
        if data_client is None:
            prices = pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])
        else:
            prices = normalize_stock_bars(get_daily_stock_bars(data_client, TICKER))
        prices.head()
        """),
        markdown("## Step 5 - Metrics\n\nMetrics ใช้ราคาวันแรกที่ซื้อขายได้ตั้งแต่ filed date เป็นต้นไป."),
        explanation("คำนวณ growth, margins, ROE และ valuation", "เห็น status ของ metric ทุกตัว", "อย่าใช้ period end เป็นวันที่งบเปิดเผย"),
        code("""
        metrics = build_financial_metrics(statements, prices)
        metrics
        """),
        markdown("## Step 6 - Charts\n\nแยกกราฟหน่วยเงินของงบและราคาหุ้นเป็นคนละ panel."),
        explanation("วาดแนวโน้มรายได้/กำไรและราคาปิด", "ได้ไฟล์ HTML หนึ่งไฟล์", "อย่าตีความความสัมพันธ์บนกราฟว่าเป็นเหตุและผล"),
        code("""
        annual_income = statements["income_statement"].query("period_type == 'annual'")
        figure = make_subplots(rows=2, cols=1, shared_xaxes=False, subplot_titles=("Annual financial facts", "Daily close"))
        for metric_name in ("revenue", "net_income"):
            selected = annual_income.query("canonical_metric == @metric_name")
            figure.add_trace(go.Bar(x=selected["end_date"], y=selected["value"], name=metric_name), row=1, col=1)
        figure.add_trace(go.Scatter(x=prices["date"], y=prices["close"].astype(float), name="close"), row=2, col=1)
        chart_path = OUTPUT_DIR / "sec-webull-financials-chart.html"
        figure.write_html(chart_path, include_plotlyjs="cdn")
        print(chart_path)
        """),
        markdown("## Step 7 - Export\n\nเรียก public pipeline เดียวกับ CLI เพื่อสร้าง CSV, Parquet, JSON และ manifest."),
        explanation("รัน pipeline และเขียน artifacts", "manifest ระบุ source status และไฟล์ครบ", "อย่า commit data/private, outputs หรือ raw credentials"),
        code("""
        manifest = run_company_pipeline(TICKER, 5, OUTPUT_DIR, sec_client, data_client)
        manifest
        """),
        markdown("""
        ## Common Mistakes

        - สลับ annual, quarterly และ YTD
        - ผสม USD กับ USD/shares
        - ใช้ period end แทน filed date
        - เติม missing XBRL fact เป็นศูนย์
        - commit `.env`, token หรือ output ส่วนตัว

        ## Exercise

        เลือก annual revenue และ net income ของ AAPL แล้วอธิบายว่าการเปลี่ยนแปลงหลัง filing
        สัมพันธ์กับราคาอย่างไร โดยไม่กล่าวอ้างว่าสามารถทำนายผลตอบแทนได้.

        ## Checklist

        - [ ] ตรวจ source tag และ unit
        - [ ] ตรวจ period type และ filed date
        - [ ] ตรวจ metric status ก่อนใช้
        - [ ] รันซ้ำแล้วได้ schema เดิม
        - [ ] ไม่มี secret ใน notebook หรือ output
        """),
    ]
    return {
        "cells": cells,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(build_notebook(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Add the offline execution test**

Append this test to `tests/test_sec_webull_financials_notebook.py`:

```python
def test_notebook_executes_offline_top_to_bottom(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_WEBULL_TUTORIAL_LIVE", "0")
    monkeypatch.setenv("SEC_WEBULL_TUTORIAL_OUTPUT_DIR", str(tmp_path / "output"))
    namespace = {}
    for index, cell in enumerate(load()["cells"]):
        if cell["cell_type"] == "code":
            exec(compile(source(cell), f"notebook cell {index}", "exec"), namespace)

    output = tmp_path / "output"
    required = {
        "income_statement.csv", "income_statement.parquet",
        "balance_sheet.csv", "balance_sheet.parquet",
        "cash_flow.csv", "cash_flow.parquet", "prices.csv", "prices.parquet",
        "financial_metrics.csv", "financial_metrics.parquet",
        "company_snapshot.json", "run_manifest.json", "sec-webull-financials-chart.html",
    }
    assert required.issubset({path.name for path in output.iterdir()})
```

Run:

```bash
python scripts/build_sec_webull_financials_notebook.py
python -m pytest tests/test_sec_webull_financials_notebook.py -v
python -m ruff check scripts/build_sec_webull_financials_notebook.py tests/test_sec_webull_financials_notebook.py
```

Expected: deterministic regeneration and offline execution pass without credentials or network.

- [ ] **Step 6: Commit the notebook**

```bash
git add src/webull_lab/tutorial_fixtures.py scripts/build_sec_webull_financials_notebook.py notebooks/sec_webull_financials_beginner.ipynb tests/test_sec_webull_financials_notebook.py
git commit -m "feat: add SEC Webull beginner notebook"
```

---

### Task 9: Document, Harden CI, and Add Manual Live Smoke Testing

**Files:**
- Create: `docs/06-sec-webull-financials-th.md`
- Create: `.github/workflows/sec-webull-live-smoke.yml`
- Modify: `README.md`
- Modify: `notebooks/README.md`
- Modify: `docs/00-learning-path-th.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `llms.txt`
- Modify: `.gitignore`
- Modify: `tests/test_repository_contract.py`
- Modify: `tests/test_docs_links.py`

- [ ] **Step 1: Write failing repository and documentation contract tests**

Add assertions for:

```python
def test_sec_webull_learning_assets_are_linked():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    notebooks = (root / "notebooks" / "README.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")

    assert "sec_webull_financials_beginner.ipynb" in readme
    assert "sec_webull_financials_beginner.ipynb" in notebooks
    assert "SEC_CONTACT_EMAIL" in agents
    assert "order" in agents.lower() and "read-only" in agents.lower()


def test_private_sec_cache_is_gitignored():
    root = Path(__file__).resolve().parents[1]
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert "data/private/" in gitignore
    assert "outputs/" in gitignore
```

- [ ] **Step 2: Run contract tests and confirm failure**

```bash
python -m pytest tests/test_repository_contract.py tests/test_docs_links.py -v
```

Expected: new notebook and SEC references are absent from documentation.

- [ ] **Step 3: Write the Thai guide and update navigation**

`docs/06-sec-webull-financials-th.md` must include:

- Goal: combine filed SEC statements with Webull daily prices.
- Core concepts: ticker, CIK, XBRL tag, 10-K, 10-Q, period end, filed date, annual, quarterly,
  YTD, reported, derived, and look-ahead bias.
- Working command: `webull-lab company-data AAPL --years 5`.
- Notebook workflow: offline first, then optional live mode.
- Exercise: compare AAPL revenue growth with post-filing price behavior without claiming
  causality or future predictability.
- Rubric: source provenance, period correctness, unit correctness, timing correctness, and
  reproducibility.
- Common mistakes: zero-filling missing facts, mixing units, treating YTD as a quarter,
  aligning prices to period end, and committing credentials.
- Real-world transfer: watchlist batch ingestion only after the single-ticker acceptance tests
  pass.

Add links to the guide and notebook from README, notebook index, learning path, `llms.txt`, and
the AI guide files. State in `AGENTS.md` that SEC financial code is read-only and must not weaken
existing order guardrails.

- [ ] **Step 4: Add a manual live smoke workflow**

```yaml
# .github/workflows/sec-webull-live-smoke.yml
name: SEC Webull Live Smoke

on:
  workflow_dispatch:
    inputs:
      ticker:
        description: US ticker
        required: true
        default: AAPL

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install -e ".[dev]"
      - name: Run live read-only pipeline
        env:
          SEC_CONTACT_EMAIL: ${{ secrets.SEC_CONTACT_EMAIL }}
          WEBULL_APP_KEY: ${{ secrets.WEBULL_APP_KEY }}
          WEBULL_APP_SECRET: ${{ secrets.WEBULL_APP_SECRET }}
        run: webull-lab company-data "${{ inputs.ticker }}" --years 5 --output-dir outputs/live-smoke
      - uses: actions/upload-artifact@v4
        with:
          name: sec-webull-live-smoke
          path: outputs/live-smoke/run_manifest.json
          if-no-files-found: error
```

The workflow must contain no order command and must never print environment variables.

- [ ] **Step 5: Run the complete local verification suite**

```bash
python scripts/build_sec_webull_financials_notebook.py
git diff --exit-code notebooks/sec_webull_financials_beginner.ipynb
python -m pytest -q
python -m ruff check .
git diff --check
git grep -nE '(WEBULL_APP_KEY|WEBULL_APP_SECRET|WEBULL_ACCOUNT_ID)=[A-Za-z0-9_./+-]{12,}' -- ':!*.example' ':!docs/*' ':!tests/*' || true
git grep -nE 'SEC_CONTACT_EMAIL=[^y][^o][^u][^r]' -- ':!*.example' ':!docs/*' ':!tests/*' || true
```

Expected:

- notebook regeneration produces no diff;
- all tests pass;
- Ruff reports `All checks passed!`;
- `git diff --check` returns no output;
- secret scans return no real credential matches.

- [ ] **Step 6: Perform the local CLI acceptance test**

Run SEC-only mode with a monitored email supplied in the shell environment:

```bash
SEC_CONTACT_EMAIL="your-monitored-email@example.com" \
  webull-lab company-data AAPL --years 5 --output-dir data/private/acceptance/AAPL
```

Expected: `run_manifest.json` reports `sec_status: available`; `webull_status` is `unavailable`
when Webull credentials are absent; all three statement formats and raw SEC JSON exist.

If approved Webull production credentials and OpenAPI market-data permission are available,
run the same command with local environment variables and verify `webull_status: available`.
Do not paste credentials into the shell history; load them from the ignored `.env` file.

- [ ] **Step 7: Commit documentation and workflow hardening**

```bash
git add README.md notebooks/README.md docs/00-learning-path-th.md docs/06-sec-webull-financials-th.md AGENTS.md CLAUDE.md llms.txt .gitignore .github/workflows/sec-webull-live-smoke.yml tests/test_repository_contract.py tests/test_docs_links.py
git commit -m "docs: publish SEC Webull financial data workflow"
```

---

## Final Review Gate

- [ ] Confirm `git status --short` is clean.
- [ ] Confirm the branch contains only the planned commits.
- [ ] Review every use of `filed_date`, `period_type`, `unit`, and `derived` against the design.
- [ ] Confirm no default code path calls Webull order APIs.
- [ ] Confirm SEC-only mode works without Webull credentials.
- [ ] Confirm notebook and CI run offline without network or secrets.
- [ ] Confirm the manual live workflow uploads only the manifest, not raw private data.
- [ ] Request code review before merging or pushing to `main`.
