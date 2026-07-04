# Webull GitHub Publishing Checklist

บทนี้เป็น checklist ก่อน publish Webull OpenAPI Thai Lab ขึ้น GitHub เพื่อให้ repo สาธารณะไม่มี secret และ CI ตรวจพื้นฐานได้

Official sources:

- Webull API Docs: https://developer.webull.com/apis/docs/
- Webull SDK Docs: https://developer.webull.com/apis/docs/sdk/
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

## 2. Secret scan แบบ noise ต่ำ

ก่อน publish ให้เริ่มจากการตรวจ tracked files ด้วย pattern ที่พยายามจับค่าจริงมากกว่า placeholder:

```bash
git grep -nE '(WEBULL_APP_KEY|WEBULL_APP_SECRET|WEBULL_ACCOUNT_ID)=[A-Za-z0-9_./+-]{12,}' -- ':!*.example' ':!docs/*' ':!tests/*'
```

คำสั่งนี้ตั้งใจข้าม `.env.example`, docs และ tests เพราะไฟล์เหล่านั้นมี placeholder และ guardrail words โดยตั้งใจอยู่แล้ว. ถ้าคำสั่งนี้เจอผลลัพธ์ ให้ตรวจทันทีว่าเป็น Webull credential, account id หรือ token จริงหรือไม่

ถ้าต้องการ manual review แบบกว้างขึ้น ใช้ broad grep ได้ แต่ผลลัพธ์จะ noisy เพราะ docs/tests มีคำเตือนและ placeholder:

```bash
rg -n "WEBULL_APP_KEY|WEBULL_APP_SECRET|WEBULL_ACCOUNT_ID|I_UNDERSTAND|token|secret|password" README.md docs tests src examples .env.example
```

ถ้าติดตั้ง scanner ไว้แล้ว ให้รันเพิ่ม:

```bash
gitleaks detect --source . --no-banner
```

หรือใช้ secret scanner ตัวอื่นที่ทีมใช้อยู่ โดยต้องตรวจผลลัพธ์ก่อน push ทุกครั้ง

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

ถ้ามี CI แล้ว หรือหลังเพิ่ม GitHub Actions ในขั้นถัดไป ให้ดูว่า command เหล่านี้ผ่าน:

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
