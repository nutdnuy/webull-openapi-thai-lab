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
