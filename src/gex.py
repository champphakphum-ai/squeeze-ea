"""
GEX / Gamma Flip engine for BTC options (Deribit).

พิสูจน์แนวคิดตามเนื้อหา "Squeeze บทที่ 5 (GEX, Gamma Flip)" และบทที่ 8 (case study)
ใช้เฉพาะ Python standard library — รันได้ทันทีโดยไม่ต้องติดตั้งอะไร

ข้อจำกัดที่ต้องรู้ (ตามจริง):
  - Deribit เป็น options แบบ coin-settled (inverse) หน่วย gamma จึงไม่ตรงกับหุ้น US เป๊ะ
    เราคำนวณ Black-Scholes gamma เทียบราคา USD แล้วถ่วงด้วย OI เพื่อหา "รูปทรง" ของ
    gamma profile และ "จุด Gamma Flip" ซึ่งเป็นสิ่งที่ใช้จริงในการเทรด
    ตัวเลข GEX สัมบูรณ์เป็นเชิงเปรียบเทียบ ไม่ใช่มูลค่าดอลลาร์ที่แม่นระดับ dealer จริง
  - สมมติ dealer ถือตรงข้ามลูกค้า: Call OI -> +gamma, Put OI -> -gamma (คอนเวนชันมาตรฐาน)
  - r = 0 (ดอกเบี้ยไม่ส่งผลมากกับ gamma ระยะสั้น)
"""
from __future__ import annotations
import math
from datetime import datetime, timezone

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def parse_instrument(name: str):
    """'BTC-27NOV26-73000-P' -> dict(expiry, strike, is_call)"""
    parts = name.split("-")
    if len(parts) != 4:
        return None
    _, exp_s, strike_s, cp = parts
    try:
        day = int(exp_s[:-5])
        mon = _MONTHS[exp_s[-5:-2]]
        year = 2000 + int(exp_s[-2:])
    except (KeyError, ValueError):
        return None
    # Deribit options หมดอายุ 08:00 UTC
    expiry = datetime(year, mon, day, 8, 0, 0, tzinfo=timezone.utc)
    return {
        "expiry": expiry,
        "strike": float(strike_s),
        "is_call": cp.upper() == "C",
    }


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_gamma(spot: float, strike: float, t_years: float, iv: float) -> float:
    """Black-Scholes gamma (r=0). iv เป็นสัดส่วน เช่น 0.40 = 40%"""
    if spot <= 0 or strike <= 0 or t_years <= 0 or iv <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + 0.5 * iv * iv * t_years) / (iv * math.sqrt(t_years))
    return _norm_pdf(d1) / (spot * iv * math.sqrt(t_years))


def build_options(rows, now=None, max_dte=None, min_oi=0.0):
    """แปลง raw book_summary rows -> list ของ option ที่พร้อมคำนวณ"""
    now = now or datetime.now(timezone.utc)
    out = []
    for r in rows:
        meta = parse_instrument(r.get("instrument_name", ""))
        if not meta:
            continue
        oi = r.get("open_interest") or 0.0
        iv = r.get("mark_iv")
        if oi <= min_oi or not iv:
            continue
        dte_days = (meta["expiry"] - now).total_seconds() / 86400.0
        if dte_days <= 0:
            continue
        if max_dte is not None and dte_days > max_dte:
            continue
        spot = r.get("underlying_price") or r.get("estimated_delivery_price")
        if not spot:
            continue
        out.append({
            "name": r["instrument_name"],
            "strike": meta["strike"],
            "is_call": meta["is_call"],
            "oi": float(oi),
            "iv": float(iv) / 100.0,
            "dte": dte_days,
            "t": dte_days / 365.0,
            "spot": float(spot),
        })
    return out


def net_gex_at(options, spot_hyp: float) -> float:
    """คำนวณ net dealer GEX สมมติราคา = spot_hyp (ใช้หา gamma flip)"""
    total = 0.0
    for o in options:
        g = bs_gamma(spot_hyp, o["strike"], o["t"], o["iv"])
        dollar_gamma = g * o["oi"] * spot_hyp * spot_hyp * 0.01
        total += dollar_gamma if o["is_call"] else -dollar_gamma
    return total


def gamma_flip(options, spot: float, lo_mult=0.7, hi_mult=1.3, steps=120):
    """หา 'จุด Gamma Flip' = ราคาที่ net GEX เปลี่ยนเครื่องหมาย (ใกล้ spot สุด)"""
    lo, hi = spot * lo_mult, spot * hi_mult
    grid = [lo + (hi - lo) * i / steps for i in range(steps + 1)]
    prev_p, prev_v = grid[0], net_gex_at(options, grid[0])
    crossings = []
    for p in grid[1:]:
        v = net_gex_at(options, p)
        if prev_v == 0 or (prev_v < 0 < v) or (prev_v > 0 > v):
            # interpolate zero crossing
            if v != prev_v:
                x = prev_p + (0 - prev_v) * (p - prev_p) / (v - prev_v)
            else:
                x = p
            crossings.append(x)
        prev_p, prev_v = p, v
    if not crossings:
        return None
    return min(crossings, key=lambda x: abs(x - spot))


def strike_gamma_profile(options, spot: float):
    """รวม dealer GEX ต่อ strike (ที่ราคาปัจจุบัน) -> ใช้หาโซนแนวรับ/ต้าน"""
    by_strike = {}
    for o in options:
        g = bs_gamma(spot, o["strike"], o["t"], o["iv"])
        dollar_gamma = g * o["oi"] * spot * spot * 0.01
        signed = dollar_gamma if o["is_call"] else -dollar_gamma
        by_strike[o["strike"]] = by_strike.get(o["strike"], 0.0) + signed
    return dict(sorted(by_strike.items()))


def analyze(rows, now=None, max_dte=45, min_oi=0.0):
    """สรุป GEX ครบชุดสำหรับ snapshot เดียว"""
    now = now or datetime.now(timezone.utc)
    opts = build_options(rows, now=now, max_dte=max_dte, min_oi=min_oi)
    if not opts:
        return None
    spot = sum(o["spot"] for o in opts) / len(opts)
    total = net_gex_at(opts, spot)
    flip = gamma_flip(opts, spot)
    profile = strike_gamma_profile(opts, spot)
    calls = {k: v for k, v in profile.items() if v > 0}
    puts = {k: v for k, v in profile.items() if v < 0}
    top_call = sorted(calls.items(), key=lambda kv: -kv[1])[:5]
    top_put = sorted(puts.items(), key=lambda kv: kv[1])[:5]
    return {
        "now": now,
        "spot": spot,
        "n_options": len(opts),
        "total_oi": sum(o["oi"] for o in opts),
        "net_gex": total,
        "dealer_long_gamma": total > 0,
        "gamma_flip": flip,
        "top_call_walls": top_call,   # โซนต้าน (dealer ขายเมื่อราคาขึ้น)
        "top_put_walls": top_put,     # โซนรับ (dealer ซื้อเมื่อราคาลง)
        "max_dte": max_dte,
    }
