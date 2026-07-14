import ast
import copy
import json
import os
import runpy
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from webull_lab.financials import build_financial_statements
from webull_lab.tutorial_fixtures import FixtureDataClient, FixtureResponse, FixtureSecClient

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_sec_webull_financials_notebook.py"
NOTEBOOK = ROOT / "notebooks" / "sec_webull_financials_beginner.ipynb"
FIXTURE_ROOT = ROOT / "tests" / "fixtures"
REQUIRED_HEADINGS = [
    "SEC EDGAR + Webull",
    "กลุ่มผู้เรียน",
    "สิ่งที่ต้องเตรียม",
    "เป้าหมายการเรียนรู้",
    "ลำดับบทเรียน",
    "Core Concepts",
    "Workflow",
    "Step 1 - Setup",
    "Step 2 - Ticker to CIK",
    "Step 3 - Financial Statements",
    "Step 4 - Webull Prices",
    "Step 5 - Metrics",
    "Step 6 - Charts",
    "Step 7 - Export",
    "Common Mistakes",
    "Exercise",
    "เฉลยตั้งต้น",
    "Checklist",
    "นำไปใช้กับงานจริง",
]
EXPECTED_ARTIFACTS = {
    "balance_sheet.csv",
    "balance_sheet.parquet",
    "cash_flow.csv",
    "cash_flow.parquet",
    "company_snapshot.json",
    "financial_metrics.csv",
    "financial_metrics.parquet",
    "income_statement.csv",
    "income_statement.parquet",
    "prices.csv",
    "prices.parquet",
    "raw/sec_companyfacts.json",
    "raw/sec_submissions.json",
    "run_manifest.json",
    "sec-webull-financials-chart.html",
}


def source(cell):
    value = cell.get("source", "")
    return "".join(value) if isinstance(value, list) else value


def load(path=NOTEBOOK):
    return json.loads(path.read_text(encoding="utf-8"))


def execute_notebook(notebook, namespace=None):
    namespace = {} if namespace is None else namespace
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            exec(compile(source(cell), f"notebook cell {index}", "exec"), namespace)
    return namespace


