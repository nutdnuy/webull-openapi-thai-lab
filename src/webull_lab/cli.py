from __future__ import annotations

import json

import typer
from rich.console import Console

from webull_lab.account import ResponseError, get_account_list
from webull_lab.clients import build_data_client, build_trade_client
from webull_lab.config import load_settings, redact_secret
from webull_lab.market_data import get_stock_snapshot

app = typer.Typer(help="Webull OpenAPI Thai Lab commands.")
console = Console()


def print_error_and_exit(error: Exception) -> None:
    console.print(f"[bold red]Error:[/bold red] {error}")
    raise typer.Exit(code=1) from error


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


if __name__ == "__main__":
    app()
