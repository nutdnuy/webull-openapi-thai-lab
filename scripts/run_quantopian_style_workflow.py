#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import time
import traceback
from contextlib import redirect_stdout
from pathlib import Path

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


def cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return str(source)


def execute_notebook(notebook_path: Path, output_root: Path) -> dict:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    slug = notebook_path.stem.replace("_", "-")
    output_dir = output_root / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    namespace: dict[str, object] = {}
    stdout = io.StringIO()
    started_at = time.perf_counter()
    status = "passed"
    error = ""

    os.environ["WEBULL_QUANTOPIAN_LIVE"] = "0"
    os.environ["WEBULL_QUANTOPIAN_OUTPUT_DIR"] = str(output_root)

    try:
        with redirect_stdout(stdout):
            for index, cell in enumerate(notebook["cells"]):
                if cell.get("cell_type") != "code":
                    continue
                code = cell_source(cell)
                compiled = compile(code, f"{notebook_path.name} cell {index}", "exec")
                exec(compiled, namespace)
    except Exception:
        status = "failed"
        error = traceback.format_exc()

    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    (output_dir / "stdout.txt").write_text(stdout.getvalue(), encoding="utf-8")
    if error:
        (output_dir / "error.txt").write_text(error, encoding="utf-8")

    json_files = sorted(path.name for path in output_dir.glob("*.json"))
    html_files = sorted(path.name for path in output_dir.glob("*.html"))
    csv_files = sorted(path.name for path in output_dir.glob("*.csv"))

    return {
        "notebook": notebook_path.name,
        "slug": slug,
        "status": status,
        "elapsed_seconds": elapsed_seconds,
        "json_files": json_files,
        "html_files": html_files,
        "csv_files": csv_files,
        "stdout": f"{slug}/stdout.txt",
        "error": f"{slug}/error.txt" if error else "",
    }


def run(notebook_dir: Path, output_dir: Path) -> int:
    if os.getenv("WEBULL_QUANTOPIAN_LIVE") == "1":
        print(
            "run_quantopian_style_workflow refuses WEBULL_QUANTOPIAN_LIVE=1 in CI-safe mode",
            file=sys.stderr,
        )
        return 2

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [execute_notebook(notebook_dir / filename, output_dir) for filename in NOTEBOOKS]
    manifest = {
        "name": "Webull Quantopian-Style Results",
        "live_mode": False,
        "notebook_count": len(results),
        "passed_count": sum(item["status"] == "passed" for item in results),
        "failed_count": sum(item["status"] != "passed" for item in results),
        "notebooks": results,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["failed_count"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Quantopian-style notebooks and collect outputs."
    )
    parser.add_argument("--notebook-dir", default="notebooks/quantopian_style")
    parser.add_argument("--output-dir", default="site/quantopian-style/results")
    args = parser.parse_args()
    return run(Path(args.notebook_dir), Path(args.output_dir))


if __name__ == "__main__":
    raise SystemExit(main())
