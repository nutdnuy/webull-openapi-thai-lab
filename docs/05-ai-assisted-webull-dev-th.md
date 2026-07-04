# Webull AI-Assisted Development: ใช้ AI ช่วย dev อย่างปลอดภัย

บทนี้แนะนำวิธีใช้ AI coding assistant กับ Webull OpenAPI โดยใช้ official docs และ `llms.txt` เป็นแหล่งอ้างอิงหลัก พร้อมกติกาความปลอดภัยสำหรับ secret, tests และ order workflow

Official sources:

- Webull API Docs: https://developer.webull.com/apis/docs/
- Webull llms.txt: https://developer.webull.com/apis/llms.txt
- Webull Python SDK: https://github.com/webull-inc/webull-openapi-python-sdk

## ใช้ llms.txt เป็น context

Webull มี `llms.txt` ที่ออกแบบมาให้ AI assistant อ่านโครงสร้างเอกสารได้ง่าย:

```text
https://developer.webull.com/apis/llms.txt
```

เวลาให้ AI ช่วย implement feature ควรให้มันอ้างอิง official docs และ SDK repo แทนการเดา endpoint หรือ field name เอง โดยเฉพาะเรื่อง authentication, account, market data, order preview และ rate limit

## Safe prompt

ใช้ prompt แนวนี้:

```text
You are helping me extend a Python tutorial repo for Webull OpenAPI.
Use only official Webull sources:
- https://developer.webull.com/apis/docs/
- https://developer.webull.com/apis/llms.txt
- https://github.com/webull-inc/webull-openapi-python-sdk

Constraints:
- Do not hard-code API keys, app secrets, account IDs, tokens, or private data.
- Use .env variables and keep examples safe for UAT.
- Add fake-client tests for SDK interactions; do not require real Webull credentials in tests.
- Do not add any CLI command that places live orders.
- For order work, prefer preview_order and local validation before SDK calls.
- Keep expected CLI errors concise and user-readable.
```

## Tests ต้องใช้ fake client

ห้ามให้ unit tests เรียก Webull จริง. Tests ควรใช้ fake client หรือ mock object เพื่อยืนยันว่าโค้ดส่ง parameter ถูกต้อง, validate input ถูกต้อง และ handle error ถูกต้อง

แนวทางนี้ช่วยให้ CI รันได้โดยไม่มี credential และไม่เสี่ยงยิงคำสั่งไปยัง account จริง

## ห้าม hard-code secrets

AI assistant มักสร้างตัวอย่างที่ใส่ placeholder แปลก ๆ หรือเผลอ hard-code token. ก่อนรับ patch ให้ตรวจ:

- ไม่มี app key/app secret/account id จริงในไฟล์
- ไม่มี token file หรือ `.env` ถูกเพิ่มเข้า git
- ไม่มี secret ใน README, docs, tests หรือ screenshot
- `webull-lab doctor` ยัง redact app key, app secret และ account id

## ห้ามเพิ่ม live order CLI

Repo นี้ตั้งใจให้ CLI มี order preview เท่านั้น. ถึงแม้โค้ดมี `place_stock_limit_buy` สำหรับต่อยอดเชิง library แต่ไม่ควรให้ AI เพิ่มคำสั่ง CLI สำหรับ live orders ใน tutorial นี้

ถ้าจะทดลอง live order นอก tutorial ต้องทำเป็นงานแยก พร้อม review, explicit opt-in, environment guard, account guard, dry-run mode, audit log และ human confirmation

## Checklist เวลาให้ AI แก้โค้ด

- ให้ AI อ่านโค้ดปัจจุบันก่อนแก้
- ให้ AI อ้าง official Webull docs เมื่อแตะ endpoint/SDK behavior
- ให้ AI เพิ่มหรือแก้ tests ที่ใช้ fake client
- รัน `python -m pytest -v` และ `python -m ruff check .`
- review diff หา secret และ live-order path ก่อน commit
