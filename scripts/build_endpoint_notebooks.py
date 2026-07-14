#!/usr/bin/env python3
# ruff: noqa: E501
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
from textwrap import dedent


@dataclass(frozen=True)
class Endpoint:
    name: str
    method: str
    path: str
    purpose: str
    params: dict[str, object]
    body: dict[str, object] | None = None


@dataclass(frozen=True)
class NotebookSpec:
    filename: str
    title: str
    slug: str
    docs: tuple[str, ...]
    endpoints: tuple[Endpoint, ...]
    samples: dict[str, object]
    focus: str
    analysis_code: str
    exercises: tuple[str, ...]
    warnings: tuple[str, ...] = ()


ENDPOINT_LABELS = {
    "create_token": "Create Token",
    "check_token": "Check Token",
    "tick": "Tick",
    "snapshot": "Snapshot",
    "quotes": "Quotes",
    "footprint": "Footprint",
    "historical_bars_batch": "Historical Bars",
    "historical_bars_single": "Historical Bars (single symbol)",
    "gainers_losers": "Gainers & Losers",
    "top_active": "Top Active",
    "company_profile": "Company Profile",
    "analyst_target_price": "Analyst Target Price",
    "analyst_rating": "Analyst Rating",
    "get_watchlist": "Get Watchlist",
    "get_watchlist_instruments": "Get Watchlist Instruments",
    "account_list": "Account List",
    "account_balance": "Account Balance",
    "account_positions": "Account Positions",
    "order_history": "Order History",
    "open_order": "Open Order",
    "order_detail": "Order Detail",
    "order_preview": "Order Preview",
}

VISUAL_ASSETS = {
    "cover": ("3 ขั้นตอนเริ่มต้นใช้ Webull Open API", "../docs/assets/webull-openapi-quickstart/01-cover.png"),
    "overview": ("ทำความเข้าใจกับ Webull OpenAPI", "../docs/assets/webull-openapi-quickstart/02-api-overview.png"),
    "app_key": ("วิธีขอ App Key และ App Secret", "../docs/assets/webull-openapi-quickstart/03-app-key-secret.png"),
    "market_data": ("วิธี Claim ข้อมูล Market Data LV1", "../docs/assets/webull-openapi-quickstart/04-claim-market-data.png"),
    "access_token": ("วิธีขอ Access Token", "../docs/assets/webull-openapi-quickstart/05-access-token.png"),
    "examples": ("ตัวอย่างการใช้งาน API", "../docs/assets/webull-openapi-quickstart/06-api-examples.png"),
}

SPEC_VISUAL_KEYS = {
    "00-auth-token": ("cover", "app_key", "access_token"),
    "01-stock-market-data": ("overview", "market_data", "examples"),
    "02-screener-fundamentals": ("overview", "market_data", "examples"),
    "03-watchlist-readonly": ("overview", "examples"),
    "04-account-assets-order-query": ("overview", "access_token", "examples"),
    "05-order-preview-guardrails": ("overview", "access_token", "examples"),
}


def endpoint_label(endpoint: Endpoint) -> str:
    return ENDPOINT_LABELS.get(endpoint.name, endpoint.name.replace("_", " ").title())


def visual_markdown(slug: str) -> str:
    lines = [
        "## Visual Quick Start",
        "",
        "ดูรูปภาพรวมก่อน แล้วค่อย run cell ด้านล่างทีละช่อง.",
        "",
    ]
    for key in SPEC_VISUAL_KEYS.get(slug, ("cover", "overview")):
        alt_text, path = VISUAL_ASSETS[key]
        lines.append(f"![{alt_text}]({path})")
        lines.append("")
    return "\n".join(lines).strip()


def markdown_cell(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(source).strip() + "\n"}


def code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dedent(source).strip() + "\n",
    }


