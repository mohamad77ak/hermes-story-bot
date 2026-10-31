#!/usr/bin/env python3
"""Hermes Gold – استوری خودکار قیمت.
دستورها:
  python bot.py render [--demo]   ساخت تصویر استوری
  python bot.py publish           انتشار آخرین تصویر ساخته‌شده روی اینستاگرام
"""
import argparse, json, os, pathlib, sys, time, datetime as dt, zoneinfo
import requests, jdatetime, arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).parent
OUT, ASSETS = ROOT / "out", ROOT / "assets"
STATE = ROOT / "state" / "last_prices.json"
TZ = zoneinfo.ZoneInfo("Asia/Tehran")
FONT_URL = "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-{w}.ttf"

# ============ تنظیمات منبع قیمت (بعد از انتخاب منبع ویرایش شود) ============
# هر مورد: (عنوان روی استوری, مسیر مقدار در JSON با نقطه، مثلا "data.gold18.price" یا "items.0.price")
ITEMS = [
    ("طلای ۱۸ عیار (هر گرم)", "gold18"),
    ("سکه امامی", "sekke"),
    ("نیم‌سکه", "nim"),
    ("ربع‌سکه", "rob"),
    ("دلار", "usd"),
]
# اگر منبع شما قیمت را به ریال می‌دهد، PRICE_DIVISOR=10 بگذارید تا تومان شود.
DEMO = {"طلای ۱۸ عیار (هر گرم)": 7650000, "سکه امامی": 78500000,
        "نیم‌سکه": 41200000, "ربع‌سکه": 23800000, "دلار": 98500}
MAX_JUMP = 0.08   # اگر قیمتی نسبت به دفعه قبل بیش از ۸٪ تغییر کند، انتشار متوقف می‌شود
# ===========================================================================

FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
AR = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def fa_num(n): return f"{n:,}".replace(",", "٬").translate(FA)
def rtl(s): return get_display(arabic_reshaper.reshape(s))

def to_int(v):
    if isinstance(v, (int, float)): return int(v)
    return int(float(str(v).translate(AR).replace(",", "").replace("٬", "").strip()))

def dig(obj, path):
    for p in path.split("."):
        obj = obj[int(p)] if isinstance(obj, list) else obj[p]
    return obj

def fetch_prices():
    url = os.environ.get("PRICE_API_URL")
    if not url: sys.exit("PRICE_API_URL تنظیم نشده است.")
    headers = json.loads(os.environ.get("PRICE_API_HEADERS") or "{}")
    r = requests.get(url, headers=headers, timeout=30); r.raise_for_status()
    data, div = r.json(), int(os.environ.get("PRICE_DIVISOR") or 1)
    return {label: to_int(dig(data, path)) // div for label, path in ITEMS}

def sanity(prices):
    if any(v <= 0 for v in prices.values()): sys.exit("قیمت نامعتبر (صفر یا منفی) – انتشار لغو شد.")
    if STATE.exists():
        last = json.loads(STATE.read_text())
        for k, v in prices.items():
            if k in last and last[k] and abs(v - last[k]) / last[k] > MAX_JUMP:
                sys.exit(f"تغییر مشکوک در «{k}»: {last[k]} → {v}. انتشار لغو شد.")

def font(w, size):
    ASSETS.mkdir(exist_ok=True)
    p = ASSETS / f"Vazirmatn-{w}.ttf"
    if not p.exists():
        p.write_bytes(requests.get(FONT_URL.format(w=w), timeout=60).content)
    return ImageFont.truetype(str(p), size, layout_engine=ImageFont.Layout.BASIC)

def render(prices, now):
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), "#0B1020")
    d = ImageDraw.Draw(img)
    for y in range(H):  # گرادیان ملایم
        t = y / H; c = (int(11 + 14 * t), int(16 + 12 * t), int(32 + 22 * t))
        d.line([(0, y), (W, y)], fill=c)
    GOLD, SOFT = "#D4AF37", "#E9E4D0"
    def right(s, y, f, fill, x=W - 90): d.text((x - d.textlength(rtl(s), font=f), y), rtl(s), font=f, fill=fill)
    def center(s, y, f, fill): d.text(((W - d.textlength(rtl(s), font=f)) / 2, y), rtl(s), font=f, fill=fill)

    center("هرمس گلد", 150, font("Bold", 110), GOLD)
    d.line([(390, 300), (690, 300)], fill=GOLD, width=3)
    center("قیمت لحظه‌ای طلا و ارز", 340, font("Bold", 60), SOFT)
    j = jdatetime.datetime.fromgregorian(datetime=now)
    center(f"{j.strftime('%Y/%m/%d')}  |  ساعت {j.strftime('%H:%M')}".translate(FA), 430, font("Regular", 44), "#9FA6BD")

    n = len(prices); card_h, gap = 170, 36
    y0 = 600
    fl, fp, fu = font("Bold", 52), font("Bold", 66), font("Regular", 34)
    for i, (label, val) in enumerate(prices.items()):
        y = y0 + i * (card_h + gap)
        d.rounded_rectangle([70, y, W - 70, y + card_h], radius=36, fill="#141B33", outline="#2A3558", width=2)
        d.rounded_rectangle([W - 76, y + 30, W - 70, y + card_h - 30], radius=3, fill=GOLD)
        right(label, y + 50, fl, SOFT, x=W - 110)
        num = fa_num(val)
        d.text((120, y + 40), num, font=fp, fill=GOLD)
        d.text((120 + d.textlength(num, font=fp) + 16, y + 78), rtl("تومان"), font=fu, fill="#9FA6BD")

    center("ظرافت، کیفیت و اصالت در کنار هم", H - 260, font("Regular", 40), SOFT)
    center("@hermes_goold", H - 190, font("Bold", 48), GOLD)
    center("قیمت‌ها جهت اطلاع‌رسانی است", H - 120, font("Regular", 30), "#6F7893")
    return img

