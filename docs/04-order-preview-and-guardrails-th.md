# Webull Order Preview และ Guardrails

บทนี้อธิบาย order workflow แบบ preview-only สำหรับ Webull OpenAPI Thai Lab พร้อม guardrails ที่ช่วยลดความเสี่ยงก่อนแตะ live order

Official sources:

- Webull API Docs: https://developer.webull.com/apis/docs/
- Webull llms.txt: https://developer.webull.com/apis/llms.txt
- Webull Python SDK: https://github.com/webull-inc/webull-openapi-python-sdk

## Preview order ผ่าน CLI

รัน:

```bash
webull-lab preview-stock-buy AAPL 100 1
```

คำสั่งนี้ preview limit buy order ของ `AAPL` ที่ราคา `100` จำนวน `1` โดยต้องมี `WEBULL_ACCOUNT_ID` ใน `.env` ก่อน

ถ้าต้องการรันผ่าน Python example:

```bash
python examples/03_order_preview.py
```

ทั้งสองทางใช้ preview endpoint เท่านั้น ไม่ใช่การส่งคำสั่งซื้อขายจริง

## ไม่มี CLI สำหรับ live order

Repo นี้ไม่มี CLI command สำหรับ place live order. คำสั่งที่เกี่ยวกับ order ใน CLI คือ `preview-stock-buy` เท่านั้น เพื่อให้ tutorial เหมาะกับการเรียนและลดความเสี่ยงจากการพิมพ์คำสั่งผิด

ในโค้ดมี helper `place_stock_limit_buy` สำหรับกรณีที่ผู้พัฒนาจะต่อยอดเอง แต่ helper นี้ถูก block ด้วย guardrail:

- ต้องมี `WEBULL_ACCOUNT_ID`
- ต้องตั้ง `WEBULL_ALLOW_LIVE_ORDERS=I_UNDERSTAND`
- ถ้าไม่ตั้ง จะ raise `LiveOrderBlocked`

อย่าตั้งค่านี้ใน `.env` ระหว่างเรียน tutorial หรือระหว่างรัน tests

## Input validation ก่อน SDK calls

Order builder validate input ก่อนเรียก Webull SDK:

- `symbol` ต้องไม่เป็นค่าว่าง และจะถูกแปลงเป็นตัวพิมพ์ใหญ่
- `limit_price` ต้องเป็นตัวเลข decimal ที่มากกว่า 0
- `quantity` ต้องเป็นตัวเลข decimal ที่มากกว่า 0
- ค่า blank, non-numeric, non-positive, infinity หรือ invalid decimal จะถูก reject ก่อน SDK call

ดังนั้นกรณีเช่น `webull-lab preview-stock-buy "" 100 1`, `webull-lab preview-stock-buy AAPL 0 1`, `webull-lab preview-stock-buy AAPL abc 1` หรือ quantity ติดลบควร fail ตั้งแต่ local validation

## Concise expected errors

คำสั่ง `preview-stock-buy` ใช้ error output แบบสั้นสำหรับ expected errors เช่น account id ยังไม่ตั้งค่า, input validation fail, SDK/runtime error หรือ Webull response error. จุดประสงค์คือให้ผู้เรียนเห็นสาเหตุหลักโดยไม่พ่น stack trace ยาวใน CLI

## Checklist ก่อน preview

- ใช้ `WEBULL_ENV=uat`
- ตั้ง `WEBULL_ACCOUNT_ID` จาก UAT account list
- ตรวจด้วย `webull-lab doctor` ว่า account id ถูก redact
- เริ่มจาก symbol, price และ quantity เล็ก ๆ เพื่อเรียนรู้ response shape
- จำไว้ว่า preview ไม่เท่ากับ place order และ repo นี้ไม่มี live-order CLI