COMMON_SETUP_CODE = r"""
import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

try:
    NOTEBOOK_DISPLAY = display
except NameError:
    def display(value: object) -> None:
        print(value)
else:
    display = NOTEBOOK_DISPLAY

BASE_URL = "https://api.webull.co.th"
HOST = "api.webull.co.th"
REGION = "th"
LIVE_MODE = os.getenv("WEBULL_TUTORIAL_LIVE", "0") == "1"
OUTPUT_ROOT = Path(os.getenv("WEBULL_TUTORIAL_OUTPUT_DIR", "outputs/webull-th-endpoints"))
OUTPUT_DIR = OUTPUT_ROOT / NOTEBOOK_SLUG
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_env_file(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def env_value(key: str, file_values: dict[str, str], default: str = "") -> str:
    return os.getenv(key, file_values.get(key, default)).strip()


def redact(value: object, keep: int = 4) -> str:
    text = str(value or "")
    if not text:
        return "<missing>"
    if len(text) <= keep * 2:
        return "*" * len(text)
    return f"{text[:keep]}...{text[-keep:]}"


def redact_nested(value: object) -> object:
    sensitive = {"account_id", "accountId", "account_number", "accountNumber", "token"}
    if isinstance(value, dict):
        return {
            key: redact(val, keep=3) if key in sensitive else redact_nested(val)
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [redact_nested(item) for item in value]
    return value


def save_json(name: str, payload: object) -> Path:
    path = OUTPUT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def save_records_csv(name: str, payload: object) -> pd.DataFrame:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = payload.get("data", payload)
    else:
        records = []
    if isinstance(records, dict):
        records = [records]
    frame = pd.DataFrame(records)
    if not frame.empty:
        frame.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)
    return frame


env_file = Path(".env.webull-th") if Path(".env.webull-th").exists() else Path(".env")
file_values = read_env_file(env_file)

APP_KEY = env_value("WEBULL_APP_KEY", file_values)
APP_SECRET = env_value("WEBULL_APP_SECRET", file_values)
ACCESS_TOKEN = env_value("WEBULL_ACCESS_TOKEN", file_values)
ACCOUNT_ID = env_value("WEBULL_ACCOUNT_ID", file_values)

if LIVE_MODE and (not APP_KEY or not APP_SECRET):
    raise RuntimeError("Live mode requires WEBULL_APP_KEY and WEBULL_APP_SECRET")

print(
    {
        "live_mode": LIVE_MODE,
        "base_url": BASE_URL,
        "env_file": str(env_file),
        "app_key": redact(APP_KEY),
        "secret_present": bool(APP_SECRET),
        "token_present": bool(ACCESS_TOKEN),
        "account_id": redact(ACCOUNT_ID),
        "output_dir": str(OUTPUT_DIR),
    }
)
"""


REQUEST_HELPER_CODE = r"""
def build_signature_headers(
    *,
    path: str,
    query_params: dict[str, object],
    body: dict[str, object] | None = None,
    algorithm: str = "HMAC-SHA256",
) -> dict[str, str]:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = str(uuid.uuid4())
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body else ""

    sign_params = {key: str(value) for key, value in query_params.items() if value is not None}
    sign_params.update(
        {
            "host": HOST,
            "x-app-key": APP_KEY,
            "x-signature-algorithm": algorithm,
            "x-signature-nonce": nonce,
            "x-signature-version": "1.0",
            "x-timestamp": timestamp,
        }
    )

    sorted_params = "&".join(f"{key}={value}" for key, value in sorted(sign_params.items()))
    string_to_sign = f"{path}&{sorted_params}"
    if body_str:
        body_md5 = hashlib.md5(body_str.encode()).hexdigest().upper()
        string_to_sign = f"{string_to_sign}&{body_md5}"

    encoded_string = quote(string_to_sign, safe="")
    digest = hashlib.sha256 if algorithm == "HMAC-SHA256" else hashlib.sha1
    signature = base64.b64encode(
        hmac.new((APP_SECRET + "&").encode(), encoded_string.encode(), digest).digest()
    ).decode()

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json",
        "x-version": "v2",
        "x-app-key": APP_KEY,
        "x-timestamp": timestamp,
        "x-signature-version": "1.0",
        "x-signature-algorithm": algorithm,
        "x-signature-nonce": nonce,
        "x-signature": signature,
        "x-webull-client-source": "sdk",
    }
    if ACCESS_TOKEN:
        headers["x-access-token"] = ACCESS_TOKEN
    return headers


def call_endpoint(
    endpoint: dict[str, object],
    *,
    sample: object,
    query_params: dict[str, object] | None = None,
    body: dict[str, object] | None = None,
) -> object:
    if not LIVE_MODE:
        return sample

    query = {key: value for key, value in (query_params or {}).items() if value is not None}
    request_body = body or None
    path = str(endpoint["path"])
    headers = build_signature_headers(path=path, query_params=query, body=request_body)
    method = str(endpoint["method"]).upper()
    response = requests.request(
        method,
        f"{BASE_URL}{path}",
        headers=headers,
        params=query,
        json=request_body,
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw_text": response.text}
    if response.status_code >= 400:
        raise RuntimeError({"status_code": response.status_code, "payload": payload})
    return payload


print("request helpers ready")
"""


def endpoint_table_code(spec: NotebookSpec) -> str:
    rows = [
        {
            "name": endpoint.name,
            "label": endpoint_label(endpoint),
            "method": endpoint.method,
            "path": endpoint.path,
            "purpose": endpoint.purpose,
            "params": endpoint.params,
            "body": endpoint.body,
        }
        for endpoint in spec.endpoints
    ]
    return f"""
NOTEBOOK_SLUG = {json.dumps(spec.slug)}
ENDPOINTS = {pformat(rows, sort_dicts=False)}
"""


def samples_code(spec: NotebookSpec) -> str:
    return f"SAMPLE_RESPONSES = {pformat(spec.samples, sort_dicts=False)}\n"


