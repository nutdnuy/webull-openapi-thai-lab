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
