import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_endpoint_notebooks.py"
NOTEBOOK_DIR = ROOT / "notebooks"

ENDPOINT_NOTEBOOKS = {
    "00_auth_token.ipynb": (
        "Create Token",
        "Check Token",
        "/openapi/auth/token/create",
        "/openapi/auth/token/check",
    ),
    "01_stock_market_data.ipynb": (
        "Tick",
        "Snapshot",
        "Quotes",
        "Footprint",
        "Historical Bars",
        "/openapi/market-data/stock/bars",
    ),
    "02_screener_fundamentals.ipynb": (
        "Gainers & Losers",
        "Top Active",
        "Company Profile",
        "Analyst Target Price",
        "Analyst Rating",
    ),
    "03_watchlist_readonly.ipynb": (
        "Get Watchlist",
        "Get Watchlist Instruments",
        "read-only",
    ),
    "04_account_assets_order_query.ipynb": (
        "Account List",
        "Account Balance",
        "Account Positions",
        "Order History",
        "Open Order",
        "Order Detail",
    ),
    "05_order_preview_guardrails.ipynb": (
        "Order Preview",
        "/openapi/trade/order/preview",
        "no Place, Replace, or Cancel",
    ),
}

WEBULL_CREDENTIAL_ENV_VARS = (
    "WEBULL_APP_KEY",
    "WEBULL_APP_SECRET",
    "WEBULL_ACCESS_TOKEN",
    "WEBULL_REFRESH_TOKEN",
    "WEBULL_TOKEN",
    "WEBULL_TOKEN_DIR",
    "WEBULL_ACCOUNT_ID",
    "WEBULL_TUTORIAL_APP_KEY",
    "WEBULL_TUTORIAL_APP_SECRET",
    "WEBULL_TUTORIAL_ACCESS_TOKEN",
)

FORBIDDEN_LIVE_ORDER_PATHS = (
    "/openapi/trade/order/place",
    "/openapi/trade/order/replace",
    "/openapi/trade/order/cancel",
)
CODE_EXPLANATION_MARKER = "### โค้ดช่องถัดไปทำอะไร"

HARDCODED_APP_SECRET_PATTERN = re.compile(
    r"""(?im)^\s*(?:os\.environ\[\s*["']WEBULL_APP_SECRET["']\s*\]|(?:WEBULL_)?APP_SECRET)\s*=\s*["'][^"']+["']"""
)
HARDCODED_ACCOUNT_ID_PATTERN = re.compile(
    r"""(?im)^\s*(?:os\.environ\[\s*["']WEBULL_ACCOUNT_ID["']\s*\]|(?:WEBULL_)?ACCOUNT_ID)\s*=\s*["'][^"']+["']"""
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


def assert_code_cells_have_plain_thai_explanations(notebook: dict, notebook_name: str) -> None:
    cells = notebook["cells"]
    code_cell_count = sum(1 for cell in cells if cell["cell_type"] == "code")
    explanation_count = notebook_text(notebook).count(CODE_EXPLANATION_MARKER)
    assert explanation_count == code_cell_count

    for index, cell in enumerate(cells):
        if cell["cell_type"] != "code":
            continue
        assert index > 0, f"{notebook_name} code cell {index} has no explanation"
        assert cells[index - 1]["cell_type"] != "code"
        previous = cells[index - 1]
        previous_source = cell_source(previous)
        assert previous["cell_type"] == "markdown"
        assert CODE_EXPLANATION_MARKER in previous_source
        assert previous_source.count("- ") >= 3


def endpoint_notebook_paths() -> list[Path]:
    return [NOTEBOOK_DIR / filename for filename in ENDPOINT_NOTEBOOKS]


def test_endpoint_notebook_builder_is_deterministic(tmp_path):
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

    for notebook_path in endpoint_notebook_paths():
        generated = load_notebook(tmp_path / notebook_path.name)
        committed = load_notebook(notebook_path)
        assert generated == committed


def test_endpoint_notebooks_have_expected_contract():
    for notebook_path in endpoint_notebook_paths():
        notebook = load_notebook(notebook_path)
        raw = notebook_path.read_text(encoding="utf-8")
        text = notebook_text(notebook)
        code = code_text(notebook)

        assert notebook["nbformat"] == 4
        assert len(notebook["cells"]) >= 14
        assert "api.webull.co.th" in text
        assert "HMAC-SHA256" in text
        assert "WEBULL_TUTORIAL_LIVE" in text
        assert "https://developer.webull.co.th/apis/docs/reference/" in text

        for required_term in ENDPOINT_NOTEBOOKS[notebook_path.name]:
            assert required_term in text

        assert "x-app-secret" not in raw.lower()
        assert not HARDCODED_APP_SECRET_PATTERN.search(text)
        assert not HARDCODED_ACCOUNT_ID_PATTERN.search(text)

        for forbidden_path in FORBIDDEN_LIVE_ORDER_PATHS:
            assert forbidden_path not in code

        assert_code_cells_have_plain_thai_explanations(notebook, notebook_path.name)

        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] == "code":
                assert cell.get("execution_count") is None
                assert cell.get("outputs") == []
                ast.parse(cell_source(cell), filename=f"{notebook_path.name} cell {index}")


def test_endpoint_notebooks_execute_top_to_bottom_offline(tmp_path, monkeypatch):
    for key in WEBULL_CREDENTIAL_ENV_VARS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WEBULL_TUTORIAL_LIVE", "0")
    monkeypatch.setenv("WEBULL_TUTORIAL_OUTPUT_DIR", str(tmp_path / "endpoint-output"))

    for notebook_path in endpoint_notebook_paths():
        notebook = load_notebook(notebook_path)
        namespace: dict[str, object] = {}

        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] != "code":
                continue
            source = cell_source(cell)
            exec(compile(source, f"{notebook_path.name} cell {index}", "exec"), namespace)

        output_dir = namespace["OUTPUT_DIR"]
        assert isinstance(output_dir, Path)
        assert output_dir.exists()
        assert list(output_dir.glob("*.json")), notebook_path.name


def test_endpoint_notebook_index_links_exist():
    readme = (NOTEBOOK_DIR / "README.md").read_text(encoding="utf-8")

    for filename in ENDPOINT_NOTEBOOKS:
        assert f"]({filename})" in readme
        assert (NOTEBOOK_DIR / filename).is_file()

    assert "webull_th_beginner.ipynb" in readme
