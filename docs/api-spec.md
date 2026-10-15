# مشخصات API

همه‌ی سرویس‌ها JSON برمی‌گردانند و هدر `Access-Control-Allow-Origin: *` می‌دهند.
خطاها همیشه به شکل `{"error": "...", "detail": "..."}` هستند.

---

## دکترین — پورت 8001

### `GET /api/health`

```json
{"ok": true, "service": "doctrine", "version": "1.0.0", "offline": true}
```

### `GET /api/schema`

طرحواره‌ی کامل پرونده، فهرست کلیدها، ۵۲ ارزیابی و راهنمای CLI.

### `GET /api/evaluations`

فهرست کنترل‌ها: `[{id, layer, layer_title, title}, ...]`

### `GET /api/search?q=عبارت`

```json
{"query": "...", "results": [{"doc_id": "S-...", "title": "...", "score": 6.4,
  "matched_terms": ["..."], "snippet": "..."}]}
```

### `POST /api/analyze`

درخواست:

```json
{"request": "متن درخواست تحلیلی", "requester": "cli",
 "documents": [{"title": "سند من", "text": "محتوای محلی"}]}
```

پاسخ: پرونده‌ی کامل. کلیدهای اصلی: `dossier_id`, `request`, `corpus`, `analysis`,
`scenarios`, `content_ready`, `source_ledger`, `confidence_score`, `confidence_matrix`,
`evaluations`, `evaluation_summary`, `pii_scan`, `audit_trail`, `integrity`.

محدودیت‌ها: حجم بدنه ≤ ۲ MB، طول درخواست ≤ ۱۰۰٬۰۰۰ نویسه، حداکثر ۳۰ سند درون‌خطی.
`documents` فقط متن محلی است؛ سرویس هیچ فایل یا URL بیرونی را خودکار نمی‌خواند.

کدهای خطا: `400 request_required` · `400 invalid_json` · `413 payload_too_large` · `413 request_too_long`.

---

## OSINT — پورت 8002

### `GET /api/health`

```json
{"ok": true, "service": "osint", "version": "1.0.0", "mode": "stdlib"}
```

### `GET /api/modules`

```json
{"allowed": ["dns", "github"],
 "not_implemented": ["social scraping", "dark web", "breach lookup", "port scanning"]}
```

### `POST /api/scan`  (نام دیگر: `POST /api/analyze`)

درخواست:

```json
{"target": "example.com", "modules": ["dns"]}
```

پاسخ:

```json
{"engine": {"name": "PerShiaA OSINT", "version": "1.0.0"},
 "target": "example.com",
 "modules": {"dns": {"status": "ok", "records": [{"type": "A", "value": "93.184.216.34"}]}},
 "graph": {"nodes": [{"data": {"id": "domain:example.com", "kind": "domain"}}],
           "edges": [{"data": {"source": "domain:example.com", "target": "ip:..."}}]},
 "synthesis": {"summary": {"nodes": 2, "edges": 1}},
 "review": {"approved": true, "issues": [], "confidence": "M"},
 "scope": {"authorized_public_sources_only": true, "port_scanning": false,
           "breach_data": false, "dark_web": false}}
```

خطاها: `400 target_required` · `400 modules_must_be_array` ·
`{"error": {"code": "unsupported_modules", "modules": [...], "allowed": [...]}}`.

`dns` آفلاین کار می‌کند (resolver سیستم). `github` به شبکه نیاز دارد و فقط داده‌ی عمومی می‌خواند.

---

## هاب — پورت 8000

### `GET /api/health`

```json
{"ok": true, "service": "hub", "version": "1.0.0"}
```

### `GET /api/config`

پیکربندی مؤثر (سرویس‌ها، نیت‌ها، پیش‌فرض‌ها، مسیرها).

### `POST /api/run`

درخواست: `{"request": "یک تحلیل OSINT بگیر و در دکترین ثبت کن"}`

پاسخ:

```json
{"run_id": "R-...", "request": "...",
 "plan": {"intents": ["osint", "doctrine"],
          "steps": [{"order": 1, "stage": "osint"}, {"order": 2, "stage": "doctrine"}]},
 "stages": [{"order": 1, "stage": "osint", "status": "ok", "detail": "...", "duration_ms": 12}],
 "summary": {"total": 2, "ok": 2, "error": 0, "skipped": 0, "status": "ok"},
 "dossier_id": "D-...", "confidence_score": 88.0, "content_frames": 5}
```

`status` می‌تواند `ok`, `partial` یا `failed` باشد. `partial` یعنی بعضی گام‌ها خطا داده‌اند
ولی خروجی معتبر دیگری موجود است.

---

## راه‌اندازی سریع

```bash
python3 doctrine/api.py --port 8001 &
python3 osint/app.py --port 8002 &
python3 hub/core.py --serve --port 8000

curl -s localhost:8000/api/health
curl -s -X POST localhost:8000/api/run -H 'Content-Type: application/json' \
  -d '{"request":"تحلیل راهبرد رسانه‌ای و تمدن نوین اسلامی"}'
```
