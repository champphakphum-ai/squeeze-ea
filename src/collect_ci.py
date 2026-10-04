"""
Collector สำหรับ GitHub Actions — เก็บ 1 snapshot ต่อยอดลง CSV

ต่างจาก collector.py (ที่วนลูปในเครื่อง): ตัวนี้ทำงานครั้งเดียวแล้วจบ
เหมาะกับ cron ของ GitHub Actions — รันบนคลาวด์ ไม่ต้องเปิดคอม

ใช้ Python standard library ล้วน -> รันบน GitHub ได้โดยไม่ต้อง pip install
ผลเก็บเป็น CSV (diff ง่าย, commit กลับ repo ได้)
"""
from __future__ import annotations
import sys
import os
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from src import deribit_client, features

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "btc_snapshots.csv")

FEATURE_ORDER = [
    "net_gex_m", "dealer_long_gamma", "gamma_flip_dist_pct",
    "call_wall_dist_pct", "put_wall_dist_pct", "atm_iv", "iv_skew_rr25",
    "term_slope", "put_call_oi_ratio", "put_gamma_share",
    "total_option_oi", "funding_rate", "perp_oi", "n_options",
]
HEADER = ["ts", "spot"] + FEATURE_ORDER


def main():
    rows = deribit_client.book_summary_options("BTC")
    try:
        fund = deribit_client.funding_rate("BTC-PERPETUAL")
    except Exception:
        fund = None
    snap = features.extract(rows, funding=fund)
    if not snap:
        print("[ci] ไม่มีข้อมูล options — ข้าม")
        return 0

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    exists = os.path.exists(CSV_PATH)
    f = snap["features"]
    row = [snap["ts"], snap["spot"]] + [f.get(k) for k in FEATURE_ORDER]
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        if not exists:
            w.writerow(HEADER)
        w.writerow(row)

    # นับจำนวนบรรทัดข้อมูล
    with open(CSV_PATH, encoding="utf-8") as fp:
        n = sum(1 for _ in fp) - 1
    print(f"[ci] เก็บแล้ว spot=${snap['spot']:,.0f} netGEX={f['net_gex_m']:+.0f}M "
          f"flip={f.get('gamma_flip_dist_pct') or 0:+.1f}% | รวม {n} แถว")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
