from pathlib import Path

DOCS = [
    "docs/00-learning-path-th.md",
    "docs/01-api-key-setup-th.md",
    "docs/02-first-call-th.md",
    "docs/03-market-data-th.md",
    "docs/04-order-preview-and-guardrails-th.md",
    "docs/05-ai-assisted-webull-dev-th.md",
    "docs/06-sec-webull-financials-th.md",
    "docs/99-publishing-github-th.md",
]

COMMANDS = [
    "webull-lab doctor",
    "webull-lab account-list",
    "webull-lab stock-snapshot AAPL",
    "webull-lab preview-stock-buy AAPL 100 1",
    "webull-lab company-data AAPL --years 5",
]

DEEP_LINKS = [
    "https://developer.webull.com/apis/docs/sdk/",
    "https://developer.webull.com/apis/docs/market-data-api/overview/",
    "https://developer.webull.com/apis/docs/trade-api/overview/",
    "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
    "https://developer.webull.com/apis/docs/market-data-api/getting-started/",
    "https://developer.webull.com/apis/docs/reference/broker-market-data-api/bars-using-get/",
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


def test_sec_webull_guide_meets_educational_contract():
    root = Path(__file__).resolve().parents[1]
    guide = (root / "docs/06-sec-webull-financials-th.md").read_text(encoding="utf-8")

    required_terms = [
        "เป้าหมาย",
        "ticker",
        "CIK",
        "XBRL tag",
        "10-K",
        "10-Q",
        "period end",
        "filed date",
        "annual",
        "quarterly",
        "YTD",
        "reported",
        "derived",
        "unit",
        "provenance",
        "look-ahead",
        "incompatible_unit",
        "missing",
        "not_meaningful",
        "forward-adjusted",
        "SEC-only",
        "run_manifest.json",
        "แบบฝึกหัด",
        "เกณฑ์",
        "ข้อผิดพลาด",
        "watchlist",
    ]
    for term in required_terms:
        assert term in guide

    assert "offline" in guide.lower()
    assert "optional live" in guide.lower()
    assert "ไม่สามารถทำนาย" in guide or "ไม่รับประกัน" in guide
    assert "single-ticker" in guide
    assert "webull-lab company-data AAPL --years 5" in guide
    assert "next trading session" in guide
    assert "acceptance timestamp" in guide
    assert "market-session" in guide


def test_documented_local_markdown_links_resolve():
    root = Path(__file__).resolve().parents[1]
    documents = [root / path for path in DOCS] + [
        root / "README.md",
        root / "notebooks/README.md",
        root / "AGENTS.md",
        root / "CLAUDE.md",
        root / "llms.txt",
    ]

    import re

    for document in documents:
        text = document.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            resolved = (document.parent / target.split("#", 1)[0]).resolve()
            assert resolved.exists(), f"Broken link in {document}: {target}"


def test_current_sandbox_host_is_used_in_learning_docs():
    root = Path(__file__).resolve().parents[1]
    learning_path = (root / "docs/00-learning-path-th.md").read_text(encoding="utf-8")

    assert "api.sandbox.webull.com" in learning_path
    assert "us-openapi-alb.uat.webullbroker.com" not in learning_path
