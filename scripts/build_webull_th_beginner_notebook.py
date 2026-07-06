#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent

CELL_IDS = [
    "intro",
    "source-notes",
    "outline",
    "setup-intro",
    "setup-code",
    "credentials-intro",
    "credentials-code",
    "token-intro",
    "token-code",
    "signature-intro",
    "signature-code",
    "fetch-bars-intro",
    "fetch-bars-code",
    "save-raw-json-intro",
    "save-raw-json-code",
    "plot-close-intro",
    "plot-close-code",
    "exercises-intro",
    "exercises-code",
    "common-pitfalls",
]


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


def build_notebook() -> dict:
    cells = [
        markdown_cell(
            """
            # Webull Thailand OpenAPI: Beginner AAPL Close Price Tutorial

            Prerequisites:
            - รู้พื้นฐาน Python notebook เช่น run cell, อ่าน error, และดูตัวแปร
            - ติดตั้ง `requests`, `pandas`, `plotly`
            - ติดตั้ง `webull-openapi-python-sdk` เฉพาะตอนใช้ live mode
            - มี Webull OpenAPI App Key / App Secret เฉพาะตอนใช้ live mode

            Learning goals:
            - แยกให้ออกว่า endpoint, parameter, header, token, และ signature คืออะไร
            - รัน offline mode เพื่อเข้าใจ flow โดยไม่ต้องมี credential
            - เปิด live mode เพื่อเรียก `api.webull.co.th` ด้วย `x-access-token` และ `HMAC-SHA256`
            - บันทึก raw JSON และ plot ราคา `close` อย่างเดียว
            """
        ),
        markdown_cell(
            """
            ## Source Notes

            ใช้เอกสาร Webull Thailand เป็นแหล่งอ้างอิง:

            - Open API Reference: https://developer.webull.co.th/apis/docs/webull-open-api-reference/
            - Signature: https://developer.webull.co.th/apis/docs/authentication/signature
            - Token: https://developer.webull.co.th/apis/docs/authentication/token
            - Market Data Overview: https://developer.webull.co.th/apis/docs/market-data-api/overview
            - Market Data Data API: https://developer.webull.co.th/apis/docs/market-data-api/data-api
            - Market Data Getting Started: https://developer.webull.co.th/apis/docs/market-data-api/getting-started

            สิ่งที่ notebook นี้ยึดเป็นหลัก:
            - Webull OpenAPI Reference เป็น version 2.0
            - `app_secret` ใช้คำนวณ signature ฝั่ง client เท่านั้น ไม่ส่งเป็น request header
            - Live request ต้องมี `x-access-token`
            - Host ไทย `api.webull.co.th` ใช้ `HMAC-SHA256`
            - US stocks/ETFs ต้องมี market-data permission หรือ subscription สำหรับ OpenAPI
            """
        ),
        markdown_cell(
            """
            ## Outline

            1. Setup
            2. Credentials
            3. Token
            4. Signature
            5. Fetch AAPL Bars
            6. Save Raw JSON
            7. Plot Close
            8. Exercises and Common Pitfalls
            """
        ),
        markdown_cell(
            """
            ## Step 1 - Setup

            Cell นี้ตั้งค่า library, endpoint, และ output folder.

            ค่า default คือ offline mode (`WEBULL_TUTORIAL_LIVE=0`)
            เพื่อให้มือใหม่ run notebook ได้ทันทีโดยไม่ต้องมี key.

            ### โค้ดช่องถัดไปทำอะไร

            - import library ที่จำเป็น เช่น JSON, request, DataFrame และกราฟ
            - ตั้งค่า host ไทย `api.webull.co.th` และ endpoint สำหรับ AAPL historical bars
            - อ่านว่า notebook อยู่ใน offline mode หรือ live mode
            - สร้างโฟลเดอร์ output สำหรับเก็บ JSON และ HTML chart
            - ลอง import Webull SDK; ถ้าไม่มี SDK ก็ยัง run offline mode ได้
            """
        ),
        code_cell(
            """
            from __future__ import annotations

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
            import plotly.graph_objects as go
            import requests

            BASE_URL = "https://api.webull.co.th"
            HOST = "api.webull.co.th"
            REGION = "th"
            PATH_STOCK_BARS = "/openapi/market-data/stock/bars"
            LIVE_MODE = os.getenv("WEBULL_TUTORIAL_LIVE", "0") == "1"
            OUTPUT_DIR = Path(os.getenv("WEBULL_TUTORIAL_OUTPUT_DIR", "outputs/webull-th-beginner"))
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            try:
                from webull.core.client import ApiClient
                from webull.data.data_client import DataClient
            except ImportError:
                ApiClient = None
                DataClient = None

            print({"live_mode": LIVE_MODE, "base_url": BASE_URL, "output_dir": str(OUTPUT_DIR)})
            """
        ),
        markdown_cell(
            """
            ## Step 2 - Credentials

            Offline mode ไม่ต้องใช้ credentials.

            Live mode ต้องมี environment variables:

            ```bash
            WEBULL_TUTORIAL_LIVE=1
            WEBULL_APP_KEY=your_app_key
            WEBULL_APP_SECRET=your_app_secret
            WEBULL_TOKEN_DIR=.webull-token-th
            ```

            อย่าเขียน secret ลง notebook โดยตรง.

            ### โค้ดช่องถัดไปทำอะไร

            - อ่านค่า credential จาก `.env.webull-th` หรือ `.env`
            - สร้าง helper `redact` เพื่อโชว์ค่าแบบปิดบางส่วน ไม่พิมพ์ secret เต็ม ๆ
            - เก็บ `APP_KEY`, `APP_SECRET` และ token directory ไว้ใช้ใน cell ถัดไป
            - ถ้าเปิด live mode แต่ยังไม่มี key/secret จะหยุดทันทีเพื่อกัน request ผิดพลาด
            """
        ),
        code_cell(
            """
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


            def redact(value: str, keep: int = 4) -> str:
                if not value:
                    return "<missing>"
                if len(value) <= keep * 2:
                    return "*" * len(value)
                return f"{value[:keep]}...{value[-keep:]}"


            env_file = Path(".env.webull-th") if Path(".env.webull-th").exists() else Path(".env")
            file_values = read_env_file(env_file)

            APP_KEY = env_value("WEBULL_APP_KEY", file_values)
            APP_SECRET = env_value("WEBULL_APP_SECRET", file_values)
            TOKEN_DIR = Path(env_value("WEBULL_TOKEN_DIR", file_values, ".webull-token-th"))

            if LIVE_MODE and (not APP_KEY or not APP_SECRET):
                raise RuntimeError("Live mode requires WEBULL_APP_KEY and WEBULL_APP_SECRET")

            print({
                "env_file": str(env_file),
                "app_key": redact(APP_KEY),
                "secret_present": bool(APP_SECRET),
                "token_dir": str(TOKEN_DIR),
            })
            """
        ),
        markdown_cell(
            """
            ## Step 3 - Token

            Token คือค่าที่ส่งใน header `x-access-token`.

            ถ้าเรียก `api.webull.co.th` โดย sign request อย่างเดียวแต่ไม่มี token มักเจอ `INVALID_TOKEN`.
            Offline mode จะใช้ token จำลองเพื่อให้เรียน flow ได้ก่อน.

            ### โค้ดช่องถัดไปทำอะไร

            - ถ้าอยู่ offline mode จะคืน token จำลองชื่อ `offline-demo-token`
            - ถ้าอยู่ live mode จะใช้ Webull SDK ขอหรืออ่าน access token จาก token directory
            - ตรวจว่า token มีจริงก่อนนำไปใช้ใน request
            - แสดง token แบบ redacted เพื่อให้รู้ว่ามีค่าแล้วโดยไม่เผย token จริง
            """
        ),
        code_cell(
            """
            def get_access_token() -> str:
                if not LIVE_MODE:
                    return "offline-demo-token"
                if ApiClient is None or DataClient is None:
                    raise RuntimeError("Install webull-openapi-python-sdk before live mode")

                api_client = ApiClient(APP_KEY, APP_SECRET, REGION, connect_timeout=8, timeout=20)
                api_client.add_endpoint(REGION, HOST)
                api_client.set_token_dir(str(TOKEN_DIR))

                # DataClient initialization triggers SDK token initialization/check flow.
                DataClient(api_client)
                token = api_client.get_token()
                if not token:
                    raise RuntimeError("SDK did not return an access token")
                return token


            ACCESS_TOKEN = get_access_token()
            print({
                "token_present": bool(ACCESS_TOKEN),
                "token_preview": redact(ACCESS_TOKEN, keep=6),
            })
            """
        ),
        markdown_cell(
            """
            ## Step 4 - Signature

            Signature ยืนยันว่า request ถูกสร้างจาก app ที่รู้ `app_secret`.

            สำหรับ `api.webull.co.th`:
            - ใช้ `HMAC-SHA256`
            - ใส่ `host` ใน string ที่นำไป sign
            - ส่ง `x-access-token` เป็น header หลัง sign แล้ว
            - ไม่ส่ง app secret เป็น header

            ### โค้ดช่องถัดไปทำอะไร

            - สร้างฟังก์ชัน `build_signature_headers` สำหรับทำ signed request
            - รวม parameter, host, app key, timestamp และ nonce ให้ตรงรูปแบบที่ Webull ใช้ตรวจ
            - ใช้ `app_secret` คำนวณ HMAC signature แต่ไม่ส่ง `app_secret` ไปใน header
            - คืน header ที่จะใช้กับ `requests.get` ใน cell ดึงราคา
            """
        ),
        code_cell(
            """
            def build_signature_headers(
                *,
                path: str,
                query_params: dict[str, str],
                app_key: str,
                app_secret: str,
                host: str,
                access_token: str,
                algorithm: str = "HMAC-SHA256",
            ) -> dict[str, str]:
                timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                nonce = str(uuid.uuid4())

                sign_params = {k: str(v) for k, v in query_params.items()}
                sign_params.update(
                    {
                        "host": host,
                        "x-app-key": app_key,
                        "x-signature-algorithm": algorithm,
                        "x-signature-nonce": nonce,
                        "x-signature-version": "1.0",
                        "x-timestamp": timestamp,
                    }
                )

                sorted_params = "&".join(f"{k}={v}" for k, v in sorted(sign_params.items()))
                string_to_sign = quote(f"{path}&{sorted_params}", safe="")
                digest = hashlib.sha256 if algorithm == "HMAC-SHA256" else hashlib.sha1
                signature = base64.b64encode(
                    hmac.new((app_secret + "&").encode(), string_to_sign.encode(), digest).digest()
                ).decode()

                return {
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "x-version": "v2",
                    "x-app-key": app_key,
                    "x-timestamp": timestamp,
                    "x-signature-version": "1.0",
                    "x-signature-algorithm": algorithm,
                    "x-signature-nonce": nonce,
                    "x-signature": signature,
                    "x-access-token": access_token,
                    "x-webull-client-source": "sdk",
                }


            print("signature helper ready")
            """
        ),
        markdown_cell(
            """
            ## Step 5 - Fetch AAPL Bars

            Endpoint:

            ```text
            GET https://api.webull.co.th/openapi/market-data/stock/bars
            ```

            Parameters:

            ```text
            symbol=AAPL
            category=US_STOCK
            timespan=D
            count=120
            real_time_required=true
            ```

            Offline mode ใช้ sample response รูปร่างเดียวกับ Webull response.

            ### โค้ดช่องถัดไปทำอะไร

            - เตรียม sample AAPL bars สำหรับ offline mode
            - สร้างฟังก์ชัน `get_stock_bars` ที่ใช้ parameter เช่น symbol, category, timespan และ count
            - ถ้า offline จะคืน sample ทันที; ถ้า live จะ sign request แล้วเรียก `api.webull.co.th`
            - ตรวจว่า response เป็น list ของ bars ก่อนส่งต่อให้ cell ถัดไป
            - แสดงจำนวน rows พร้อมแถวแรกและแถวสุดท้ายเพื่อเช็กข้อมูลเร็ว ๆ
            """
        ),
        code_cell(
            """
            OFFLINE_AAPL_BARS = [
                {
                    "tickerId": "913256135",
                    "symbol": "AAPL",
                    "time": "2026-01-09T05:00:00.000+0000",
                    "open": "258.59455",
                    "close": "258.889002",
                    "high": "259.727445",
                    "low": "255.744844",
                    "volume": "39996967",
                    "trading_session": "",
                },
                {
                    "tickerId": "913256135",
                    "symbol": "AAPL",
                    "time": "2026-01-12T05:00:00.000+0000",
                    "open": "261.10",
                    "close": "263.42",
                    "high": "264.11",
                    "low": "260.70",
                    "volume": "42110000",
                    "trading_session": "",
                },
                {
                    "tickerId": "913256135",
                    "symbol": "AAPL",
                    "time": "2026-01-13T05:00:00.000+0000",
                    "open": "264.00",
                    "close": "262.80",
                    "high": "265.20",
                    "low": "261.90",
                    "volume": "39000000",
                    "trading_session": "",
                },
                {
                    "tickerId": "913256135",
                    "symbol": "AAPL",
                    "time": "2026-01-14T05:00:00.000+0000",
                    "open": "263.20",
                    "close": "266.10",
                    "high": "267.00",
                    "low": "262.50",
                    "volume": "45500000",
                    "trading_session": "",
                },
                {
                    "tickerId": "913256135",
                    "symbol": "AAPL",
                    "time": "2026-01-15T05:00:00.000+0000",
                    "open": "266.50",
                    "close": "268.70",
                    "high": "269.10",
                    "low": "265.80",
                    "volume": "47200000",
                    "trading_session": "",
                },
                {
                    "tickerId": "913256135",
                    "symbol": "AAPL",
                    "time": "2026-01-16T05:00:00.000+0000",
                    "open": "269.00",
                    "close": "271.25",
                    "high": "272.20",
                    "low": "268.60",
                    "volume": "51000000",
                    "trading_session": "",
                },
                {
                    "tickerId": "913256135",
                    "symbol": "AAPL",
                    "time": "2026-01-20T05:00:00.000+0000",
                    "open": "271.70",
                    "close": "270.40",
                    "high": "273.00",
                    "low": "269.50",
                    "volume": "43800000",
                    "trading_session": "",
                },
                {
                    "tickerId": "913256135",
                    "symbol": "AAPL",
                    "time": "2026-01-21T05:00:00.000+0000",
                    "open": "270.80",
                    "close": "274.35",
                    "high": "275.10",
                    "low": "270.00",
                    "volume": "48600000",
                    "trading_session": "",
                },
            ]


            def get_stock_bars(
                *,
                symbol: str = "AAPL",
                category: str = "US_STOCK",
                timespan: str = "D",
                count: int = 120,
                real_time_required: bool = True,
            ) -> list[dict[str, str]]:
                if not LIVE_MODE:
                    return OFFLINE_AAPL_BARS

                query_params = {
                    "symbol": symbol.upper(),
                    "category": category,
                    "timespan": timespan,
                    "count": str(count),
                    "real_time_required": str(real_time_required).lower(),
                }
                headers = build_signature_headers(
                    path=PATH_STOCK_BARS,
                    query_params=query_params,
                    app_key=APP_KEY,
                    app_secret=APP_SECRET,
                    host=HOST,
                    access_token=ACCESS_TOKEN,
                )
                response = requests.get(
                    f"{BASE_URL}{PATH_STOCK_BARS}",
                    headers=headers,
                    params=query_params,
                    timeout=30,
                )
                try:
                    payload = response.json()
                except ValueError:
                    payload = {"raw_text": response.text}

                if response.status_code != 200:
                    raise RuntimeError({"status_code": response.status_code, "payload": payload})
                if not isinstance(payload, list):
                    raise RuntimeError({
                        "status_code": response.status_code,
                        "unexpected_payload": payload,
                    })
                return payload


            bars = get_stock_bars(symbol="AAPL", count=120)
            print({"rows": len(bars), "first": bars[0], "last": bars[-1]})
            """
        ),
        markdown_cell(
            """
            ## Step 6 - Save Raw JSON

            Save raw response ก่อนแปลงข้อมูล เพื่อให้ย้อนดู response เดิมได้.

            ### โค้ดช่องถัดไปทำอะไร

            - save response ดิบเป็น `aapl-bars-raw.json`
            - แปลง JSON เป็น `pandas.DataFrame`
            - เปลี่ยน `time` เป็นวันที่ และแปลง open/high/low/close/volume เป็นตัวเลข
            - sort วันที่จากเก่าไปใหม่ แล้วสรุปจำนวน rows, ช่วงวันที่ และ close ล่าสุด
            """
        ),
        code_cell(
            """
            raw_json_path = OUTPUT_DIR / "aapl-bars-raw.json"
            raw_json_path.write_text(
                json.dumps(bars, indent=2, ensure_ascii=False) + "\\n",
                encoding="utf-8",
            )

            data = pd.DataFrame(bars).rename(columns={"time": "date"})
            data["date"] = pd.to_datetime(data["date"], errors="coerce")
            for column in ["open", "high", "low", "close", "volume"]:
                data[column] = pd.to_numeric(data[column], errors="coerce")
            data = data.sort_values("date").reset_index(drop=True)

            summary = {
                "rows": len(data),
                "first_date": str(data["date"].iloc[0]),
                "last_date": str(data["date"].iloc[-1]),
                "last_close": float(data["close"].iloc[-1]),
                "raw_json_path": str(raw_json_path),
            }
            summary
            """
        ),
        markdown_cell(
            """
            ## Step 7 - Plot Close

            เริ่มจากกราฟ `close` อย่างเดียว เพราะอ่านง่ายที่สุดสำหรับมือใหม่.

            ### โค้ดช่องถัดไปทำอะไร

            - สร้างกราฟเส้นจากคอลัมน์ `close`
            - ใช้แกน X เป็นวันที่ และแกน Y เป็นราคาปิด
            - save กราฟเป็น HTML เพื่อเปิดดูหรือแชร์ต่อได้
            - แสดงกราฟใน notebook ทันทีหลัง run cell
            """
        ),
        code_cell(
            """
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=data["date"],
                    y=data["close"],
                    mode="lines",
                    name="Close",
                    line={"color": "#2563eb", "width": 2.8},
                )
            )
            fig.update_layout(
                title="AAPL Close Price via Webull Thailand OpenAPI",
                xaxis_title="Date",
                yaxis_title="Close Price",
                template="plotly_white",
                hovermode="x unified",
                height=560,
                showlegend=False,
            )

            chart_path = OUTPUT_DIR / "aapl-close-chart.html"
            fig.write_html(chart_path, include_plotlyjs=True)
            print({"chart_path": str(chart_path)})
            fig
            """
        ),
        markdown_cell(
            """
            ## Exercises

            1. เปลี่ยน `count=120` เป็น `count=20` แล้วดูจำนวน rows ที่ได้
            2. เปิด live mode แล้วลองดึง symbol อื่นที่ account มี permission
            3. เพิ่ม EMA 22 จาก `data["close"]` แล้ว plot ทับกับ close

            ### โค้ดช่องถัดไปทำอะไร

            - copy ตารางราคาเป็นตัวแปรใหม่เพื่อไม่แก้ `data` ต้นฉบับ
            - คำนวณ EMA 22 จากราคาปิด
            - แสดง 5 แถวท้ายเพื่อดูว่า `ema22` ถูกเพิ่มเข้ามาแล้ว
            """
        ),
        code_cell(
            """
            exercise = data.copy()
            exercise["ema22"] = exercise["close"].ewm(span=22, adjust=False).mean()
            exercise[["date", "close", "ema22"]].tail()
            """
        ),
        markdown_cell(
            """
            ## Common Pitfalls

            - `INVALID_TOKEN`: ไม่มี token หรือ token หมดอายุ ให้ rerun Step 3
            - `Insufficient permission, please subscribe to stock quotes`:
              account/app ยังไม่มี market-data permission สำหรับ symbol นั้น
            - Signature mismatch: สำหรับ `api.webull.co.th` ใช้ `HMAC-SHA256`
            - Secret leak: อย่าเขียน App Secret ลง notebook, README, screenshot, หรือ git history

            ## Next Step

            เมื่อ notebook นี้รันได้แล้ว ให้แยก helper functions เป็น module เล็ก ๆ
            แล้วนำ `data` ไปต่อยอดกับ backtest หรือ factor research.
            """
        ),
    ]

    for cell, cell_id in zip(cells, CELL_IDS, strict=True):
        cell["id"] = cell_id

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


def write_notebook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    notebook = build_notebook()
    path.write_text(json.dumps(notebook, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Webull TH beginner tutorial notebook.")
    parser.add_argument("--out", default="notebooks/webull_th_beginner.ipynb")
    args = parser.parse_args()
    output = Path(args.out)
    write_notebook(output)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
