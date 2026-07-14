# SEC EDGAR + Webull Financial Data: งบการเงินที่ตรวจสอบย้อนกลับได้

บทนี้สอน workflow แบบ read-only สำหรับรวมงบที่ยื่นต่อ SEC กับ daily prices จาก
Webull โดยเริ่มจากข้อมูลตัวอย่างแบบ offline ก่อน แล้วจึงเลือกใช้ optional live mode
เมื่อพร้อม เนื้อหานี้เป็นกรอบงานวิจัยการลงทุนและการตรวจสอบสมมติฐาน ไม่ใช่คำทำนายราคา
และไม่สามารถทำนายหรือรับประกันผลตอบแทนได้

ข้อมูลและลิงก์ official primary sources ตรวจสอบ ณ วันที่ 2026-07-14:

- SEC EDGAR APIs (Company Facts, Submissions, การระบุตัวตนและนโยบาย programmatic access;
  ไม่ต้องใช้ API key): https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- Webull Market Data Getting Started (SDK, production/test endpoints และ market-data
  permission): https://developer.webull.com/apis/docs/market-data-api/getting-started/
- Webull Bars reference (daily ขึ้นไปเป็น forward-adjusted):
  https://developer.webull.com/apis/docs/reference/broker-market-data-api/bars-using-get/
- Webull Market Data Overview (OpenAPI subscription แยกจากสิทธิ์ใน app/desktop):
  https://developer.webull.com/apis/docs/market-data-api/overview/
- Webull API Docs: https://developer.webull.com/apis/docs/
- Webull llms.txt: https://developer.webull.com/apis/llms.txt
- Webull Python SDK: https://github.com/webull-inc/webull-openapi-python-sdk

## เป้าหมาย

เมื่อจบบทนี้ คุณควรสามารถ:

- แปลง ticker เป็น CIK และอ่าน Company Facts/Submissions จาก SEC
- แยก annual, quarterly และ YTD โดยไม่ผสมช่วงเวลา
- รักษา unit และ provenance ของ XBRL fact ทุกแถว
- ใช้ filed date แทน period end เมื่อต้องจับคู่ข้อมูลกับราคาเพื่อลด look-ahead bias
  แต่ถือว่า next trading session เป็นวันใช้ข้อมูลแรกตามหลัก conservative หากไม่มีเวลา
  acceptance และ market-session logic ที่พิสูจน์ว่าใช้ราคา same-day ได้
- เติม Webull daily prices แบบ optional โดยยัง export SEC-only ได้หาก Webull ไม่พร้อม
- ตรวจ cache, raw payload และ `run_manifest.json` เพื่อทำซ้ำและ audit งานได้

## Core concepts

| แนวคิด | ใช้อย่างไรใน workflow นี้ |
|---|---|
| ticker | ชื่อย่อหลักทรัพย์ เช่น `AAPL`; เป็น input ที่ผู้ใช้สะดวก แต่ไม่ใช่รหัสถาวรของ SEC |
| CIK | รหัสบริษัท 10 หลักของ SEC เช่น `0000320193`; ต้องเก็บเลขศูนย์ด้านหน้า |
| XBRL tag | ชื่อ fact ต้นทาง เช่น revenue หรือ net income; mapping เป็น canonical metric ต้องเก็บ `source_tag` ไว้ |
| 10-K / 10-Q | 10-K ใช้รายงานประจำปี ส่วน 10-Q ใช้รายงานระหว่างปี; ฉบับแก้ไขอาจ supersede รายการเดิม |
| period end | วันสิ้นงวดที่ตัวเลขอธิบาย ไม่ใช่วันที่ตลาดรู้ข้อมูล |
| filed date | วันที่ filing ถูกยื่น ช่วยลด look-ahead เมื่อเทียบกับ period end แต่ daily date ไม่บอกเวลา acceptance ระหว่างวัน จึงยังพิสูจน์ same-day availability ไม่ได้ |
| annual / quarterly / YTD | annual ครอบคลุมปี, quarterly คือไตรมาสเดี่ยว, YTD สะสมตั้งแต่ต้นปี; ห้ามถือ YTD เป็นไตรมาสเดี่ยว |
| reported / derived | `reported` มาจาก fact ที่บริษัทส่ง; `derived=true` คือค่าที่ pipeline คำนวณและต้องตรวจสูตร/inputs |
| unit | หน่วย เช่น `USD`, `shares`, `USD/shares`; ตัวเลขคนละ unit ห้ามนำมาหารหรือรวมโดยไม่ตรวจความหมาย |
| provenance | taxonomy, source tag, form, accession number, unit, period และ filed date ที่ทำให้ย้อนกลับไปยังต้นทางได้ |
| look-ahead bias | การใช้ข้อมูลก่อนตลาดมีโอกาสเห็น เช่น จับงบกับราคาที่ period end ทั้งที่ filing มาทีหลัง |

