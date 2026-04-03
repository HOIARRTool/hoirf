# Incident Entry + RCA (GitHub-ready)

แอป Streamlit สำหรับบันทึกอุบัติการณ์ โดยผู้ใช้ **เลือก code แล้วระบบเติม metadata ให้อัตโนมัติ** จาก master files และมี **fallback PSG9** หากไม่พบ mapping

## ความสามารถหลัก

- เลือก `รหัส` แล้วเติมอัตโนมัติ:
  - `ชื่ออุบัติการณ์ความเสี่ยง`
  - `กลุ่ม`
  - `หมวด`
  - `ประเภท`
  - `ประเภทย่อย`
- map ไปยัง `PSG_ID`, `หมวดหมู่PSG`, `หมวดหมู่มาตรฐานสำคัญ`
- ถ้าไม่พบ PSG9 จะใช้ค่า fallback เป็น `ไม่จัดอยู่ใน PSG9 Catalog`
- ผู้ใช้กรอกส่วนที่เหลือเอง เช่น:
  - วันที่ / เวลา
  - ระดับความรุนแรง
  - รายละเอียดเหตุการณ์
  - สถานะ
  - RCA
  - contributing factors 36 รายการ
- บันทึกข้อมูลลง `data/output/incident_entry_records.csv`
- ดาวน์โหลดข้อมูลเป็น CSV / Excel ได้จากหน้าแอป

## โครงสร้างโฟลเดอร์

```text
incident-entry-github/
├─ app.py
├─ requirements.txt
├─ README.md
├─ .gitignore
├─ .streamlit/
│  └─ config.toml
└─ data/
   ├─ masters/
   │  ├─ Code2024.xlsx
   │  ├─ PSG9code.xlsx
   │  └─ contributing_factor.xlsx
   └─ output/
      └─ .gitkeep
```

## master files ที่แอปใช้

### 1) `Code2024.xlsx`
ใช้เป็น master หลักสำหรับเติมอัตโนมัติ:
- `รหัส`
- `ชื่ออุบัติการณ์ความเสี่ยง`
- `กลุ่ม`
- `หมวด`
- `ประเภท`
- `ประเภทย่อย`

### 2) `PSG9code.xlsx`
ใช้ map เพิ่มเติม:
- `รหัส`
- `PSG_ID`
- `หมวดหมู่PSG`

### 3) `contributing_factor.xlsx`
ใช้สร้างรายการ contributing factors 36 รายการในฟอร์ม

## วิธีรันในเครื่อง

### 1) ติดตั้ง package
```bash
pip install -r requirements.txt
```

### 2) รันแอป
```bash
streamlit run app.py
```

## Environment variables (ไม่บังคับ)

ถ้าต้องการชี้ path เอง สามารถกำหนดได้:

- `CODE_MASTER_PATH`
- `PSG9_MASTER_PATH`
- `CONTRIB_MASTER_PATH`
- `INCIDENT_OUTPUT_PATH`

ถ้าไม่กำหนด แอปจะหาไฟล์ตามตำแหน่งมาตรฐานใน `data/masters/`

## คอลัมน์สำคัญที่รองรับการประมวลผลต่อใน `app.py`

แอปนี้เตรียม field สำคัญให้แล้ว เช่น:

- `รหัส: เรื่องอุบัติการณ์`
- `วันที่เกิดอุบัติการณ์`
- `ความรุนแรง`
- `สถานะ`
- `รายละเอียดการเกิด`

รวมถึง metadata เพิ่มเติม เช่น:

- `รหัส`
- `ชื่ออุบัติการณ์ความเสี่ยง`
- `กลุ่ม`
- `หมวด`
- `ประเภท`
- `ประเภทย่อย`
- `PSG_ID`
- `หมวดหมู่PSG`
- `หมวดหมู่มาตรฐานสำคัญ`

และส่วน RCA / contributing factors สำหรับการวิเคราะห์ต่อ

## หมายเหตุ

- output ถูกตั้งให้ไม่ถูก commit โดย default ผ่าน `.gitignore`
- master files ถูกวางไว้ใน repo นี้แล้ว จึงสามารถ push ขึ้น GitHub ได้ทันที
- หากต้องการผสานเข้ากับระบบเดิมภายหลัง สามารถย้าย logic ใน `app.py` นี้ไปเป็นอีกเมนูหนึ่งได้
