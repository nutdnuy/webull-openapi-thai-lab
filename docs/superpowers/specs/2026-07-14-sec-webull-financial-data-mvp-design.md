# SEC EDGAR + Webull Financial Data MVP Design

**Date:** 2026-07-14  
**Status:** Approved in conversation; pending written-spec review  
**Repository:** `nutdnuy/webull-openapi-thai-lab`

## 1. Objective

Extend the existing Thai Webull learning repository with a read-only, beginner-friendly
pipeline that accepts one US equity ticker and produces auditable financial statements from
SEC EDGAR plus daily historical prices from Webull.

The MVP must let a new user run one command or one Jupyter notebook and obtain:

- normalized income statement, balance sheet, and cash-flow data;
- daily Webull OHLCV data when Webull credentials and market-data permission are available;
- a small set of reproducible financial and valuation metrics;
- CSV, Parquet, and JSON artifacts with source provenance; and
- an offline demonstration that requires no credentials.

This remains an educational research workflow. It must not place, modify, or cancel orders.

## 2. Scope

### Included

- One ticker per run, with `AAPL` as the documented example.
- Five years of data by default, configurable by the caller.
- SEC ticker-to-CIK resolution.
- SEC Submissions and Company Facts/XBRL retrieval.
- Reported 10-K and 10-Q facts for the three primary financial statements.
- Webull daily historical prices through the existing official-SDK client boundary.
- Canonical metric mapping with retained XBRL provenance.
- A CLI orchestration command.
- One Thai, end-to-end beginner notebook with offline and optional live modes.
- Offline unit, fixture, contract, CLI, and notebook tests in GitHub Actions.

### Excluded from the MVP

- Batch watchlists or full-market ingestion.
- Intraday or streaming prices.
- Real-time dashboards.
- Full filing-document parsing, footnotes, tables, or narrative extraction.
- Forecasting, alpha claims, portfolio construction, or trading automation.
- Any order, position, or account mutation.
- A production database or cloud scheduler.

Batch watchlists are the intended first extension after the single-ticker pipeline is stable.

## 3. Chosen Approach

Add SEC EDGAR support to `webull-openapi-thai-lab` rather than create a second repository.
This reuses the repository's Python package, safe configuration, official Webull SDK wrapper,
offline fixtures, deterministic notebook builders, tests, CI, and Thai learning path.

SEC EDGAR is the source of truth for filed financial statements. Webull is the source for
historical market prices. Webull fundamentals may be explored later but must not silently
replace SEC-filed facts in this pipeline.

## 4. User Experience

### CLI

The primary interface is:

```bash
webull-lab company-data AAPL --years 5 --output-dir data/private/AAPL
```

Expected behavior:

1. Validate and normalize the ticker.
2. Resolve its SEC CIK.
3. Fetch or reuse cached SEC JSON.
4. normalize statements and provenance;
5. fetch Webull daily bars when live mode is configured;
6. compute metrics only when their required inputs exist; and
7. write a manifest describing success, partial success, missing fields, and output files.

The command succeeds with a documented partial-result status when SEC data is available but
Webull is not configured. Invalid tickers, malformed upstream responses, and unusable output
directories are hard failures with actionable messages.

### Beginner notebook

Add `notebooks/sec_webull_financials_beginner.ipynb`, generated from a deterministic builder.
Every code cell must have a preceding Thai explanation containing:

- what the next cell does;
- what output the learner should expect; and
- the common failure or interpretation risk for that step.

The notebook learning sequence is:

1. Explain the different roles of SEC EDGAR and Webull.
2. Check the environment and choose offline or live mode.
3. Enter and validate a ticker.
4. Resolve ticker to CIK.
5. Retrieve SEC Company Facts and filing metadata.
6. Build the three statements.
7. Retrieve Webull daily prices if available.
8. Compute selected ratios and growth metrics.
9. Plot financial trends against price.
10. Export and inspect the artifacts and provenance.

Offline mode uses committed, synthetic or carefully reduced fixtures and must execute from top
to bottom without network access or credentials. Live mode is opt-in and uses local `.env`
configuration that is already excluded from Git.

## 5. Architecture

### Components

