# شروع سریع PerShiaA-Network

## ۱) خودآزمایی بدون هیچ نصب

```bash
python3 scripts/selftest_all.py
```

انتظار: `16/16 آزمون موفق`. هیچ اینترنت، کلید یا سرویس بیرونی لازم نیست.

## ۲) موتور تحلیلی دکترین (CLI)

```bash
python3 doctrine/doctrine_engine.py --selftest
python3 doctrine/doctrine_engine.py --request "تحلیل راهبرد رسانه‌ای و تمدن نوین اسلامی" \
  --corpus data/corpus --out data/dossiers/dossier.json
```

## ۳) داشبوردها و API‌ها

```bash
python3 doctrine/api.py --port 8001      # داشبورد + API دکترین
python3 osint/app.py    --port 8002      # داشبورد + API OSINT
python3 hub/core.py     --serve --port 8000   # هاب مرکزی
python3 -m http.server 8080 --directory web   # سایت اندیشکده
```

مرورگر: `http://localhost:8000` (هاب) · `http://localhost:8001` (دکترین) ·
`http://localhost:8002` (OSINT) · `http://localhost:8080` (سایت)

## ۴) با Docker

```bash
docker compose up -d
```

## ۵) کتابخانه‌ی TypeScript بله

```bash
cd bots/bale/balejs
npm run build && npm run selftest
```

## ۶) تولید محتوا (آفلاین)

```bash
python3 ai/generate.py --mode text  --prompt "درباره تمدن نوین اسلامی" --out ai/output
python3 ai/generate.py --mode image --prompt "کتابخانه‌ای در غروب" --smart --out ai/output
python3 ai/gallery.py --dir ai/output
```

## ۷) دانلودر تلگرام

```bash
python3 bots/telegram/downloader.py --selftest
# اجرای واقعی نیازمند TG_API_ID، TG_API_HASH و TG_SESSION است
```

---

## نکات مهم

- همه‌ی سرویس‌ها **آفلاین-اول** اند؛ وابستگی سنگین اختیاری است.
- سرورها به‌صورت پیش‌فرض فقط روی `127.0.0.1` گوش می‌دهند.
- هیچ کلید/نشستی در بسته نیست؛ از GitHub Secrets یا متغیر محیطی استفاده کن.
- ماژول‌های OSINT خارج از محدوده (اسکن پورت، breach، dark web) عمداً پیاده نشده‌اند.
- مستندات: `docs/architecture.md`, `docs/api-spec.md`, `docs/prompts.md`
