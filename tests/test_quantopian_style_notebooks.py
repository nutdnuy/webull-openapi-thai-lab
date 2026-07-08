import ast
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_quantopian_style_notebooks.py"
NOTEBOOK_DIR = ROOT / "notebooks" / "quantopian_style"
CODE_EXPLANATION_MARKER = "### โค้ดช่องถัดไปทำอะไร"

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

FORBIDDEN_ORDER_PATHS = (
    "/openapi/trade/order/place",
    "/openapi/trade/order/replace",
    "/openapi/trade/order/cancel",
    "place_order",
    "replace_order",
    "cancel_order",
)


def load_notebook(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return source


def notebook_text(notebook: dict) -> str:
    return "\n".join(cell_source(cell) for cell in notebook["cells"])


def code_text(notebook: dict) -> str:
    return "\n".join(
        cell_source(cell) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )


def test_quantopian_style_builder_is_deterministic(tmp_path):
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--out-dir", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == (
        NOTEBOOK_DIR / "README.md"
    ).read_text(encoding="utf-8")

    for filename in NOTEBOOKS:
        assert load_notebook(tmp_path / filename) == load_notebook(NOTEBOOK_DIR / filename)


def test_quantopian_style_notebooks_have_contract():
    for filename in NOTEBOOKS:
        path = NOTEBOOK_DIR / filename
        notebook = load_notebook(path)
        text = notebook_text(notebook)
        code = code_text(notebook)

        assert notebook["nbformat"] == 4
        assert len(notebook["cells"]) >= 7
        assert "QuantopianDoc" in text
        assert "Webull Market Data" in text
        assert "https://developer.webull.com/apis/docs/market-data-api/getting-started" in text
        assert "https://github.com/nutdnuy/quantopiandoc/tree/main" in text
        assert "WEBULL_QUANTOPIAN_LIVE" in text
        assert CODE_EXPLANATION_MARKER in text
        assert "historical results" in text.lower() or "historical backtest" in text.lower()

        for forbidden in FORBIDDEN_ORDER_PATHS:
            assert forbidden not in code

        assert "WEBULL_APP_SECRET =" not in text
        assert "WEBULL_ACCOUNT_ID =" not in text

        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] != "code":
                continue
            assert cell.get("execution_count") is None
            assert cell.get("outputs") == []
            ast.parse(cell_source(cell), filename=f"{filename} cell {index}")


def test_quantopian_style_notebooks_execute_offline(tmp_path, monkeypatch):
    for key in os.environ:
        if key.startswith("WEBULL_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WEBULL_QUANTOPIAN_LIVE", "0")
    monkeypatch.setenv("WEBULL_QUANTOPIAN_OUTPUT_DIR", str(tmp_path / "quantopian-style"))

    for filename in NOTEBOOKS:
        notebook = load_notebook(NOTEBOOK_DIR / filename)
        namespace: dict[str, object] = {}

        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] != "code":
                continue
            exec(compile(cell_source(cell), f"{filename} cell {index}", "exec"), namespace)

        output_dir = namespace["OUTPUT_DIR"]
        assert isinstance(output_dir, Path)
        assert output_dir.exists()
        assert list(output_dir.glob("*.json")), filename
        assert list(output_dir.glob("*.html")), filename


def test_quantopian_style_readme_links_exist():
    readme = (NOTEBOOK_DIR / "README.md").read_text(encoding="utf-8")

    for filename in NOTEBOOKS:
        assert f"]({filename})" in readme
        assert (NOTEBOOK_DIR / filename).is_file()

    assert "Webull Historical Bars" in readme
    assert "QuantopianDoc reference repo" in readme
