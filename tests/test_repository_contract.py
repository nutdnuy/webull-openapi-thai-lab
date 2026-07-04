from pathlib import Path


REQUIRED_FILES = [
    "README.md",
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
