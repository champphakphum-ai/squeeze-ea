# รายการของที่ต้องเตรียม — ระบบ Squeeze EA (ครบกระบวนการ + Self-Learning)

> แนวทาง: **เริ่มฟรีทั้งหมด** · เฟสแรกโฟกัส **BTC/Deribit** (ทางเดียวที่ได้ full gamma pipeline แบบฟรี) · พ่วง MT5 demo ไว้ทำ Volatility Squeeze ของ Gold/Oil
>
> ⚠️ เนื้อหาต้นทางเป็น "เพื่อการศึกษา" ตัวเลขในภาพหลายอันเป็นค่าสมมติ — ทุกพารามิเตอร์ต้อง backtest กับข้อมูลจริงก่อนใช้เงินจริง

---

## ภาพรวมสถาปัตยกรรม (4 ชั้น)

```
[1] DATA LAYER        ดึงข้อมูลดิบ: options chain, OI, IV, funding, ราคา
        │
[2] BRAIN LAYER       คำนวณ GEX / Gamma Flip / Skew / ATR-BB / Squeeze score  (Python)
        │
[3] EXECUTION LAYER   ส่งคำสั่งเทรด: Deribit API (BTC) และ/หรือ MT5 EA (Gold/Oil)
        │
[4] LEARNING LAYER    บันทึกทุกเทรด → เก็บ feature+ผลลัพธ์ → เทรนโมเดลกรองสัญญาณใหม่เป็นรอบ
```

---

## ✅ A. ซอฟต์แวร์ที่ต้องติดตั้ง (ฟรีทั้งหมด)

- [ ] **Python 3.11+** — ภาษาแกนหลักของ Brain + Learning layer → https://www.python.org/downloads/
- [ ] **VS Code** (หรือ IDE ที่ถนัด) — เขียน/แก้โค้ด → https://code.visualstudio.com/
- [ ] **Git for Windows** — เก็บเวอร์ชันโค้ด → https://git-scm.com/download/win
- [ ] **MetaTrader 5 (terminal + MetaEditor)** — รัน EA ฝั่ง Gold/Oil (โหลดจากโบรกที่เปิดบัญชี demo)
- [ ] **DB Browser for SQLite** (ไม่บังคับ) — เปิดดูฐานข้อมูลเทรดด้วยตา → https://sqlitebrowser.org/

## ✅ B. บัญชี / API Key (เฟสแรกฟรีหมด)

- [ ] **Deribit — บัญชี Testnet** (ข้อมูล options ฟรี + เทรดจำลองด้วยเงินปลอม)
      - สมัคร: https://test.deribit.com  → เมนู API → สร้าง **Client ID + Client Secret**
      - ใช้ดึง: options chain, OI, IV, Greeks, funding rate, index price ของ BTC/ETH
- [ ] **Deribit — บัญชี Mainnet** (ไว้ดึงข้อมูลตลาดจริง ยังไม่ต้องฝากเงิน) https://www.deribit.com
- [ ] **โบรก Forex/CFD ที่มี MT5 + เปิดบัญชี Demo ฟรี** — ไว้เทรด XAUUSD (ทอง) / WTI
      - โบรกไหนก็ได้ที่ให้ MT5 demo (เช่น IC Markets, Exness, Pepperstone ฯลฯ) — เลือกมา 1 เจ้า
- [ ] **ปฏิทินข่าวเศรษฐกิจ (ฟรี)** — ไว้เว้นช่วง FOMC/CPI
      - ForexFactory calendar (มี RSS/สครัปได้) หรือ API ฟรีอื่น ๆ
- [ ] **(ภายหลัง/ถ้าจะเล่น Gold gamma จริง)** CME DataMine หรือ vendor (SpotGamma / MenthorQ / ConvexValue) — **เสียเงิน ยังไม่ต้องตอนนี้**

> 👉 สิ่งที่คุณต้องส่งให้ผม/กรอกใน `.env`: **Deribit Client ID + Client Secret (ของ testnet ก่อน)**
> และ **เลขบัญชี MT5 demo + password + ชื่อเซิร์ฟเวอร์** (ถ้าจะทำฝั่งทอง)
> ⚠️ อย่าวางคีย์จริงลงแชตหรือ GitHub — ใส่ในไฟล์ `.env` ที่อยู่ในเครื่องเท่านั้น

## ✅ C. Python packages (ผมจะใส่ให้ในไฟล์ requirements.txt ตอนลงมือ)

