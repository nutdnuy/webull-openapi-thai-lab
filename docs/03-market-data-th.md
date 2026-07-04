# Webull Market Data: ดึงราคาหุ้นและเข้าใจข้อจำกัด

บทนี้พาดึง market data จาก Webull OpenAPI โดยใช้ stock snapshot เป็นตัวอย่างหลักของ CLI

Official sources:

- Webull API Docs: https://developer.webull.com/apis/docs/
- Webull Market Data Overview: https://developer.webull.com/apis/docs/market-data-api/overview/
- Webull llms.txt: https://developer.webull.com/apis/llms.txt
- Webull Python SDK: https://github.com/webull-inc/webull-openapi-python-sdk

## รันผ่าน CLI

ตัวอย่างปัจจุบันของ CLI คือ stock snapshot:

```bash
webull-lab stock-snapshot AAPL
```

คำสั่งนี้โหลด settings, สร้าง data client และเรียก helper `get_stock_snapshot` โดย normalize symbol เป็นตัวพิมพ์ใหญ่ก่อนส่งไป SDK

ถ้าเจอ expected error เช่น credential ไม่ครบ, Webull response error หรือ symbol ที่ API ไม่รับ คำสั่ง `stock-snapshot` จะแสดง error output แบบสั้นและอ่านง่าย

## รันผ่านตัวอย่าง Python

```bash
python examples/02_market_data_snapshot.py
```

ตัวอย่างนี้ทำ flow เดียวกันแบบ Python script: โหลด `.env`, สร้าง data client, เรียก snapshot ของ `AAPL` แล้ว print JSON

## Snapshot และ historical bars

Market data helper ใน `src/webull_lab/market_data.py` รองรับสองรูปแบบ:

- `get_stock_snapshot`: ดึง snapshot ของ symbol
- `get_stock_bars`: ดึง historical bars โดยค่าเริ่มต้นใช้ timespan `M1`

ใน task ปัจจุบัน CLI example เปิดเฉพาะ stock snapshot เพื่อให้ tutorial สั้นและตรวจง่าย แต่โค้ด helper เตรียม historical bars ไว้สำหรับบทถัดไปหรือ extension

## Rate limit และ subscription caveat

Webull official docs ระบุข้อจำกัดของ HTTP API และ rate limit. ก่อนเขียน loop ดึงข้อมูลหลาย symbol หรือหลาย timeframe ต้องเช็กข้อกำหนดล่าสุดจาก https://developer.webull.com/apis/docs/ และออกแบบ retry/backoff ให้เหมาะสม

Market data บางส่วนอาจขึ้นกับ permission, subscription, market, region หรือ account entitlement. ถ้า snapshot บาง symbol ไม่ตอบตามที่คาด ให้แยกตรวจว่าเป็นปัญหา credential, subscription, symbol format, market type หรือ rate limit

## Checklist

- เริ่มจาก `webull-lab stock-snapshot AAPL`
- ถ้าต้อง debug ให้เทียบกับ `python examples/02_market_data_snapshot.py`
- อย่า hard-code app key หรือ app secret ใน script
- อย่าเขียน loop ยิง API ถี่ ๆ โดยไม่อ่าน Webull rate limit docs
