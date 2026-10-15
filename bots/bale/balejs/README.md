# balejs — کتابخانه‌ی Node.js/TypeScript برای بله

کتابخانه‌ی سبک ESM برای Node.js 18+، بدون وابستگی زمان اجرا. دو مسیر را از هم جدا می‌کند:

1. **Bot API**: `BotClient` با long polling، پیام/فرمان/callback، متن، عکس، سند، فاکتور و پاسخ pre-checkout.
2. **نشست حساب کاربری**: `UserClient` با نشست ذخیره‌شده و یک adapter قابل‌تزریق. پروتکل ورود کاربر باید از مستندات مجازِ فعلی پیاده‌سازی شود؛ کتابخانه endpoint ناشناخته جعل نمی‌کند.

## نصب و ساخت

```bash
npm install
npm run build
npm run selftest
```

یا در یک پروژه‌ی مصرف‌کننده:

```bash
npm install @pershiaa/balejs
```

این مخزن به‌صورت کد محلی آماده است؛ تا زمان انتشار در npm، از مسیر فایل استفاده کن:

```json
{"dependencies":{"@pershiaa/balejs":"file:../PerShiaA-Network/bots/bale/balejs"}}
```

## ربات اکو

```bash
npm run build
BALE_BOT_TOKEN='توکن-ربات' node examples/echo.mjs
```

توکن را در Git یا فایل عمومی ننویس؛ از secret/environment استفاده کن.

## نشست کاربر

```ts
import { UserClient } from '@pershiaa/balejs';
const user = new UserClient({ adapter: baleUserAdapter, session: process.env.BALE_USER_SESSION });
await user.sendMessage('123456', 'سلام');
```

برای ورود شماره‌ای، adapter باید `loginWithPhone(phone, code, password)` داشته باشد:

```ts
const client = await UserClient.loginWithPhone({
  phone: '+989121234567', adapter,
  promptCode: async () => process.stdin.read(),
  saveSession: async (session) => { /* ذخیره در Secret Manager */ },
});
```

## API پایه

```ts
const bot = new BotClient({ token: process.env.BALE_BOT_TOKEN });
bot.onCommand('start', (msg, args, api) => api.sendMessage(msg.chat.id, 'سلام!'));
bot.onMessage((msg, api) => {
  if (msg.text) return api.sendMessage(msg.chat.id, `گفتی: ${msg.text}`);
});
await bot.polling({ signal: abortController.signal });
```

متدهای پایه: `sendMessage`, `editMessage`, `deleteMessage`, `forwardMessage`, `copyMessage`,
`sendPhoto`, `sendDocument`, `sendInvoice`, `answerPreCheckoutQuery`, `answerCallbackQuery`,
`setWebhook`, `deleteWebhook`, `getUpdates`.

## خطا و تلاش دوباره

- `BaleValidationError`: ورودی نامعتبر؛ دوباره تلاش نکن.
- `BaleAuthError`: توکن/نشست نامعتبر؛ اعتبارنامه را بررسی کن.
- `BaleTransportError`: شبکه یا سرور؛ تلاش دوباره با backoff نمایی.
- `BotClient` به‌صورت پیش‌فرض حداکثر دو بار تلاش می‌کند؛ `maxRetries: 0` غیرفعال می‌کند.

## قراردادهای قابل پیکربندی

Bot API به‌صورت پیش‌فرض از ساختار URL رایج `https://tapi.bale.ai/bot<TOKEN>/<method>` استفاده می‌کند؛
`baseUrl` را می‌توان با proxy یا استقرار دیگر عوض کرد. روش‌های پرداخت ممکن است نیازمند فعال‌سازی ارائه‌دهنده باشند.

پروتکل نشست کاربر، WebSocket، گروه‌ها و کیف پول در سمت adapter قرار دارد و باید مطابق مستندات رسمی/مجاز همان سرویس پیاده‌سازی شود. این کتابخانه ادعا نمی‌کند endpoint یا قابلیت‌های خصوصی/مستندنشده در همه‌ی حساب‌ها در دسترس است.

## خودآزمایی

```bash
npm run selftest
```

آزمون‌ها با fetch جعلی اجرا می‌شوند و به شبکه یا توکن واقعی نیاز ندارند.
