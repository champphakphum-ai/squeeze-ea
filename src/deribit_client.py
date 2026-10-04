"""
Deribit data client.

เฟสพิสูจน์แนวคิด: ใช้ public endpoint (ไม่ต้องมี API key)
เฟสเทรดจริง: เพิ่มฟังก์ชัน auth ด้วย client_id/secret จาก .env ภายหลัง

ใช้แค่ urllib (standard library) เพื่อให้รันได้ทันทีโดยไม่ต้องติดตั้งอะไร
"""
from __future__ import annotations
import json
import urllib.request
import urllib.parse

# testnet: https://test.deribit.com/api/v2  | mainnet: https://www.deribit.com/api/v2
BASE = "https://www.deribit.com/api/v2"


def _get(path: str, params: dict, timeout: int = 30):
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "squeeze-ea/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "error" in data and data["error"]:
        raise RuntimeError(f"Deribit error: {data['error']}")
    return data["result"]


def book_summary_options(currency: str = "BTC"):
    """options chain พร้อม OI, mark_iv, underlying_price (ก้อนเดียวจบ)"""
    return _get("/public/get_book_summary_by_currency",
                {"currency": currency, "kind": "option"})


def index_price(currency: str = "BTC"):
    r = _get("/public/get_index_price", {"index_name": f"{currency.lower()}_usd"})
    return r.get("index_price")


def funding_rate(instrument: str = "BTC-PERPETUAL"):
    """funding rate ปัจจุบัน (ใช้สัญญาณ Liquidation/Leverage squeeze ภายหลัง)"""
    r = _get("/public/ticker", {"instrument_name": instrument})
    return {
        "funding_8h": r.get("current_funding"),
        "funding_rate": r.get("funding_8h"),
        "mark_price": r.get("mark_price"),
        "open_interest": r.get("open_interest"),
    }
