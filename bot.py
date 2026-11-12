#!/usr/bin/env python3
"""Hermes Gold – استوری خودکار قیمت (روی طرح اختصاصی).
دستورها:
  python bot.py render [--demo]   ساخت تصویر استوری
  python bot.py publish           انتشار آخرین تصویر ساخته‌شده روی اینستاگرام
"""
import argparse, json, os, pathlib, sys, time, datetime as dt, zoneinfo
import requests, jdatetime
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).parent
OUT, ASSETS = ROOT / "out", ROOT / "assets"
STATE = ROOT / "state" / "last_prices.json"
TZ = zoneinfo.ZoneInfo("Asia/Tehran")

# ============ منبع قیمت: Iran Market Data (فایل JSON عمومی، مجوز MIT، داده از TGJU، هر ۳۰ دقیقه) ============
FEED_URL = os.environ.get("PRICE_API_URL") or "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/latest-toman.json"
MAX_AGE_MIN = 100   # اگر فایل منبع قدیمی‌تر از این باشد، انتشار متوقف می‌شود
# کلید ← (نماد در منبع, نوع)؛ نوع "toman" یعنی تومان و "usd" یعنی دلار
ITEMS = [
    ("gold18",  "GOLD_18K_IRR",     "toman"),   # طلا ۱۸ عیار (گرم)
    ("emami",   "COIN_EMAMI_IRR",   "toman"),   # سکه امامی
    ("usd",     "USD_IRR_FREE",     "toman"),   # دلار آمریکا (بازار آزاد)
    ("mesghal", "GOLD_MESGHAL_IRR", "toman"),   # مثقال طلا
    ("ounce",   "XAU_USD",          "usd"),     # انس طلای جهانی
]
DEMO = {"gold18": 18697000, "emami": 188000000, "usd": 192300, "mesghal": 81000000, "ounce": 4064.78}
MAX_JUMP = 0.08   # اگر قیمتی نسبت به دفعه قبل بیش از ۸٪ تغییر کند، انتشار متوقف می‌شود

# مختصات روی قالب (۱۰۸۰×۱۹۱۲): (مرکز x, مرکز y, ارتفاع ارقام)
LAYOUT = {"date": (823.5, 844.5, 38), "time": (367.5, 844.5, 35),
          "gold18": (723.5, 988, 46), "emami": (723.5, 1150, 46), "usd": (720.5, 1300, 46),
          "mesghal": (722, 1438.5, 46), "ounce": (718, 1574.5, 46)}
INK = (26, 21, 16)
# ===========================================================================

def fetch_prices():
    for attempt in range(7):   # اگر درست لحظهٔ ساعت گرد اجرا شد، تا ۹۰ ثانیه برای قیمت‌های تازه صبر می‌کند
        r = requests.get(FEED_URL, timeout=40, headers={"Cache-Control": "no-cache"}); r.raise_for_status()
        j = r.json()
        pub = dt.datetime.fromisoformat(j["meta"]["published_at"].replace("Z", "+00:00")).astimezone(TZ)
        age = (dt.datetime.now(TZ) - pub).total_seconds() / 60
        if age <= 28 or attempt == 6: break
        time.sleep(15)
    if age > MAX_AGE_MIN: sys.exit(f"داده منبع قدیمی است ({int(age)} دقیقه) – انتشار لغو شد.")
    idx = {row["symbol"]: row for rows in j["data"]["categories"].values() for row in rows}
    out = {}
    for key, sym, kind in ITEMS:
        row = idx.get(sym)
        if not row or row.get("price") is None: sys.exit(f"نماد {sym} در منبع پیدا نشد.")
        if row.get("currency") != ("USD" if kind == "usd" else "IRT"): sys.exit(f"واحد {sym} غیرمنتظره است.")
        if kind == "toman" and row.get("stale"): sys.exit(f"قیمت {sym} کهنه است – انتشار لغو شد.")
        v = float(row["price"])
        out[key] = round(v, 2) if kind == "usd" else int(round(v))
    return out, pub

