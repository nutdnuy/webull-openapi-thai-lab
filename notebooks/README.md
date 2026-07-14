# Webull Thailand Endpoint Tutorial Notebooks

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
