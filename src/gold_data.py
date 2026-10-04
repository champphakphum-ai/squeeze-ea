"""
Gold data collector (MT5) — ดูดราคาทอง XAUUSD จาก MT5 ลง SQLite

- Backfill ประวัติย้อนหลังทั้งหมดที่ terminal มี (รันครั้งแรก)
- รันซ้ำ = อัปเดตเฉพาะแท่งใหม่ (incremental, แท่งเก่าไม่ซ้ำ)
- เก็บ "ราคาดิบ" (OHLCV) ไว้ ส่วน feature คำนวณทีหลังได้ยืดหยุ่น

รัน:
    python src/gold_data.py                 # H1, สัญลักษณ์ XAUUSD-STDc
    python src/gold_data.py --symbol XAUUSD-STDc --tf H1
    python src/gold_data.py --max 20000

*** อ่านข้อมูลอย่างเดียว ไม่ส่งคำสั่งเทรด — ปลอดภัยแม้บัญชีจริง ***
"""
from __future__ import annotations
import sys
import os
import sqlite3
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import MetaTrader5 as mt5

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "gold.db")

_TF = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1,
       "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1}


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS bars (
            symbol TEXT, tf TEXT, time INTEGER,
            open REAL, high REAL, low REAL, close REAL,
            tick_volume INTEGER, spread INTEGER,
            PRIMARY KEY (symbol, tf, time)
        )""")
    con.commit()
    return con


def fetch_bars(symbol, tf_name, max_bars):
    if not mt5.initialize():
        raise RuntimeError(f"initialize ล้มเหลว: {mt5.last_error()}")
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"เลือกสัญลักษณ์ {symbol} ไม่ได้")
    tf = _TF[tf_name]
    bars = mt5.copy_rates_from_pos(symbol, tf, 0, max_bars)
    if bars is None:
        err = mt5.last_error()
        mt5.shutdown()
        raise RuntimeError(f"ดึงข้อมูลไม่ได้: {err}")
    return bars


def main(argv):
    symbol = "XAUUSD-STDc"
    tf = "H1"
    max_bars = 20000
    i = 0
    while i < len(argv):
        if argv[i] == "--symbol" and i + 1 < len(argv):
            symbol = argv[i + 1]; i += 2
        elif argv[i] == "--tf" and i + 1 < len(argv):
            tf = argv[i + 1]; i += 2
        elif argv[i] == "--max" and i + 1 < len(argv):
            max_bars = int(argv[i + 1]); i += 2
        else:
            i += 1

    con = init_db()
    bars = fetch_bars(symbol, tf, max_bars)
    rows = [(symbol, tf, int(b["time"]), float(b["open"]), float(b["high"]),
             float(b["low"]), float(b["close"]), int(b["tick_volume"]),
             int(b["spread"])) for b in bars]
    before = con.execute("SELECT COUNT(*) FROM bars WHERE symbol=? AND tf=?",
                         (symbol, tf)).fetchone()[0]
    con.executemany(
        "INSERT OR IGNORE INTO bars VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    after = con.execute("SELECT COUNT(*) FROM bars WHERE symbol=? AND tf=?",
                        (symbol, tf)).fetchone()[0]
    mt5.shutdown()

    first = datetime.fromtimestamp(rows[0][2], timezone.utc)
    last = datetime.fromtimestamp(rows[-1][2], timezone.utc)
    print("=" * 56)
    print(f"  GOLD DATA  |  {symbol}  {tf}")
    print("=" * 56)
    print(f"  ดึงมา      : {len(rows):,} แท่ง")
    print(f"  ช่วงเวลา   : {first}  ->  {last}")
    print(f"  เพิ่มใหม่  : {after - before:,} แท่ง  (รวมใน DB: {after:,})")
    print(f"  DB         : {DB_PATH}")
    print("=" * 56)


if __name__ == "__main__":
    main(sys.argv[1:])
