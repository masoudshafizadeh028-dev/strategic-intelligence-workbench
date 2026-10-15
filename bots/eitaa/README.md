# AutoEitaa — افزونه‌ی ربات ایتا

چارچوب قابل‌گسترش پایتون برای ثبت handlerها، پردازش پیام‌ها و ساخت adapter.
چون قرارداد API می‌تواند تغییر کند و هر سرویس/نسخه جزئیات متفاوتی داشته باشد،
هسته‌ی پروژه API خاصی را حدس نمی‌زند: `PollingAdapter` یک adapter ساده‌ی HTTP
قابل تنظیم است و برای اتصال به API رسمیِ در دسترس حساب خودت، فقط `base_url` و
فرمت پیام را در `bot/adapters/http_polling.py` تنظیم کن.

## اجرا

```bash
python3 main.py --selftest
python3 main.py --demo
# با adapter HTTP (پس از پیکربندی):
EITAA_BASE_URL=https://your-approved-api.example EITAA_TOKEN=... python3 main.py
```

## افزودن منطق

فایل `bot/handlers/custom.py` را باز کن و تابعی با `@on_message(...)` ثبت کن.
handlerها پیام ورودی استاندارد می‌گیرند: `{"chat_id": ..., "text": ..., "raw": ...}`.
هیچ رمز یا توکنی را داخل کد کامیت نکن؛ از متغیر محیطی استفاده کن.
