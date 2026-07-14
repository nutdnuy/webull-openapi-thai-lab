# Claude Guide

Read `AGENTS.md` first. It is the shared source of truth for Claude, Codex,
and other coding assistants working in this repository.

Key reminders:

- This is a Thai educational Webull OpenAPI lab, not a production trading bot.
- Keep UAT as the default.
- Never expose or commit secrets, token files, account IDs, or private data.
- Keep order placement guarded; examples and CLI should focus on preview first.
- Read [the SEC + Webull financial guide](docs/06-sec-webull-financials-th.md) and
  [deterministic beginner notebook](notebooks/sec_webull_financials_beginner.ipynb)
  before changing `company-data`, its builder, or financial artifacts.
- The SEC workflow is read-only, requires `SEC_CONTACT_EMAIL`, supports SEC-only mode,
  and must never call order APIs or weaken order guardrails.
- Run `python -m pytest -q` and `python -m ruff check .` before pushing changes.
