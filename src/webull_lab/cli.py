from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from webull.core.exception.exceptions import ClientException, ServerException

from webull_lab.account import ResponseError, get_account_list
from webull_lab.clients import build_data_client, build_trade_client
from webull_lab.company_pipeline import run_company_pipeline
from webull_lab.config import load_settings, redact_secret
from webull_lab.market_data import get_stock_snapshot
from webull_lab.orders import preview_stock_limit_buy
from webull_lab.sec_client import SecClient, SecDataError
from webull_lab.sec_config import load_sec_settings

app = typer.Typer(help="Webull OpenAPI Thai Lab commands.")
console = Console()
DEFAULT_COMPANY_DATA_OUTPUT_DIR = Path("data/private/company-data")


def print_error_and_exit(error: Exception) -> None:
    console.print(f"[bold red]Error:[/bold red] {error}")
    raise typer.Exit(code=1) from error


class PartialWebullCredentialsError(RuntimeError):
    pass


class _UnavailableMarketData:
    @staticmethod
    def get_history_bar(*args, **kwargs):
        raise RuntimeError("Webull market data client is unavailable")


class _UnavailableDataClient:
    market_data = _UnavailableMarketData()


UNAVAILABLE_DATA_CLIENT = _UnavailableDataClient()


def build_optional_data_client():
    app_key = os.getenv("WEBULL_APP_KEY", "").strip()
    app_secret = os.getenv("WEBULL_APP_SECRET", "").strip()
    if not app_key and not app_secret:
        return None
    if not app_key or not app_secret:
        raise PartialWebullCredentialsError(
            "Set both WEBULL_APP_KEY and WEBULL_APP_SECRET, or leave both unset."
        )
    settings = load_settings()
    try:
        return build_data_client(settings)
    except (ClientException, ServerException):
        return UNAVAILABLE_DATA_CLIENT
    except Exception:
        raise RuntimeError("Webull data client initialization failed") from None


def print_company_data_error_and_exit(error: Exception) -> None:
    if isinstance(error, PartialWebullCredentialsError):
        safe_message = str(error)
    elif isinstance(error, ResponseError):
        safe_message = "Webull request failed while building company data."
    elif isinstance(error, SecDataError):
        safe_message = "SEC request failed while building company data."
    elif isinstance(error, OSError):
        safe_message = "Unable to write company data output."
    elif isinstance(error, ValueError):
        safe_message = "Invalid company data input."
    else:
        safe_message = (
            "Company data configuration or processing failed. Check SEC_CONTACT_EMAIL "
            "and optional Webull credentials."
        )
    print_error_and_exit(RuntimeError(safe_message))


@app.command()
def doctor() -> None:
    settings = load_settings()
    console.print("[bold green]Webull Lab configuration loaded[/bold green]")
    console.print(f"Environment: {settings.env}")
    console.print(f"Region: {settings.region}")
    console.print(f"Trading endpoint: {settings.trading_endpoint}")
    console.print(f"App key: {redact_secret(settings.app_key)}")
    console.print(f"App secret: {redact_secret(settings.app_secret)}")
    account_id = redact_secret(settings.account_id) if settings.account_id else "<not set>"
    console.print(f"Account ID: {account_id}")


@app.command("account-list")
def account_list() -> None:
    try:
        settings = load_settings()
        trade_client = build_trade_client(settings)
        payload = get_account_list(trade_client)
        console.print(json.dumps(payload, ensure_ascii=False, indent=2))
    except (ResponseError, RuntimeError, ValueError) as error:
        print_error_and_exit(error)


@app.command("stock-snapshot")
def stock_snapshot(symbol: str = typer.Argument("AAPL")) -> None:
    try:
        settings = load_settings()
        data_client = build_data_client(settings)
        payload = get_stock_snapshot(data_client, symbol)
        console.print(json.dumps(payload, ensure_ascii=False, indent=2))
    except (ResponseError, RuntimeError, ValueError) as error:
        print_error_and_exit(error)


@app.command("preview-stock-buy")
def preview_stock_buy(
    symbol: str = typer.Argument("AAPL"),
    limit_price: str = typer.Argument("100"),
    quantity: str = typer.Argument("1"),
) -> None:
    try:
        settings = load_settings()
        if settings.account_id is None:
            raise ValueError("Set WEBULL_ACCOUNT_ID in .env before previewing an order.")
        trade_client = build_trade_client(settings)
        payload = preview_stock_limit_buy(
            trade_client,
            settings.account_id,
            symbol,
            limit_price,
            quantity,
        )
        console.print(json.dumps(payload, ensure_ascii=False, indent=2))
    except (ResponseError, RuntimeError, ValueError) as error:
        print_error_and_exit(error)


@app.command("company-data")
def company_data(
    symbol: Annotated[str, typer.Argument()] = "AAPL",
    years: Annotated[int, typer.Option(min=1, max=20)] = 5,
    output_dir: Annotated[Path, typer.Option()] = DEFAULT_COMPANY_DATA_OUTPUT_DIR,
) -> None:
    try:
        sec_client = SecClient(load_sec_settings())
        manifest = run_company_pipeline(
            symbol,
            years,
            output_dir,
            sec_client,
            build_optional_data_client(),
        )
        typer.echo(json.dumps(manifest, ensure_ascii=False, indent=2))
    except (ResponseError, SecDataError, RuntimeError, ValueError, OSError) as error:
        print_company_data_error_and_exit(error)


if __name__ == "__main__":
    app()