def run_endpoints_code(spec: NotebookSpec) -> str:
    return """
def resolve_endpoint_value(value: object) -> object:
    if value == "from_env_or_sample":
        return ACCOUNT_ID or "offline-account-001"
    if value == "from_env":
        return APP_KEY or "offline-app-key"
    if isinstance(value, dict):
        return {key: resolve_endpoint_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_endpoint_value(item) for item in value]
    return value


results = {}
saved_paths = {}

for endpoint in ENDPOINTS:
    name = endpoint["name"]
    query_params = resolve_endpoint_value(endpoint.get("params") or {})
    body = resolve_endpoint_value(endpoint.get("body"))
    payload = call_endpoint(
        endpoint,
        sample=SAMPLE_RESPONSES[name],
        query_params=query_params,
        body=body,
    )
    clean_payload = redact_nested(payload)
    results[name] = clean_payload
    saved_paths[name] = str(save_json(name, clean_payload))

print({"endpoints": list(results), "saved_paths": saved_paths})
"""


def notebook_intro(spec: NotebookSpec) -> str:
    docs = "\n".join(f"- {url}" for url in spec.docs)
    endpoints = "\n".join(
        f"- `{endpoint.method} {endpoint.path}` - {endpoint_label(endpoint)}"
        for endpoint in spec.endpoints
    )
    return "\n".join(
        [
            f"# {spec.title}",
            "",
            visual_markdown(spec.slug),
            "",
            "Learning goals:",
            "- รู้ว่า endpoint ในหมวดนี้ใช้ทำอะไร",
            "- เริ่มจาก offline sample response ก่อนใช้ credential จริง",
            "- บันทึก raw JSON ทุก endpoint เพื่อกลับมาตรวจ response ได้",
            "- แปลง response เป็น DataFrame หรือกราฟเมื่อเหมาะสม",
            "",
            "Official sources:",
            docs,
            "",
            "Endpoints covered:",
            endpoints,
        ]
    )


def build_notebook(spec: NotebookSpec) -> dict:
    warning_text = "\n".join(f"- {item}" for item in spec.warnings) or "- No write calls in this notebook."
    exercises = "\n".join(f"{index}. {item}" for index, item in enumerate(spec.exercises, start=1))
    cells = [
        markdown_cell(notebook_intro(spec)),
        markdown_cell(
            """
            ## Safety Defaults

            ค่า default คือ offline mode (`WEBULL_TUTORIAL_LIVE=0`) จึง run ได้โดยไม่ต้องมี credential.
            ถ้าจะยิง API จริง ให้ตั้งค่า `.env.webull-th` หรือ `.env` แล้วเปิด `WEBULL_TUTORIAL_LIVE=1`.

            ### โค้ดช่องถัดไปทำอะไร

            - กำหนดชื่อ notebook เพื่อใช้ตั้งชื่อโฟลเดอร์ output
            - สร้างรายการ endpoint ที่ notebook นี้จะเรียก เช่น method, path, parameter และ body
            - ยังไม่ยิง API จริง เป็นแค่การเตรียมแผนที่ endpoint ให้ cell ถัด ๆ ไปใช้ร่วมกัน
            """
        ),
        code_cell(endpoint_table_code(spec)),
        markdown_cell(
            """
            ### โค้ดช่องถัดไปทำอะไร

            - import library ที่ใช้กับ API, JSON, DataFrame และไฟล์ output
            - ตั้งค่า `BASE_URL`, host ไทย, live/offline mode และโฟลเดอร์ output
            - อ่านค่า credential จาก `.env.webull-th` หรือ `.env` แต่ไม่พิมพ์ secret ออกมาตรง ๆ
            - สร้าง helper สำหรับ redact ข้อมูลส่วนตัว, save JSON และ export CSV
            """
        ),
        code_cell(COMMON_SETUP_CODE),
        markdown_cell(
            f"""
            ## Endpoint Map

            หมวดนี้โฟกัส: {spec.focus}

            ### โค้ดช่องถัดไปทำอะไร

            - แสดง endpoint ทั้งหมดใน notebook นี้เป็นตารางอ่านง่าย
            - ใช้ตรวจเร็ว ๆ ว่าแต่ละ endpoint เป็น `GET` หรือ `POST`
            - ช่วยให้เห็น path จริงก่อนเริ่มเรียก API หรืออ่าน sample response
            """
        ),
        code_cell(
            """
            pd.DataFrame(
                [
                    {
                        "name": endpoint["name"],
                        "method": endpoint["method"],
                        "path": endpoint["path"],
                        "purpose": endpoint["purpose"],
                    }
                    for endpoint in ENDPOINTS
                ]
            )
            """
        ),
        markdown_cell(
            """
            ## Offline Samples

            Cell ถัดไปคือ sample response สำหรับโหมด offline. โครงสร้างนี้ใช้เพื่อสอนการอ่าน JSON,
            ไม่ใช่ข้อมูลตลาดแบบ real-time.

            ### โค้ดช่องถัดไปทำอะไร

            - สร้างตัวแปร `SAMPLE_RESPONSES` เป็นข้อมูลจำลองสำหรับทุก endpoint
            - ทำให้ run notebook ได้ทันที แม้ยังไม่มี App Key, App Secret หรือ token
            - ใช้ฝึกอ่านโครงสร้าง JSON ก่อนค่อยเปิด live mode
            """
        ),
        code_cell(samples_code(spec)),
        markdown_cell(
            """
            ## Request Helper

            Helper นี้สร้าง signed request สำหรับ live mode ด้วย `HMAC-SHA256`.
            ใน offline mode จะคืน sample response ทันที.

            ### โค้ดช่องถัดไปทำอะไร

            - สร้าง header ที่ Webull ต้องใช้ เช่น `x-app-key`, timestamp, nonce และ signature
            - รวม query/body ให้เป็น request ที่ส่งด้วย `requests.request`
            - ถ้าอยู่ offline mode จะไม่ยิง internet และคืน sample response แทน
            - ถ้า live API error จะ raise error พร้อม status code และ payload เพื่อ debug
            """
        ),
        code_cell(REQUEST_HELPER_CODE),
        markdown_cell(
            """
            ## Run Endpoints

            ทุก response จะถูก redacted แล้ว save เป็น JSON ใน `OUTPUT_DIR`.

            ### โค้ดช่องถัดไปทำอะไร

            - วนเรียก endpoint ทุกตัวใน `ENDPOINTS`
            - แทน placeholder เช่น account id ด้วยค่าจาก env หรือ sample
            - redact token/account id ก่อนเก็บใน `results`
            - save raw JSON แยกเป็นไฟล์เพื่อให้เปิดดูย้อนหลังหรือแคปหน้าจอได้
            """
        ),
        code_cell(run_endpoints_code(spec)),
        markdown_cell(
            """
            ## Inspect and Export

            ### โค้ดช่องถัดไปทำอะไร

            - นำผลลัพธ์จาก `results` มาแปลงเป็นตาราง, CSV หรือกราฟตามชนิด endpoint
            - ช่วยให้คนทั่วไปอ่าน response ได้ง่ายกว่า raw JSON
            - output สำคัญจะถูกเก็บไว้ใน `OUTPUT_DIR` เพื่อกลับมาเปิดดูได้ภายหลัง
            """
        ),
        code_cell(spec.analysis_code),
        markdown_cell(
            f"""
            ## Guardrails and Non-Goals

            {warning_text}
            """
        ),
        markdown_cell(
            f"""
            ## Exercises

            {exercises}
            """
        ),
    ]

    for index, cell in enumerate(cells):
        cell["id"] = f"{spec.slug}-{index:02d}"

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "pygments_lexer": "ipython3",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


