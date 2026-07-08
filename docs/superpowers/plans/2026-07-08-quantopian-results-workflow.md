# Quantopian Results Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GitHub workflow that runs the Webull Quantopian-style notebooks for real in offline-safe mode, publishes the generated research outputs as a GitHub Pages dashboard, and stores the raw results as Actions artifacts.

**Architecture:** Keep notebook source files clean and unexecuted, then add a separate deterministic runner that executes every Quantopian-style notebook into `site/quantopian-style/results/`. A small dashboard builder reads the generated JSON/HTML outputs and creates static pages that GitHub Pages can host without secrets or live Webull credentials.

**Tech Stack:** Python 3.11, pandas, Plotly, pytest, Ruff, GitHub Actions, GitHub Pages static artifact deployment.

---

## File Structure

- Create `scripts/run_quantopian_style_workflow.py`: execute the nine Quantopian-style notebooks offline, capture stdout/errors, and write a machine-readable manifest to `site/quantopian-style/results/manifest.json`.
- Create `scripts/build_quantopian_style_dashboard.py`: read the manifest and generated notebook outputs, then build `site/index.html`, `site/quantopian-style/index.html`, and `site/quantopian-style/results-summary.json`.
- Create `.github/workflows/quantopian-style-results.yml`: run tests, execute the notebooks, upload raw results, upload the static site artifact, and deploy to GitHub Pages on `main`.
- Create `tests/test_quantopian_style_workflow.py`: verify runner output, dashboard output, workflow YAML contract, no live Webull mode, and no order endpoint paths.
- Modify `README.md`: add the results workflow badge/link and explain where to view GitHub Pages outputs.
- Modify `notebooks/quantopian_style/README.md`: add a “Run Results Workflow” section with exact local and GitHub usage.
- Modify `llms.txt`: add the runner, dashboard builder, and workflow so Claude/Codex can find the actual runnable workflow.

## Scope

This plan does not call live Webull API or use credentials in CI. The workflow proves the research path is executable and produces real static artifacts from deterministic offline Webull-style OHLCV data. Live Webull runs remain a local opt-in through existing `WEBULL_QUANTOPIAN_LIVE=1` notebook support.

### Task 1: Offline Notebook Results Runner

**Files:**
- Create: `scripts/run_quantopian_style_workflow.py`
- Test: `tests/test_quantopian_style_workflow.py`

- [ ] **Step 1: Write failing runner tests**

Add this file:

```python
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_quantopian_style_workflow.py"
NOTEBOOK_DIR = ROOT / "notebooks" / "quantopian_style"

EXPECTED_NOTEBOOKS = [
    "01_research_environment.ipynb",
    "02_plotting_returns.ipynb",
    "03_autocorrelation_ar.ipynb",
    "04_regression_beta.ipynb",
    "05_pairs_trading.ipynb",
    "06_factor_ranking.ipynb",
    "07_portfolio_var_cvar.ipynb",
    "08_liquidity_slippage.ipynb",
    "09_overfitting_guardrails.ipynb",
]


def run_runner(output_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("WEBULL_"):
            env.pop(key)
    env["WEBULL_QUANTOPIAN_LIVE"] = "0"
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--notebook-dir",
            str(NOTEBOOK_DIR),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_quantopian_style_workflow_runner_executes_all_notebooks(tmp_path):
    output_dir = tmp_path / "results"
    result = run_runner(output_dir)

    assert result.returncode == 0, result.stderr
    manifest_path = output_dir / "manifest.json"
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["live_mode"] is False
    assert manifest["notebook_count"] == len(EXPECTED_NOTEBOOKS)
    assert [item["notebook"] for item in manifest["notebooks"]] == EXPECTED_NOTEBOOKS

    for item in manifest["notebooks"]:
        notebook_output = output_dir / item["slug"]
        assert notebook_output.is_dir()
        assert item["status"] == "passed"
        assert item["json_files"], item["slug"]
        assert item["html_files"], item["slug"]
        assert (notebook_output / "stdout.txt").is_file()


def test_quantopian_style_runner_refuses_live_mode(tmp_path):
    env = os.environ.copy()
    env["WEBULL_QUANTOPIAN_LIVE"] = "1"

    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--notebook-dir",
            str(NOTEBOOK_DIR),
            "--output-dir",
            str(tmp_path / "results"),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "refuses WEBULL_QUANTOPIAN_LIVE=1" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_quantopian_style_workflow.py -q
```

