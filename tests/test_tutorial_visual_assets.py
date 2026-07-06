import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = ROOT / "notebooks"
ASSET_DIR = ROOT / "docs" / "assets" / "webull-openapi-quickstart"

VISUAL_ASSETS = (
    "01-cover.png",
    "02-api-overview.png",
    "03-app-key-secret.png",
    "04-claim-market-data.png",
    "05-access-token.png",
    "06-api-examples.png",
)

FULL_GALLERY_FILES = (
    ROOT / "README.md",
    NOTEBOOK_DIR / "README.md",
    NOTEBOOK_DIR / "webull_th_beginner.ipynb",
)

ENDPOINT_NOTEBOOK_IMAGES = {
    "00_auth_token.ipynb": ("01-cover.png", "03-app-key-secret.png", "05-access-token.png"),
    "01_stock_market_data.ipynb": (
        "02-api-overview.png",
        "04-claim-market-data.png",
        "06-api-examples.png",
    ),
    "02_screener_fundamentals.ipynb": (
        "02-api-overview.png",
        "04-claim-market-data.png",
        "06-api-examples.png",
    ),
    "03_watchlist_readonly.ipynb": ("02-api-overview.png", "06-api-examples.png"),
    "04_account_assets_order_query.ipynb": (
        "02-api-overview.png",
        "05-access-token.png",
        "06-api-examples.png",
    ),
    "05_order_preview_guardrails.ipynb": (
        "02-api-overview.png",
        "05-access-token.png",
        "06-api-examples.png",
    ),
}


def document_text(path: Path) -> str:
    if path.suffix == ".ipynb":
        notebook = json.loads(path.read_text(encoding="utf-8"))
        sources = []
        for cell in notebook["cells"]:
            source = cell.get("source", "")
            sources.append("".join(source) if isinstance(source, list) else source)
        return "\n".join(sources)

    return path.read_text(encoding="utf-8")


def markdown_image_paths(text: str) -> list[str]:
    return re.findall(r"!\[[^\]]*\]\(([^)]+webull-openapi-quickstart/[^)]+)\)", text)


def resolve_markdown_path(source_file: Path, image_path: str) -> Path:
    return (source_file.parent / image_path).resolve()


def test_visual_assets_exist_and_are_png():
    for filename in VISUAL_ASSETS:
        path = ASSET_DIR / filename
        assert path.is_file(), filename
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), filename


def test_visual_quick_start_image_links_resolve():
    documents = (
        ROOT / "README.md",
        NOTEBOOK_DIR / "README.md",
        NOTEBOOK_DIR / "webull_th_beginner.ipynb",
        *(NOTEBOOK_DIR / filename for filename in ENDPOINT_NOTEBOOK_IMAGES),
    )

    for document in documents:
        text = document_text(document)
        image_paths = markdown_image_paths(text)
        assert image_paths, document.name
        for image_path in image_paths:
            assert resolve_markdown_path(document, image_path).is_file(), image_path


def test_beginner_and_indexes_show_full_visual_gallery():
    for document in FULL_GALLERY_FILES:
        text = document_text(document)
        assert "Visual Quick Start" in text
        for filename in VISUAL_ASSETS:
            assert filename in text, f"{document.name} missing {filename}"


def test_endpoint_notebooks_show_relevant_visual_guides():
    for notebook_name, expected_images in ENDPOINT_NOTEBOOK_IMAGES.items():
        text = document_text(NOTEBOOK_DIR / notebook_name)
        assert "## Visual Quick Start" in text
        for filename in expected_images:
            assert filename in text, f"{notebook_name} missing {filename}"
