"""
เฟส C — เทรน ML ตัวแรกบนทอง (Volatility Squeeze / บท 4)

ขั้นตอน:
  1) โหลดแท่ง H1 จาก data/gold.db
  2) สร้าง feature (ATR, BB width/%b, realized vol, squeeze ratio, momentum, เวลา)
  3) สร้าง label แบบ Triple-Barrier:
        มองไปข้างหน้า N แท่ง — ชน +M*ATR ก่อน = +1 (ขึ้น),
        ชน -M*ATR ก่อน = -1 (ลง), ไม่ชนเลย = 0 (ไม่ไปไหน/chop)
  4) Walk-forward (TimeSeriesSplit) — เทรนอดีต ทดสอบอนาคต กัน overfit
  5) รายงาน: ความแม่น, เทียบ baseline, expectancy ของสัญญาณ, feature สำคัญ

รัน:  python src/train_gold.py
      python src/train_gold.py --horizon 12 --barrier 1.5
"""
from __future__ import annotations
import sys
import os
import sqlite3
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "gold.db")


def load(symbol="XAUUSD-STDc", tf="H1"):
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT time,open,high,low,close,tick_volume FROM bars "
        "WHERE symbol=? AND tf=? ORDER BY time", con, params=(symbol, tf))
    con.close()
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df


