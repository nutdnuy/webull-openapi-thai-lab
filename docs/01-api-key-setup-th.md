# Webull API Key Setup: ตั้งค่า secret อย่างปลอดภัย

บทนี้อธิบายการตั้งค่า API key สำหรับ Webull OpenAPI Thai Lab โดยใช้ UAT ก่อนเสมอ และจัดการ secret ให้ไม่หลุดเข้า GitHub

Official sources:

- Webull API Docs: https://developer.webull.com/apis/docs/
- Webull llms.txt: https://developer.webull.com/apis/llms.txt
- Webull Python SDK: https://github.com/webull-inc/webull-openapi-python-sdk

## ขั้นตอนตั้งค่า

เริ่มจากคัดลอกไฟล์ตัวอย่าง:

```bash
cp .env.example .env
```

แก้ `.env` เป็นค่าของคุณ:

```dotenv
WEBULL_ENV=uat
WEBULL_REGION=us
WEBULL_APP_KEY=replace_with_your_app_key
WEBULL_APP_SECRET=replace_with_your_app_secret
WEBULL_ACCOUNT_ID=replace_after_running_account_list
WEBULL_TOKEN_DIR=.webull-token
WEBULL_ALLOW_LIVE_ORDERS=NO
```

ค่าเริ่มต้นควรเป็น `WEBULL_ENV=uat` เพื่อให้ endpoint อยู่ที่ test environment ก่อน ไม่ควรเริ่มจาก production

## ห้าม commit secret

อย่า commit ค่าเหล่านี้:

- `.env`
- `WEBULL_APP_KEY`
- `WEBULL_APP_SECRET`
- `WEBULL_ACCOUNT_ID`
- token files ใน `.webull-token/`
- private key, database, หรือไฟล์ output ที่มีข้อมูลส่วนตัว

Repo นี้ ignore `.env`, `.env.*` ยกเว้น `.env.example` และ ignore `.webull-token/` แล้ว แต่ยังควรตรวจด้วยตาและรัน secret scan ก่อน publish

## ตรวจ configuration

หลังใส่ค่าแล้วรัน:

```bash
webull-lab doctor
```

คำสั่ง `doctor` โหลด configuration และแสดง Webull environment, region, trading endpoint, app key, app secret และ account id โดย redact ค่า sensitive ก่อนแสดงผล เช่น `abcd...wxyz` หรือ `<not set>` สำหรับ account id ที่ยังไม่ตั้งค่า

## Expected errors แบบอ่านง่าย

ถ้า `.env` ยังขาด `WEBULL_APP_KEY` หรือ `WEBULL_APP_SECRET` โปรแกรมจะหยุดด้วย error สั้น ๆ. คำสั่ง `account-list`, `stock-snapshot` และ `preview-stock-buy` ถูกออกแบบให้แสดง concise error output สำหรับ expected errors เช่น config ไม่ครบ, API response error, หรือ input validation fail

## Checklist

- `.env` มี `WEBULL_ENV=uat`
- `.env` มี app key และ app secret จริง แต่ไม่ถูก commit
- `.webull-token/` อยู่ใน `.gitignore`
- `webull-lab doctor` แสดงค่าแบบ redacted
- ยังไม่ตั้ง `WEBULL_ALLOW_LIVE_ORDERS=I_UNDERSTAND` ระหว่างเรียนบทพื้นฐาน