def cmd_render(demo):
    now = dt.datetime.now(TZ)
    prices = DEMO if demo else fetch_prices()
    if not demo: sanity(prices)
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("story_*.jpg"): old.unlink()
    name = f"story_{now:%Y%m%d_%H%M}.jpg"
    render(prices, now).save(OUT / name, "JPEG", quality=92)
    (OUT / "latest.txt").write_text(name)
    if not demo:
        STATE.parent.mkdir(exist_ok=True); STATE.write_text(json.dumps(prices, ensure_ascii=False))
    print("ساخته شد:", name)

def composio(slug, arguments):
    body = {"arguments": arguments}
    if os.environ.get("COMPOSIO_CONNECTED_ACCOUNT_ID"): body["connected_account_id"] = os.environ["COMPOSIO_CONNECTED_ACCOUNT_ID"]
    if os.environ.get("COMPOSIO_USER_ID"): body["user_id"] = os.environ["COMPOSIO_USER_ID"]
    r = requests.post(f"https://backend.composio.dev/api/v3/tools/execute/{slug}",
                      headers={"x-api-key": os.environ["COMPOSIO_API_KEY"], "Content-Type": "application/json"},
                      json=body, timeout=180)
    if r.status_code >= 400: sys.exit(f"{slug} → HTTP {r.status_code}: {r.text[:500]}")
    j = r.json()
    if j.get("successful") is False: sys.exit(f"{slug} ناموفق: {j.get('error')}")
    return j.get("data") or {}

def find_id(d):
    if isinstance(d, dict):
        if "id" in d: return d["id"]
        for v in d.values():
            x = find_id(v)
            if x: return x

def cmd_publish():
    name = (OUT / "latest.txt").read_text().strip()
    url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{os.environ.get('GITHUB_REF_NAME','main')}/out/{name}"
    for _ in range(18):  # صبر تا عکس روی لینک عمومی در دسترس شود
        try:
            if requests.get(url, timeout=20).status_code == 200: break
        except requests.RequestException: pass
        time.sleep(5)
    else: sys.exit("تصویر روی لینک عمومی در دسترس نشد.")
    uid = os.environ.get("IG_USER_ID", "me")
    cid = find_id(composio("INSTAGRAM_POST_IG_USER_MEDIA", {"ig_user_id": uid, "media_type": "STORIES", "image_url": url}))
    if not cid: sys.exit("شناسه کانتینر دریافت نشد.")
    mid = find_id(composio("INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH", {"ig_user_id": uid, "creation_id": str(cid)}))
    print("استوری منتشر شد. media_id =", mid)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["render", "publish"]); ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    cmd_render(a.demo) if a.cmd == "render" else cmd_publish()