def add_features(df, atr_p=14, bb_p=20):
    c, h, l = df["close"], df["high"], df["low"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(atr_p).mean()

    mid = c.rolling(bb_p).mean()
    sd = c.rolling(bb_p).std()
    upper, lower = mid + 2 * sd, mid - 2 * sd
    df["bb_width"] = (upper - lower) / mid * 100
    df["bb_pos"] = (c - lower) / (upper - lower)          # %B (0=ล่าง,1=บน)
    df["bb_width_ratio"] = df["bb_width"] / df["bb_width"].rolling(50).mean()
    df["atr_ratio"] = df["atr"] / df["atr"].rolling(50).mean()

    logret = np.log(c / prev_c)
    df["rv14"] = logret.rolling(14).std() * np.sqrt(14)
    df["mom5"] = c / c.shift(5) - 1
    df["mom10"] = c / c.shift(10) - 1
    df["dist_mid"] = (c - mid) / df["atr"]                # ห่างเส้นกลางกี่ ATR
    df["hour"] = df["dt"].dt.hour
    df["dow"] = df["dt"].dt.dayofweek
    return df


def triple_barrier(df, horizon=12, barrier=1.5):
    """label: +1 ชนขอบบนก่อน, -1 ชนขอบล่างก่อน, 0 ไม่ชน"""
    c = df["close"].values
    hi = df["high"].values
    lo = df["low"].values
    atr = df["atr"].values
    n = len(df)
    y = np.zeros(n, dtype=int)
    for i in range(n):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            y[i] = -99; continue
        up = c[i] + barrier * a
        dn = c[i] - barrier * a
        end = min(i + horizon, n - 1)
        lab = 0
        for j in range(i + 1, end + 1):
            hit_up = hi[j] >= up
            hit_dn = lo[j] <= dn
            if hit_up and hit_dn:
                lab = 1 if (hi[j] - up) <= (dn - lo[j]) else -1  # ประมาณว่าแตะไหนก่อน
                break
            if hit_up:
                lab = 1; break
            if hit_dn:
                lab = -1; break
        y[i] = lab
    df["label"] = y
    # forward return จริง (ไว้วัด expectancy)
    df["fwd_ret_atr"] = (pd.Series(c).shift(-horizon) - c) / df["atr"]

    # --- โหมด expansion: วัด "ระยะสุดขั้ว" ที่ราคาไปถึงใน N แท่ง (ไม่สนทิศ) ---
    n = len(df)
    exc = np.full(n, np.nan)
    for i in range(n):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        end = min(i + horizon, n - 1)
        if end <= i:
            continue
        mx = np.max(hi[i + 1:end + 1]); mn = np.min(lo[i + 1:end + 1])
        exc[i] = max(mx - c[i], c[i] - mn) / a       # ระยะสุดขั้ว (ATR)
    df["fwd_excursion_atr"] = exc
    df["exp_label"] = (exc >= barrier).astype(int)    # 1 = ระเบิดใหญ่, 0 = นิ่ง
    return df


FEATURES = ["bb_width", "bb_pos", "bb_width_ratio", "atr_ratio", "rv14",
            "mom5", "mom10", "dist_mid", "hour", "dow", "atr"]


def run_expansion(df, horizon, barrier):
    """โจทย์ที่ตรงกับบท4: 'จะเกิดการระเบิดใหญ่ไหม' (ไม่สนทิศ)"""
    X = df[FEATURES].values
    y = df["exp_label"].values
    exc = df["fwd_excursion_atr"].values

    print("=" * 62)
    print(f"  GOLD ML — โหมด EXPANSION (ระเบิด >= {barrier} ATR ใน {horizon} แท่ง?)")
    print("=" * 62)
    base = y.mean()
    print(f"  ตัวอย่าง: {len(df):,}  | อัตราเกิดระเบิดจริง (base rate): {base*100:.1f}%")
    print(f"  ระยะสุดขั้วเฉลี่ยทุกแท่ง: {np.nanmean(exc):.2f} ATR")
    print("-" * 62)

    tss = TimeSeriesSplit(n_splits=5)
    precs, lifts, imps = [], [], []
    fold = 0
    for tr_idx, te_idx in tss.split(X):
        fold += 1
        clf = RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=50,
            class_weight="balanced", n_jobs=-1, random_state=42)
        clf.fit(X[tr_idx], y[tr_idx])
        proba = clf.predict_proba(X[te_idx])[:, 1]
        # เลือกสัญญาณ: บาร์ที่โมเดลมั่นใจสุด 30% ว่าจะระเบิด
        thr = np.quantile(proba, 0.70)
        sig = proba >= thr
        exc_te = exc[te_idx]
        exc_sig = np.nanmean(exc_te[sig]) if sig.sum() else np.nan
        exc_all = np.nanmean(exc_te)
        prec = y[te_idx][sig].mean() if sig.sum() else np.nan   # ความแม่นว่าระเบิดจริง
        lift = exc_sig - exc_all
        precs.append(prec); lifts.append(lift); imps.append(clf.feature_importances_)
        print(f"  Fold {fold}: เลือก {sig.sum():4,} บาร์ | ระเบิดจริง {prec*100:4.1f}% "
              f"(base {y[te_idx].mean()*100:4.1f}%) | excursion {exc_sig:.2f} vs {exc_all:.2f} ATR")

    print("-" * 62)
    print(f"  เฉลี่ย precision สัญญาณ: {np.nanmean(precs)*100:.1f}%  (base {base*100:.1f}%)")
    print(f"  Lift ระยะระเบิด: {np.nanmean(lifts):+.2f} ATR  "
          f"(บวก=บาร์ที่โมเดลเลือกระเบิดแรงกว่าค่าเฉลี่ยจริง)")
    print("-" * 62)
    imp = np.mean(imps, axis=0); order = np.argsort(imp)[::-1]
    print("  Feature สำคัญสุด:")
    for k in order[:6]:
        print(f"    {FEATURES[k]:16} {imp[k]*100:4.1f}%")
    print("=" * 62)
    print("  * precision > base ชัด + lift บวก = ทำนาย 'จังหวะระเบิด' ได้")
    print("    -> เทรดแบบ straddle/bracket (กินได้ทั้งสองทาง) ได้")
    print("=" * 62)