AUTH_SPEC = NotebookSpec(
    filename="00_auth_token.ipynb",
    title="Webull Thailand Endpoint Tutorial: Authentication Token",
    slug="00-auth-token",
    docs=(
        "https://developer.webull.co.th/apis/docs/reference/custom/authentication/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/create-token/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/check-token/",
    ),
    focus="Create Token และ Check Token สำหรับ server-to-server authentication",
    endpoints=(
        Endpoint(
            "create_token",
            "POST",
            "/openapi/auth/token/create",
            "Create access token; token may require app verification before normal use.",
            {},
            {"app_key": "from_env"},
        ),
        Endpoint(
            "check_token",
            "POST",
            "/openapi/auth/token/check",
            "Check whether a token is NORMAL, PENDING, INVALID, or EXPIRED.",
            {},
            {"access_token": "from_env_or_sample"},
        ),
    ),
    samples={
        "create_token": {
            "access_token": "offline-demo-token",
            "expires_in_days": 15,
            "status": "PENDING",
            "message": "Verify the token in the Webull app before live use.",
        },
        "check_token": {
            "access_token": "offline-demo-token",
            "status": "NORMAL",
            "checked_at": "2026-07-06T00:00:00Z",
        },
    },
    analysis_code=r"""
summary = pd.DataFrame(
    [
        {
            "endpoint": name,
            "status": payload.get("status") if isinstance(payload, dict) else None,
            "saved_json": saved_paths[name],
        }
        for name, payload in results.items()
    ]
)
summary.to_csv(OUTPUT_DIR / "auth-token-summary.csv", index=False)
summary
""",
    warnings=(
        "อย่าใส่ App Secret ลง notebook, screenshot, หรือ git history",
        "Token จริงเป็น credential; output ใน notebook นี้ต้อง redact ก่อนแชร์",
    ),
    exercises=(
        "ลองปิด live mode แล้วดูว่า sample response ถูก save ที่ไหน",
        "เปิดไฟล์ JSON ที่ save แล้วดู field `status` ของ token",
        "เขียน checklist สั้น ๆ ว่าเมื่อ token เป็น PENDING ต้องทำอะไรต่อ",
    ),
)


