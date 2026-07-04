# Webull OpenAPI Thai Lab: เส้นทางการเรียนรู้

เอกสารชุดนี้เป็น tutorial ภาษาไทยสำหรับเรียน Webull OpenAPI แบบปลอดภัย โดยเริ่มจากการตั้งค่า credential, ใช้ UAT, เรียกบัญชี, ดึง market data, preview order และใช้ AI coding assistant อ่านเอกสาร official โดยไม่ทำให้ secret หรือคำสั่งซื้อขายจริงหลุดออกไป

แหล่งอ้างอิงหลัก:

- Webull API Docs: https://developer.webull.com/apis/docs/
- Webull llms.txt: https://developer.webull.com/apis/llms.txt
- Webull Python SDK: https://github.com/webull-inc/webull-openapi-python-sdk

## เป้าหมาย

เมื่อเรียนครบ คุณควรทำสิ่งเหล่านี้ได้:

- ตั้งค่า `.env` สำหรับ Webull UAT โดยไม่ commit secret
- ตรวจ configuration ด้วย `webull-lab doctor`
- เรียกบัญชี UAT ด้วย `webull-lab account-list`
- ดึง snapshot ของหุ้นด้วย `webull-lab stock-snapshot AAPL`
- preview limit buy order ด้วย `webull-lab preview-stock-buy AAPL 100 1`
- ใช้ Webull `llms.txt` ให้ AI assistant ช่วย dev โดยยังบังคับ fake-client tests, ไม่มี hard-coded secrets และไม่มี live order จาก CLI

## Learning Path

1. ตั้งค่า API key และ secret
   อ่าน `docs/01-api-key-setup-th.md` เพื่อสร้าง `.env`, ตั้ง `WEBULL_ENV=uat`, เก็บ token ใน `.webull-token/` และเข้าใจว่า `webull-lab doctor` จะแสดง app key, app secret และ account id แบบ redacted

2. เรียก API ครั้งแรก
   อ่าน `docs/02-first-call-th.md` แล้วรัน `webull-lab doctor` ตามด้วย `webull-lab account-list` เพื่อยืนยันว่าเชื่อมต่อ UAT endpoint `us-openapi-alb.uat.webullbroker.com` ได้

3. ดึง market data
   อ่าน `docs/03-market-data-th.md` แล้วรัน `webull-lab stock-snapshot AAPL` หรือ `python examples/02_market_data_snapshot.py` ปัจจุบัน CLI ตัวอย่างเป็น stock snapshot ส่วน helper ในโค้ดรองรับทั้ง snapshot และ historical bars

4. Preview order พร้อม guardrails
   อ่าน `docs/04-order-preview-and-guardrails-th.md` แล้วรัน `webull-lab preview-stock-buy AAPL 100 1` หรือ `python examples/03_order_preview.py` เพื่อ preview เท่านั้น ไม่มี CLI command สำหรับส่ง live order

5. ใช้ AI ช่วยพัฒนาอย่างปลอดภัย
   อ่าน `docs/05-ai-assisted-webull-dev-th.md` เพื่อใช้ official docs และ `llms.txt` เป็น context ให้ AI assistant พร้อมข้อกำหนด fake-client tests และข้อห้ามเรื่อง secrets/live orders

6. Publish ขึ้น GitHub
   อ่าน `docs/99-publishing-github-th.md` เพื่อเช็ก secret, รัน tests, สร้าง repo และเปิด secret scanning ก่อนเผยแพร่

## หลักคิด

Repo นี้เป็น lab เพื่อเรียนรู้ API workflow ไม่ใช่ production trading system. ทุกขั้นควรแยก read-only call, market data call, order preview และ live order risk ออกจากกันให้ชัดเจนเสมอ
