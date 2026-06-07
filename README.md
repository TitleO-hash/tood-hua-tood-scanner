# 📊 ตูด หัว ตูด Scanner

ระบบ ViVi Investor by THREE CAP
สแกนหาหุ้น Beginning of Trend ตาม Dow Theory + RSI Divergence

## Features

- สแกนหาหุ้นที่มี Pattern ตูด-หัว-ตูด ตามระบบ ViVi
- แบ่งกลุ่ม "จ่อ Break" 4 ระดับ และ "Break แล้ว" 4 ระดับ
- Rank ด้วย Volume ผิดปกติ (LV1-LV4)
- รองรับโครงสร้างซ้อน (Matryoshka Gen1/Gen2)
- Sidebar กรองและ Input รายชื่อหุ้นได้อิสระ

## โครงสร้าง Pattern

```
ATL 90 วัน = ตูด 1 (เริ่มต้น)
    ↓ RSI Diff >= 8
ระบุตูด 1 ✅
    ↓ ราคาขึ้น/ลง/ขึ้น → Peak → ย้อ → RSI Diff >= 8
ระบุหัว ✅ (หัว > ตูด1 เสมอ)
    ↓
กรณี 1: ปิดต่ำกว่าตูด1 → ล้างไพ่
กรณี 2: ปิดสูงกว่าหัว (Breakout!)
→ คอนเฟิม ตูด 2 + Signal BUY + Entry เปิดวันถัดไป
```

## Priority Group

| กลุ่ม | เงื่อนไข |
|-------|----------|
| กลุ่ม 4 | RSI Diff >= 8 แล้ว + ราคาจ่อหัว <= 3% |
| กลุ่ม 3 | RSI Diff >= 8 แล้ว |
| กลุ่ม 2 | RSI Diff >= 4 (ใกล้ 8) |
| กลุ่ม 1 | ระบุหัวแล้ว รอย้อลง |

## Volume LV

| LV | เงื่อนไข |
|----|----------|
| LV4 | Max Vol >= ATH Vol 1 ปี |
| LV3 | Max Vol >= 5x avg20 |
| LV2 | Max Vol >= 1.5x avg20 |
| LV1 | ปกติ |

## วิธีติดตั้ง

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy บน Streamlit Cloud

1. Push code ขึ้น GitHub
2. ไปที่ share.streamlit.io
3. เลือก repo → branch → app.py
4. Deploy!

---
© THREE CAP | facebook.com/3percentcapital