STOCK_SPEC = NotebookSpec(
    filename="01_stock_market_data.ipynb",
    title="Webull Thailand Endpoint Tutorial: Stock Market Data",
    slug="01-stock-market-data",
    docs=(
        "https://developer.webull.co.th/apis/docs/reference/trade-api/stock-market-data/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/tick/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/snapshot/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/quotes/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/footprint/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/historical-bars/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/bars/",
    ),
    focus="AAPL read-only market data และ close price plot",
    endpoints=(
        Endpoint("tick", "GET", "/openapi/market-data/stock/tick", "Tick-by-tick trades.", {"symbol": "AAPL", "category": "US_STOCK", "count": 5}),
        Endpoint("snapshot", "GET", "/openapi/market-data/stock/snapshot", "Realtime market snapshot.", {"symbol": "AAPL", "category": "US_STOCK"}),
        Endpoint("quotes", "GET", "/openapi/market-data/stock/quotes", "Bid/ask quote depth.", {"symbol": "AAPL", "category": "US_STOCK", "depth": 5}),
        Endpoint("footprint", "GET", "/openapi/market-data/stock/footprint", "Recent footprint records.", {"symbol": "AAPL", "category": "US_STOCK", "timespan": "D", "count": 5}),
        Endpoint("historical_bars_batch", "POST", "/openapi/market-data/stock/batch-bars", "Batch historical bars.", {}, {"symbols": ["AAPL"], "category": "US_STOCK", "timespan": "D", "count": 8}),
        Endpoint("historical_bars_single", "GET", "/openapi/market-data/stock/bars", "Single-symbol historical bars.", {"symbol": "AAPL", "category": "US_STOCK", "timespan": "D", "count": 8, "real_time_required": "true"}),
    ),
    samples={
        "tick": [
            {"symbol": "AAPL", "time": "2026-01-21T14:30:01Z", "price": "274.35", "volume": "100", "direction": "BUY"},
            {"symbol": "AAPL", "time": "2026-01-21T14:30:00Z", "price": "274.31", "volume": "200", "direction": "SELL"},
        ],
        "snapshot": {"symbol": "AAPL", "latest_price": "274.35", "change": "3.95", "change_ratio": "1.46", "volume": "48600000"},
        "quotes": {"symbol": "AAPL", "bids": [{"price": "274.34", "size": "300"}], "asks": [{"price": "274.36", "size": "250"}]},
        "footprint": [{"symbol": "AAPL", "time": "2026-01-21", "buy_volume": "26000000", "sell_volume": "22600000"}],
        "historical_bars_batch": {
            "AAPL": [
                {"symbol": "AAPL", "time": "2026-01-12T05:00:00.000+0000", "open": "261.10", "high": "264.11", "low": "260.70", "close": "263.42", "volume": "42110000"},
                {"symbol": "AAPL", "time": "2026-01-13T05:00:00.000+0000", "open": "264.00", "high": "265.20", "low": "261.90", "close": "262.80", "volume": "39000000"},
            ]
        },
        "historical_bars_single": [
            {"tickerId": "913256135", "symbol": "AAPL", "time": "2026-01-12T05:00:00.000+0000", "open": "261.10", "high": "264.11", "low": "260.70", "close": "263.42", "volume": "42110000"},
            {"tickerId": "913256135", "symbol": "AAPL", "time": "2026-01-13T05:00:00.000+0000", "open": "264.00", "high": "265.20", "low": "261.90", "close": "262.80", "volume": "39000000"},
            {"tickerId": "913256135", "symbol": "AAPL", "time": "2026-01-14T05:00:00.000+0000", "open": "263.20", "high": "267.00", "low": "262.50", "close": "266.10", "volume": "45500000"},
            {"tickerId": "913256135", "symbol": "AAPL", "time": "2026-01-15T05:00:00.000+0000", "open": "266.50", "high": "269.10", "low": "265.80", "close": "268.70", "volume": "47200000"},
        ],
    },
    analysis_code=r"""
import plotly.graph_objects as go

bars = pd.DataFrame(results["historical_bars_single"]).rename(columns={"time": "date"})
bars["date"] = pd.to_datetime(bars["date"], errors="coerce")
for column in ["open", "high", "low", "close", "volume"]:
    bars[column] = pd.to_numeric(bars[column], errors="coerce")
bars = bars.sort_values("date").reset_index(drop=True)
bars.to_csv(OUTPUT_DIR / "aapl-bars.csv", index=False)

fig = go.Figure()
fig.add_trace(go.Scatter(x=bars["date"], y=bars["close"], mode="lines+markers", name="Close"))
fig.update_layout(
    title="AAPL Close Price from Stock Historical Bars",
    xaxis_title="Date",
    yaxis_title="Close",
    template="plotly_white",
    height=520,
)
chart_path = OUTPUT_DIR / "aapl-close-chart.html"
fig.write_html(chart_path, include_plotlyjs=True)
print({"csv": str(OUTPUT_DIR / "aapl-bars.csv"), "chart": str(chart_path)})
fig
""",
    warnings=(
        "Market data permission/subscription อาจจำกัด endpoint ที่เรียกได้ใน live mode",
        "Notebook นี้ไม่ใช้ข้อมูลราคาเป็นคำทำนายผลตอบแทน",
    ),
    exercises=(
        "เปลี่ยน `count` ของ historical bars เป็น 20 แล้วดูจำนวน rows",
        "เพิ่ม EMA 22 จาก `close` แล้ว plot ทับเส้นเดิม",
        "เปรียบเทียบ field ที่ต่างกันระหว่าง snapshot กับ quotes",
    ),
)


