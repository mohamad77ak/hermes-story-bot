# استوری خودکار قیمت – هرمس گلد

هر روز حدود ساعت ۱۲ و ۱۸ (به وقت تهران) قیمت‌ها را می‌گیرد، تصویر استوری می‌سازد و روی اینستاگرام منتشر می‌کند.

## راه‌اندازی (یک‌بار، حدود ۲۰ دقیقه)

1. در github.com حساب بسازید و یک ریپوی جدید **Public** با نام دلخواه (مثلاً `hermes-story-bot`) بسازید.
   (Public لازم است چون اینستاگرام باید تصویر را از یک لینک عمومی بردارد. هیچ کلید و رمزی داخل کد نیست.)
2. همهٔ فایل‌های این پوشه را آپلود کنید. نکته: پوشهٔ `.github` مخفی است. اگر آپلود نشد، در گیت‌هاب
   `Add file ← Create new file` را بزنید، نام را `.github/workflows/story.yml` بنویسید و محتوای فایل را کپی کنید.
3. در ریپو: `Settings ← Secrets and variables ← Actions ← New repository secret` و این‌ها را اضافه کنید:
   - `COMPOSIO_API_KEY` : از platform.composio.dev ← Settings ← API Keys
   - `COMPOSIO_CONNECTED_ACCOUNT_ID` : از داشبورد کامپوزیو، بخش Connected Accounts، شناسهٔ اتصال اینستاگرام (شبیه `ca_...`)
   - `PRICE_API_URL` : آدرس منبع قیمت
   - `PRICE_API_HEADERS` (اختیاری) : اگر منبع هدر/توکن می‌خواهد، به شکل JSON مثل `{"Authorization":"Bearer ..."}`
4. `Settings ← Actions ← General ← Workflow permissions` را روی **Read and write permissions** بگذارید.
5. در `bot.py` بخش `ITEMS` را با ساختار JSON منبع قیمتتان تنظیم کنید. اگر منبع ریال می‌دهد،
   در `Settings ← Variables` متغیر `PRICE_DIVISOR` را `10` بگذارید.

## تست
- تب **Actions** ← Hermes Story ← **Run workflow** با `dry_run = true`: فقط تصویر ساخته می‌شود (از بخش Artifacts ببینید).
- اگر خوب بود دوباره اجرا کنید با `dry_run = false` تا یک استوری واقعی منتشر شود.
- بعد از آن خودکار است.

## ایمنی
- اگر قیمتی صفر باشد یا نسبت به دفعهٔ قبل بیش از ۸٪ تغییر کند، استوری منتشر **نمی‌شود** و اجرا خطا می‌دهد.
- برای توقف موقت: تب Actions ← Hermes Story ← ⋯ ← Disable workflow.
