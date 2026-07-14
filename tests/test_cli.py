import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner
from webull.core.exception.exceptions import ServerException

import webull_lab.cli as cli_module
from webull_lab.account import ResponseError
from webull_lab.cli import app
from webull_lab.company_pipeline import SAFE_WEBULL_WARNING
from webull_lab.market_data import get_daily_stock_bars

WEBULL_ENV_VARS = [
    "WEBULL_ENV",
    "WEBULL_REGION",
    "WEBULL_APP_KEY",
    "WEBULL_APP_SECRET",
    "WEBULL_ACCOUNT_ID",
    "WEBULL_TOKEN_DIR",
    "WEBULL_ALLOW_LIVE_ORDERS",
]

COMPANY_DATA_ENV_VARS = [
    *WEBULL_ENV_VARS,
    "SEC_CONTACT_EMAIL",
    "SEC_CACHE_DIR",
    "SEC_TIMEOUT_SECONDS",
    "SEC_MAX_ATTEMPTS",
]


def clear_webull_env(monkeypatch):
    for key in WEBULL_ENV_VARS:
        monkeypatch.delenv(key, raising=False)


def prepare_company_data_env(monkeypatch, tmp_path):
    for key in COMPANY_DATA_ENV_VARS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "researcher@example.com")


def test_doctor_redacts_account_id_and_secret(monkeypatch):
    clear_webull_env(monkeypatch)
    account_id = "J6HA4EBQRQFJD2J6NQH0F7M649"
    app_secret = "secret_456789"
    monkeypatch.setenv("WEBULL_APP_KEY", "key_123456")
    monkeypatch.setenv("WEBULL_APP_SECRET", app_secret)
    monkeypatch.setenv("WEBULL_ACCOUNT_ID", account_id)

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert account_id not in result.output
    assert "J6HA...M649" in result.output
    assert app_secret not in result.output


def test_stock_snapshot_prints_json_payload(monkeypatch):
    calls = []
    settings = object()
    data_client = object()

    def fake_build_data_client(received_settings):
        calls.append(("build_data_client", received_settings))
        return data_client

    def fake_get_stock_snapshot(received_data_client, symbol):
        calls.append(("get_stock_snapshot", received_data_client, symbol))
        return {"symbol": symbol, "last_price": "200.00"}

    monkeypatch.setattr("webull_lab.cli.load_settings", lambda: settings)
    monkeypatch.setattr("webull_lab.cli.build_data_client", fake_build_data_client)
    monkeypatch.setattr("webull_lab.cli.get_stock_snapshot", fake_get_stock_snapshot)

    result = CliRunner().invoke(app, ["stock-snapshot", "AAPL"])

    assert result.exit_code == 0
    assert '"symbol": "AAPL"' in result.output
    assert '"last_price": "200.00"' in result.output
    assert calls == [
        ("build_data_client", settings),
        ("get_stock_snapshot", data_client, "AAPL"),
    ]


def test_stock_snapshot_prints_error_without_traceback(monkeypatch):
    monkeypatch.setattr("webull_lab.cli.load_settings", lambda: object())
    monkeypatch.setattr("webull_lab.cli.build_data_client", lambda settings: object())

    def fake_get_stock_snapshot(data_client, symbol):
        raise ResponseError("HTTP 401: bad signature")

    monkeypatch.setattr("webull_lab.cli.get_stock_snapshot", fake_get_stock_snapshot)

    result = CliRunner().invoke(app, ["stock-snapshot", "AAPL"])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "HTTP 401" in result.output
    assert "Traceback" not in result.output


def test_account_list_prints_error_without_traceback(monkeypatch):
    monkeypatch.setattr("webull_lab.cli.load_settings", lambda: object())
    monkeypatch.setattr("webull_lab.cli.build_trade_client", lambda settings: object())

    def fake_get_account_list(trade_client):
        raise ResponseError("HTTP 401: bad signature")

    monkeypatch.setattr("webull_lab.cli.get_account_list", fake_get_account_list)

    result = CliRunner().invoke(app, ["account-list"])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "HTTP 401" in result.output
    assert "Traceback" not in result.output