SCREENER_FUNDAMENTALS_SPEC = NotebookSpec(
    filename="02_screener_fundamentals.ipynb",
    title="Webull Thailand Endpoint Tutorial: Screener and Fundamentals",
    slug="02-screener-fundamentals",
    docs=(
        "https://developer.webull.co.th/apis/docs/reference/trade-api/screener/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/get-gainers-losers/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/get-top-active/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/fundamentals/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/get-company-profile/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/get-analyst-target-price/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/get-analyst-rating/",
    ),
    focus="Screener ranking และ AAPL fundamentals/analyst data",
    endpoints=(
        Endpoint("gainers_losers", "GET", "/openapi/market-data/screener/gainers-losers", "Top gainers or losers.", {"category": "US_STOCK", "order": "CHANGE_RATIO", "direction": "DESC", "limit": 5}),
        Endpoint("top_active", "GET", "/openapi/market-data/screener/top-active", "Most active stocks.", {"category": "US_STOCK", "order": "VOLUME", "limit": 5}),
        Endpoint("company_profile", "GET", "/openapi/instrument/company/profile", "Company profile.", {"symbol": "AAPL", "category": "US_STOCK"}),
        Endpoint("analyst_target_price", "GET", "/openapi/instrument/analyst/target-price", "Analyst target price summary.", {"symbol": "AAPL", "category": "US_STOCK"}),
        Endpoint("analyst_rating", "GET", "/openapi/instrument/analyst/rating", "Analyst rating counts.", {"symbol": "AAPL", "category": "US_STOCK"}),
    ),
    samples={
        "gainers_losers": [{"symbol": "AAPL", "name": "Apple Inc.", "change_ratio": "1.46", "last_price": "274.35"}],
        "top_active": [{"symbol": "AAPL", "volume": "48600000", "turnover": "13200000000", "relative_volume_10d": "1.12"}],
        "company_profile": {"symbol": "AAPL", "company_name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics"},
        "analyst_target_price": {"symbol": "AAPL", "high": "320.00", "low": "220.00", "mean": "285.00", "median": "282.00"},
        "analyst_rating": {"symbol": "AAPL", "strong_buy": 12, "buy": 18, "hold": 10, "sell": 2, "strong_sell": 0},
    },
    analysis_code=r"""
tables = {}
for name, payload in results.items():
    frame = save_records_csv(name, payload)
    tables[name] = {"rows": len(frame), "columns": list(frame.columns)}

target = pd.DataFrame([results["analyst_target_price"]])
rating = pd.DataFrame([results["analyst_rating"]])
print({"tables": tables})
display(target)
rating
""",
    warnings=("Analyst target/rating เป็นข้อมูลอ้างอิง ไม่ใช่คำแนะนำซื้อขายหรือการรับประกันราคา",),
    exercises=(
        "ลองเปลี่ยน screener direction เป็น ASC เพื่อดู losers",
        "แปลง analyst rating เป็นเปอร์เซ็นต์ของจำนวน analyst ทั้งหมด",
        "รวม company profile กับ analyst target price เป็นตารางเดียว",
    ),
)


WATCHLIST_SPEC = NotebookSpec(
    filename="03_watchlist_readonly.ipynb",
    title="Webull Thailand Endpoint Tutorial: Watchlist Read-only",
    slug="03-watchlist-readonly",
    docs=(
        "https://developer.webull.co.th/apis/docs/reference/trade-api/watchlist/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/get-watchlist/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/get-watchlist-instruments/",
    ),
    focus="Get Watchlist และ Get Watchlist Instruments แบบ read-only",
    endpoints=(
        Endpoint("get_watchlist", "GET", "/openapi/market-data/watchlist/list", "Get all watchlists.", {}),
        Endpoint("get_watchlist_instruments", "GET", "/openapi/market-data/watchlist/instruments/list", "Get instruments in a watchlist.", {"watchlist_id": "offline-watchlist-001"}),
    ),
    samples={
        "get_watchlist": [{"watchlist_id": "offline-watchlist-001", "name": "US Tech", "sort_order": 100}],
        "get_watchlist_instruments": [
            {"watchlist_id": "offline-watchlist-001", "symbol": "AAPL", "category": "US_STOCK", "sort_order": 100},
            {"watchlist_id": "offline-watchlist-001", "symbol": "MSFT", "category": "US_STOCK", "sort_order": 90},
        ],
    },
    analysis_code=r"""
watchlists = save_records_csv("watchlists", results["get_watchlist"])
instruments = save_records_csv("watchlist-instruments", results["get_watchlist_instruments"])
display(watchlists)
instruments
""",
    warnings=(
        "Create/Update/Delete watchlist และ Add/Remove instruments เป็น write endpoints; notebook นี้ไม่ execute",
        "ถ้าจะทำ phase 2 ต้องมี confirmation cell และ dry-run flag แยก",
    ),
    exercises=(
        "เลือก watchlist id จาก response แล้วใช้เป็น parameter สำหรับ instruments",
        "นับจำนวน instruments ต่อ watchlist",
        "export watchlist instruments เป็น CSV เพื่อใช้กับ research pipeline",
    ),
)


