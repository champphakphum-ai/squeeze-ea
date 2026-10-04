# Squeeze EA — BTC (พิสูจน์แนวคิด)

ระบบวิเคราะห์ Squeeze ตามเนื้อหา MTRADERS (Short / Gamma / Volatility / Liquidity)
เฟสแรกโฟกัส **BTC บน Deribit** เพราะได้ข้อมูล options ฟรีครบ

## สถานะตอนนี้: ✅ พิสูจน์แนวคิดสำเร็จ (เฟส 1)
ดึง options BTC สดจาก Deribit → คำนวณ **GEX, Gamma Flip, โซนรับ/ต้าน** ได้จริง

## วิธีรัน (ไม่ต้องติดตั้งอะไร — ใช้ Python มาตรฐาน)
```bash
python src/snapshot.py            # ข้อมูลสด, options อายุ <=45 วัน
python src/snapshot.py --dte 30   # กรองอายุ <=30 วัน
```
ผลล่าสุดถูกเก็บไว้ที่ `data/last_snapshot.txt`

## โครงไฟล์
- `src/deribit_client.py` — ดึงข้อมูลจาก Deribit public API
- `src/gex.py` — Black-Scholes gamma, Net GEX, Gamma Flip, strike profile
- `src/snapshot.py` — สรุปผลออกหน้าจอ
- `REQUIREMENTS.md` — รายการของที่ต้องเตรียมทั้งระบบ + roadmap เฟส 0–6
- `requirements.txt` — แพ็กเกจสำหรับเฟสถัดไป

## เฟสถัดไป (ดู REQUIREMENTS.md)
2. เพิ่มสัญญาณ Squeeze + กฎเข้า-ออก + บันทึกลง DB
3. เทรดอัตโนมัติบน Deribit **testnet** (ต้องมี API key)
4. Learning layer — เรียนรู้จากเทรดที่ผิด แล้วกรองสัญญาณ

> ⚠️ เพื่อการศึกษา — ต้อง backtest กับข้อมูลจริงก่อนใช้เงินจริงเสมอ
