from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class SecSettings:
    contact_email: str
    cache_dir: Path
    timeout_seconds: float = 20.0
    max_attempts: int = 3

    @property
    def user_agent(self) -> str:
        return f"webull-openapi-thai-lab {self.contact_email}"


def load_sec_settings(env_file: str | Path | None = ".env") -> SecSettings:
    if env_file is not None:
        load_dotenv(env_file)

    contact_email = os.getenv("SEC_CONTACT_EMAIL", "").strip()
    local_part, separator, domain = contact_email.partition("@")
    if (
        contact_email.count("@") != 1
        or not separator
        or not local_part
        or not domain
        or any(character.isspace() for character in contact_email)
        or contact_email == "your_monitored_email@example.com"
    ):
        raise RuntimeError("SEC_CONTACT_EMAIL must be a valid email address")

    timeout_seconds = float(os.getenv("SEC_TIMEOUT_SECONDS", "20"))
    max_attempts = int(os.getenv("SEC_MAX_ATTEMPTS", "3"))
    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("SEC_TIMEOUT_SECONDS must be positive")
    if max_attempts <= 0:
        raise ValueError("SEC_MAX_ATTEMPTS must be positive")

    cache_dir = os.getenv("SEC_CACHE_DIR", "").strip()
    return SecSettings(
        contact_email=contact_email,
        cache_dir=Path(cache_dir or "data/private/sec-cache"),
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
    )