ACCOUNT_ORDER_SPEC = NotebookSpec(
    filename="04_account_assets_order_query.ipynb",
    title="Webull Thailand Endpoint Tutorial: Account, Assets, and Order Query",
    slug="04-account-assets-order-query",
    docs=(
        "https://developer.webull.co.th/apis/docs/reference/trade-api/account-list/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/account-balance/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/account-position/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/order-history/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/order-open/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/order-detail/",
    ),
    focus="Account/assets/order query with account id redaction",
    endpoints=(
        Endpoint("account_list", "GET", "/openapi/account/list", "Query account list.", {}),
        Endpoint("account_balance", "GET", "/openapi/assets/balance", "Query account balance by account id.", {"account_id": "from_env_or_sample"}),
        Endpoint("account_positions", "GET", "/openapi/assets/positions", "Query positions by account id.", {"account_id": "from_env_or_sample"}),
        Endpoint("order_history", "GET", "/openapi/trade/order/history", "Query orders from the past 7 days.", {"account_id": "from_env_or_sample", "page_size": 20}),
        Endpoint("open_order", "GET", "/openapi/trade/order/open", "Query pending orders.", {"account_id": "from_env_or_sample", "page_size": 20}),
        Endpoint("order_detail", "GET", "/openapi/trade/order/detail", "Query order detail by order id.", {"account_id": "from_env_or_sample", "order_id": "offline-order-001"}),
    ),
    samples={
        "account_list": [{"account_id": "offline-account-001", "account_type": "MARGIN", "status": "NORMAL"}],
        "account_balance": {"account_id": "offline-account-001", "net_liquidation": "100000.00", "cash": "25000.00", "currency": "USD"},
        "account_positions": [{"account_id": "offline-account-001", "symbol": "AAPL", "quantity": "10", "market_value": "2743.50"}],
        "order_history": [{"account_id": "offline-account-001", "order_id": "offline-order-001", "symbol": "AAPL", "side": "BUY", "status": "FILLED"}],
        "open_order": [],
        "order_detail": {"account_id": "offline-account-001", "order_id": "offline-order-001", "symbol": "AAPL", "status": "FILLED"},
    },
    analysis_code=r"""
for name, payload in results.items():
    save_records_csv(name, payload)

account_list = pd.DataFrame(results["account_list"])
positions = pd.DataFrame(results["account_positions"])
orders = pd.DataFrame(results["order_history"])
display(account_list)
display(positions)
orders
""",
    warnings=(
        "Account ID เป็นข้อมูลส่วนตัวและต้อง redact ก่อนแชร์",
        "Order query เป็น read-only; notebook นี้ไม่มี place/replace/cancel",
    ),
    exercises=(
        "ตรวจว่า account id ใน output ถูก redact ก่อน screenshot",
        "คำนวณ market value รวมจาก positions",
        "กรอง order_history เฉพาะ symbol AAPL",
    ),
)


ORDER_PREVIEW_SPEC = NotebookSpec(
    filename="05_order_preview_guardrails.ipynb",
    title="Webull Thailand Endpoint Tutorial: Order Preview Guardrails",
    slug="05-order-preview-guardrails",
    docs=(
        "https://developer.webull.co.th/apis/docs/reference/trade-api/trading/",
        "https://developer.webull.co.th/apis/docs/reference/trade-api/common-order-preview/",
    ),
    focus="Order Preview only; no Place, Replace, or Cancel execution",
    endpoints=(
        Endpoint(
            "order_preview",
            "POST",
            "/openapi/trade/order/preview",
            "Estimate cost and amount for a simple order.",
            {},
            {
                "account_id": "from_env_or_sample",
                "symbol": "AAPL",
                "category": "US_STOCK",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": "1",
                "limit_price": "250.00",
                "time_in_force": "DAY",
            },
        ),
    ),
    samples={
        "order_preview": {
            "account_id": "offline-account-001",
            "symbol": "AAPL",
            "side": "BUY",
            "estimated_amount": "250.00",
            "estimated_fee": "0.00",
            "status": "PREVIEW_ONLY",
        }
    },
    analysis_code=r"""
preview = pd.DataFrame([results["order_preview"]])
preview.to_csv(OUTPUT_DIR / "order-preview.csv", index=False)
preview
""",
    warnings=(
        "ไม่มี cell ใดใน notebook นี้เรียก Order Place, Order Replace, หรือ Order Cancel",
        "Preview ไม่ได้แปลว่า order จะส่งจริงหรือ fill จริง",
        "ถ้าจะเพิ่ม live order ในอนาคต ต้องแยก notebook และมี explicit confirmation gate",
    ),
    exercises=(
        "เปลี่ยน quantity ใน body เป็น 2 แล้วดู estimated_amount ใน offline sample",
        "เพิ่ม validation ว่า quantity ต้องมากกว่า 0 ก่อน preview",
        "เขียน checklist ว่าต้องตรวจอะไรบ้างก่อนอนุญาต live order",
    ),
)


