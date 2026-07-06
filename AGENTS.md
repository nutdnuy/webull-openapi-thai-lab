# Agent Guide

This repository is a Thai learning lab for the Webull OpenAPI Python SDK.
It is educational code, not a production trading system.

## First Read

When an AI assistant receives only the GitHub link, read these files in order:

1. `README.md` for the course overview, install steps, and learning path.
2. `docs/00-learning-path-th.md` for the Thai lesson sequence.
3. `.env.example` for configuration names without secrets.
4. `src/webull_lab/config.py` for environment loading and redaction rules.
5. `src/webull_lab/orders.py` before changing anything related to orders.

## Project Intent

- Teach Thai users how to start with Webull OpenAPI safely.
- Keep UAT as the default environment.
- Separate read-only account calls, market data calls, and order workflows.
- Demonstrate order preview first; live order placement must remain guarded.
- Make the repository easy for Claude, Codex, and other coding assistants to inspect.

## Safety Rules

- Never commit real `WEBULL_APP_KEY`, `WEBULL_APP_SECRET`, tokens, account IDs, `.env`,
  `.webull-token/`, private data, or screenshots containing credentials.
- Keep all examples safe for UAT by default.
- Do not add a CLI command that places live orders by default.
- `place_stock_limit_buy` must stay blocked unless
  `WEBULL_ALLOW_LIVE_ORDERS=I_UNDERSTAND` is set explicitly.
- Do not print raw secrets or raw account IDs in logs, errors, docs, or tests.
- Treat investment/trading content as education and risk-aware workflow design, not
  return prediction.

## Repository Map

- `README.md` - user-facing landing page and quick start.
- `docs/` - Thai tutorial lessons.
- `notebooks/webull_th_beginner.ipynb` - beginner AAPL close price notebook for `api.webull.co.th`.
- `notebooks/README.md` - endpoint-split notebook learning order.
- `notebooks/00_auth_token.ipynb` through `notebooks/05_order_preview_guardrails.ipynb` - endpoint-focused notebooks with offline samples and guarded live mode.
- `scripts/build_webull_th_beginner_notebook.py` - source builder for regenerating the notebook.
- `scripts/build_endpoint_notebooks.py` - source builder for regenerating endpoint-split notebooks.
- `src/webull_lab/config.py` - `.env` loading, UAT/prod endpoint selection, secret redaction.
- `src/webull_lab/clients.py` - Webull SDK client factories.
- `src/webull_lab/account.py` - read-only account helper functions.
- `src/webull_lab/market_data.py` - market data helper functions.
- `src/webull_lab/orders.py` - preview and guarded live-order helper functions.
- `src/webull_lab/cli.py` - `webull-lab` Typer CLI.
- `tests/` - offline tests with fake clients; tests should not require real Webull credentials.

## Common Commands

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

```bash
python -m pytest -q
python -m ruff check .
webull-lab doctor
webull-lab account-list
webull-lab stock-snapshot AAPL
webull-lab preview-stock-buy AAPL 100 1
```

## Development Rules

- Prefer small, direct changes that match the existing module boundaries.
- Add or update offline fake-client tests for behavior changes.
- Update Thai docs when changing user-facing behavior.
- Keep public examples minimal and copy-paste friendly.
- Use structured SDK/helper calls rather than stringly typed shortcuts where possible.
- If Webull official docs or SDK behavior changed, cite the official source in docs.

## Expected Verification

Before pushing meaningful changes:

```bash
python -m pytest -q
python -m ruff check .
git grep -nE '(WEBULL_APP_KEY|WEBULL_APP_SECRET|WEBULL_ACCOUNT_ID)=[A-Za-z0-9_./+-]{12,}' -- ':!*.example' ':!docs/*' ':!tests/*' || true
```

The grep command should return no real credentials.

## Official Sources

- Webull API Docs: https://developer.webull.com/apis/docs/
- Webull `llms.txt`: https://developer.webull.com/apis/llms.txt
- Webull Python SDK: https://github.com/webull-inc/webull-openapi-python-sdk