def sanity(prices):
    if set(prices) != set(k for k, _, _ in ITEMS): sys.exit("همهٔ قیمت‌ها دریافت نشد.")
    if any(v <= 0 for v in prices.values()): sys.exit("قیمت نامعتبر (صفر یا منفی) – انتشار لغو شد.")
    if STATE.exists():
        last = json.loads(STATE.read_text())
        for k, v in prices.items():
            if k in last and last[k] and abs(v - last[k]) / last[k] > MAX_JUMP:
                sys.exit(f"تغییر مشکوک در «{k}»: {last[k]} → {v}. انتشار لغو شد.")

def fit_font(target_h):
    p = str(ASSETS / "BarlowCondensed-Bold.ttf")
    lo, hi = 20, 120
    while lo < hi:                      # اندازه‌ای که ارتفاع رقم دقیقاً برابر هدف شود
        mid = (lo + hi) // 2
        b = ImageFont.truetype(p, mid).getbbox("0")
        if b[3] - b[1] < target_h: lo = mid + 1
        else: hi = mid
    return ImageFont.truetype(p, lo)

def render(prices, now):
    import numpy as np
    img = Image.open(ASSETS / "template.jpg").convert("RGB")
    d = ImageDraw.Draw(img)
    j = jdatetime.datetime.fromgregorian(datetime=now)
    texts = {"date": j.strftime("%Y/%m/%d"), "time": j.strftime("%H:%M")}
    for key, _, kind in ITEMS:
        texts[key] = f"{prices[key]:,.2f}" if kind == "usd" else f"{int(prices[key]):,}"
    for key, (cx, cy, h) in LAYOUT.items():
        f = fit_font(h)
        b = d.textbbox((0, 0), texts[key], font=f)
        d.text((cx - (b[0] + b[2]) / 2, cy - (b[1] + b[3]) / 2), texts[key], font=f, fill=INK)
    arr = np.pad(np.array(img), ((4, 4), (0, 0), (0, 0)), mode="edge")   # ۱۹۱۲ → ۱۹۲۰ (نسبت ۹:۱۶)
    return Image.fromarray(arr)

def cmd_render(demo):
    now = dt.datetime.now(TZ)
    if demo: prices, as_of = DEMO, now
    else:
        prices, as_of = fetch_prices(); sanity(prices)
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("story_*.jpg"): old.unlink()
    name = f"story_{now:%Y%m%d_%H%M}.jpg"
    render(prices, as_of).save(OUT / name, "JPEG", quality=92)
    (OUT / "latest.txt").write_text(name)
    if not demo:
        STATE.parent.mkdir(exist_ok=True); STATE.write_text(json.dumps(prices, ensure_ascii=False))
    print("ساخته شد:", name)

MCP_URL = "https://connect.composio.dev/mcp"

