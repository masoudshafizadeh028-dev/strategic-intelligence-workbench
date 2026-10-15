/**
 * balejs runtime — Node.js 18+; ESM; built-in fetch only.
 * Official Bot API calls are isolated in BotClient. User-account login is an
 * adapter seam because the user-session protocol must be supplied by a
 * documented, authorized transport; this package does not invent endpoints.
 */
export class BaleError extends Error {
  constructor(message, { code, status, retryable = false } = {}) {
    super(message); this.name = 'BaleError'; this.code = code; this.status = status; this.retryable = retryable;
  }
}
export class BaleAuthError extends BaleError {
  constructor(message = 'Authentication failed') { super(message, { code: 'AUTH' }); this.name = 'BaleAuthError'; }
}
export class BaleValidationError extends BaleError {
  constructor(message) { super(message, { code: 'VALIDATION' }); this.name = 'BaleValidationError'; }
}
export class BaleTransportError extends BaleError {
  constructor(message, status) { super(message, { code: 'TRANSPORT', status, retryable: true }); this.name = 'BaleTransportError'; }
}

const defaultLogger = {
  debug: (m, x) => { if (process.env.BALEJS_LOG_LEVEL === 'debug') console.debug('[balejs]', m, x ?? ''); },
  info: (m, x) => console.info('[balejs]', m, x ?? ''),
  warn: (m, x) => console.warn('[balejs]', m, x ?? ''),
  error: (m, x) => console.error('[balejs]', m, x ?? ''),
};
const wait = (ms, signal) => new Promise((resolve, reject) => {
  const timer = setTimeout(resolve, ms);
  if (signal) {
    if (signal.aborted) { clearTimeout(timer); reject(signal.reason ?? new Error('Aborted')); }
    signal.addEventListener('abort', () => { clearTimeout(timer); reject(signal.reason ?? new Error('Aborted')); }, { once: true });
  }
});
const validChatId = (id) => {
  const x = String(id ?? '').trim();
  if (!/^-?\d+$/.test(x) && !/^@[A-Za-z0-9_]{3,64}$/.test(x)) throw new BaleValidationError('chatId must be an integer-like id or @username');
  return x;
};
const required = (v, name) => {
  if (typeof v !== 'string' || !v.trim()) throw new BaleValidationError(`${name} must be non-empty`);
  return v;
};
const asJson = async (response) => {
  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { throw new BaleTransportError(`Invalid JSON response: ${text.slice(0, 200)}`, response.status); }
  if (!response.ok) throw new BaleTransportError(data?.description ?? `HTTP ${response.status}`, response.status);
  if (data && data.ok === false) throw new BaleError(data.description ?? 'Bale API request failed', { code: data.error_code, status: response.status, retryable: response.status >= 500 });
  return data?.result ?? data;
};

/** Shared HTTP utility with timeout and exponential retry. */
export class HttpTransport {
  constructor({ fetchImpl = globalThis.fetch, timeoutMs = 20000, maxRetries = 2, baseDelayMs = 350, logger = defaultLogger } = {}) {
    if (typeof fetchImpl !== 'function') throw new BaleError('Node 18+ or a fetch implementation is required');
    this.fetch = fetchImpl; this.timeoutMs = timeoutMs; this.maxRetries = maxRetries; this.baseDelayMs = baseDelayMs; this.logger = logger;
  }
  async request(url, { method = 'GET', headers = {}, body, signal } = {}) {
    let last;
    for (let attempt = 0; attempt <= this.maxRetries; attempt += 1) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(new Error('Request timeout')), this.timeoutMs);
      const abort = () => controller.abort(signal.reason ?? new Error('Aborted'));
      signal?.addEventListener('abort', abort, { once: true });
      try {
        const response = await this.fetch(url, { method, headers, body, signal: controller.signal });
        if (response.status >= 500 && attempt < this.maxRetries) throw new BaleTransportError(`HTTP ${response.status}`, response.status);
        return await asJson(response);
      } catch (err) {
        last = err;
        const retryable = err?.retryable || /timeout|ECONNRESET|ETIMEDOUT|fetch failed/i.test(String(err?.message ?? err));
        if (!retryable || attempt >= this.maxRetries) throw err;
        const delay = Math.min(8000, this.baseDelayMs * (2 ** attempt)) * (0.5 + Math.random() * 0.5);
        this.logger.warn(`retry ${attempt + 1}/${this.maxRetries} after ${Math.round(delay)}ms`, String(err));
        await wait(delay, signal);
      } finally {
        clearTimeout(timer); signal?.removeEventListener('abort', abort);
      }
    }
    throw last;
  }
}

