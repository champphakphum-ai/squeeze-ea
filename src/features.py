"""
Feature factory — แปลง "ทุกบท" ให้เป็น feature ตัวเลขชุดเดียว ป้อน ML

แต่ละบท = กลุ่ม feature:
  บท 5  -> GEX: net_gex, gamma_flip_dist_pct, dealer_long_gamma, call/put wall ใกล้สุด
  บท 6  -> IV:  atm_iv, iv_skew, rr_25_proxy, term_slope
  บท 7  -> Put side: put_call_oi_ratio, put_gamma_share
  บท 2  -> Flow: funding_rate, perp_oi, total_option_oi

หมายเหตุ: feature สายราคา (ATR, BB Width — บท 4) คำนวณทีหลังจาก "spot series"
ที่ collector เก็บไว้ (ไม่ต้องคำนวณต่อ tick) — ดู derive_price_features()
"""
from __future__ import annotations
import math
from datetime import datetime, timezone
from src import gex


def _nearest_expiry_opts(opts):
    if not opts:
        return []
    min_dte = min(o["dte"] for o in opts)
    # จัดกลุ่มใกล้ ๆ expiry แรก (ภายใน +3 วัน)
    return [o for o in opts if o["dte"] <= min_dte + 3]


def _atm_iv(opts, spot):
    if not opts:
        return None
    o = min(opts, key=lambda x: abs(x["strike"] - spot))
    return o["iv"]


def _iv_at_moneyness(opts, spot, target_mny, is_call):
    """หา IV ของ option ที่ strike ใกล้ spot*target_mny ที่สุด (แยก call/put)"""
    cands = [o for o in opts if o["is_call"] == is_call]
    if not cands:
        return None
    target = spot * target_mny
    o = min(cands, key=lambda x: abs(x["strike"] - target))
    return o["iv"]


def extract(option_rows, now=None, funding=None, max_dte=45):
    """รับ raw Deribit rows -> dict feature ตัวเลขชุดเดียว"""
    now = now or datetime.now(timezone.utc)
    opts = gex.build_options(option_rows, now=now, max_dte=max_dte, min_oi=0.0)
    if not opts:
        return None
    spot = sum(o["spot"] for o in opts) / len(opts)

    # ---- บท 5: GEX / Gamma Flip ----
    net = gex.net_gex_at(opts, spot)
    flip = gex.gamma_flip(opts, spot)
    profile = gex.strike_gamma_profile(opts, spot)
    call_walls = {k: v for k, v in profile.items() if v > 0}
    put_walls = {k: v for k, v in profile.items() if v < 0}
    nearest_call = min(call_walls, key=lambda k: abs(k - spot)) if call_walls else None
    nearest_put = min(put_walls, key=lambda k: abs(k - spot)) if put_walls else None

    # ---- บท 6: IV / Skew / Term structure ----
    near = _nearest_expiry_opts(opts)
    atm_iv = _atm_iv(near, spot)
    otm_call_iv = _iv_at_moneyness(near, spot, 1.10, True)
    otm_put_iv = _iv_at_moneyness(near, spot, 0.90, False)
    rr_25 = (otm_call_iv - otm_put_iv) if (otm_call_iv and otm_put_iv) else None  # บวก=call skew
    # term slope: ATM IV ของ expiry ไกล - ATM IV ของ expiry ใกล้
    far = [o for o in opts if o["dte"] > (min(o2["dte"] for o2 in opts) + 20)]
    term_slope = (_atm_iv(far, spot) - atm_iv) if (far and atm_iv) else None

    # ---- บท 7: Put side ----
    call_oi = sum(o["oi"] for o in opts if o["is_call"])
    put_oi = sum(o["oi"] for o in opts if not o["is_call"])
    put_call_oi_ratio = (put_oi / call_oi) if call_oi else None
    total_call_g = sum(abs(v) for v in call_walls.values())
    total_put_g = sum(abs(v) for v in put_walls.values())
    put_gamma_share = (total_put_g / (total_call_g + total_put_g)) \
        if (total_call_g + total_put_g) else None

    feat = {
        # บท 5
        "net_gex_m": net / 1e6,
        "dealer_long_gamma": 1 if net > 0 else 0,
        "gamma_flip_dist_pct": ((flip / spot - 1) * 100) if flip else None,
        "call_wall_dist_pct": ((nearest_call / spot - 1) * 100) if nearest_call else None,
        "put_wall_dist_pct": ((nearest_put / spot - 1) * 100) if nearest_put else None,
        # บท 6
        "atm_iv": atm_iv,
        "iv_skew_rr25": rr_25,
        "term_slope": term_slope,
        # บท 7
        "put_call_oi_ratio": put_call_oi_ratio,
        "put_gamma_share": put_gamma_share,
        # บท 2
        "total_option_oi": call_oi + put_oi,
        "funding_rate": (funding or {}).get("funding_rate"),
        "perp_oi": (funding or {}).get("open_interest"),
        # บริบท
        "n_options": len(opts),
    }
    return {"ts": now.isoformat(), "spot": spot, "features": feat}


# ---------- บท 4: feature สายราคา (คำนวณจาก spot series ทีหลัง) ----------
def derive_price_features(spots, period=14):
    """รับ list ของ spot ล่าสุด (เรียงเก่า->ใหม่) -> ATR-like, realized vol, BB pos"""
    if len(spots) < period + 1:
        return {"rv": None, "bb_pos": None, "range_pct": None}
    window = spots[-(period + 1):]
    rets = [window[i] / window[i - 1] - 1 for i in range(1, len(window))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    rv = math.sqrt(var) * math.sqrt(len(rets))  # realized vol ในหน้าต่าง
    hi, lo = max(window), min(window)
    range_pct = (hi - lo) / lo * 100 if lo else None
    # ตำแหน่งในกรอบ (0=ล่างสุด,1=บนสุด) คล้าย %B ของ Bollinger
    bb_pos = (window[-1] - lo) / (hi - lo) if hi > lo else 0.5
    return {"rv": rv, "bb_pos": bb_pos, "range_pct": range_pct}