def test_builder_is_deterministic_idempotent_and_notebook_compiles(tmp_path):
    first = tmp_path / "first.ipynb"
    second = tmp_path / "second.ipynb"
    for output in (first, second):
        result = subprocess.run(
            [sys.executable, str(BUILDER), "--out", str(output)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    committed_bytes = NOTEBOOK.read_bytes()
    assert first.read_bytes() == second.read_bytes() == committed_bytes

    subprocess.run(
        [sys.executable, str(BUILDER)], cwd=ROOT, check=True, capture_output=True, text=True
    )
    assert NOTEBOOK.read_bytes() == committed_bytes

    notebook = load()
    text = "\n".join(source(cell) for cell in notebook["cells"])
    for heading in REQUIRED_HEADINGS:
        assert heading in text

    code_cells = 0
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        code_cells += 1
        assert cell["outputs"] == []
        assert cell["execution_count"] is None
        ast.parse(source(cell), filename=f"notebook cell {index}")
        assert index > 0
        assert notebook["cells"][index - 1]["cell_type"] == "markdown"
        assert "### โค้ดช่องถัดไปทำอะไร" in source(notebook["cells"][index - 1])
        assert index < 2 or notebook["cells"][index - 1]["cell_type"] != "code"

    assert text.count("### โค้ดช่องถัดไปทำอะไร") == code_cells
    assert all(
        not (
            notebook["cells"][index]["cell_type"] == "code"
            and notebook["cells"][index + 1]["cell_type"] == "code"
        )
        for index in range(len(notebook["cells"]) - 1)
    )


def test_fixture_clients_validate_inputs_and_do_not_mutate_payloads(tmp_path):
    sec_dir = FIXTURE_ROOT / "sec"
    bars_path = FIXTURE_ROOT / "webull" / "aapl_daily_bars_sample.json"
    sec_client = FixtureSecClient(sec_dir)
    data_client = FixtureDataClient(bars_path)

    assert sec_client.resolve_cik(" aapl ") == "0000320193"
    submissions = sec_client.get_submissions("0000320193")
    companyfacts = sec_client.get_companyfacts("320193")
    bars = data_client.market_data.get_history_bar("AAPL", "US_STOCK", "D").json()
    originals = copy.deepcopy((submissions, companyfacts, bars))

    submissions["name"] = "changed"
    companyfacts["entityName"] = "changed"
    bars[0]["close"] = "0"
    assert sec_client.get_submissions("0000320193") == originals[0]
    assert sec_client.get_companyfacts("0000320193") == originals[1]
    assert data_client.market_data.get_history_bar("AAPL", "US_STOCK", "D").json() == originals[2]
    assert originals[1] == json.loads(
        (sec_dir / "aapl_companyfacts_tutorial.json").read_text(encoding="utf-8")
    )

    with pytest.raises(ValueError, match="AAPL only"):
        sec_client.resolve_cik("MSFT")
    for method in (sec_client.get_submissions, sec_client.get_companyfacts):
        with pytest.raises(ValueError, match="CIK"):
            method("0000789019")
    with pytest.raises(ValueError, match="AAPL daily US stock bars only"):
        data_client.market_data.get_history_bar("MSFT", "US_STOCK", "D")
    with pytest.raises(ValueError, match="AAPL daily US stock bars only"):
        data_client.market_data.get_history_bar("AAPL", "CRYPTO", "D")
    with pytest.raises(ValueError, match="AAPL daily US stock bars only"):
        data_client.market_data.get_history_bar("AAPL", "US_STOCK", "M1")

    missing = tmp_path / "missing"
    with pytest.raises(ValueError, match="fixture directory"):
        FixtureSecClient(missing)
    with pytest.raises(ValueError, match="bars fixture"):
        FixtureDataClient(missing / "bars.json")


def test_tutorial_fixture_derives_total_debt_from_matched_components():
    payload = json.loads(
        (FIXTURE_ROOT / "sec" / "aapl_companyfacts_tutorial.json").read_text(
            encoding="utf-8"
        )
    )

    balance = build_financial_statements("AAPL", "320193", payload)[
        "balance_sheet"
    ]
    debt = balance.loc[balance["canonical_metric"] == "debt"].set_index(
        "fiscal_year"
    )

    assert debt["value"].to_dict() == {
        2023: 105_103_000_000,
        2024: 96_662_000_000,
    }
    assert debt["derived"].tolist() == [True, True]
    assert set(debt["source_tag"]) == {
        "LongTermDebtCurrent + LongTermDebtNoncurrent"
    }


def test_notebook_executes_offline_top_to_bottom_without_network_or_credentials(
    tmp_path, monkeypatch
):
    output = tmp_path / "output"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEC_WEBULL_TUTORIAL_LIVE", "0")
    monkeypatch.setenv("SEC_WEBULL_TUTORIAL_OUTPUT_DIR", str(output))
    monkeypatch.setenv("WEBULL_APP_KEY", "hostile-key-that-must-not-be-read")
    monkeypatch.setenv("WEBULL_APP_SECRET", "hostile-secret-that-must-not-be-read")
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "hostile@example.invalid")

    def block_network(*args, **kwargs):
        raise AssertionError("offline notebook attempted network access")

    monkeypatch.setattr(socket, "create_connection", block_network)
    monkeypatch.setattr("requests.sessions.Session.request", block_network)
    monkeypatch.setattr(
        "webull_lab.cli.build_optional_data_client",
        lambda: (_ for _ in ()).throw(AssertionError("offline mode inspected Webull config")),
    )
    monkeypatch.setattr(
        "webull_lab.sec_config.load_sec_settings",
        lambda: (_ for _ in ()).throw(AssertionError("offline mode inspected SEC config")),
    )

    namespace = execute_notebook(load())

    actual = {
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    }
    assert actual == EXPECTED_ARTIFACTS
    assert namespace["CIK"] == "0000320193"
    assert namespace["manifest"]["webull_status"] == "available"
    annual_income = namespace["statements"]["income_statement"].query(
        "period_type == 'annual'"
    )
    assert set(annual_income["fiscal_year"]) == {2023, 2024}
    assert {
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "diluted_eps",
    }.issubset(set(annual_income["canonical_metric"]))
    assert set(annual_income.loc[annual_income["canonical_metric"] == "diluted_eps", "unit"]) == {
        "USD/shares"
    }
    assert set(annual_income["source_taxonomy"]) == {"us-gaap"}
    assert set(annual_income["accession_number"]) == {
        "0000320193-23-000106",
        "0000320193-24-000123",
    }
    annual_balance = namespace["statements"]["balance_sheet"].query(
        "period_type == 'annual'"
    )
    assert {"stockholders_equity", "debt"}.issubset(
        set(annual_balance["canonical_metric"])
    )
    annual_cash_flow = namespace["statements"]["cash_flow"].query(
        "period_type == 'annual'"
    )
    assert {"operating_cash_flow", "capital_expenditure"}.issubset(
        set(annual_cash_flow["canonical_metric"])
    )
    assert set(namespace["exercise_answer"]["fiscal_year"]) == {2023, 2024}
    assert set(namespace["exercise_answer"]["canonical_metric"]) == {
        "revenue",
        "net_income",
    }
    assert set(
        namespace["exercise_answer"][["fiscal_year", "canonical_metric"]].itertuples(
            index=False, name=None
        )
    ) == {
        (2023, "revenue"),
        (2023, "net_income"),
        (2024, "revenue"),
        (2024, "net_income"),
    }
    available = set(
        namespace["metrics"].loc[
            namespace["metrics"]["status"] == "available", "metric"
        ]
    )
    assert {
        "revenue_growth",
        "gross_margin",
        "operating_margin",
        "roe",
        "free_cash_flow",
        "pe",
    }.issubset(available)
    persisted_manifest = json.loads(
        (output / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert persisted_manifest == namespace["manifest"]
    assert persisted_manifest["notebook_artifacts"] == [
        "sec-webull-financials-chart.html"
    ]
    assert "sec-webull-financials-chart.html" in persisted_manifest["files"]
    assert all((output / relative).is_file() for relative in persisted_manifest["files"])
    chart = (output / "sec-webull-financials-chart.html").read_text(encoding="utf-8")
    assert "plotly.js" in chart.lower()
    assert '<script src="https://cdn.plot.ly' not in chart


def test_live_mode_continues_sec_only_when_optional_webull_initialization_fails(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "output"
    secret_marker = "live-webull-secret-marker"
    fixture_sec_client = FixtureSecClient(FIXTURE_ROOT / "sec")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEC_WEBULL_TUTORIAL_LIVE", "1")
    monkeypatch.setenv("SEC_WEBULL_TUTORIAL_OUTPUT_DIR", str(output))
    monkeypatch.setattr("webull_lab.sec_config.load_sec_settings", lambda: object())
    monkeypatch.setattr("webull_lab.sec_client.SecClient", lambda settings: fixture_sec_client)
    monkeypatch.setattr(
        "webull_lab.cli.build_optional_data_client",
        lambda: (_ for _ in ()).throw(RuntimeError(secret_marker)),
    )

    namespace = execute_notebook(load())

    captured = capsys.readouterr()
    assert namespace["LIVE_MODE"] is True
    assert namespace["manifest"]["sec_status"] == "available"
    assert namespace["manifest"]["webull_status"] == "unavailable"
    assert secret_marker not in captured.out
    assert secret_marker not in captured.err
    assert all(
        secret_marker not in path.read_text(encoding="utf-8", errors="ignore")
        for path in output.rglob("*")
        if path.is_file()
    )


def test_live_mode_supports_non_aapl_ticker_consistently(tmp_path, monkeypatch):
    output = tmp_path / "output"
    companyfacts = json.loads(
        (FIXTURE_ROOT / "sec" / "aapl_companyfacts_tutorial.json").read_text(
            encoding="utf-8"
        )
    )
    companyfacts["cik"] = 789019
    companyfacts["entityName"] = "Microsoft Corporation"
    submissions = json.loads(
        (FIXTURE_ROOT / "sec" / "aapl_submissions_sample.json").read_text(
            encoding="utf-8"
        )
    )
    submissions["cik"] = "0000789019"
    submissions["name"] = "Microsoft Corporation"
    submissions["tickers"] = ["MSFT"]
    bars = json.loads(
        (FIXTURE_ROOT / "webull" / "aapl_daily_bars_sample.json").read_text(
            encoding="utf-8"
        )
    )
    for bar in bars:
        bar["symbol"] = "MSFT"

    class StubSecClient:
        def resolve_cik(self, ticker):
            assert ticker == "MSFT"
            return "0000789019"

        def get_submissions(self, cik):
            assert cik == "0000789019"
            return copy.deepcopy(submissions)

        def get_companyfacts(self, cik):
            assert cik == "0000789019"
            return copy.deepcopy(companyfacts)

    class StubMarketData:
        def get_history_bar(self, symbol, category, timespan):
            assert (symbol, category, timespan) == ("MSFT", "US_STOCK", "D")
            return FixtureResponse(bars)

    class StubDataClient:
        market_data = StubMarketData()

    stub_sec_client = StubSecClient()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEC_WEBULL_TUTORIAL_LIVE", "1")
    monkeypatch.setenv("SEC_WEBULL_TUTORIAL_TICKER", "MSFT")
    monkeypatch.setenv("SEC_WEBULL_TUTORIAL_OUTPUT_DIR", str(output))
    monkeypatch.setattr("webull_lab.sec_config.load_sec_settings", lambda: object())
    monkeypatch.setattr("webull_lab.sec_client.SecClient", lambda settings: stub_sec_client)
    monkeypatch.setattr("webull_lab.cli.build_optional_data_client", StubDataClient)

    namespace = execute_notebook(load())

    assert namespace["TICKER"] == "MSFT"
    assert namespace["CIK"] == "0000789019"
    assert namespace["manifest"]["ticker"] == "MSFT"
    assert set(namespace["prices"]["symbol"]) == {"MSFT"}
    chart = (output / "sec-webull-financials-chart.html").read_text(encoding="utf-8")
    assert "MSFT: SEC financial facts and Webull prices" in chart


def test_notebook_documents_forward_adjusted_webull_prices():
    text = "\n".join(source(cell) for cell in load()["cells"])

    assert "forward-adjusted close" in text
    assert "ปรับย้อนหลัง" in text


def test_notebook_uses_atomic_manifest_update_and_conservative_price_timing():
    text = "\n".join(source(cell) for cell in load()["cells"])

    assert "write_json_atomic" in text
    assert "manifest_path.write_text" not in text
    assert "next trading session" in text
    assert "acceptance timestamp" in text
    assert "market-session" in text
    assert "timing-safe metrics" not in text
    assert "ข้อมูลพร้อมใช้ไม่ก่อน `filed_date`" not in text


def test_builder_source_and_notebook_do_not_contain_embedded_secrets():
    texts = [BUILDER.read_text(encoding="utf-8"), NOTEBOOK.read_text(encoding="utf-8")]
    forbidden_values = [
        value
        for name in ("WEBULL_APP_KEY", "WEBULL_APP_SECRET", "WEBULL_ACCOUNT_ID")
        if len(value := os.getenv(name, "")) >= 12
    ]
    for text in texts:
        assert "AKIA" not in text
        assert "-----BEGIN PRIVATE KEY-----" not in text
        assert "WEBULL_APP_SECRET=" not in text
        assert all(value not in text for value in forbidden_values)


def test_builder_is_self_contained_and_does_not_use_skill_scaffold():
    namespace = runpy.run_path(str(BUILDER))

    assert callable(namespace["build_notebook"])
    assert "tmp/jupyter-notebook" not in BUILDER.read_text(encoding="utf-8")
