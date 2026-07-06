# Webull Thailand Endpoint Tutorial Notebooks

ชุด notebook นี้แยกตามหมวด endpoint เพื่อให้มือใหม่เรียนทีละส่วนได้ง่ายขึ้น.

ทุก notebook:

- ใช้ offline mode เป็นค่าเริ่มต้น (`WEBULL_TUTORIAL_LIVE=0`)
- มี sample response เพื่อ run ได้โดยไม่ต้องมี credential
- save raw JSON ลง `outputs/webull-th-endpoints/<notebook-slug>/`
- ใช้ `api.webull.co.th` และ `HMAC-SHA256` เมื่อเปิด live mode
- ไม่ฝัง App Key, App Secret, token, หรือ account id จริง

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
