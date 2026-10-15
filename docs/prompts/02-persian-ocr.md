# 02 — OCR فارسی PDF

ابتدا وجود لایه‌ی متنی PDF را بررسی کن. متن دیجیتال را صفحه‌به‌صفحه استخراج کن؛ برای PDF اسکن‌شده فقط اگر Tesseract فارسی و Poppler واقعاً در دسترس‌اند OCR اجرا کن. اصل و نسخه‌ی نرمال‌شده را به هم پیوند بده.

خروجی: `document_id`, `checksum`, `method`, `language`, `pages:[{page,text,confidence}]`, `warnings`, `searchable_text`. متن مبهم را حدس نزن؛ confidence پایین را صریح علامت بزن.