def test_preview_stock_buy_prints_json_payload(monkeypatch):
    calls = []
    settings = SimpleNamespace(account_id="acct_1")
    trade_client = object()

    def fake_build_trade_client(received_settings):
        calls.append(("build_trade_client", received_settings))
        return trade_client

    def fake_preview_stock_limit_buy(
        received_trade_client, account_id, symbol, limit_price, quantity
    ):
        calls.append(
            (
                "preview_stock_limit_buy",
                received_trade_client,
                account_id,
                symbol,
                limit_price,
                quantity,
            )
        )
        return {"preview": "ok", "symbol": symbol}

    monkeypatch.setattr("webull_lab.cli.load_settings", lambda: settings)
    monkeypatch.setattr("webull_lab.cli.build_trade_client", fake_build_trade_client)
    monkeypatch.setattr("webull_lab.cli.preview_stock_limit_buy", fake_preview_stock_limit_buy)

    result = CliRunner().invoke(app, ["preview-stock-buy", "AAPL", "100", "1"])

    assert result.exit_code == 0
    assert '"preview": "ok"' in result.output
    assert '"symbol": "AAPL"' in result.output
    assert calls == [
        ("build_trade_client", settings),
        ("preview_stock_limit_buy", trade_client, "acct_1", "AAPL", "100", "1"),
    ]


def test_preview_stock_buy_missing_account_id_prints_error_without_traceback(monkeypatch):
    monkeypatch.setattr("webull_lab.cli.load_settings", lambda: SimpleNamespace(account_id=None))

    result = CliRunner().invoke(app, ["preview-stock-buy", "AAPL", "100", "1"])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "WEBULL_ACCOUNT_ID" in result.output
    assert "Traceback" not in result.output


def test_preview_stock_buy_prints_response_error_without_traceback(monkeypatch):
    monkeypatch.setattr(
        "webull_lab.cli.load_settings",
        lambda: SimpleNamespace(account_id="acct_1"),
    )
    monkeypatch.setattr("webull_lab.cli.build_trade_client", lambda settings: object())

    def fake_preview_stock_limit_buy(trade_client, account_id, symbol, limit_price, quantity):
        raise ResponseError("HTTP 401: bad signature")

    monkeypatch.setattr("webull_lab.cli.preview_stock_limit_buy", fake_preview_stock_limit_buy)

    result = CliRunner().invoke(app, ["preview-stock-buy", "AAPL", "100", "1"])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "HTTP 401" in result.output
    assert "Traceback" not in result.output