Expected: FAIL because `scripts/run_quantopian_style_workflow.py` does not exist.

- [ ] **Step 3: Implement the runner**

Create `scripts/run_quantopian_style_workflow.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import traceback
from contextlib import redirect_stdout
from pathlib import Path


NOTEBOOKS = [
    "01_research_environment.ipynb",
    "02_plotting_returns.ipynb",
    "03_autocorrelation_ar.ipynb",
    "04_regression_beta.ipynb",
    "05_pairs_trading.ipynb",
    "06_factor_ranking.ipynb",
    "07_portfolio_var_cvar.ipynb",
    "08_liquidity_slippage.ipynb",
    "09_overfitting_guardrails.ipynb",
]


def cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return str(source)


def execute_notebook(notebook_path: Path, output_root: Path) -> dict:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    slug = notebook_path.stem.replace("_", "-")
    output_dir = output_root / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    namespace: dict[str, object] = {}
    stdout = io.StringIO()
    started_at = time.perf_counter()
    status = "passed"
    error = ""

    os.environ["WEBULL_QUANTOPIAN_LIVE"] = "0"
    os.environ["WEBULL_QUANTOPIAN_OUTPUT_DIR"] = str(output_root)

    try:
        with redirect_stdout(stdout):
            for index, cell in enumerate(notebook["cells"]):
                if cell.get("cell_type") != "code":
                    continue
                code = cell_source(cell)
                compiled = compile(code, f"{notebook_path.name} cell {index}", "exec")
                exec(compiled, namespace)
    except Exception:
        status = "failed"
        error = traceback.format_exc()

    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    (output_dir / "stdout.txt").write_text(stdout.getvalue(), encoding="utf-8")
    if error:
        (output_dir / "error.txt").write_text(error, encoding="utf-8")

    json_files = sorted(path.name for path in output_dir.glob("*.json"))
    html_files = sorted(path.name for path in output_dir.glob("*.html"))
    csv_files = sorted(path.name for path in output_dir.glob("*.csv"))

    return {
        "notebook": notebook_path.name,
        "slug": slug,
        "status": status,
        "elapsed_seconds": elapsed_seconds,
        "json_files": json_files,
        "html_files": html_files,
        "csv_files": csv_files,
        "stdout": f"{slug}/stdout.txt",
        "error": f"{slug}/error.txt" if error else "",
    }


def run(notebook_dir: Path, output_dir: Path) -> int:
    if os.getenv("WEBULL_QUANTOPIAN_LIVE") == "1":
        print("run_quantopian_style_workflow refuses WEBULL_QUANTOPIAN_LIVE=1 in CI-safe mode", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    results = [execute_notebook(notebook_dir / filename, output_dir) for filename in NOTEBOOKS]
    manifest = {
        "name": "Webull Quantopian-Style Results",
        "live_mode": False,
        "notebook_count": len(results),
        "passed_count": sum(item["status"] == "passed" for item in results),
        "failed_count": sum(item["status"] != "passed" for item in results),
        "notebooks": results,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["failed_count"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Quantopian-style notebooks and collect outputs.")
    parser.add_argument("--notebook-dir", default="notebooks/quantopian_style")
    parser.add_argument("--output-dir", default="site/quantopian-style/results")
    args = parser.parse_args()
    return run(Path(args.notebook_dir), Path(args.output_dir))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_quantopian_style_workflow.py -q
```

Expected: PASS with 2 tests passing.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_quantopian_style_workflow.py tests/test_quantopian_style_workflow.py
git commit -m "feat: run quantopian style notebook results"
```

### Task 2: Static Dashboard Builder

**Files:**
- Create: `scripts/build_quantopian_style_dashboard.py`
- Modify: `tests/test_quantopian_style_workflow.py`

- [ ] **Step 1: Add failing dashboard tests**

Append to `tests/test_quantopian_style_workflow.py`:

```python
DASHBOARD = ROOT / "scripts" / "build_quantopian_style_dashboard.py"