- [ ] `MetaTrader5` — เชื่อม Python ↔ MT5 โดยตรง (ดึงราคา/ส่งออเดอร์)
- [ ] `websocket-client`, `requests` — ต่อ Deribit API (websocket + REST)
- [ ] `pandas`, `numpy`, `scipy` — คำนวณ Greeks / GEX / ATR / Bollinger
- [ ] `python-dotenv` — อ่านคีย์จากไฟล์ `.env`
- [ ] `SQLAlchemy` + `sqlite` (มากับ Python) — ฐานข้อมูลบันทึกเทรด
- [ ] `scikit-learn` — โมเดลเรียนรู้ (กรองสัญญาณ) เฟสแรก
- [ ] `lightgbm` — โมเดลแรงขึ้น (เฟสหลัง)
- [ ] `matplotlib` — กราฟ/รายงานผล backtest
- [ ] `APScheduler` — ตั้งให้รันเก็บข้อมูล/เทรนเป็นรอบอัตโนมัติ

## ✅ D. ฮาร์ดแวร์ / ที่รันระบบ (ตัดสินใจภายหลังได้)

- [ ] เฟสพัฒนา+ทดสอบ → รันบน **PC เครื่องนี้** ก็พอ
- [ ] เฟสรันจริง (BTC เทรด 24/7) → ค่อยพิจารณา **Windows VPS** (ถ้าจะรัน MT5 ด้วย ต้องเป็น Windows)

---

## 🧠 ส่วน Self-Learning (เรียนรู้จากที่ผิด) — ต้องเตรียมอะไร

ไม่ต้องโหลดอะไรเพิ่ม ใช้ `scikit-learn` + `sqlite` ที่อยู่ในรายการแล้ว กลไกคือ:

1. **บันทึกทุกสัญญาณ/ทุกเทรด** ลง DB พร้อม "feature" ณ ตอนเข้า:
   GEX, ระยะห่างจาก Gamma Flip, IV, Skew (25Δ RR), ATR, BB Width, funding, วัน/เวลา, ฯลฯ
2. **ติดผลลัพธ์** ให้แต่ละเทรด: กำไร/ขาดทุน (R-multiple), ชน SL/TP, ถือกี่แท่ง
3. **เทรนโมเดลเป็นรอบ** (เช่น ทุกสัปดาห์): เรียนว่า feature แบบไหน → เทรดแพ้บ่อย
4. **นำโมเดลกลับมากรอง**: สัญญาณใหม่ที่โมเดลให้ "โอกาสแพ้สูง" จะถูกข้าม/ลดขนาด
5. **Walk-forward validation**: วัดว่าเวอร์ชันใหม่ดีกว่าเก่าจริงก่อนเอาไปใช้ (กันโมเดลมั่ว)

> ข้อควรรู้: โมเดลต้องสะสม "จำนวนเทรด" พอสมควรถึงจะเรียนได้ดี — ช่วงแรกจึงให้มันรันเก็บสถิติบน testnet/demo ไปก่อน ยังไม่ต้องเชื่อเต็มที่

---

## 🗺️ แผนลงมือ (เฟส)

| เฟส | ทำอะไร | ผลลัพธ์ที่จับต้องได้ |
|---|---|---|
| **0** | เตรียมของตามรายการ A–C + สมัคร Deribit testnet | พร้อมเขียนโค้ด |
| **1** | Python ดึง options chain ของ BTC จาก Deribit → คำนวณ **GEX + Gamma Flip** | เห็นแผนที่ gamma จริงของ BTC |
| **2** | เพิ่มสัญญาณ Squeeze (Volatility/Gamma) + กฎเข้า-ออก + บันทึกลง DB | ระบบออกสัญญาณได้ |
| **3** | ต่อ execution บน **Deribit testnet** (เทรดจำลองอัตโนมัติ) | บอทเทรดเองได้ (เงินปลอม) |
| **4** | เพิ่ม **Learning layer** (เทรน + กรองสัญญาณ) + รายงานผล | ระบบเริ่ม "พัฒนาตัวเอง" |
| **5** | (ขนาน) เขียน **MT5 EA: Volatility Squeeze** สำหรับ XAUUSD/WTI | EA ทอง/น้ำมันบน MT5 |
| **6** | Backtest จริงจัง + ตัดสินใจเรื่อง VPS / เงินจริง | พร้อมใช้งานจริง (ถ้าผลผ่าน) |

---

## 📌 สิ่งที่ต้องการจากคุณ "ตอนนี้" (เพื่อเริ่มเฟส 0→1)

1. สมัคร **Deribit testnet** → สร้าง API key → เก็บ **Client ID + Secret** ไว้
2. (ถ้าจะทำฝั่งทองด้วย) เลือกโบรก MT5 สักเจ้า → เปิด **demo** → เก็บเลขบัญชี/pass/server
3. ติดตั้ง **Python + VS Code + Git** ตามข้อ A
4. บอกผมว่าพร้อมแล้ว → ผมจะวางโครงโปรเจกต์ + requirements.txt + สคริปต์ดึง GEX ตัวแรกให้

> หมายเหตุ: คีย์ API ทั้งหมดใส่ในไฟล์ `.env` (ผมจะทำ `.env.example` + `.gitignore` ให้) ห้ามแปะในแชต
