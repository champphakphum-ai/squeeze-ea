"""
Data Collector — หัวใจของการสร้าง ML ที่เก่ง

เก็บ snapshot ของ BTC ทุก ๆ INTERVAL นาที ลง SQLite:
  - features ของทุกบท (จาก features.py)
  - spot (ไว้คำนวณ "ผลในอนาคต" = label ตอนเทรน)

รัน (เปิดทิ้งไว้ ยิ่งนานยิ่งมีข้อมูลเทรนเยอะ):
    python src/collector.py                 # ทุก 5 นาที (ค่าเริ่มต้น)
    python src/collector.py --interval 300   # กำหนดวินาทีเอง
    python src/collector.py --once           # เก็บครั้งเดียวแล้วออก (ไว้ทดสอบ)

ใช้แค่ Python standard library (sqlite3) — ไม่ต้องติดตั้งอะไร
"""
from __future__ import annotations
import sys
import os
import time
import json
import sqlite3
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from src import deribit_client, features  # noqa: E402

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "snapshots.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL UNIQUE,
            spot REAL NOT NULL,
            features TEXT NOT NULL
        )""")
    con.commit()
    return con


def collect_once(con) -> bool:
    try:
        rows = deribit_client.book_summary_options("BTC")
        try:
            fund = deribit_client.funding_rate("BTC-PERPETUAL")
        except Exception:
            fund = None
        snap = features.extract(rows, funding=fund)
        if not snap:
            print("  [skip] ไม่มี options ที่ใช้ได้")
            return False
        con.execute("INSERT OR IGNORE INTO snapshots (ts, spot, features) VALUES (?,?,?)",
                    (snap["ts"], snap["spot"], json.dumps(snap["features"])))
        con.commit()
        n = con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        f = snap["features"]
        gf = f.get("gamma_flip_dist_pct")
        print(f"  [{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
              f"spot=${snap['spot']:,.0f}  netGEX={f['net_gex_m']:+.0f}M  "
              f"flip={gf:+.1f}%  atmIV={f.get('atm_iv') or 0:.1%}  "
              f"| rows ทั้งหมด: {n}")
        return True
    except Exception as e:
        print(f"  [error] {type(e).__name__}: {e}")
        return False


def main(argv):
    interval = 300
    once = False
    i = 0
    while i < len(argv):
        if argv[i] == "--interval" and i + 1 < len(argv):
            interval = int(argv[i + 1]); i += 2
        elif argv[i] == "--once":
            once = True; i += 1
        else:
            i += 1

    con = init_db()
    print(f"[collector] DB: {DB_PATH}")
    if once:
        collect_once(con)
        return
    print(f"[collector] เก็บทุก {interval}s — กด Ctrl+C เพื่อหยุด (ข้อมูลที่เก็บแล้วไม่หาย)")
    try:
        while True:
            collect_once(con)
            time.sleep(interval)
    except KeyboardInterrupt:
        n = con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        print(f"\n[collector] หยุดแล้ว — มีข้อมูลสะสม {n} snapshot")


if __name__ == "__main__":
    main(sys.argv[1:])