| Component | Responsibility | Dependencies |
|---|---|---|
| `sec_client.py` | SEC HTTP client, headers, retry, cache, CIK lookup, Submissions and Company Facts retrieval | HTTP client, local cache |
| `financials.py` | Select facts, map canonical metrics, distinguish periods, deduplicate filings, retain provenance | SEC response models |
| `market_data.py` | Existing Webull client boundary for normalized daily OHLCV retrieval | Official Webull SDK |
| `company_pipeline.py` | Orchestrate SEC, Webull, metrics, partial-result behavior, and artifact manifest | SEC, financials, market data, exports |
| `metrics.py` | Pure functions for growth, profitability, leverage, and valuation calculations | Normalized statements and price alignment |
| `exports.py` | Deterministic CSV, Parquet, JSON, and manifest writing | pandas/Parquet engine |
| `cli.py` | Expose `company-data` without changing order guardrails | Pipeline |
| notebook builder | Generate the Thai beginner notebook reproducibly | Public package interfaces |

Each component must expose typed, testable interfaces. HTTP and SDK response parsing stays out
of the CLI and notebook. Metric calculations must not perform network access.

### Data flow

```text
ticker
  -> SEC ticker map -> zero-padded CIK
  -> SEC Submissions + Company Facts -> cached raw JSON
  -> fact selection + canonical mapping -> normalized statements + provenance
  -> Webull daily bars -> normalized OHLCV, or explicit unavailable status
  -> date alignment + pure metric calculations
  -> CSV / Parquet / JSON / manifest
  -> CLI summary and beginner notebook charts
```

## 6. Financial Data Model and Integrity Rules

### Canonical statements

The initial canonical metric set should stay small and widely useful.

- Income statement: revenue, gross profit when reported, operating income, net income, basic
  EPS, and diluted EPS.
- Balance sheet: cash and equivalents, current assets, total assets, current liabilities,
  total liabilities, debt when reported, and stockholders' equity.
- Cash flow: operating cash flow, capital expenditure when reported, investing cash flow,
  financing cash flow, and dividends paid when reported.

Each normalized observation must retain:

- ticker and CIK;
- canonical metric and original taxonomy/tag;
- value and unit;
- start and end dates when supplied;
- form, fiscal year, fiscal period, filed date, frame, and accession number; and
- whether the observation was reported directly or derived.

### Selection and deduplication

- Limit the primary statement outputs to facts associated with 10-K, 10-Q, and their amended
  forms where relevant.
- Keep the latest filed observation for the same canonical metric, fiscal period, duration,
  and unit while preserving the displaced observation in provenance or diagnostics.
- Do not assume every issuer uses the same US-GAAP tag. Canonical mappings may list ordered
  candidate tags, but the chosen source tag must remain visible.
- Do not replace missing values with zero.
- Do not combine incompatible units.
- Keep annual, discrete quarterly, and year-to-date observations distinct.
- A quarterly value derived from a year-to-date value must be explicitly labeled `derived` and
  calculated only when comparable prior cumulative observations are available.

### Timing and look-ahead controls

- A filing-derived observation becomes available on its SEC `filed` date, not its period end.
- Price-based valuation metrics must use a price on or after the filed date according to a
  documented alignment rule.
- The output must retain both period end and information-availability date.
- Restated or amended values must not be treated as if they were known before their filed date.

## 7. Initial Metrics

Calculate a metric only when compatible inputs are available:

- revenue growth;
- diluted EPS growth;
- gross margin when gross profit is reported;
- operating margin;
- net margin;
- return on equity, with the averaging convention documented;
- debt-to-equity;
- operating cash-flow growth;
- free cash flow using operating cash flow less capital expenditure when both are available;
- price-to-earnings using diluted EPS; and
- price-to-book when share-price and per-share/book inputs can be formed without hidden
  assumptions.

Every metric row must record its formula, input periods, information-availability date, and a
status such as `available`, `missing_input`, `incompatible_unit`, or `not_meaningful`.

## 8. Output Contract

For ticker `AAPL`, the default output directory contains:

```text
data/private/AAPL/
  raw/
    sec_submissions.json
    sec_companyfacts.json
  income_statement.csv
  income_statement.parquet
  balance_sheet.csv
  balance_sheet.parquet
  cash_flow.csv
  cash_flow.parquet
  prices.csv
  prices.parquet
  financial_metrics.csv
  financial_metrics.parquet
  company_snapshot.json
  run_manifest.json
```

