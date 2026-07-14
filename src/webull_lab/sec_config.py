from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SecSettings:
    contact_email: str
    cache_dir: Path
    timeout_seconds: float = 20.0
    max_attempts: int = 3

    @property
    def user_agent(self) -> str:
        return f"webull-openapi-thai-lab {self.contact_email}"


def load_sec_settings() -> SecSettings:
    contact_email = os.getenv("SEC_CONTACT_EMAIL", "").strip()
    local_part, separator, domain = contact_email.partition("@")
    if (
        contact_email.count("@") != 1
        or not separator
        or not local_part
        or not domain
        or any(character.isspace() for character in contact_email)
    ):
        raise RuntimeError("SEC_CONTACT_EMAIL must be a valid email address")

    timeout_seconds = float(os.getenv("SEC_TIMEOUT_SECONDS", "20"))
    max_attempts = int(os.getenv("SEC_MAX_ATTEMPTS", "3"))
    if timeout_seconds <= 0:
        raise ValueError("SEC_TIMEOUT_SECONDS must be positive")
    if max_attempts <= 0:
        raise ValueError("SEC_MAX_ATTEMPTS must be positive")

    return SecSettings(
        contact_email=contact_email,
        cache_dir=Path(os.getenv("SEC_CACHE_DIR", "data/private/sec-cache")),
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
    )