def main(argv):
    horizon, barrier, squeeze_max, mode = 12, 1.5, None, "direction"
    i = 0
    while i < len(argv):
        if argv[i] == "--horizon" and i + 1 < len(argv):
            horizon = int(argv[i + 1]); i += 2
        elif argv[i] == "--barrier" and i + 1 < len(argv):
            barrier = float(argv[i + 1]); i += 2
        elif argv[i] == "--squeeze_max" and i + 1 < len(argv):
            squeeze_max = float(argv[i + 1]); i += 2
        elif argv[i] == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1]; i += 2
        else:
            i += 1

    df = load()
    df = add_features(df)
    df = triple_barrier(df, horizon=horizon, barrier=barrier)
    df = df[df["label"] != -99].dropna(
        subset=FEATURES + ["label", "fwd_ret_atr", "fwd_excursion_atr"])
    if squeeze_max is not None:
        df = df[df["bb_width_ratio"] <= squeeze_max]   # เฉพาะช่วงบีบตัวจริง
        print(f"  [filter] เฉพาะช่วงบีบตัว bb_width_ratio <= {squeeze_max}")
    df = df.reset_index(drop=True)

    if mode == "expansion":
        return run_expansion(df, horizon, barrier)

    X = df[FEATURES].values
    y = df["label"].values
    fwd = df["fwd_ret_atr"].values

    print("=" * 60)
    print(f"  GOLD ML — Triple-Barrier (horizon={horizon} แท่ง, ±{barrier} ATR)")
    print("=" * 60)
    print(f"  ตัวอย่างทั้งหมด: {len(df):,}")
    vc = pd.Series(y).value_counts().sort_index()
    names = {-1: "ลง(-1)", 0: "ไม่ไป(0)", 1: "ขึ้น(+1)"}
    for k, v in vc.items():
        print(f"    {names[k]:10}: {v:6,}  ({v/len(y)*100:4.1f}%)")
    baseline = vc.max() / len(y)
    print(f"  Baseline (เดาคลาสใหญ่สุด): {baseline*100:.1f}%")
    print("-" * 60)

    tss = TimeSeriesSplit(n_splits=5)
    accs, importances, exps = [], [], []
    fold = 0
    for tr_idx, te_idx in tss.split(X):
        fold += 1
        clf = RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=50,
            class_weight="balanced", n_jobs=-1, random_state=42)
        clf.fit(X[tr_idx], y[tr_idx])
        pred = clf.predict(X[te_idx])
        acc = accuracy_score(y[te_idx], pred)
        accs.append(acc)
        importances.append(clf.feature_importances_)
        # expectancy: เมื่อโมเดลบอก +1/-1 ได้ผลตอบแทนจริงเฉลี่ยกี่ ATR (ปรับทิศ)
        mask = pred != 0
        if mask.sum() > 0:
            signed = np.where(pred[mask] == 1, fwd[te_idx][mask], -fwd[te_idx][mask])
            exps.append((mask.sum(), np.nanmean(signed)))
        else:
            exps.append((0, np.nan))
        print(f"  Fold {fold}: acc={acc*100:5.1f}%  | สัญญาณเทรด {mask.sum():5,} ไม้  "
              f"expectancy={exps[-1][1]:+.3f} ATR/ไม้")

    print("-" * 60)
    print(f"  เฉลี่ย out-of-sample accuracy: {np.mean(accs)*100:.1f}%  "
          f"(baseline {baseline*100:.1f}%)")
    tot_sig = sum(e[0] for e in exps)
    w = np.nansum([e[0]*e[1] for e in exps if np.isfinite(e[1])]) / max(tot_sig, 1)
    print(f"  Expectancy เฉลี่ยถ่วงน้ำหนัก: {w:+.3f} ATR ต่อไม้  (บวก=มี edge)")
    print("-" * 60)
    imp = np.mean(importances, axis=0)
    order = np.argsort(imp)[::-1]
    print("  Feature สำคัญสุด:")
    for k in order[:8]:
        print(f"    {FEATURES[k]:16} {imp[k]*100:4.1f}%")
    print("=" * 60)
    print("  * ผลนี้คือ out-of-sample (ทดสอบบนอนาคตที่โมเดลไม่เคยเห็น)")
    print("  * expectancy > 0 ชัดเจน = แนวคิดมี edge / ใกล้ 0 = ต้องปรับ feature/label")
    print("=" * 60)


if __name__ == "__main__":
    main(sys.argv[1:])