class Composio:
    """اتصال به Composio Connect (همان اتصال چت) با کلید ck_ از طریق MCP."""
    def __init__(self, key):
        self.h = {"x-consumer-api-key": key, "Content-Type": "application/json",
                  "Accept": "application/json, text/event-stream"}
        self.sid, self.n, self.session = None, 0, None
        self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "hermes-story-bot", "version": "1.0"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _post(self, body):
        h = dict(self.h)
        if self.sid: h["Mcp-Session-Id"] = self.sid
        r = requests.post(MCP_URL, headers=h, json=body, timeout=180)
        if r.status_code >= 400: sys.exit(f"Composio → HTTP {r.status_code}: {r.text[:400]}")
        if r.headers.get("Mcp-Session-Id"): self.sid = r.headers["Mcp-Session-Id"]
        return r

    def _rpc(self, method, params):
        self.n += 1
        r = self._post({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        if "text/event-stream" in r.headers.get("Content-Type", ""):
            msgs = [json.loads(l[5:].strip()) for l in r.text.splitlines() if l.startswith("data:") and l[5:].strip()]
        else:
            msgs = [r.json()] if r.text.strip() else []
        msg = next((m for m in msgs if m.get("id") == self.n), msgs[-1] if msgs else {})
        if "error" in msg: sys.exit(f"Composio خطا: {msg['error']}")
        return msg.get("result", {})

    def tool(self, name, args):
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        text = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        if res.get("isError"): sys.exit(f"{name} خطا: {text[:500]}")
        try: return json.loads(text)
        except ValueError: sys.exit(f"پاسخ نامعتبر از {name}: {text[:300]}")

    def run(self, slug, arguments):
        if not self.session:
            out = self.tool("COMPOSIO_SEARCH_TOOLS", {"queries": [{"use_case": "publish an Instagram story",
                            "known_fields": "toolkit:instagram"}], "session": {"generate_id": True}})
            self.session = (out.get("data") or {}).get("session", {}).get("id")
            if not self.session: sys.exit(f"شناسه نشست دریافت نشد: {str(out)[:300]}")
        out = self.tool("COMPOSIO_MULTI_EXECUTE_TOOL", {"tools": [{"tool_slug": slug, "arguments": arguments}],
                        "session_id": self.session, "sync_response_to_workbench": False,
                        "thought": "Publish daily price story for the shop.", "current_step": "PUBLISH_STORY"})
        results = (out.get("data") or {}).get("results") or []
        if not results: sys.exit(f"{slug}: پاسخی نیامد: {str(out)[:400]}")
        resp = results[0].get("response") or {}
        if not resp.get("successful"): sys.exit(f"{slug} ناموفق: {str(resp.get('error') or resp)[:500]}")
        return resp.get("data") or {}

def find_id(d):
    if isinstance(d, dict):
        if d.get("id"): return d["id"]
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
    c = Composio(os.environ["COMPOSIO_API_KEY"])
    uid = os.environ.get("IG_USER_ID", "me")
    cid = find_id(c.run("INSTAGRAM_POST_IG_USER_MEDIA", {"ig_user_id": uid, "media_type": "STORIES", "image_url": url}))
    if not cid: sys.exit("شناسه کانتینر دریافت نشد.")
    mid = find_id(c.run("INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH", {"ig_user_id": uid, "creation_id": str(cid)}))
    print("استوری منتشر شد. media_id =", mid)

# ---- قفل ساعت و جلوگیری از انتشار تکراری ----
SLOTS = [("noon", (11, 55), (13, 45)), ("evening", (17, 55), (19, 45))]   # بازهٔ مجاز به وقت تهران
SLOT_STATE = ROOT / "state" / "last_slots.txt"

def _emit(go, slot=""):
    line = f"go={'true' if go else 'false'}\nslot={slot}\n"
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f: f.write(line)
    print(line.replace("\n", " | "))

def cmd_gate():
    now = dt.datetime.now(TZ)
    if os.environ.get("EVENT_NAME") != "schedule" and os.environ.get("AUTO") != "true":      # اجرای دستی همیشه مجاز است
        return _emit(True, "manual")
    mins = now.hour * 60 + now.minute
    for name, (h1, m1), (h2, m2) in SLOTS:
        if h1 * 60 + m1 <= mins < h2 * 60 + m2:
            slot = f"{now:%Y-%m-%d}-{name}"
            done = SLOT_STATE.read_text().split() if SLOT_STATE.exists() else []
            if slot in done:
                print("استوری این بازه قبلاً منتشر شده؛ رد شد."); return _emit(False)
            return _emit(True, slot)
    print(f"ساعت {now:%H:%M} تهران خارج از بازهٔ مجاز است؛ استوری منتشر نمی‌شود."); _emit(False)

def cmd_mark(slot):
    if not slot or slot == "manual": return
    SLOT_STATE.parent.mkdir(exist_ok=True)
    done = SLOT_STATE.read_text().split()[-20:] if SLOT_STATE.exists() else []
    SLOT_STATE.write_text("\n".join(done + [slot]) + "\n")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["render", "publish", "gate", "mark"]); ap.add_argument("--demo", action="store_true"); ap.add_argument("--slot", default="")
    a = ap.parse_args()
    {"render": lambda: cmd_render(a.demo), "publish": cmd_publish, "gate": cmd_gate, "mark": lambda: cmd_mark(a.slot)}[a.cmd]()