def test_quantopian_style_dashboard_builds_static_site(tmp_path):
    output_dir = tmp_path / "site" / "quantopian-style" / "results"
    runner_result = run_runner(output_dir)
    assert runner_result.returncode == 0, runner_result.stderr

    dashboard_result = subprocess.run(
        [
            sys.executable,
            str(DASHBOARD),
            "--results-dir",
            str(output_dir),
            "--site-dir",
            str(tmp_path / "site"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert dashboard_result.returncode == 0, dashboard_result.stderr
    site_index = tmp_path / "site" / "index.html"
    research_index = tmp_path / "site" / "quantopian-style" / "index.html"
    summary_json = tmp_path / "site" / "quantopian-style" / "results-summary.json"

    assert site_index.is_file()
    assert research_index.is_file()
    assert summary_json.is_file()

    html = research_index.read_text(encoding="utf-8")
    assert "Webull Quantopian-Style Results" in html
    assert "01_research_environment.ipynb" in html
    assert "manifest.json" in html
    assert "live Webull trading calls: none" in html

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["passed_count"] == len(EXPECTED_NOTEBOOKS)
    assert summary["failed_count"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_quantopian_style_workflow.py::test_quantopian_style_dashboard_builds_static_site -q
```

Expected: FAIL because `scripts/build_quantopian_style_dashboard.py` does not exist.

- [ ] **Step 3: Implement the dashboard builder**

Create `scripts/build_quantopian_style_dashboard.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


STYLE = """
:root { color-scheme: dark; }
body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #121212; color: rgba(255,255,255,0.87); }
main { max-width: 1120px; margin: 0 auto; padding: 40px 20px 72px; }
a { color: #69F0AE; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 24px 0; }
.kpi, .card { background: #1D1D1D; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 16px; }
.kpi strong { display: block; font-size: 28px; color: #69F0AE; }
table { width: 100%; border-collapse: collapse; margin-top: 18px; }
th, td { border-bottom: 1px solid rgba(255,255,255,0.1); padding: 10px 8px; text-align: left; vertical-align: top; }
th { color: #03DAC6; font-weight: 650; }
.status-passed { color: #00E676; font-weight: 700; }
.status-failed { color: #FF5252; font-weight: 700; }
.muted { color: rgba(255,255,255,0.62); }
"""


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def artifact_links(item: dict, slug: str, key: str) -> str:
    links = []
    for filename in item[key]:
        url = f"results/{slug}/{html.escape(filename)}"
        links.append(f'<a href="{url}">{html.escape(filename)}</a>')
    return "<br>".join(links) if links else '<span class="muted">none</span>'


def build(results_dir: Path, site_dir: Path) -> None:
    manifest_path = results_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    passed = int(manifest["passed_count"])
    failed = int(manifest["failed_count"])
    rows = []
    for item in manifest["notebooks"]:
        slug = item["slug"]
        status_class = f"status-{html.escape(item['status'])}"
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['notebook'])}</td>"
            f"<td class=\"{status_class}\">{html.escape(item['status'])}</td>"
            f"<td>{item['elapsed_seconds']}</td>"
            f"<td>{artifact_links(item, slug, 'json_files')}</td>"
            f"<td>{artifact_links(item, slug, 'html_files')}</td>"
            f'<td><a href="results/{slug}/stdout.txt">stdout</a></td>'
            "</tr>"
        )

    research_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Webull Quantopian-Style Results</title>
  <style>{STYLE}</style>
</head>
<body>
  <main>
    <p><a href="../index.html">Home</a></p>
    <h1>Webull Quantopian-Style Results</h1>
    <p class="muted">Deterministic offline research run from Webull-style OHLCV sample data. live Webull trading calls: none.</p>
    <section class="kpis">
      <div class="kpi"><span>notebooks</span><strong>{manifest["notebook_count"]}</strong></div>
      <div class="kpi"><span>passed</span><strong>{passed}</strong></div>
      <div class="kpi"><span>failed</span><strong>{failed}</strong></div>
    </section>
    <section class="card">
      <h2>Run Outputs</h2>
      <p><a href="results/manifest.json">manifest.json</a> | <a href="results-summary.json">results-summary.json</a></p>
      <table>
        <thead><tr><th>Notebook</th><th>Status</th><th>Seconds</th><th>JSON</th><th>Charts</th><th>Log</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""

    home_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Webull OpenAPI Thai Lab</title>
  <style>{STYLE}</style>
</head>
<body>
  <main>
    <h1>Webull OpenAPI Thai Lab</h1>
    <p class="muted">Static research outputs generated by GitHub Actions.</p>
    <section class="card">
      <h2>Quantopian-Style Research Results</h2>
      <p>{passed} notebooks passed, {failed} notebooks failed.</p>
      <p><a href="quantopian-style/index.html">Open results dashboard</a></p>
    </section>
  </main>
</body>
</html>
"""

    summary = {
        "name": manifest["name"],
        "live_mode": manifest["live_mode"],
        "notebook_count": manifest["notebook_count"],
        "passed_count": passed,
        "failed_count": failed,
        "notebooks": [
            {
                "notebook": item["notebook"],
                "slug": item["slug"],
                "status": item["status"],
                "json_files": item["json_files"],
                "html_files": item["html_files"],
            }
            for item in manifest["notebooks"]
        ],
    }

    write(site_dir / "index.html", home_html)
    write(site_dir / "quantopian-style" / "index.html", research_html)
    write(
        site_dir / "quantopian-style" / "results-summary.json",
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
    )
    print(f"Wrote dashboard to {site_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build static dashboard for Quantopian-style results.")
    parser.add_argument("--results-dir", default="site/quantopian-style/results")
    parser.add_argument("--site-dir", default="site")
    args = parser.parse_args()
    build(Path(args.results_dir), Path(args.site_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run dashboard test to verify it passes**

Run:

```bash
python -m pytest tests/test_quantopian_style_workflow.py::test_quantopian_style_dashboard_builds_static_site -q
```

Expected: PASS with 1 test passing.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_quantopian_style_dashboard.py tests/test_quantopian_style_workflow.py
git commit -m "feat: build quantopian style results dashboard"
```

### Task 3: GitHub Actions Results Workflow

**Files:**
- Create: `.github/workflows/quantopian-style-results.yml`
- Modify: `tests/test_quantopian_style_workflow.py`

- [ ] **Step 1: Add failing workflow contract test**

Append to `tests/test_quantopian_style_workflow.py`:

```python
WORKFLOW = ROOT / ".github" / "workflows" / "quantopian-style-results.yml"


def test_quantopian_style_results_workflow_contract():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "name: Quantopian-Style Results" in workflow
    assert "workflow_dispatch:" in workflow
    assert "push:" in workflow
    assert "WEBULL_QUANTOPIAN_LIVE: \"0\"" in workflow
    assert "python scripts/run_quantopian_style_workflow.py" in workflow
    assert "python scripts/build_quantopian_style_dashboard.py" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "actions/upload-pages-artifact@v3" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "contents: read" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "/openapi/trade/order/place" not in workflow
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_quantopian_style_workflow.py::test_quantopian_style_results_workflow_contract -q
```

Expected: FAIL because `.github/workflows/quantopian-style-results.yml` does not exist.

- [ ] **Step 3: Add GitHub workflow**

Create `.github/workflows/quantopian-style-results.yml`:

```yaml
name: Quantopian-Style Results

on:
  workflow_dispatch:
  push:
    branches: [main]
    paths:
      - "notebooks/quantopian_style/**"
      - "scripts/build_quantopian_style_notebooks.py"
      - "scripts/run_quantopian_style_workflow.py"
      - "scripts/build_quantopian_style_dashboard.py"
      - "tests/test_quantopian_style_workflow.py"
      - ".github/workflows/quantopian-style-results.yml"

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

env:
  WEBULL_QUANTOPIAN_LIVE: "0"

jobs:
  build-results:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install package
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"

      - name: Verify tests
        run: |
          python -m ruff check .
          python -m pytest tests/test_quantopian_style_notebooks.py tests/test_quantopian_style_workflow.py -q

      - name: Run Quantopian-style notebooks
        run: |
          python scripts/run_quantopian_style_workflow.py \
            --notebook-dir notebooks/quantopian_style \
            --output-dir site/quantopian-style/results

      - name: Build static dashboard
        run: |
          python scripts/build_quantopian_style_dashboard.py \
            --results-dir site/quantopian-style/results \
            --site-dir site

      - name: Upload raw results artifact
        uses: actions/upload-artifact@v4
        with:
          name: quantopian-style-results
          path: site/quantopian-style/results

      - name: Upload GitHub Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build-results
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 4: Run workflow contract test**

Run:

```bash
python -m pytest tests/test_quantopian_style_workflow.py::test_quantopian_style_results_workflow_contract -q
```

Expected: PASS with 1 test passing.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/quantopian-style-results.yml tests/test_quantopian_style_workflow.py
git commit -m "ci: publish quantopian style results"
```

### Task 4: Documentation and LLM Map

**Files:**
- Modify: `README.md`
- Modify: `notebooks/quantopian_style/README.md`
- Modify: `llms.txt`
- Modify: `tests/test_quantopian_style_workflow.py`

- [ ] **Step 1: Add failing docs tests**

Append to `tests/test_quantopian_style_workflow.py`:

```python
def test_quantopian_style_results_docs_are_linked():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    notebook_readme = (NOTEBOOK_DIR / "README.md").read_text(encoding="utf-8")
    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")

    assert "Quantopian-Style Results" in readme
    assert "actions/workflows/quantopian-style-results.yml" in readme
    assert "GitHub Pages" in readme
    assert "python scripts/run_quantopian_style_workflow.py" in notebook_readme
    assert "python scripts/build_quantopian_style_dashboard.py" in notebook_readme
    assert "WEBULL_QUANTOPIAN_LIVE=0" in notebook_readme
    assert "scripts/run_quantopian_style_workflow.py" in llms
    assert "scripts/build_quantopian_style_dashboard.py" in llms
    assert ".github/workflows/quantopian-style-results.yml" in llms
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_quantopian_style_workflow.py::test_quantopian_style_results_docs_are_linked -q
```

Expected: FAIL because docs do not mention the new workflow yet.

- [ ] **Step 3: Update README**

Add this badge below the existing CI badge in `README.md`:

```markdown
[![Quantopian-Style Results](https://github.com/nutdnuy/webull-openapi-thai-lab/actions/workflows/quantopian-style-results.yml/badge.svg)](https://github.com/nutdnuy/webull-openapi-thai-lab/actions/workflows/quantopian-style-results.yml)
```

Add this section after the Quantopian-style notebook link block:

```markdown
## Quantopian-Style Results Workflow

GitHub Actions รันชุด Webull Quantopian-style notebooks แบบ offline-safe แล้ว publish เป็น static dashboard ผ่าน GitHub Pages:

- Workflow: [Quantopian-Style Results](https://github.com/nutdnuy/webull-openapi-thai-lab/actions/workflows/quantopian-style-results.yml)
- Results dashboard: `https://nutdnuy.github.io/webull-openapi-thai-lab/quantopian-style/`
- Raw artifact: เปิด workflow run ล่าสุด แล้วดาวน์โหลด artifact ชื่อ `quantopian-style-results`

ค่า CI ใช้ `WEBULL_QUANTOPIAN_LIVE=0` เสมอ จึงไม่มีการเรียก live Webull credential หรือ trading endpoint.
```

- [ ] **Step 4: Update notebook README**

Add this section to `notebooks/quantopian_style/README.md`:

```markdown
## Run Results Workflow

Local offline run:

```bash
WEBULL_QUANTOPIAN_LIVE=0 python scripts/run_quantopian_style_workflow.py \
  --notebook-dir notebooks/quantopian_style \
  --output-dir site/quantopian-style/results

python scripts/build_quantopian_style_dashboard.py \
  --results-dir site/quantopian-style/results \
  --site-dir site
```

Open `site/quantopian-style/index.html` to inspect the generated dashboard.

GitHub run:

1. Open Actions > Quantopian-Style Results.
2. Click Run workflow.
3. Wait for the deploy job to finish.
4. Open `https://nutdnuy.github.io/webull-openapi-thai-lab/quantopian-style/`.

The workflow forces `WEBULL_QUANTOPIAN_LIVE=0`, so it runs deterministic offline Webull-style data and does not use App Key, App Secret, token, account id, or order endpoints.
```

- [ ] **Step 5: Update llms.txt**

Add these lines to the notebook/workflow map in `llms.txt`:

```text
- scripts/run_quantopian_style_workflow.py — executes the Quantopian-style notebooks offline and writes static result artifacts.
- scripts/build_quantopian_style_dashboard.py — builds the GitHub Pages dashboard from generated Quantopian-style results.
- .github/workflows/quantopian-style-results.yml — GitHub Actions workflow that runs notebooks, uploads raw artifacts, and deploys GitHub Pages.
```

- [ ] **Step 6: Run docs test**

Run:

```bash
python -m pytest tests/test_quantopian_style_workflow.py::test_quantopian_style_results_docs_are_linked -q
```

Expected: PASS with 1 test passing.

- [ ] **Step 7: Commit**

```bash
git add README.md notebooks/quantopian_style/README.md llms.txt tests/test_quantopian_style_workflow.py
git commit -m "docs: document quantopian style results workflow"
```

### Task 5: Full Validation, Push, and Remote Run Check

**Files:**
- Modify only if validation finds a concrete defect in files from Tasks 1-4.

- [ ] **Step 1: Regenerate notebooks to prove determinism remains intact**

Run:

```bash
python scripts/build_quantopian_style_notebooks.py
```

Expected: command exits 0 and `git diff -- notebooks/quantopian_style` shows no content changes except the README section intentionally added in Task 4 if the builder does not yet include that section.

- [ ] **Step 2: If notebook README changed, update the builder template**

If Step 1 removes the “Run Results Workflow” section from `notebooks/quantopian_style/README.md`, add the same Markdown section to the README template inside `scripts/build_quantopian_style_notebooks.py`, rerun the builder, and confirm:

```bash
git diff -- notebooks/quantopian_style/README.md scripts/build_quantopian_style_notebooks.py
```

Expected: the generated README keeps the workflow section and the builder contains the same text.

- [ ] **Step 3: Run the actual local workflow**

Run:

```bash
rm -rf site
WEBULL_QUANTOPIAN_LIVE=0 python scripts/run_quantopian_style_workflow.py \
  --notebook-dir notebooks/quantopian_style \
  --output-dir site/quantopian-style/results
python scripts/build_quantopian_style_dashboard.py \
  --results-dir site/quantopian-style/results \
  --site-dir site
```

Expected:

```text
site/index.html exists
site/quantopian-style/index.html exists
site/quantopian-style/results/manifest.json exists
site/quantopian-style/results-summary.json exists
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_quantopian_style_notebooks.py tests/test_quantopian_style_workflow.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Run full validation**

Run:

```bash
python -m pytest -q
python -m ruff check .
git diff --check
```

Expected: pytest passes, Ruff prints `All checks passed!`, and `git diff --check` prints nothing.

- [ ] **Step 6: Secret and live-trading scan**

Run:

```bash
rg -n "WEBULL_APP_SECRET\\s*=|x-access-token|/openapi/trade/order/place|/openapi/trade/order/replace|/openapi/trade/order/cancel" . --glob '!*.png'
```

Expected: no real secret values and no order place/replace/cancel path in the new runner, dashboard, or workflow. Existing documentation may mention safety wording; confirm it is instructional only.

- [ ] **Step 7: Final commit if builder or validation fixes changed files**

Run:

```bash
git status --short
git add scripts/build_quantopian_style_notebooks.py notebooks/quantopian_style/README.md
git commit -m "fix: keep quantopian results docs generated"
```

Expected: commit only runs if Step 2 changed generated docs or builder code.

- [ ] **Step 8: Push**

Run:

```bash
git push origin main
```

Expected: push succeeds and GitHub starts both CI and Quantopian-Style Results workflows.

- [ ] **Step 9: Check remote workflow**

Run:

```bash
gh run list --repo nutdnuy/webull-openapi-thai-lab --limit 5
gh run view --repo nutdnuy/webull-openapi-thai-lab --log --exit-status
```

Expected: latest CI passes, latest Quantopian-Style Results run passes, raw artifact `quantopian-style-results` exists, and GitHub Pages deployment URL is available.

## Self-Review

- Spec coverage: The plan covers a real runner, static results, workflow artifact upload, GitHub Pages deployment, docs, LLM map, local validation, remote validation, and the safety requirement that CI must not use live Webull credentials or order endpoints.
- Placeholder scan: No task contains placeholder implementation language; every file creation step includes concrete code or exact Markdown/YAML.
- Type consistency: Test constants, script names, CLI flags, workflow path, output directories, and manifest fields match across tasks.