SPECS = (
    AUTH_SPEC,
    STOCK_SPEC,
    SCREENER_FUNDAMENTALS_SPEC,
    WATCHLIST_SPEC,
    ACCOUNT_ORDER_SPEC,
    ORDER_PREVIEW_SPEC,
)


README_TEMPLATE = """# Webull Thailand Endpoint Tutorial Notebooks

ชุด notebook นี้แยกตามหมวด endpoint เพื่อให้มือใหม่เรียนทีละส่วนได้ง่ายขึ้น.

ทุก notebook:

- ใช้ offline mode เป็นค่าเริ่มต้น (`WEBULL_TUTORIAL_LIVE=0`)
- มี sample response เพื่อ run ได้โดยไม่ต้องมี credential
- save raw JSON ลง `outputs/webull-th-endpoints/<notebook-slug>/`
- ใช้ `api.webull.co.th` และ `HMAC-SHA256` เมื่อเปิด live mode
- ไม่ฝัง App Key, App Secret, token, หรือ account id จริง

## Visual Quick Start

![3 ขั้นตอนเริ่มต้นใช้ Webull Open API](../docs/assets/webull-openapi-quickstart/01-cover.png)

![ทำความเข้าใจกับ Webull OpenAPI](../docs/assets/webull-openapi-quickstart/02-api-overview.png)

![วิธีขอ App Key และ App Secret](../docs/assets/webull-openapi-quickstart/03-app-key-secret.png)

![วิธี Claim ข้อมูล Market Data LV1](../docs/assets/webull-openapi-quickstart/04-claim-market-data.png)

![วิธีขอ Access Token](../docs/assets/webull-openapi-quickstart/05-access-token.png)

![ตัวอย่างการใช้งาน API](../docs/assets/webull-openapi-quickstart/06-api-examples.png)

## Learning Order

1. [Auth Token](00_auth_token.ipynb)
2. [Stock Market Data](01_stock_market_data.ipynb)
3. [Screener and Fundamentals](02_screener_fundamentals.ipynb)
4. [Watchlist Read-only](03_watchlist_readonly.ipynb)
5. [Account, Assets, and Order Query](04_account_assets_order_query.ipynb)
6. [Order Preview Guardrails](05_order_preview_guardrails.ipynb)

## Quick Beginner Path

ถ้าต้องการเริ่มจากตัวอย่างเดียวก่อน ให้เปิด
[Webull Thailand Beginner Notebook](webull_th_beginner.ipynb).

## Quantopian-Style Research Path

ถ้าต้องการ notebook แนว Quantopian lecture ที่ใช้ Webull historical bars เป็น
data source ให้เปิด [Webull Quantopian-Style Research Notebooks](quantopian_style/README.md).

## SEC Financial Data Path

เรียนการแปลง ticker เป็น CIK, normalize XBRL statements, ใช้ filed date ลด
look-ahead bias และเติม Webull daily prices แบบ optional จาก
[คู่มือ SEC EDGAR + Webull Financial Data](../docs/06-sec-webull-financials-th.md)
แล้วเปิด [SEC Webull Financials Beginner Notebook](sec_webull_financials_beginner.ipynb).

Notebook นี้สร้างแบบ deterministic จาก
`scripts/build_sec_webull_financials_notebook.py`, เริ่ม offline ด้วย fixtures และรองรับ
SEC-only fallback เมื่อ Webull market-data permission ไม่พร้อม
"""


def write_notebook(path: Path, spec: NotebookSpec) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    notebook = build_notebook(spec)
    path.write_text(json.dumps(notebook, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_all(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for spec in SPECS:
        write_notebook(output_dir / spec.filename, spec)
    (output_dir / "README.md").write_text(README_TEMPLATE, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build endpoint-split Webull TH tutorial notebooks.")
    parser.add_argument("--out-dir", default="notebooks")
    args = parser.parse_args()
    output_dir = Path(args.out_dir)
    write_all(output_dir)
    print(f"Wrote {len(SPECS)} endpoint notebooks to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
