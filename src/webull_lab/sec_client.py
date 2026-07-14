from __future__ import annotations

import json
import random
import tempfile
import time
from pathlib import Path

import requests

from webull_lab.sec_config import SecSettings

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class SecDataError(RuntimeError):
    pass


class SecNotFoundError(SecDataError):
    pass


def normalize_cik(cik: int | str) -> str:
    value = str(cik).strip()
    if not value.isascii() or not value.isdigit() or len(value) > 10:
        raise ValueError("CIK must contain at most 10 digits")
    return value.zfill(10)


class SecClient:
    def __init__(self, settings: SecSettings, session=None):
        self.settings = settings
        self.session = requests.Session() if session is None else session
        self.cache_hits = 0
        self.network_requests = 0

    def get_json(self, url: str, cache_name: str) -> dict:
        cache_path = self.settings.cache_dir / cache_name
        if cache_path.exists():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise SecDataError("SEC cache contains invalid JSON") from None
            if not isinstance(payload, dict):
                raise SecDataError("SEC cache must contain a JSON object")
            self.cache_hits += 1
            return payload

        response = None
        for attempt in range(self.settings.max_attempts):
            self.network_requests += 1
            try:
                response = self.session.get(
                    url,
                    headers={
                        "User-Agent": self.settings.user_agent,
                        "Accept-Encoding": "gzip, deflate",
                    },
                    timeout=self.settings.timeout_seconds,
                )
            except requests.RequestException:
                raise SecDataError("SEC request failed") from None

            if response.status_code < 400:
                break
            if response.status_code not in RETRYABLE_STATUS_CODES:
                raise SecDataError(f"SEC request failed with HTTP {response.status_code}")
            if attempt + 1 == self.settings.max_attempts:
                raise SecDataError(
                    f"SEC request failed after {self.settings.max_attempts} attempts"
                )

            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after is not None else None
            except ValueError:
                delay = None
            if delay is None:
                delay = 2**attempt + random.uniform(0.0, 1.0)
            time.sleep(max(0.0, delay))

        if response is None:  # pragma: no cover - SecSettings prevents zero attempts
            raise SecDataError("SEC request failed")
        try:
            payload = response.json()
        except ValueError:
            raise SecDataError("SEC response contains invalid JSON") from None
        if not isinstance(payload, dict):
            raise SecDataError("SEC response must contain a JSON object")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=cache_path.parent, delete=False
        ) as temporary:
            json.dump(payload, temporary)
            temporary_path = Path(temporary.name)
        temporary_path.replace(cache_path)
        return payload

    def resolve_cik(self, ticker: str) -> str:
        normalized_ticker = ticker.strip().upper()
        if not normalized_ticker:
            raise SecNotFoundError("SEC ticker '' not found")

        companies = self.get_json(TICKERS_URL, "company_tickers.json")
        for company in companies.values():
            if str(company.get("ticker", "")).strip().upper() == normalized_ticker:
                return normalize_cik(company["cik_str"])
        raise SecNotFoundError(f"SEC ticker {normalized_ticker!r} not found")

    def get_submissions(self, cik: int | str) -> dict:
        normalized_cik = normalize_cik(cik)
        payload = self.get_json(
            SUBMISSIONS_URL.format(cik=normalized_cik),
            f"{normalized_cik}-submissions.json",
        )
        if not isinstance(payload.get("filings"), dict):
            raise SecDataError("SEC submissions missing filings object")
        return payload

    def get_companyfacts(self, cik: int | str) -> dict:
        normalized_cik = normalize_cik(cik)
        payload = self.get_json(
            COMPANYFACTS_URL.format(cik=normalized_cik),
            f"{normalized_cik}-companyfacts.json",
        )
        if not isinstance(payload.get("facts"), dict):
            raise SecDataError("SEC company facts missing facts object")
        return payload
