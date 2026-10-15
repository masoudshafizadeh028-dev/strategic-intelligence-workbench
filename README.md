# PerShiaA-Network

شبکه یکپارچه‌ی هشت پروژه‌ی تحلیلی، وب، OSINT، خودکارسازی پیام‌رسان و تولید محتوا.

> همه‌ی اجزا به‌صورت پیش‌فرض **آفلاین-اول** طراحی شده‌اند: هر سرویس یک حالت stdlib-only دارد که بدون هیچ وابستگی بیرونی اجرا می‌شود، و اگر وابستگی‌های سنگین‌تر (FastAPI، Telethon، Selenium، Tesseract) نصب باشند، خودکار به حالت کامل ارتقا پیدا می‌کند.

---

## فهرست سرویس‌ها

| # | پوشه | پروژه اصلی | زبان | نقش | پورت |
|---|------|-----------|------|-----|------|
| 1 | `doctrine/` | persiaa-doctrine | Python (stdlib) | موتور تحلیلی فارسی + OCR + پرونده‌ی دکترین | 8001 |
| 2 | `web/` | pershiaa | HTML/CSS/JS | سایت اندیشکده‌ی تمدن نوین اسلامی | 8080 |
| 3 | `osint/` | PerShiaA-osint | Python + FastAPI | داشبورد OSINT چندعامله + گراف شبکه | 8002 |
| 4 | `bots/telegram/` | TelegramDownloader | Python + Actions | دانلود خودکار فایل از پست تلگرام | — |
| 5 | `bots/eitaa/` | AutoEitaa | Python | چارچوب ربات ایتا | — |
| 6 | `bots/bale/baleself/` | baleself | Python + Selenium | سلف‌بات بله | — |
| 7 | `bots/bale/balejs/` | balejs | TypeScript/Node | کتابخانه‌ی بله | — |
| 8 | `ai/` | ai_melli | Python + Actions | تولید تصویر/متن روی GitHub Actions | — |
| ★ | `hub/` | — | Python | هماهنگ‌ساز کلان (Master Orchestrator) | 8000 |

---

## اجرای سریع

### ۱) بدون هیچ نصب — حالت آفلاین

```bash
# خودآزمایی کل شبکه
python3 scripts/selftest_all.py

# موتور دکترین (CLI)
python3 doctrine/doctrine_engine.py --request "تحلیل وضعیت رسانه‌ای منطقه"

# API دکترین (stdlib fallback)
python3 doctrine/api.py --port 8001

# OSINT API
python3 osint/app.py --port 8002

# هماهنگ‌ساز کلان
python3 hub/core.py --request "یک تحلیل OSINT بگیر و در دکترین ثبت کن"

# داشبورد وب
python3 -m http.server 8080 --directory web
```

### ۲) با Docker

```bash
docker compose up -d
# doctrine → http://localhost:8001
# osint    → http://localhost:8002
# hub      → http://localhost:8000
# web      → http://localhost:8080
```

### ۳) با وابستگی کامل

```bash
pip install -r requirements.txt          # FastAPI, pdfminer, pillow, ...
cd bots/bale/balejs && npm install && npm run build
```

---

## اصول طراحی

1. **آفلاین-اول**: هر سرویس با کتابخانه‌ی استاندارد پایتون کار می‌کند. وابستگی‌ها اختیاری‌اند.
2. **خودآزمایی**: هر پوشه یک `--selftest` دارد. `scripts/selftest_all.py` همه را یک‌جا اجرا می‌کند.
3. **برچسب اطمینان**: هر ادعا در خروجی تحلیلی یکی از برچسب‌های `[F]` (قطعی)، `[H]` (احتمال بالا)، `[M]` (احتمال متوسط)، `[I]` (استنباط)، `[U]` (نامعلوم) را می‌گیرد.
4. **ثبت منبع**: هر گزاره به یک `doc_id` در دفتر منابع (`source_ledger`) ارجاع می‌دهد.
5. **خرابی جزئی مجاز است**: در هماهنگ‌ساز، شکست یک زیرسیستم بقیه را متوقف نمی‌کند.
6. **RTL و فارسی-محور**: همه‌ی رابط‌های کاربری راست‌به‌چپ و با فونت وزیرمتن.

---

## ساختار

```
PerShiaA-Network/
├── README.md
├── docker-compose.yml
├── requirements.txt
├── requirements-optional.txt
├── scripts/
│   └── selftest_all.py
├── .github/workflows/
│   ├── doctrine-update.yml
│   ├── osint-scan.yml
│   ├── ai-generate.yml
│   └── telegram-download.yml
├── hub/
│   ├── core.py            # Master Orchestrator
│   ├── dashboard.html     # داشبورد مرکزی وضعیت
│   ├── config.yaml
│   └── Dockerfile
├── doctrine/
│   ├── doctrine_engine.py # موتور تحلیلی
│   ├── ocr_pipeline.py    # OCR فارسی
│   ├── api.py             # API دوگانه
│   ├── doctrine_app.html  # داشبورد ۱۷ تبی
│   └── Dockerfile
├── web/
│   ├── index.html         # سایت اندیشکده
│   ├── assets/app.js
│   ├── robots.txt
│   ├── sitemap.xml
│   └── manifest.webmanifest
├── osint/
│   ├── app.py             # FastAPI + fallback
│   ├── agents.py          # PM / Research / Synthesis / Review
│   ├── github_history.py  # کشف ایمیل از تاریخچه کامیت
│   ├── static/index.html  # UI تیره + Cytoscape
│   └── Dockerfile
├── bots/
│   ├── telegram/          # دانلودر
│   ├── eitaa/             # چارچوب ربات ایتا
│   └── bale/
│       ├── baleself/      # سلف‌بات Selenium
│       └── balejs/        # کتابخانه TypeScript
├── ai/
│   ├── generate.py        # تولید تصویر/متن
│   └── gallery.py         # ساخت گالری HTML
└── docs/
    ├── architecture.md
    ├── prompts.md         # ۱۲ پرامپت یکپارچه
    └── api-spec.md
```

## مجوز

MIT — استفاده، تغییر و انتشار آزاد.
