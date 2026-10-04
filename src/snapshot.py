"""
BTC GEX / Gamma Flip snapshot — พิสูจน์แนวคิด

รัน:  python src/snapshot.py            (ดึงข้อมูลสดจาก Deribit)
      python src/snapshot.py file.json  (ใช้ไฟล์ที่ดาวน์โหลดไว้)
      python src/snapshot.py --dte 30   (กรองเฉพาะ options อายุ <= 30 วัน)

ใช้แค่ Python standard library ล้วน ๆ
"""
from __future__ import annotations
import sys
import os
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:  # ให้ภาษาไทยแสดงผลถูกบน Windows console
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from src import gex  # noqa: E402


def _fmt(n, d=0):
    return f"{n:,.{d}f}"


def load_rows(args):
    max_dte = 45
    src_file = None
    i = 0
    while i < len(args):
        if args[i] == "--dte" and i + 1 < len(args):
            max_dte = float(args[i + 1]); i += 2
        else:
            src_file = args[i]; i += 1
    if src_file:
        rows = json.load(open(src_file))
        rows = rows.get("result", rows)
        print(f"[source] ไฟล์: {src_file}")
    else:
        from src import deribit_client
        print("[source] Deribit public API (live)")
        rows = deribit_client.book_summary_options("BTC")
    return rows, max_dte


def main(argv):
    rows, max_dte = load_rows(argv)
    res = gex.analyze(rows, max_dte=max_dte)
    if not res:
        print("ไม่มีข้อมูล options ที่ใช้ได้"); return

    bar = "=" * 64
    print(bar)
    print(f"  BTC GEX SNAPSHOT  |  {res['now'].strftime('%Y-%m-%d %H:%M UTC')}")
    print(bar)
    print(f"  Spot (underlying)      : ${_fmt(res['spot'], 1)}")
    print(f"  Options ที่ใช้ (DTE<={int(max_dte)}) : {res['n_options']}  |  OI รวม {_fmt(res['total_oi'],1)} BTC")
    print()
    # Net GEX / Dealer regime
    regime = "LONG GAMMA (ตลาดมักนิ่ง, ดูดความผันผวน)" if res["dealer_long_gamma"] \
        else "SHORT GAMMA (เร่งการเคลื่อนไหว, เสี่ยง Squeeze สูง)"
    sign = "+" if res["net_gex"] >= 0 else "-"
    print(f"  Net Dealer GEX         : {sign}{_fmt(abs(res['net_gex'])/1e6,1)}M  ->  Dealer {regime}")
    if res["gamma_flip"]:
        rel = (res["gamma_flip"] / res["spot"] - 1) * 100
        side = "เหนือราคา" if rel > 0 else "ใต้ราคา"
        print(f"  Gamma Flip level       : ${_fmt(res['gamma_flip'],1)}  ({rel:+.1f}% {side})")
        print(f"    -> ต่ำกว่าเส้นนี้ = Dealer Short Gamma (เสี่ยง squeeze) / สูงกว่า = Long Gamma")
    else:
        print("  Gamma Flip level       : ไม่พบในกรอบ +-30%")
    print()
    print("  โซนต้าน (Call Gamma Walls — dealer ขายเมื่อราคาขึ้น):")
    for k, v in res["top_call_walls"]:
        print(f"      ${_fmt(k)}   gamma={_fmt(v/1e6,2)}M")
    print()
    print("  โซนรับ (Put Gamma Walls — dealer ซื้อเมื่อราคาลง):")
    for k, v in res["top_put_walls"]:
        print(f"      ${_fmt(k)}   gamma={_fmt(abs(v)/1e6,2)}M")
    print(bar)
    print("  * พิสูจน์แนวคิด — ตัวเลข GEX เป็นเชิงเปรียบเทียบ (ดู gex.py หมายเหตุ)")
    print(bar)


if __name__ == "__main__":
    main(sys.argv[1:])
