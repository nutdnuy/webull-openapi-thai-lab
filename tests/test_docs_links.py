from pathlib import Path

DOCS = [
    "docs/00-learning-path-th.md",
    "docs/01-api-key-setup-th.md",
    "docs/02-first-call-th.md",
    "docs/03-market-data-th.md",
    "docs/04-order-preview-and-guardrails-th.md",
    "docs/05-ai-assisted-webull-dev-th.md",
    "docs/99-publishing-github-th.md",
]

COMMANDS = [
    "webull-lab doctor",
    "webull-lab account-list",
    "webull-lab stock-snapshot AAPL",
    "webull-lab preview-stock-buy AAPL 100 1",
]

DEEP_LINKS = [
    "https://developer.webull.com/apis/docs/sdk/",
    "https://developer.webull.com/apis/docs/market-data-api/overview/",
    "https://developer.webull.com/apis/docs/trade-api/overview/",
]


def test_required_docs_exist_and_are_thai_first():
    root = Path(__file__).resolve().parents[1]
    for doc in DOCS:
        text = (root / doc).read_text(encoding="utf-8")
        assert "# " in text
        assert "Webull" in text
        assert any(ch in text for ch in "กขคงจฉชซญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหอฮ")


def test_docs_reference_official_webull_sources():
    root = Path(__file__).resolve().parents[1]
    combined = "\n".join((root / doc).read_text(encoding="utf-8") for doc in DOCS)

    assert "https://developer.webull.com/apis/docs/" in combined
    assert "https://developer.webull.com/apis/llms.txt" in combined
    assert "https://github.com/webull-inc/webull-openapi-python-sdk" in combined


def test_readme_learning_path_targets_exist():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")

    for doc in DOCS:
        assert f"]({doc})" in readme
        assert (root / doc).is_file()


def test_docs_mention_current_cli_commands():
    root = Path(__file__).resolve().parents[1]
    combined = "\n".join((root / doc).read_text(encoding="utf-8") for doc in DOCS)

    for command in COMMANDS:
        assert command in combined


def test_docs_do_not_reference_removed_examples_directory():
    root = Path(__file__).resolve().parents[1]
    combined = "\n".join((root / doc).read_text(encoding="utf-8") for doc in DOCS)

    assert "examples/" not in combined


def test_docs_reference_relevant_official_deep_links():
    root = Path(__file__).resolve().parents[1]
    combined = "\n".join((root / doc).read_text(encoding="utf-8") for doc in DOCS)

    for link in DEEP_LINKS:
        assert link in combined
