from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

TRADING_ENDPOINTS = {
    "uat": "api.sandbox.webull.com",
    "prod": "api.webull.com",
}


def redact_secret(value: str | None) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 5:
        return "*****"
    return f"{value[:4]}...{value[-4:]}"


@dataclass(frozen=True)
class Settings:
    env: str
    region: str
    app_key: str
    app_secret: str
    account_id: str | None
    token_dir: Path | None
    live_orders_enabled: bool = False

    @property
    def trading_endpoint(self) -> str:
        return TRADING_ENDPOINTS[self.env]

    def __repr__(self) -> str:
        return (
            "Settings("
            f"env={self.env!r}, "
            f"region={self.region!r}, "
            f"app_key={redact_secret(self.app_key)!r}, "
            f"app_secret={redact_secret(self.app_secret)!r}, "
            f"account_id={redact_secret(self.account_id)!r}, "
            f"token_dir={str(self.token_dir) if self.token_dir else None!r}, "
            f"live_orders_enabled={self.live_orders_enabled!r}"
            ")"
        )


def load_settings(env_file: str | Path | None = ".env") -> Settings:
    if env_file is not None:
        load_dotenv(env_file)
    env = os.getenv("WEBULL_ENV", "uat").strip().lower()
    if env not in TRADING_ENDPOINTS:
        valid = ", ".join(sorted(TRADING_ENDPOINTS))
        raise ValueError(f"WEBULL_ENV must be one of: {valid}")

    app_key = os.getenv("WEBULL_APP_KEY", "").strip()
    app_secret = os.getenv("WEBULL_APP_SECRET", "").strip()
    if not app_key or not app_secret:
        raise RuntimeError("WEBULL_APP_KEY and WEBULL_APP_SECRET are required")

    account_id_value = os.getenv("WEBULL_ACCOUNT_ID", "").strip()
    token_dir_value = os.getenv("WEBULL_TOKEN_DIR", "").strip()

    return Settings(
        env=env,
        region=os.getenv("WEBULL_REGION", "us").strip().lower(),
        app_key=app_key,
        app_secret=app_secret,
        account_id=account_id_value or None,
        token_dir=Path(token_dir_value) if token_dir_value else None,
        live_orders_enabled=os.getenv("WEBULL_ALLOW_LIVE_ORDERS") == "I_UNDERSTAND",
    )
