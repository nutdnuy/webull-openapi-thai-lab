# Webull First Call: เรียก API ครั้งแรกใน UAT

บทนี้พาเรียก Webull OpenAPI ครั้งแรกแบบปลอดภัย โดยเริ่มจาก diagnostic command แล้วค่อยเรียก account list ใน UAT

Official sources:

- Webull API Docs: https://developer.webull.com/apis/docs/
- Webull SDK Docs: https://developer.webull.com/apis/docs/sdk/
- Webull Trading API Overview: https://developer.webull.com/apis/docs/trade-api/overview/
- Webull llms.txt: https://developer.webull.com/apis/llms.txt
- Webull Python SDK: https://github.com/webull-inc/webull-openapi-python-sdk

## 1. ตรวจ setup

รัน:

```bash
webull-lab doctor
```

ควรเห็น environment เป็น `uat` และ trading endpoint เป็น:

```text
us-openapi-alb.uat.webullbroker.com
```

เมื่อ configuration โหลดสำเร็จ คำสั่งนี้ redact app key, app secret และ account id ก่อนแสดงผล จึงใช้ตรวจ setup ได้โดยไม่เผลอ print secret แบบเต็ม

## 2. เรียก account list

รัน:

```bash
webull-lab account-list
```

คำสั่งนี้โหลด `.env`, สร้าง trade client และเรียก account list ผ่าน Webull Python SDK. ถ้า credential ถูกต้อง ควรได้ JSON response จาก UAT. ถ้ามี expected error เช่น config ไม่ครบหรือ API response ไม่สำเร็จ คำสั่ง `account-list` จะแสดง error สั้น ๆ โดยไม่พ่น traceback ยาว

## 3. ใส่ account id ใน `.env`

หลังได้ account id จาก UAT response ให้ใส่ใน `.env`:

```dotenv
WEBULL_ACCOUNT_ID=your_uat_account_id_here
```

อย่านำ account id จริงไปแปะใน README, issue, pull request, screenshot หรือ chat สาธารณะ แม้ account id ไม่ใช่ app secret ก็ควรถือเป็นข้อมูลส่วนตัวของบัญชี

## 4. ทดสอบซ้ำ

รัน:

```bash
webull-lab doctor
```

ตอนนี้ `Account ID` ควรไม่ใช่ `<not set>` แต่ยังต้องเป็นค่า redacted เท่านั้น

## หมายเหตุ

บทนี้ยังไม่แตะ order workflow. เป้าหมายคือยืนยันว่า Webull credential, endpoint และ account lookup ทำงานใน UAT ก่อน