def test_company_data_prints_manifest_without_webull_credentials(monkeypatch, tmp_path):
    prepare_company_data_env(monkeypatch, tmp_path)
    manifest = {
        "ticker": "AAPL",
        "sec_status": "available",
        "webull_status": "unavailable",
    }
    sec_settings = object()
    sec_client = object()
    calls = []

    monkeypatch.setattr(cli_module, "load_sec_settings", lambda: sec_settings, raising=False)
    monkeypatch.setattr(cli_module, "SecClient", lambda settings: sec_client, raising=False)
    monkeypatch.setattr(
        "webull_lab.cli.load_settings",
        lambda: calls.append("load_settings") or object(),
    )
    monkeypatch.setattr(
        "webull_lab.cli.build_data_client",
        lambda settings: calls.append("build_data_client") or object(),
    )

    def fake_run_company_pipeline(symbol, years, output_dir, received_sec_client, data_client):
        calls.append(
            (
                "run_company_pipeline",
                symbol,
                years,
                output_dir,
                received_sec_client,
                data_client,
            )
        )
        return manifest

    monkeypatch.setattr(
        cli_module, "run_company_pipeline", fake_run_company_pipeline, raising=False
    )

    result = CliRunner().invoke(
        app,
        ["company-data", "aapl", "--years", "5", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == manifest
    assert calls == [
        ("run_company_pipeline", "aapl", 5, tmp_path, sec_client, None),
    ]


def test_company_data_builds_webull_client_when_both_credentials_exist(
    monkeypatch, tmp_path
):
    prepare_company_data_env(monkeypatch, tmp_path)
    monkeypatch.setenv("WEBULL_APP_KEY", "test-key")
    monkeypatch.setenv("WEBULL_APP_SECRET", "test-secret")
    sec_settings = object()
    webull_settings = object()
    sec_client = object()
    data_client = object()
    calls = []

    monkeypatch.setattr(cli_module, "load_sec_settings", lambda: sec_settings, raising=False)
    monkeypatch.setattr(cli_module, "SecClient", lambda settings: sec_client, raising=False)
    monkeypatch.setattr(
        "webull_lab.cli.load_settings",
        lambda: calls.append("load_settings") or webull_settings,
    )
    monkeypatch.setattr(
        "webull_lab.cli.build_data_client",
        lambda settings: calls.append(("build_data_client", settings)) or data_client,
    )
    monkeypatch.setattr(
        cli_module,
        "run_company_pipeline",
        lambda *args: calls.append(("run_company_pipeline", *args)) or {"ok": True},
        raising=False,
    )

    result = CliRunner().invoke(app, ["company-data"])

    assert result.exit_code == 0
    assert calls == [
        "load_settings",
        ("build_data_client", webull_settings),
        (
            "run_company_pipeline",
            "AAPL",
            5,
            Path("data/private/company-data"),
            sec_client,
            data_client,
        ),
    ]


def test_company_data_recognizes_webull_credentials_loaded_from_dotenv(monkeypatch, tmp_path):
    prepare_company_data_env(monkeypatch, tmp_path)
    monkeypatch.delenv("SEC_CONTACT_EMAIL")
    (tmp_path / ".env").write_text(
        "SEC_CONTACT_EMAIL=researcher@example.com\n"
        "WEBULL_APP_KEY=dotenv-key\n"
        "WEBULL_APP_SECRET=dotenv-secret\n",
        encoding="utf-8",
    )
    settings_seen = []
    data_client = object()
    monkeypatch.setattr(cli_module, "SecClient", lambda settings: object(), raising=False)
    monkeypatch.setattr(
        "webull_lab.cli.load_settings",
        lambda: settings_seen.append("loaded") or object(),
    )
    monkeypatch.setattr("webull_lab.cli.build_data_client", lambda settings: data_client)
    monkeypatch.setattr(
        cli_module,
        "run_company_pipeline",
        lambda *args: {"webull_enabled": args[-1] is data_client},
        raising=False,
    )

    result = CliRunner().invoke(app, ["company-data"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"webull_enabled": True}
    assert settings_seen == ["loaded"]


def test_company_data_rejects_partial_webull_credentials_without_leaking_them(
    monkeypatch, tmp_path
):
    prepare_company_data_env(monkeypatch, tmp_path)
    marker_secret = "MARKER_SECRET_MUST_NOT_LEAK"
    monkeypatch.setenv("WEBULL_APP_KEY", marker_secret)
    monkeypatch.setenv("WEBULL_APP_SECRET", "   ")
    pipeline_calls = []
    monkeypatch.setattr(cli_module, "SecClient", lambda settings: object(), raising=False)
    monkeypatch.setattr(
        cli_module,
        "run_company_pipeline",
        lambda *args: pipeline_calls.append(args) or {},
        raising=False,
    )

    result = CliRunner().invoke(app, ["company-data"])

    assert result.exit_code == 1
    assert "WEBULL_APP_KEY" in result.output
    assert "WEBULL_APP_SECRET" in result.output
    assert marker_secret not in result.output
    assert "Traceback" not in result.output
    assert pipeline_calls == []


def test_company_data_accepts_year_bounds_and_rejects_out_of_range_before_network(
    monkeypatch, tmp_path
):
    prepare_company_data_env(monkeypatch, tmp_path)
    years_seen = []
    network_calls = []
    monkeypatch.setattr(cli_module, "SecClient", lambda settings: object(), raising=False)
    monkeypatch.setattr(
        cli_module,
        "run_company_pipeline",
        lambda symbol, years, *args: years_seen.append(years) or {"years": years},
        raising=False,
    )

    for years in (1, 20):
        result = CliRunner().invoke(app, ["company-data", "AAPL", "--years", str(years)])
        assert result.exit_code == 0

    monkeypatch.setattr(
        cli_module,
        "load_sec_settings",
        lambda: network_calls.append("load_sec_settings") or object(),
        raising=False,
    )
    for years in (0, 21):
        result = CliRunner().invoke(app, ["company-data", "AAPL", "--years", str(years)])
        assert result.exit_code != 0
        assert "years" in result.output.lower()

    assert years_seen == [1, 20]
    assert network_calls == []


def test_company_data_safely_reports_pipeline_errors(monkeypatch, tmp_path):
    prepare_company_data_env(monkeypatch, tmp_path)
    marker_secret = "MARKER_SECRET_MUST_NOT_LEAK"
    monkeypatch.setattr(cli_module, "SecClient", lambda settings: object(), raising=False)

    def fail_pipeline(*args):
        raise ResponseError(f"HTTP 401 contained {marker_secret}")

    monkeypatch.setattr(cli_module, "run_company_pipeline", fail_pipeline, raising=False)

    result = CliRunner().invoke(app, ["company-data"])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Webull" in result.output
    assert marker_secret not in result.output
    assert "Traceback" not in result.output


def test_company_data_safely_reports_sec_and_output_errors(monkeypatch, tmp_path):
    from webull_lab.sec_client import SecDataError

    prepare_company_data_env(monkeypatch, tmp_path)
    marker_secret = "MARKER_SECRET_MUST_NOT_LEAK"
    monkeypatch.setattr(cli_module, "SecClient", lambda settings: object(), raising=False)

    for error in (SecDataError(marker_secret), OSError(marker_secret)):
        def fail_pipeline(*args, current_error=error):
            raise current_error

        monkeypatch.setattr(cli_module, "run_company_pipeline", fail_pipeline, raising=False)
        result = CliRunner().invoke(app, ["company-data"])

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert marker_secret not in result.output
        assert "Traceback" not in result.output


def test_company_data_degrades_sdk_init_failure_to_safe_sec_only_manifest(
    monkeypatch, tmp_path
):
    prepare_company_data_env(monkeypatch, tmp_path)
    marker_secret = "MARKER_SECRET_MUST_NOT_LEAK"
    monkeypatch.setenv("WEBULL_APP_KEY", "test-key")
    monkeypatch.setenv("WEBULL_APP_SECRET", marker_secret)
    pipeline_calls = []
    monkeypatch.setattr(cli_module, "SecClient", lambda settings: object())
    monkeypatch.setattr(cli_module, "load_settings", lambda: object())

    def fail_sdk_initialization(settings):
        raise ServerException("SDK_INIT", marker_secret, 500, "request-id")

    monkeypatch.setattr(cli_module, "build_data_client", fail_sdk_initialization)

    def fake_run_company_pipeline(symbol, years, output_dir, sec_client, data_client):
        pipeline_calls.append((symbol, years, output_dir, sec_client))
        try:
            get_daily_stock_bars(data_client, symbol)
        except RuntimeError:
            return {
                "ticker": symbol,
                "webull_status": "unavailable",
                "warnings": [SAFE_WEBULL_WARNING],
            }
        raise AssertionError("unavailable Webull client did not fail at fetch boundary")

    monkeypatch.setattr(cli_module, "run_company_pipeline", fake_run_company_pipeline)

    result = CliRunner().invoke(app, ["company-data", "AAPL"])

    assert result.exit_code == 0
    assert '"ticker": "AAPL"' in result.output
    assert '"webull_status": "unavailable"' in result.output
    assert "Webull market data unavailable" in result.output
    assert "SEC financial outputs were still" in result.output
    assert len(pipeline_calls) == 1
    assert marker_secret not in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("error_type", [RuntimeError, TypeError, AttributeError])
def test_company_data_does_not_downgrade_unexpected_client_build_errors(
    monkeypatch, tmp_path, error_type
):
    prepare_company_data_env(monkeypatch, tmp_path)
    marker_secret = "MARKER_SECRET_MUST_NOT_LEAK"
    monkeypatch.setenv("WEBULL_APP_KEY", "test-key")
    monkeypatch.setenv("WEBULL_APP_SECRET", marker_secret)
    pipeline_calls = []
    monkeypatch.setattr(cli_module, "SecClient", lambda settings: object())
    monkeypatch.setattr(cli_module, "load_settings", lambda: object())

    def fail_with_programming_error(settings):
        raise error_type(marker_secret)

    monkeypatch.setattr(cli_module, "build_data_client", fail_with_programming_error)
    monkeypatch.setattr(
        cli_module,
        "run_company_pipeline",
        lambda *args: pipeline_calls.append(args) or {},
    )

    result = CliRunner().invoke(app, ["company-data"])

    assert result.exit_code == 1
    assert "configuration or processing failed" in result.output
    assert pipeline_calls == []
    assert marker_secret not in result.output
    assert "Traceback" not in result.output


def test_company_data_manifest_json_does_not_wrap_long_warning(monkeypatch, tmp_path):
    prepare_company_data_env(monkeypatch, tmp_path)
    manifest = {
        "ticker": "AAPL",
        "webull_status": "unavailable",
        "warnings": [SAFE_WEBULL_WARNING],
    }
    monkeypatch.setattr(cli_module, "SecClient", lambda settings: object())
    monkeypatch.setattr(cli_module, "run_company_pipeline", lambda *args: manifest)

    result = CliRunner().invoke(app, ["company-data"], terminal_width=40)

    assert result.exit_code == 0
    assert json.loads(result.output) == manifest
