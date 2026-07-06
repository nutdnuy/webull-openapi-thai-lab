import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_webull_th_beginner_notebook.py"
NOTEBOOK = ROOT / "notebooks" / "webull_th_beginner.ipynb"

FORBIDDEN_SECRET_FRAGMENTS = (
    "FAKE_WEBULL_APP_SECRET_CANARY_DO_NOT_USE_0001",
    "FAKE_WEBULL_APP_SECRET_CANARY_DO_NOT_USE_0002",
    "FAKE_WEBULL_APP_SECRET_CANARY_DO_NOT_USE_0003",
    "FAKE_WEBULL_APP_SECRET_CANARY_DO_NOT_USE_0004",
)
ORDERED_MARKDOWN_SECTION_MARKERS = (
    "Webull Thailand OpenAPI",
    "Source Notes",
    "Outline",
    "Step 1 - Setup",
    "Step 2 - Credentials",
    "Step 3 - Token",
    "Step 4 - Signature",
    "Step 5 - Fetch AAPL Bars",
    "Step 6 - Save Raw JSON",
    "Step 7 - Plot Close",
    "Exercises",
    "Common Pitfalls",
)
REQUIRED_TERMS = (
    "Audience",
    "Prerequisites",
    "Learning goals",
    "https://developer.webull.co.th/apis/docs/webull-open-api-reference/",
    "https://developer.webull.co.th/apis/docs/authentication/signature",
    "https://developer.webull.co.th/apis/docs/authentication/token",
    "https://developer.webull.co.th/apis/docs/market-data-api/data-api",
    "HMAC-SHA256",
    "x-access-token",
    "api.webull.co.th",
    "WEBULL_TUTORIAL_LIVE",
)
WEBULL_CREDENTIAL_ENV_VARS = (
    "WEBULL_APP_KEY",
    "WEBULL_APP_SECRET",
    "WEBULL_ACCESS_TOKEN",
    "WEBULL_REFRESH_TOKEN",
    "WEBULL_TOKEN",
    "WEBULL_TOKEN_DIR",
    "WEBULL_TUTORIAL_APP_KEY",
    "WEBULL_TUTORIAL_APP_SECRET",
    "WEBULL_TUTORIAL_ACCESS_TOKEN",
)
HARDCODED_APP_SECRET_PATTERN = re.compile(
    r"""(?im)^\s*(?:os\.environ\[\s*["']WEBULL_APP_SECRET["']\s*\]|(?:WEBULL_)?APP_SECRET)\s*=\s*["'][^"']+["']"""
)


def load_notebook(path: Path = NOTEBOOK) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return source


def notebook_text(notebook: dict) -> str:
    return "\n".join(cell_source(cell) for cell in notebook["cells"])


def markdown_headings(notebook: dict) -> list[str]:
    headings = []
    for cell in notebook["cells"]:
        if cell["cell_type"] != "markdown":
            continue
        for line in cell_source(cell).splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                headings.append(stripped.lstrip("#").strip())
    return headings


def assert_notebook_shape(notebook: dict) -> None:
    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) >= 16
    assert notebook["cells"][0]["cell_type"] == "markdown"
    assert "Webull Thailand OpenAPI" in cell_source(notebook["cells"][0])


def assert_beginner_learning_flow(notebook: dict) -> None:
    headings = markdown_headings(notebook)
    text = notebook_text(notebook)
    previous_index = -1

    for marker in ORDERED_MARKDOWN_SECTION_MARKERS:
        matching_indexes = [
            index
            for index, heading in enumerate(headings)
            if marker in heading and index > previous_index
        ]
        assert matching_indexes, f"Missing ordered markdown section: {marker}"
        previous_index = matching_indexes[0]

    for term in REQUIRED_TERMS:
        assert term in text


def assert_notebook_clean_and_compile(
    notebook: dict,
    raw: str,
    source_name: str = "webull_th_beginner.ipynb",
) -> None:
    text = notebook_text(notebook)

    for fragment in FORBIDDEN_SECRET_FRAGMENTS:
        assert fragment not in raw

    assert "x-app-secret" not in raw.lower()
    assert not HARDCODED_APP_SECRET_PATTERN.search(text)

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            assert cell.get("execution_count") is None
            assert cell.get("outputs") == []
            ast.parse(cell_source(cell), filename=f"{source_name} cell {index}")


def assert_notebook_contract(notebook: dict, raw: str, source_name: str) -> None:
    assert_notebook_shape(notebook)
    assert_beginner_learning_flow(notebook)
    assert_notebook_clean_and_compile(notebook, raw, source_name)


def test_builder_creates_beginner_notebook(tmp_path):
    output = tmp_path / "webull_th_beginner.ipynb"

    result = subprocess.run(
        [sys.executable, str(BUILDER), "--out", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    notebook = load_notebook(output)
    assert notebook == load_notebook()
    assert_notebook_contract(notebook, output.read_text(encoding="utf-8"), str(output))


def test_notebook_has_beginner_learning_flow():
    notebook = load_notebook()
    assert_notebook_shape(notebook)
    assert_beginner_learning_flow(notebook)


def test_notebook_cells_are_clean_and_compile():
    notebook = load_notebook()
    raw = NOTEBOOK.read_text(encoding="utf-8")
    assert_notebook_clean_and_compile(notebook, raw)


def test_notebook_executes_top_to_bottom_offline(tmp_path, monkeypatch):
    notebook = load_notebook()
    namespace: dict[str, object] = {}

    for key in WEBULL_CREDENTIAL_ENV_VARS:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("WEBULL_TUTORIAL_LIVE", "0")
    monkeypatch.setenv("WEBULL_TUTORIAL_OUTPUT_DIR", str(tmp_path / "webull-output"))

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = cell_source(cell)
        exec(compile(source, f"webull_th_beginner.ipynb cell {index}", "exec"), namespace)

    output_dir = Path(os.environ["WEBULL_TUTORIAL_OUTPUT_DIR"])
    assert (output_dir / "aapl-bars-raw.json").exists()
    assert (output_dir / "aapl-close-chart.html").exists()

    bars = json.loads((output_dir / "aapl-bars-raw.json").read_text(encoding="utf-8"))
    assert len(bars) == 8
    assert bars[-1]["symbol"] == "AAPL"
