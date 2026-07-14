from pathlib import Path

REQUIRED_FILES = [
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "llms.txt",
    "LICENSE",
    ".gitignore",
    ".env.example",
    "pyproject.toml",
]


def test_required_root_files_exist():
    root = Path(__file__).resolve().parents[1]
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    assert missing == []


def test_readme_mentions_uat_and_secret_safety():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "UAT" in readme
    assert "ห้าม commit" in readme
    assert "App Secret" in readme


def test_gitignore_excludes_webull_token_directory():
    root = Path(__file__).resolve().parents[1]
    gitignore = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".webull-token/" in gitignore


def test_ai_context_files_describe_safety_contract():
    root = Path(__file__).resolve().parents[1]
    agent_guide = (root / "AGENTS.md").read_text(encoding="utf-8")
    llms_txt = (root / "llms.txt").read_text(encoding="utf-8")

    assert "UAT" in agent_guide
    assert "Never commit real" in agent_guide
    assert "WEBULL_ALLOW_LIVE_ORDERS=I_UNDERSTAND" in agent_guide
    assert "AGENTS.md" in llms_txt


def test_sec_webull_learning_assets_are_linked():
    root = Path(__file__).resolve().parents[1]
    navigation_files = [
        "README.md",
        "notebooks/README.md",
        "docs/00-learning-path-th.md",
        "AGENTS.md",
        "CLAUDE.md",
        "llms.txt",
    ]

    for path in navigation_files:
        text = (root / path).read_text(encoding="utf-8")
        assert "docs/06-sec-webull-financials-th.md" in text or (
            path.startswith("docs/") and "06-sec-webull-financials-th.md" in text
        )
        assert "sec_webull_financials_beginner.ipynb" in text

    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "SEC_CONTACT_EMAIL" in agents
    assert "SEC-only" in agents
    assert "read-only" in agents.lower()
    assert "order APIs" in agents
    assert "must never weaken" in agents


def test_private_sec_cache_and_outputs_are_gitignored():
    root = Path(__file__).resolve().parents[1]
    gitignore = (root / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "data/private/" in gitignore
    assert "outputs/" in gitignore


def test_manual_live_smoke_is_read_only_and_uploads_only_manifest():
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github" / "workflows" / "sec-webull-live-smoke.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "default: AAPL" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "timeout-minutes:" in workflow
    assert "actions/checkout@v4" in workflow
    assert "actions/setup-python@v5" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert 'webull-lab company-data "${{ inputs.ticker }}"' in workflow
    assert "path: outputs/live-smoke/run_manifest.json" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "preview-stock-buy" not in workflow
    assert "place" not in workflow.lower()
    assert "printenv" not in workflow.lower()
    assert "env |" not in workflow.lower()
    assert "outputs/live-smoke/raw" not in workflow