ราคา Webull interval ระดับ daily ขึ้นไปเป็น **forward-adjusted** ตามเอกสาร official:
ประวัติจะถูกปรับย้อนหลังเมื่อเกิด corporate action จึงต้องระวังเป็นพิเศษเมื่อนำราคาย้อนหลัง
ไปเทียบกับ per-share facts ที่รายงานในอดีต และต้องบันทึกวิธีปรับราคาไว้ในงานวิจัย

## Working CLI

ตั้ง contact email ที่มีผู้ดูแลจริงเพื่อให้ SEC ติดต่อได้ตามนโยบาย programmatic access:

```dotenv
SEC_CONTACT_EMAIL=your_monitored_email@example.com
```

จากนั้นรันคำสั่งหลัก:

```bash
webull-lab company-data AAPL --years 5
```

`--years` ใช้กับทั้งงบ SEC และช่วงราคา Webull ไม่ใช่เฉพาะงบ Pipeline ส่ง
`start_time`/`end_time` ตามช่วงปฏิทินที่ขอ และ paginate ย้อนหลังเมื่อเกินเพดาน 1,200 bars
ต่อคำขอของ SDK โดยเว้นจังหวะระหว่างหน้าให้สอดคล้องกับ rate limit ของ endpoint
หากหุ้นเพิ่งเข้าตลาด, permission จำกัด หรือ pagination ไปไม่ถึงขอบเขตที่ขอ manifest จะ
รายงาน `partial`/`unavailable` แทนการอ้างว่ามีประวัติครบ

ค่าเริ่มต้นเขียนผลลัพธ์ใต้ `data/private/company-data/` ซึ่งถูก gitignore หากไม่มี Webull
credentials pipeline จะทำงานแบบ SEC-only: `sec_status` ยังเป็น `available` และ
`webull_status` เป็น `unavailable` โดย metrics ที่ต้องใช้ราคาจะอธิบาย input ที่ขาด
แทนการสร้างตัวเลขขึ้นมา

## อ่าน status ก่อนอ่าน value

- `available`: inputs ครบ หน่วยเข้ากัน และคำนวณค่าได้
- `missing_input` หรือ `missing`: ไม่มี fact หรือราคา timing-safe ที่จำเป็น ค่าไม่ควรถูกแทนด้วยศูนย์
- `incompatible_unit`: inputs มี unit ที่ใช้ร่วมกันไม่ได้ เช่น USD กับค่าต่อหุ้น
- `not_meaningful`: สูตรคำนวณได้ในเชิงโปรแกรมแต่ denominator เป็นศูนย์หรือไม่มีความหมายเชิงเศรษฐศาสตร์

status ที่ไม่ใช่ `available` ต้องคง value เป็นค่าว่าง อย่าแปลงเป็น 0 เพราะ 0 คือข้อสังเกตจริง
ที่มีความหมายต่างจากข้อมูลขาด

Pipeline จับราคาวันแรกที่ date มากกว่าหรือเท่ากับ `filed_date` เพื่อสร้าง metric อย่างเป็น
ระบบ แต่ SEC daily filing date ไม่มี **acceptance timestamp** ในชุดข้อมูลที่ใช้ตรงนี้
ดังนั้นงานวิจัยควรเลื่อน availability ไป **next trading session** เป็นค่าเริ่มต้นแบบ
conservative หากต้องการใช้ราคา same-day ต้องมี acceptance timestamp ที่ตรวจสอบได้ พร้อม
timezone, วันหยุด และ **market-session** logic ที่พิสูจน์ว่าตลาดยังรับข้อมูลทันก่อนเลือกราคา

## Offline-first notebook แล้วค่อย optional live

เปิด [SEC Webull Financials Beginner Notebook](../notebooks/sec_webull_financials_beginner.ipynb)
และ Run All ในโหมดเริ่มต้น `SEC_WEBULL_TUTORIAL_LIVE=0` ก่อน Notebook จะใช้ reduced
fixtures ใน repo จึง deterministic, ไม่ใช้ network และไม่อ่าน credentials

หลังผ่าน offline checklist แล้วจึงตั้ง `SEC_WEBULL_TUTORIAL_LIVE=1` พร้อม
`SEC_CONTACT_EMAIL` หากมี Webull OpenAPI market-data permission จึงเติม credentials
ใน `.env` ที่ไม่ถูก commit หากไม่ได้รับ permission หรือ API ตอบ 403 ให้ยอมรับ SEC-only
fallback; subscription ของ OpenAPI market data แยกจากสิทธิ์ข้อมูลใน Webull app/desktop

## Artifacts และ audit trail

