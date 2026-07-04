from __future__ import annotations

import json

import typer
from rich.console import Console

from webull_lab.account import get_account_list
from webull_lab.clients import build_trade_client
from webull_lab.config import load_settings, redact_secret

app = typer.Typer(help="Webull OpenAPI Thai Lab commands.")
console = Console()


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
    settings = load_settings()
    trade_client = build_trade_client(settings)
    payload = get_account_list(trade_client)
    console.print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
