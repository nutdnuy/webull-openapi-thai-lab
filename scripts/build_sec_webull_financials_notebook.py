#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "notebooks" / "sec_webull_financials_beginner.ipynb"


def markdown(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": dedent(source).strip() + "\n",
    }


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dedent(source).strip() + "\n",
    }


def explanation(action: str, expected: str, mistake: str) -> dict:
    return markdown(
        f"""
        ### โค้ดช่องถัดไปทำอะไร

        - สิ่งที่จะทำ: {action}
        - ผลลัพธ์ที่ควรเห็น: {expected}
        - จุดที่ต้องระวัง: {mistake}
        """
    )


def interpretation(source: str) -> dict:
    return markdown(f"#### วิธีอ่านผลลัพธ์\n\n{source}")


def build_notebook() -> dict:
    cells = [
        markdown(
            """
            # SEC EDGAR + Webull Financial Data for Beginners

            Tutorial ภาษาไทยแบบ offline-first สำหรับสร้างงบการเงิน AAPL จาก SEC EDGAR,
            เติม daily prices จาก Webull, คำนวณ timing-safe metrics และ export ชุดข้อมูลที่
            ตรวจสอบย้อนกลับได้ โดยไม่กล่าวอ้างว่าสามารถทำนายราคาได้

            ## กลุ่มผู้เรียน

            ผู้เริ่มต้น Python/Pandas ที่ต้องการต่อยอดไปสู่งาน equity research หรือ
            quantitative research และต้องการเข้าใจความต่างระหว่างข้อมูล ณ `period end`
            กับวันที่ข้อมูลพร้อมใช้จริง (`filed date`)

            ## สิ่งที่ต้องเตรียม

            - ติดตั้งโปรเจกต์ด้วย `pip install -e ".[dev]"`
            - Offline mode ไม่ใช้ key, credential หรือ network
            - Live mode ต้องตั้ง `SEC_WEBULL_TUTORIAL_LIVE=1`, `SEC_CONTACT_EMAIL` และ
              Webull credentials เฉพาะเมื่อมี market-data permission; หาก Webull ไม่พร้อม
              ส่วน SEC-only ยังทำงานได้

            ## เป้าหมายการเรียนรู้

            1. แปลง ticker เป็น CIK 10 หลัก
            2. แยก annual, quarterly และ YTD facts พร้อม provenance
            3. normalize Webull OHLCV ให้เป็น canonical schema
            4. ใช้ `filed_date` จับคู่ราคาเพื่อลด look-ahead bias
            5. สร้างกราฟและ export artifacts ที่ audit ได้

            ## ลำดับบทเรียน

            Setup → Ticker to CIK → Financial Statements → Webull Prices → Metrics →
            Charts → Export → Exercise → Checklist

            ## Core Concepts

            - **CIK** คือรหัสบริษัทของ SEC; ต้องรักษาเลขศูนย์ด้านหน้า
            - **Provenance** คือข้อมูลที่บอก source taxonomy, XBRL tag, unit, form,
              accession number และ filed date
            - **Timing safety** หมายถึงไม่ใช้ข้อมูลงบก่อนวันที่ตลาดมีโอกาสรับรู้
            - Webull เป็น optional enrichment; ความล้มเหลวของราคาไม่ควรทำให้งบ SEC หาย

            ## Workflow

            ใช้ public pipeline เดียวกับ CLI:
            `SEC client → build_financial_statements → Webull normalization →
            build_financial_metrics → write_company_artifacts`
            """
        ),
        markdown(
            """
            ## Step 1 - Setup

            Notebook เริ่มใน offline mode เสมอ เว้นแต่ผู้ใช้เปิด live mode ชัดเจนด้วยค่า `1`.
            Output default อยู่ใต้ `outputs/` ซึ่งถูก gitignore และเปลี่ยนได้ด้วย environment
            variable จึงไม่ควรฝัง path ส่วนตัวหรือ secret ใน notebook.
            """
        ),
        explanation(
            "โหลด library, หา repository root จาก package และสร้าง client ตาม mode",
            "เห็น ticker, mode และ output directory โดยไม่มี credential ปรากฏ",
            "อย่าเรียก config loader หรือ client factory ใน offline mode",
        ),
        code(
            """
            import json
            import os
            from pathlib import Path

            import pandas as pd
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            from webull.core.exception.exceptions import ClientException, ServerException

            import webull_lab
            from webull_lab.account import ResponseError
            from webull_lab.cli import PartialWebullCredentialsError, build_optional_data_client
            from webull_lab.company_pipeline import run_company_pipeline
            from webull_lab.financials import build_financial_statements
            from webull_lab.market_data import get_daily_stock_bars, normalize_stock_bars
            from webull_lab.metrics import build_financial_metrics
            from webull_lab.sec_client import SecClient
            from webull_lab.sec_config import load_sec_settings
            from webull_lab.tutorial_fixtures import FixtureDataClient, FixtureSecClient

            LIVE_MODE = os.getenv("SEC_WEBULL_TUTORIAL_LIVE", "0") == "1"
            TICKER = os.getenv("SEC_WEBULL_TUTORIAL_TICKER", "AAPL").strip().upper()
            REPO_ROOT = Path(webull_lab.__file__).resolve().parents[2]
            default_output = REPO_ROOT / "outputs" / "sec-webull-financials"
            OUTPUT_DIR = Path(
                os.getenv("SEC_WEBULL_TUTORIAL_OUTPUT_DIR", str(default_output))
            ).expanduser()
            FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures"

            if LIVE_MODE:
                sec_client = SecClient(load_sec_settings())
                try:
                    data_client = build_optional_data_client()
                except (PartialWebullCredentialsError, RuntimeError):
                    data_client = None
                    print("Webull ไม่พร้อม: บทเรียนจะทำงานต่อในโหมด SEC-only")
            else:
                sec_client = FixtureSecClient(FIXTURE_ROOT / "sec")
                data_client = FixtureDataClient(
                    FIXTURE_ROOT / "webull" / "aapl_daily_bars_sample.json"
                )

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            print({"ticker": TICKER, "live_mode": LIVE_MODE, "output_dir": str(OUTPUT_DIR)})
            """
        ),
        interpretation(
            "`live_mode=False` ยืนยันว่า cell ไม่อ่าน Webull/SEC credentials และใช้เฉพาะ "
            "fixture ใน repository."
        ),
        markdown(
            """
            ## Step 2 - Ticker to CIK

            SEC ใช้ CIK 10 หลักเป็นรหัสบริษัท ส่วน ticker เป็นชื่อย่อในตลาด.
            """
        ),
        explanation(
            "resolve ticker เป็น CIK ผ่าน interface เดียวกันทั้ง offline และ live",
            "ได้ CIK 10 หลักที่ตรงกับ ticker (`0000320193` สำหรับ AAPL offline)",
            "อย่าแปลง CIK เป็น integer เพราะเลขศูนย์ด้านหน้าจะหาย",
        ),
        code(
            """
            CIK = sec_client.resolve_cik(TICKER)
            print({"ticker": TICKER, "cik": CIK})
            """
        ),
        interpretation("CIK ต้องยาว 10 หลักและใช้ค่านี้กับ submissions/companyfacts ชุดเดียวกัน."),
        markdown(
            """
            ## Step 3 - Financial Statements

            Company Facts มี XBRL tags หลายแบบ. ตัว normalizer เลือก canonical metrics,
            เก็บ source tag/unit/form/accession และแยก annual, quarterly, YTD โดยไม่แทน missing
            fact ด้วยศูนย์.
            """
        ),
        explanation(
            "โหลด Company Facts และสร้าง Income Statement, Balance Sheet, Cash Flow",
            "เห็นจำนวนแถวและชนิด period ของแต่ละงบแบบสรุป",
            "อย่าผสม `USD` กับ `USD/shares` หรือรวม quarterly กับ YTD",
        ),
        code(
            """
            companyfacts = sec_client.get_companyfacts(CIK)
            statements = build_financial_statements(TICKER, CIK, companyfacts, years=5)
            statement_summary = pd.DataFrame(
                [
                    {
                        "statement": name,
                        "rows": len(frame),
                        "period_types": ", ".join(sorted(frame["period_type"].unique())),
                    }
                    for name, frame in statements.items()
                ]
            )
            statement_summary
            """
        ),
        interpretation(
            "จำนวนแถวต่างกันได้เพราะ SEC facts บาง metric ไม่มีทุกงวด; ให้ตรวจ `source_tag`, "
            "`unit`, `period_type` และ `filed_date` ก่อนวิเคราะห์."
        ),
        markdown(
            """
            ## Step 4 - Webull Prices

            Webull daily OHLCV เป็นข้อมูลเสริม. Offline fixture มีแถวขนาดเล็กเพื่อทดสอบ schema;
            live mode อาจไม่มีราคาเมื่อ permission ไม่พร้อม แต่ขั้น SEC ยังไปต่อได้.
            ตามเอกสาร Webull, bars ระดับ daily ขึ้นไปเป็น forward-adjusted: ประวัติราคา
            ถูกปรับย้อนหลังเมื่อมี corporate actions. จึงต้องระวังเมื่อเทียบราคาเก่ากับ
            per-share facts ที่รายงาน ณ เวลานั้น.
            """
        ),
        explanation(
            "ดึง daily bars ผ่าน public helper และ normalize เป็น canonical price table",
            "เห็นคอลัมน์ `symbol, date, open, high, low, close, volume` ไม่เกิน 5 แถว",
            "HTTP 403 มักเป็นเรื่อง market-data permission; ไม่ควรพิมพ์ raw exception ที่อาจมีข้อมูลอ่อนไหว",
        ),
        code(
            """
            if data_client is None:
                prices = normalize_stock_bars([])
            else:
                try:
                    prices = normalize_stock_bars(get_daily_stock_bars(data_client, TICKER))
                except (ResponseError, ClientException, ServerException, RuntimeError, ValueError):
                    prices = normalize_stock_bars([])
                    print("ราคา Webull ไม่พร้อม: ใช้ SEC-only ต่อโดยไม่เปิดเผยรายละเอียดอ่อนไหว")
            prices.head(5)
            """
        ),
        interpretation(
            "ตารางว่างใน live mode ไม่ใช่ความล้มเหลวของ SEC pipeline; valuation metrics "
            "ที่ต้องใช้ราคาจะมี status บอก missing input."
        ),
        markdown(
            """
            ## Step 5 - Metrics

            Metrics ใช้ annual facts และราคาวันซื้อขายแรกตั้งแต่ `filed_date` เป็นต้นไป.
            ค่า `status` สำคัญเท่ากับ `value` เพราะบอกว่า input ขาด, unit ไม่เข้ากัน
            หรือ denominator ไม่ meaningful.
            """
        ),
        explanation(
            "คำนวณ growth, margins, ROE, cash flow และ valuation metrics",
            "เห็น metric/status/value/available_date/price_date แบบตารางสั้น",
            "อย่าใช้ period end เป็นวันที่ข้อมูลงบเปิดเผย และอย่าข้าม status",
        ),
        code(
            """
            metrics = build_financial_metrics(statements, prices)
            metric_preview = metrics[
                ["metric", "status", "value", "available_date", "price_date"]
            ].head(12)
            metric_preview
            """
        ),
        interpretation(
            "ใช้เฉพาะแถว `status == 'available'` สำหรับการคำนวณต่อ และรักษา "
            "`available_date` ไว้ใน research dataset เพื่อป้องกัน leakage."
        ),
        markdown(
            """
            ## Step 6 - Charts

            แยกหน่วยเงินของงบกับราคาหุ้นเป็นคนละ panel. กราฟนี้ใช้เพื่อสำรวจข้อมูล
            ไม่ใช่หลักฐานเชิงเหตุและผลหรือการพยากรณ์ผลตอบแทน. เส้นราคาคือ
            `forward-adjusted close`; corporate actions ในอนาคตอาจทำให้ประวัติถูกปรับย้อนหลัง.
            """
        ),
        explanation(
            "วาด annual revenue/net income และ daily close แล้วบันทึก HTML แบบมี Plotly JS ในไฟล์",
            "ได้ `sec-webull-financials-chart.html` ที่เปิด offline ได้",
            "อย่าใช้ CDN เพราะกราฟจะเปิดไม่ได้เมื่อไม่มี network",
        ),
        code(
            """
            annual_income = statements["income_statement"].query("period_type == 'annual'")
            figure = make_subplots(
                rows=2,
                cols=1,
                subplot_titles=(
                    "Annual financial facts (USD)",
                    "Forward-adjusted daily close (USD)",
                ),
                vertical_spacing=0.14,
            )
            for metric_name in ("revenue", "net_income"):
                selected = annual_income.query("canonical_metric == @metric_name")
                figure.add_trace(
                    go.Bar(
                        x=selected["end_date"],
                        y=selected["value"].map(float),
                        name=metric_name,
                    ),
                    row=1,
                    col=1,
                )
            if not prices.empty:
                figure.add_trace(
                    go.Scatter(
                        x=prices["date"],
                        y=prices["close"].map(float),
                        name="forward-adjusted close",
                    ),
                    row=2,
                    col=1,
                )
            figure.update_layout(
                template="plotly_dark",
                title=f"{TICKER}: SEC financial facts and Webull prices",
                height=760,
            )
            chart_path = OUTPUT_DIR / "sec-webull-financials-chart.html"
            figure.write_html(chart_path, include_plotlyjs=True, full_html=True)
            print(chart_path)
            """
        ),
        interpretation(
            "เปิด HTML ได้โดยไม่ต่ออินเทอร์เน็ต. แนวโน้มที่เห็นเป็นเพียง descriptive view; "
            "ต้องออกแบบสมมติฐานและ validation แยกต่างหากก่อนใช้กับการลงทุน."
        ),
        markdown(
            """
            ## Step 7 - Export

            เรียก public pipeline เดียวกับคำสั่ง `company-data` เพื่อเขียน canonical CSV,
            Parquet, JSON, raw SEC payloads และ manifest. Pipeline จะ normalize และคำนวณใหม่
            จาก inputs จึงไม่พึ่ง hidden notebook state. Public pipeline เป็นเจ้าของ data
            artifacts ส่วนกราฟเป็น notebook-created artifact จึงลงทะเบียนเพิ่มหลัง pipeline สำเร็จ.
            """
        ),
        explanation(
            "รัน pipeline, ลงทะเบียนกราฟใน audit metadata และเขียน manifest แบบ deterministic JSON",
            "manifest ระบุ source status, files และ `notebook_artifacts` ตรงกับไฟล์บน disk",
            "อย่า commit `outputs/`, raw payload ส่วนตัว, `.env` หรือ token",
        ),
        code(
            """
            manifest = run_company_pipeline(TICKER, 5, OUTPUT_DIR, sec_client, data_client)
            manifest["notebook_artifacts"] = [chart_path.name]
            manifest["files"] = sorted({*manifest["files"], chart_path.name})
            manifest_path = OUTPUT_DIR / "run_manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\\n",
                encoding="utf-8",
            )
            export_summary = {
                "ticker": manifest["ticker"],
                "sec_status": manifest["sec_status"],
                "webull_status": manifest["webull_status"],
                "warnings": manifest["warnings"],
                "file_count": len(manifest["files"]),
            }
            print(export_summary)
            """
        ),
        interpretation(
            "ตรวจ `run_manifest.json` ก่อนใช้ผลลัพธ์ทุกครั้ง. `webull_status=unavailable` "
            "ยังยอมรับได้สำหรับงาน SEC-only แต่ valuation metrics อาจไม่พร้อม."
        ),
        markdown(
            """
            ## Common Mistakes

            - สลับ annual, quarterly และ YTD หรือรวมคนละ unit
            - ใช้ `period end` แทน `filed date` จนเกิด look-ahead bias
            - เติม missing XBRL fact เป็นศูนย์ หรือใช้ metric โดยไม่ตรวจ status
            - สรุปจากกราฟว่าปัจจัยหนึ่งทำให้อีกปัจจัยเปลี่ยนโดยไม่มีการทดสอบ
            - เทียบ forward-adjusted price กับ historical per-share facts โดยไม่ตรวจ corporate actions
            - เปิด live mode โดยไม่ตั้ง SEC contact ที่เหมาะสม หรือเผย secret ใน output

            ## Exercise

            เลือก annual revenue และ net income สองปีล่าสุด แล้วสร้างตารางที่มี
            `fiscal_year`, `canonical_metric`, `value`, `unit`, `filed_date`.
            จากนั้นเขียน 2–3 ประโยคว่า facts ใด “พร้อมใช้” เมื่อใด และเพราะเหตุใด
            เราจึงยังสรุปการทำนายผลตอบแทนจากตารางนี้ไม่ได้.
            """
        ),
        explanation(
            "สร้าง answer scaffold สำหรับแบบฝึกหัดโดยเลือกเฉพาะ annual facts สองปีล่าสุด",
            "ได้ตารางเล็กที่ยังมีช่องให้เขียน interpretation ต่อ",
            "อย่าลบ filed_date หรือเลือกแถวด้วยตำแหน่งโดยไม่ sort fiscal_year",
        ),
        code(
            """
            exercise_source = statements["income_statement"].query(
                "period_type == 'annual' and canonical_metric in ['revenue', 'net_income']"
            )
            latest_years = sorted(exercise_source["fiscal_year"].dropna().unique())[-2:]
            exercise_answer = (
                exercise_source.loc[
                    exercise_source["fiscal_year"].isin(latest_years),
                    ["fiscal_year", "canonical_metric", "value", "unit", "filed_date"],
                ]
                .sort_values(["fiscal_year", "canonical_metric"])
                .reset_index(drop=True)
            )
            exercise_answer
            # เฉลยตั้งต้น: เขียน interpretation โดยอ้าง filed_date และ metric status ที่นี่
            """
        ),
        interpretation(
            "เฉลยตั้งต้นควรระบุว่าข้อมูลพร้อมใช้ไม่ก่อน `filed_date`; ความสัมพันธ์กับราคา "
            "ต้องทดสอบ out-of-sample พร้อม transaction costs และไม่รับประกันผลตอบแทน."
        ),
        markdown(
            """
            ## Checklist

            - [ ] CIK มี 10 หลักและตรงกับ ticker
            - [ ] ตรวจ source tag, unit, form, accession และ period type
            - [ ] ใช้ filed date/available date และตรวจ metric status
            - [ ] เปิด chart ได้ offline และไม่มี external CDN dependency
            - [ ] manifest ระบุ source status และ artifacts ครบ
            - [ ] รันจากบนลงล่างได้โดยไม่มี hidden state
            - [ ] ไม่มี secret ใน notebook, logs หรือ output ที่แชร์

            ## นำไปใช้กับงานจริง

            เปลี่ยนเป็น live modeเฉพาะเมื่อพร้อม แล้วเก็บ SEC cache/output ในพื้นที่ private.
            สำหรับ backtest ให้สร้าง point-in-time dataset จาก `filed_date`, แยก train/test,
            ตรวจ data leakage, survivorship bias, restatements, transaction costs และ risk controls.
            ผลลัพธ์นี้เป็น research input ไม่ใช่คำรับรองราคา/ผลตอบแทน.

            ### Optional Extension

            เพิ่ม ticker อื่นใน live mode แล้วเปรียบเทียบ schema และ missing metrics โดยไม่แก้
            pipeline. ถ้า Webull ไม่พร้อม ให้ทำ SEC-only comparison และบันทึกข้อจำกัดใน manifest.
            """
        ),
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the SEC Webull beginner notebook.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(build_notebook(), ensure_ascii=False, indent=1) + "\n"
    args.out.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()
