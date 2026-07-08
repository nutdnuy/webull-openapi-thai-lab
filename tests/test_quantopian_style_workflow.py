import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_quantopian_style_workflow.py"
DASHBOARD = ROOT / "scripts" / "build_quantopian_style_dashboard.py"
WORKFLOW = ROOT / ".github" / "workflows" / "quantopian-style-results.yml"
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


def test_quantopian_style_workflow_runner_removes_stale_artifacts(tmp_path):
    output_dir = tmp_path / "results"
    stale_dir = output_dir / "01-research-environment"
    stale_dir.mkdir(parents=True)
    stale_file = stale_dir / "stale.html"
    stale_file.write_text("old output", encoding="utf-8")

    result = run_runner(output_dir)

    assert result.returncode == 0, result.stderr
    assert not stale_file.exists()
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    first_notebook = manifest["notebooks"][0]
    assert "stale.html" not in first_notebook["html_files"]


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
    assert "offline_webull_style_prices.csv" in html

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["passed_count"] == len(EXPECTED_NOTEBOOKS)
    assert summary["failed_count"] == 0
    assert summary["notebooks"][0]["csv_files"] == ["offline_webull_style_prices.csv"]


def test_quantopian_style_results_workflow_contract():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "name: Quantopian-Style Results" in workflow
    assert "workflow_dispatch:" in workflow
    assert "push:" in workflow
    assert 'WEBULL_QUANTOPIAN_LIVE: "0"' in workflow
    assert "python scripts/run_quantopian_style_workflow.py" in workflow
    assert "python scripts/build_quantopian_style_dashboard.py" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v3" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "contents: read" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "/openapi/trade/order/place" not in workflow
    assert "/openapi/trade/order/replace" not in workflow
    assert "/openapi/trade/order/cancel" not in workflow
    assert "${{ secrets." not in workflow


def test_quantopian_style_runtime_files_do_not_use_trading_or_secrets():
    files = [
        RUNNER,
        DASHBOARD,
        WORKFLOW,
        ROOT / "README.md",
        NOTEBOOK_DIR / "README.md",
        ROOT / "llms.txt",
    ]
    forbidden_terms = [
        "/openapi/trade/order/place",
        "/openapi/trade/order/replace",
        "/openapi/trade/order/cancel",
        "place_order",
        "replace_order",
        "cancel_order",
        "${{ secrets.",
    ]

    for path in files:
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            assert term not in text, f"{path} contains {term}"


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