`run_manifest.json` records the ticker, CIK, run timestamp, requested period, source statuses,
cache status, missing metrics, warnings, and generated paths. The directory remains Git-ignored.
Small sanitized fixtures used by tests live separately under `tests/fixtures/`.

## 9. API, Caching, and Failure Behavior

### SEC EDGAR

- Send a descriptive `User-Agent` with a configurable contact email.
- Use bounded timeouts, retry with exponential backoff and jitter for retryable failures, and
  respect upstream throttling responses.
- Cache raw responses locally and expose whether data came from cache.
- Treat ticker-not-found, malformed schema, and missing company facts as distinct errors.
- Prefer SEC bulk archives only for future batch ingestion; the single-ticker MVP uses the
  public JSON endpoints.

### Webull

- Use the official SDK through the existing client factory.
- Keep sandbox/test behavior as the development default and live market data opt-in.
- Respect the documented Market Data HTTP limit of 300 requests per 60 seconds.
- Explain authentication, HTTP 403, and missing OpenAPI non-display market-data permission
  separately.
- If Webull is unavailable, continue with SEC outputs and record `webull_status: unavailable`
  rather than fabricating price data.
- Never expose application keys, secrets, access tokens, signed headers, or account IDs in
  logs, exceptions, artifacts, fixtures, notebooks, or CI output.

## 10. Testing and CI

### Offline tests

- Ticker normalization and ticker-to-CIK mapping.
- SEC request headers, timeout, cache, retry, and error classification using fakes.
- XBRL tag candidates, units, annual/quarterly/YTD separation, amendments, and deduplication.
- Derived-quarter calculations and their provenance labels.
- Metric formulas, missing-input statuses, and filed-date price alignment.
- Webull response normalization and partial-result behavior.
- Deterministic output schemas and manifest contents.
- CLI success, partial success, and hard-failure cases.
- Deterministic notebook generation and clean top-to-bottom offline execution.
- Secret scans covering source, notebooks, fixtures, outputs, and documentation.

### Contract and live checks

- Offline contract tests assert the minimum SEC and Webull fields the parsers require.
- An optional manual GitHub Actions workflow may run a live smoke test when explicitly enabled
  and supplied with repository secrets.
- Normal pull-request CI must never require network access or real Webull credentials.

### Acceptance criteria

The MVP is accepted when:

1. `webull-lab company-data AAPL --years 5` produces the documented artifact set from offline
   fixtures and produces live SEC results when network access is enabled.
2. The beginner notebook executes offline from top to bottom and teaches the same public
   pipeline used by the CLI.
3. SEC-only output remains useful when Webull credentials or permission are absent.
4. Every financial observation and calculated metric is traceable to its inputs and filing
   availability date.
5. Unit tests, Ruff, notebook tests, deterministic regeneration, and secret scans pass in CI.
6. Existing Webull order guardrails and tests remain unchanged and passing.

## 11. Documentation Changes During Implementation

- Add the new notebook to the root README and `notebooks/README.md` learning path.
- Add a Thai lesson explaining SEC EDGAR, CIK, XBRL, filing dates, and the difference between
  reported and derived facts.
- Extend `.env.example` with a non-secret SEC contact-email setting.
- Update `AGENTS.md`, `CLAUDE.md`, and `llms.txt` with the new read-only pipeline map.
- Cite official SEC EDGAR API and Webull Market Data documentation near implementation-specific
  constraints.

## 12. Official References

- SEC EDGAR APIs: <https://www.sec.gov/search-filings/edgar-application-programming-interfaces>
- SEC Privacy and Security Policy: <https://www.sec.gov/about/privacy-information/security-policy>
- Webull OpenAPI overview: <https://developer.webull.com/apis/docs/about-open-api/>
- Webull SDKs and environments: <https://developer.webull.com/apis/docs/sdk/>
- Webull Market Data overview: <https://developer.webull.com/apis/docs/market-data-api/overview/>
- Webull Market Data getting started: <https://developer.webull.com/apis/docs/market-data-api/getting-started/>

## 13. Implementation Sequence

After this written design is approved, create a separate implementation plan. The expected
delivery sequence is SEC client and fixtures, financial normalization, exports, metrics and
timing rules, orchestration CLI, deterministic beginner notebook, documentation, then full CI
and live manual smoke verification.
