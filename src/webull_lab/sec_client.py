from __future__ import annotations

import json
import random
import tempfile
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import isfinite
from pathlib import Path

import requests

from webull_lab.sec_config import SecSettings

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRY_DELAY_SECONDS = 60.0


class SecDataError(RuntimeError):
    pass


class SecNotFoundError(SecDataError):
    pass


def normalize_cik(cik: int | str) -> str:
    value = str(cik).strip()
    if not value.isascii() or not value.isdigit() or len(value) > 10:
        raise ValueError("CIK must contain at most 10 digits")
    return value.zfill(10)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_retry_after(value: str | None, *, now: datetime) -> float | None:
    if value is None:
        return None
    try:
        numeric_delay = float(value)
    except (TypeError, ValueError):
        numeric_delay = None
    else:
        return numeric_delay if isfinite(numeric_delay) and numeric_delay >= 0 else None

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    else:
        retry_at = retry_at.astimezone(UTC)
    normalized_now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    delay = max(0.0, (retry_at - normalized_now).total_seconds())
    return delay if isfinite(delay) else None


class SecClient:
    def __init__(self, settings: SecSettings, session=None):
        self.settings = settings
        self.session = requests.Session() if session is None else session
        self.cache_hits = 0
        self.network_requests = 0

    def _cache_path(self, cache_name: str) -> Path:
        relative_path = Path(cache_name)
        if not cache_name or relative_path.is_absolute() or ".." in relative_path.parts:
            raise SecDataError("Invalid SEC cache path")
        try:
            cache_root = self.settings.cache_dir.resolve()
            cache_path = (cache_root / relative_path).resolve()
        except (OSError, RuntimeError):
            raise SecDataError("Invalid SEC cache path") from None
        if cache_path == cache_root or not cache_path.is_relative_to(cache_root):
            raise SecDataError("Invalid SEC cache path")
        return cache_path

    @staticmethod
    def _write_cache(cache_path: Path, payload: dict) -> None:
        temporary_path = None
        replaced = False
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=cache_path.parent, delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(payload, temporary)
                temporary.flush()
            temporary_path.replace(cache_path)
            replaced = True
        except (OSError, TypeError, ValueError, OverflowError, RecursionError):
            raise SecDataError("Unable to write SEC cache") from None
        finally:
            if temporary_path is not None and not replaced:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def get_json(self, url: str, cache_name: str) -> dict:
        cache_path = self._cache_path(cache_name)
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

            delay = _parse_retry_after(response.headers.get("Retry-After"), now=_utc_now())
            if delay is None:
                delay = 2**attempt + random.uniform(0.0, 1.0)
            time.sleep(min(MAX_RETRY_DELAY_SECONDS, max(0.0, delay)))

        if response is None:  # pragma: no cover - SecSettings prevents zero attempts
            raise SecDataError("SEC request failed")
        try:
            payload = response.json()
        except ValueError:
            raise SecDataError("SEC response contains invalid JSON") from None
        if not isinstance(payload, dict):
            raise SecDataError("SEC response must contain a JSON object")
        self._write_cache(cache_path, payload)
        return payload

    def resolve_cik(self, ticker: str) -> str:
        normalized_ticker = ticker.strip().upper()
        if not normalized_ticker:
            raise SecNotFoundError("SEC ticker '' not found")

        companies = self.get_json(TICKERS_URL, "company_tickers.json")
        for company in companies.values():
            if not isinstance(company, dict):
                raise SecDataError("SEC response contains malformed company ticker data")
            company_ticker = company.get("ticker")
            if not isinstance(company_ticker, str) or not company_ticker.strip():
                raise SecDataError("SEC response contains malformed company ticker data")
            try:
                company_cik = normalize_cik(company.get("cik_str", ""))
            except ValueError:
                raise SecDataError("SEC response contains malformed company ticker data") from None
            if company_ticker.strip().upper() == normalized_ticker:
                return company_cik
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
