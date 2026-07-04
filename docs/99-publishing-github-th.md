# Webull GitHub Publishing Checklist

บทนี้เป็น checklist ก่อน publish Webull OpenAPI Thai Lab ขึ้น GitHub เพื่อให้ repo สาธารณะไม่มี secret และ CI ตรวจพื้นฐานได้

Official sources:

- Webull API Docs: https://developer.webull.com/apis/docs/
- Webull llms.txt: https://developer.webull.com/apis/llms.txt
- Webull Python SDK: https://github.com/webull-inc/webull-openapi-python-sdk

## 1. ตรวจไฟล์ก่อน push

รัน tests และ lint:

```bash
python -m pytest -v
python -m ruff check .
```

ตรวจ git status:

```bash
git status --short
```

ไฟล์ที่ไม่ควรขึ้น git:

- `.env`
- `.env.*` ยกเว้น `.env.example`
- `.webull-token/`
- token files
- private key files
- raw data หรือ output ที่มีข้อมูลบัญชี

## 2. Secret grep

ก่อน publish ให้ค้นหาคำที่เสี่ยง:

```bash
rg -n "WEBULL_APP_KEY|WEBULL_APP_SECRET|WEBULL_ACCOUNT_ID|I_UNDERSTAND|token|secret|password" .
```

การเจอคำใน `.env.example`, docs หรือ tests อาจเป็นเรื่องปกติถ้าเป็น placeholder หรือคำเตือน แต่ห้ามมีค่าจริงของ Webull credential, account id หรือ token

## 3. สร้าง GitHub repo และ push

เมื่อพร้อมแล้วรัน:

```bash
gh repo create nutdnuy/webull-openapi-thai-lab --public --source=. --remote=origin --push
```

ถ้ามี remote `origin` อยู่แล้ว ให้ตรวจด้วย:

```bash
git remote -v
```

แล้วค่อย push ไป remote ที่ถูกต้อง

## 4. ตั้ง topics

ตั้ง GitHub topics เพื่อให้ค้นหา repo ง่ายขึ้น เช่น:

```text
webull
openapi
python
thai
trading-api
market-data
uat
```

## 5. CI check

หลัง push ให้ดู GitHub Actions หรือ CI ที่ตั้งไว้ว่า command เหล่านี้ผ่าน:

```bash
python -m pytest -v
python -m ruff check .
```

ถ้า CI fail เพราะต้องใช้ Webull credential แปลว่า tests ยังไม่ isolate พอ. Unit tests ควรใช้ fake client และไม่ต้องพึ่ง account จริง

## 6. เปิด secret scanning

ใน GitHub repository settings ให้เปิด secret scanning และ push protection ถ้า plan รองรับ. ถึง repo นี้จะ ignore `.env` แล้ว แต่ secret scanning เป็น guardrail อีกชั้นก่อนเผยแพร่ต่อสาธารณะ

## 7. Review หลัง publish

เปิดหน้า repo สาธารณะแล้วตรวจ:

- README link ไป docs ครบ
- Docs ภาษาไทยเปิดอ่านได้
- Official Webull source links ถูกต้อง
- ไม่มี screenshot หรือ output ที่เห็น account id เต็ม
- ไม่มี CLI command สำหรับ live order
- Order docs ย้ำว่า preview เท่านั้น และ `place_stock_limit_buy` ต้อง opt-in ด้วย `WEBULL_ALLOW_LIVE_ORDERS=I_UNDERSTAND`