/** Official Bot API client. API root is configurable; default follows the public Bale Bot API URL shape. */
export class BotClient {
  constructor({ token, baseUrl = 'https://tapi.bale.ai/bot', timeoutMs = 20000, maxRetries = 2, fetchImpl, logger = defaultLogger } = {}) {
    this.token = required(token, 'token'); this.baseUrl = baseUrl.replace(/\/$/, '');
    this.transport = new HttpTransport({ timeoutMs, maxRetries, fetchImpl, logger }); this.logger = logger;
    this.handlers = { message: [], command: new Map(), callback: [], checkout: [] }; this.offset = 0;
  }
  async call(method, payload = {}, { signal } = {}) {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(method)) throw new BaleValidationError('invalid method name');
    const url = `${this.baseUrl}${this.baseUrl.endsWith('/bot') ? '' : ''}${this.baseUrl.endsWith(this.token) ? '' : this.token}/${method}`;
    return this.transport.request(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload), signal });
  }
  onMessage(fn) { this.handlers.message.push(fn); return this; }
  onCommand(command, fn) { this.handlers.command.set(command.replace(/^\//, '').toLowerCase(), fn); return this; }
  onCallback(fn) { this.handlers.callback.push(fn); return this; }
  onPreCheckout(fn) { this.handlers.checkout.push(fn); return this; }
  async sendMessage(chatId, text, options = {}) {
    validChatId(chatId); required(text, 'text');
    return this.call('sendMessage', { chat_id: chatId, text, ...options });
  }
  async editMessage(chatId, messageId, text, options = {}) {
    validChatId(chatId); required(text, 'text');
    return this.call('editMessageText', { chat_id: chatId, message_id: messageId, text, ...options });
  }
  async deleteMessage(chatId, messageId) { validChatId(chatId); return this.call('deleteMessage', { chat_id: chatId, message_id: messageId }); }
  async forwardMessage(chatId, fromChatId, messageId) { validChatId(chatId); validChatId(fromChatId); return this.call('forwardMessage', { chat_id: chatId, from_chat_id: fromChatId, message_id: messageId }); }
  async copyMessage(chatId, fromChatId, messageId, options = {}) { validChatId(chatId); validChatId(fromChatId); return this.call('copyMessage', { chat_id: chatId, from_chat_id: fromChatId, message_id: messageId, ...options }); }
  async sendPhoto(chatId, photo, options = {}) { validChatId(chatId); return this.call('sendPhoto', { chat_id: chatId, photo, ...options }); }
  async sendDocument(chatId, document, options = {}) { validChatId(chatId); return this.call('sendDocument', { chat_id: chatId, document, ...options }); }
  async sendInvoice(options) {
    for (const f of ['chat_id', 'title', 'description', 'payload', 'provider_token', 'currency', 'prices']) if (options[f] == null) throw new BaleValidationError(`invoice field ${f} is required`);
    return this.call('sendInvoice', options);
  }
  async answerPreCheckoutQuery(id, ok, errorMessage) { return this.call('answerPreCheckoutQuery', { pre_checkout_query_id: id, ok, ...(errorMessage ? { error_message: errorMessage } : {}) }); }
  async answerCallbackQuery(id, options = {}) { return this.call('answerCallbackQuery', { callback_query_id: id, ...options }); }
  async setWebhook(url, options = {}) { required(url, 'url'); return this.call('setWebhook', { url, ...options }); }
  async deleteWebhook(options = {}) { return this.call('deleteWebhook', options); }
  async getUpdates(options = {}) {
    const raw = await this.call('getUpdates', { offset: this.offset, timeout: 25, allowed_updates: ['message', 'callback_query', 'pre_checkout_query'], ...options });
    const updates = Array.isArray(raw) ? raw : [];
    for (const u of updates) this.offset = Math.max(this.offset, Number(u.update_id ?? 0) + 1);
    return updates;
  }
  async handleUpdate(update) {
    const msg = update?.message ?? update?.edited_message;
    if (msg) {
      const text = msg.text ?? msg.caption ?? '';
      const command = text.match(/^\/(\w+)(?:@\w+)?(?:\s+([\s\S]*))?$/);
      if (command && this.handlers.command.has(command[1].toLowerCase())) {
        await this.handlers.command.get(command[1].toLowerCase())(msg, (command[2] ?? '').trim().split(/\s+/).filter(Boolean), this);
      }
      for (const fn of this.handlers.message) await fn(msg, this);
    }
    if (update?.callback_query) for (const fn of this.handlers.callback) await fn(update.callback_query, this);
    if (update?.pre_checkout_query) for (const fn of this.handlers.checkout) await fn(update.pre_checkout_query, this);
  }
  async polling({ signal, timeout = 25, backoffMs = 1200 } = {}) {
    while (!signal?.aborted) {
      try {
        const updates = await this.getUpdates({ timeout, ...(signal ? { signal } : {}) });
        for (const update of updates) await this.handleUpdate(update);
      } catch (err) {
        if (signal?.aborted) break;
        this.logger.error('polling error', err);
        await wait(backoffMs, signal);
      }
    }
  }
}

/**
 * User-session façade. Supply an adapter implementing login/session/API calls.
 * No undocumented user login endpoint is fabricated by this library.
 */
export class UserClient {
  constructor({ adapter, session, logger = defaultLogger } = {}) {
    if (!adapter || typeof adapter.request !== 'function') throw new BaleValidationError('UserClient requires a documented transport adapter with request(method, payload)');
    this.adapter = adapter; this.session = session; this.logger = logger; this.handlers = [];
  }
  static async loginWithPhone({ phone, adapter, promptCode, promptPassword, saveSession, logger } = {}) {
    required(String(phone ?? ''), 'phone');
    if (!adapter || typeof adapter.request !== 'function') throw new BaleValidationError('phone login needs an explicitly configured, documented user-session adapter');
    if (typeof adapter.loginWithPhone !== 'function') throw new BaleValidationError('adapter must implement loginWithPhone(phone, code, password)');
    const code = await promptCode();
    const password = promptPassword ? await promptPassword() : undefined;
    const session = await adapter.loginWithPhone(phone, code, password);
    if (!session || typeof session !== 'string') throw new BaleAuthError('adapter returned no reusable session');
    if (saveSession) await saveSession(session);
    return new UserClient({ adapter, session, logger });
  }
  onMessage(fn) { this.handlers.push(fn); return this; }
  async call(method, payload = {}) {
    if (!this.session) throw new BaleAuthError('No saved user session. Login first or pass a saved session.');
    return this.adapter.request(method, payload, { session: this.session });
  }
  async sendMessage(chatId, text, options = {}) { validChatId(chatId); required(text, 'text'); return this.call('sendMessage', { chatId, text, ...options }); }
  async editMessage(chatId, messageId, text) { return this.call('editMessage', { chatId, messageId, text }); }
  async deleteMessage(chatId, messageId) { return this.call('deleteMessage', { chatId, messageId }); }
  async forwardMessage(fromChatId, toChatId, messageId) { return this.call('forwardMessage', { fromChatId, toChatId, messageId }); }
  async copyMessage(fromChatId, toChatId, messageId) { return this.call('copyMessage', { fromChatId, toChatId, messageId }); }
  async sendPhoto(chatId, file, options = {}) { return this.call('sendPhoto', { chatId, file, ...options }); }
  async sendDocument(chatId, file, options = {}) { return this.call('sendDocument', { chatId, file, ...options }); }
  async joinChat(chatId) { return this.call('joinChat', { chatId }); }
  async leaveChat(chatId) { return this.call('leaveChat', { chatId }); }
  async getChat(chatId) { return this.call('getChat', { chatId }); }
  async getUpdates(options = {}) {
    const updates = await this.call('getUpdates', options);
    return Array.isArray(updates) ? updates : [];
  }
  async poll({ signal, intervalMs = 1200 } = {}) {
    while (!signal?.aborted) {
      const updates = await this.getUpdates({ signal });
      for (const update of updates) for (const fn of this.handlers) await fn(update, this);
      if (!updates.length) await wait(intervalMs, signal);
    }
  }
}

export class Bale {
  static bot(options) { return new BotClient(options); }
  static user(options) { return new UserClient(options); }
}

export function parseBaleLink(link) {
  const m = /^(?:https?:\/\/)?(?:ble\.ai|bale\.ai|web\.bale\.ai)\/(?:(c|b)\/)?([A-Za-z0-9_]+)\/(\d+)\/?$/.exec(String(link ?? '').trim());
  if (!m) throw new BaleValidationError(`Invalid Bale link: ${link}`);
  return { isBot: m[1] === 'b', target: m[2], messageId: Number(m[3]) };
}

export function chunkText(text, max = 4000) {
  if (!Number.isInteger(max) || max < 100) throw new BaleValidationError('max must be an integer >= 100');
  const rest = String(text ?? ''); const chunks = []; let pending = rest;
  while (pending.length > max) {
    const window = pending.slice(0, max); const cut = Math.max(window.lastIndexOf('\n'), window.lastIndexOf(' '));
    const n = cut > max * 0.55 ? cut : max; chunks.push(pending.slice(0, n).trim()); pending = pending.slice(n).trim();
  }
  if (pending) chunks.push(pending); return chunks;
}
