from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from webull_lab.sec_client import normalize_cik

_TICKER = "AAPL"
_CIK = "0000320193"


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError(f"Offline {label} fixture is unavailable or invalid") from None
    if not isinstance(payload, dict):
        raise ValueError(f"Offline {label} fixture must contain a JSON object")
    return payload


class FixtureResponse:
    status_code = 200
    text = "offline fixture"

    def __init__(self, payload: Any):
        self._payload = copy.deepcopy(payload)

    def json(self) -> Any:
        return copy.deepcopy(self._payload)


class FixtureMarketData:
    def __init__(self, bars_path: Path):
        path = Path(bars_path)
        if not path.is_file():
            raise ValueError("Offline bars fixture path must be an existing file")
        self.bars_path = path

    def get_history_bar(
        self,
        symbol: str,
        category: str,
        timespan: str,
        count: str = "200",
        real_time_required: bool | None = None,
        trading_sessions: list[str] | str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> FixtureResponse:
        if symbol != _TICKER or category != "US_STOCK" or timespan != "D":
            raise ValueError("Offline fixture supports AAPL daily US stock bars only")
        try:
            payload = json.loads(self.bars_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ValueError("Offline bars fixture is unavailable or invalid") from None
        if not isinstance(payload, list):
            raise ValueError("Offline bars fixture must contain a JSON array")
        return FixtureResponse(payload)


class FixtureDataClient:
    def __init__(self, bars_path: Path):
        self.market_data = FixtureMarketData(bars_path)


class FixtureSecClient:
    def __init__(self, fixture_dir: Path):
        directory = Path(fixture_dir)
        if not directory.is_dir():
            raise ValueError("Offline SEC fixture directory must exist")
        for filename in ("aapl_submissions_sample.json", "aapl_companyfacts_tutorial.json"):
            if not (directory / filename).is_file():
                raise ValueError("Offline SEC fixture directory is incomplete")
        self.fixture_dir = directory

    def resolve_cik(self, ticker: str) -> str:
        if not isinstance(ticker, str) or ticker.strip().upper() != _TICKER:
            raise ValueError("Offline fixture supports AAPL only")
        return _CIK

    @staticmethod
    def _validate_cik(cik: int | str) -> str:
        try:
            normalized = normalize_cik(cik)
        except (TypeError, ValueError):
            raise ValueError("Offline fixture CIK is invalid") from None
        if normalized != _CIK:
            raise ValueError("Offline fixture CIK must match AAPL")
        return normalized

    def get_submissions(self, cik: int | str) -> dict[str, Any]:
        normalized = self._validate_cik(cik)
        payload = _load_json_object(
            self.fixture_dir / "aapl_submissions_sample.json", "SEC submissions"
        )
        try:
            payload_cik = normalize_cik(payload.get("cik", ""))
        except (TypeError, ValueError):
            raise ValueError("Offline SEC submissions fixture CIK is invalid") from None
        if payload_cik != normalized:
            raise ValueError("Offline SEC submissions fixture CIK does not match AAPL")
        return payload

    def get_companyfacts(self, cik: int | str) -> dict[str, Any]:
        normalized = self._validate_cik(cik)
        payload = _load_json_object(
            self.fixture_dir / "aapl_companyfacts_tutorial.json", "SEC company facts"
        )
        try:
            payload_cik = normalize_cik(payload.get("cik", ""))
        except (TypeError, ValueError):
            raise ValueError("Offline SEC company facts fixture CIK is invalid") from None
        if payload_cik != normalized:
            raise ValueError("Offline SEC company facts fixture CIK does not match AAPL")
        return payload