- Cache: `data/private/sec-cache/` เก็บ SEC JSON ที่ดึงแล้ว ลด network request และช่วยทำซ้ำ
- Raw: `<output>/raw/sec_submissions.json` และ `<output>/raw/sec_companyfacts.json`
  เป็นหลักฐานต้นทางส่วนตัว ห้าม upload ใน live-smoke artifact
- Tables: งบทั้งสาม, prices และ metrics มี CSV/Parquet; `company_snapshot.json` เป็นสรุป
- Manifest: `<output>/run_manifest.json` บันทึก ticker, CIK, requested years,
  `sec_status`, `webull_status`, cache status, warnings, missing metrics และรายชื่อไฟล์
- Price coverage: `price_history` ใน manifest แยก requested start/end ออกจาก observed
  start/end, จำนวน bars, จำนวนหน้าที่ขอ, สถานะ pagination และ `range_observed`/
  `partial`/`unavailable` โดย `range_observed` หมายถึงเห็นข้อมูลใกล้ขอบช่วงทั้งสองด้าน
  ไม่ได้รับรองว่าไม่มี trading session ใดขาดหาย จึงควรตรวจจำนวนแถวประกอบเสมอ

Raw/cache/output ทั้งหมดเป็น private artifacts แม้ SEC payload จะเป็นข้อมูลสาธารณะ เพราะ
directory เดียวกันอาจมี metadata จากการรันจริง Workflow live smoke จึง upload เฉพาะ
`outputs/live-smoke/run_manifest.json`

## แบบฝึกหัด

ใช้ AAPL เปรียบเทียบ revenue growth กับพฤติกรรมราคาหลัง filed date:

1. Run All notebook แบบ offline และเลือก annual revenue สองปีล่าสุด
2. ยืนยัน `source_tag`, `unit`, `form`, `accession_number`, `period_type` และ `derived`
3. หา next trading session หลัง filed date เป็น conservative availability; จะใช้ราคา
   same-day ได้ต่อเมื่อมี acceptance timestamp และ market-session logic รองรับ
4. สรุปว่าเกิดอะไรขึ้นหลัง filing โดยใช้ภาษาว่า “สัมพันธ์กันในตัวอย่างนี้”
5. ระบุว่าการเปรียบเทียบนี้ไม่พิสูจน์ causality และไม่รับประกันพฤติกรรมราคาในอนาคต

## เกณฑ์ประเมิน / rubric checklist

- [ ] Source provenance: ย้อนทุกตัวเลขถึง SEC taxonomy/tag/form/accession ได้
- [ ] Period correctness: แยก annual, quarterly, YTD และ amended filing ถูกต้อง
- [ ] Unit correctness: ไม่ผสมหน่วย และอธิบาย `incompatible_unit` ได้
- [ ] Timing correctness: ไม่ใช้ period end และ default เป็น next trading session;
  same-day ต้องมี acceptance timestamp, timezone และ market-session logic รองรับ
- [ ] Reproducibility: Run All offline ผ่านและ `run_manifest.json` ตรงกับ artifacts ที่มีจริง
- [ ] Interpretation: แยก fact, assumption และ interpretation โดยไม่กล่าวอ้างการทำนาย

## ข้อผิดพลาดที่พบบ่อย

- เติม 0 ให้ missing fact ทำให้ “ไม่มีข้อมูล” กลายเป็น “บริษัทมีค่าเป็นศูนย์”
- ผสม `USD`, `shares` และ `USD/shares` แล้วได้ ratio ที่ไม่มีความหมาย
- อ่าน YTD ใน Q2/Q3 เป็น quarterly โดยไม่หักยอดสะสมก่อนหน้า
- จับราคาเข้ากับ period end แทน filed date หรือถือว่า filed date แบบ daily พิสูจน์
  same-day availability ได้ จนเกิด look-ahead bias
- ลืมว่า daily Webull bars เป็น forward-adjusted
- คิดว่าสิทธิ์ market data ใน app/desktop เท่ากับ OpenAPI subscription แล้วไม่ตรวจ 403
- commit `.env`, SEC contact email ส่วนตัว, cache, raw payload หรือ outputs
- ตีความ correlation หลัง filing เป็น causality หรือเป็นสัญญาณทำนายผลตอบแทนแน่นอน

## Transfer to real-world use

ให้ผ่าน single-ticker acceptance ของ AAPL ก่อน: provenance, periods, units, timing,
status, artifacts และ rerun ต้องถูกต้องทั้งหมด จึงค่อยขยายเป็น watchlist batch ingestion
เมื่อขยายแล้วควรเพิ่ม rate control, per-ticker failure isolation, immutable manifests,
data-quality report และ out-of-sample research protocol ไม่ควรขยาย universe เพื่อกลบปัญหา
ของ ticker แรก
