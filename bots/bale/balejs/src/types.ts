/**
 * قراردادهای نوعی کتابخانه balejs.
 * همه‌ی تایپ‌ها اینجا متمرکزند تا لایه‌ی اجرا سبک بماند.
 */

export type ChatKind = "private" | "group" | "channel";

export interface BaleConfig {
  /** توکن ربات رسمی بله (اگر از BotClient استفاده می‌کنی). */
  token?: string;
  /** نشست کاربر که با loginWithPhone ساخته شده است. */
  session?: string;
  /** آدرس پایه‌ی API ربات. */
  baseUrl?: string;
  /** آدرس WebSocket برای نشست کاربر. */
  wsUrl?: string;
  /** آدرس fallback مبتنی بر HTTP. */
  rpcUrl?: string;
  requestTimeoutMs?: number;
  maxRetries?: number;
  retryBaseDelayMs?: number;
  fetchImpl?: FetchLike;
  logger?: Logger;
}

export interface Logger {
  debug: (msg: string, meta?: unknown) => void;
  info: (msg: string, meta?: unknown) => void;
  warn: (msg: string, meta?: unknown) => void;
  error: (msg: string, meta?: unknown) => void;
}

export interface HttpResponseLike {
  ok: boolean;
  status: number;
  text: () => Promise<string>;
  json: () => Promise<unknown>;
}

export type FetchLike = (url: string, init?: Record<string, unknown>) => Promise<HttpResponseLike>;

export interface Chat {
  id: string;
  kind: ChatKind;
  title?: string;
  username?: string;
}

export interface User {
  id: string;
  name?: string;
  username?: string;
  phone?: string;
  isBot?: boolean;
}

export interface MessageEntity {
  type: "mention" | "bot_command" | "url" | "bold" | "italic" | "code" | "pre" | "link";
  offset: number;
  length: number;
  url?: string;
}

export interface Message {
  id: string;
  chat: Chat;
  sender?: User;
  text?: string;
  caption?: string;
  date: number;
  replyToId?: string;
  entities?: MessageEntity[];
  raw?: unknown;
}

export interface SendMessageOptions {
  chatId: string;
  text: string;
  replyToId?: string;
  parseMode?: "none" | "markdown" | "html";
  disablePreview?: boolean;
}

export interface EditMessageOptions {
  chatId: string;
  messageId: string;
  text: string;
  parseMode?: "none" | "markdown" | "html";
}

export interface DeleteMessageOptions {
  chatId: string;
  messageId: string;
}

export interface ForwardOptions {
  fromChatId: string;
  toChatId: string;
  messageId: string;
}

export interface CopyOptions {
  fromChatId: string;
  toChatId: string;
  messageId: string;
  caption?: string;
}

export interface MediaOptions {
  chatId: string;
  filePath?: string;
  fileUrl?: string;
  caption?: string;
  fileName?: string;
  replyToId?: string;
}

export interface KeyboardButton {
  text: string;
  callbackData?: string;
  url?: string;
}

export interface InlineKeyboard {
  rows: KeyboardButton[][];
}

export interface InvoiceOptions {
  chatId: string;
  title: string;
  description: string;
  payload: string;
  providerToken: string;
  currency: string;
  prices: Array<{ label: string; amount: number }>;
  photoUrl?: string;
}

export interface PreCheckoutQuery {
  id: string;
  fromId: string;
  payload: string;
  totalAmount: number;
  currency: string;
}

export interface WalletBalance {
  available: number;
  currency: string;
  gifts?: Array<{ id: string; name: string; value: number }>;
}

export interface PollOptions {
  timeout?: number;
  limit?: number;
  allowedUpdates?: string[];
  signal?: AbortSignal;
}

export interface Update {
  updateId: string;
  type: "message" | "callback_query" | "pre_checkout_query" | "unknown";
  message?: Message;
  callbackQuery?: { id: string; data: string; fromId: string; messageId?: string; chatId?: string };
  preCheckoutQuery?: PreCheckoutQuery;
  raw?: unknown;
}

export type MessageHandler = (message: Message, client: unknown) => Promise<void> | void;
export type CommandHandler = (message: Message, args: string[], client: unknown) => Promise<void> | void;
export type CallbackHandler = (query: Update["callbackQuery"], client: unknown) => Promise<void> | void;

export interface GroupMember {
  user: User;
  role: "member" | "admin" | "owner";
}

export interface ReportOptions {
  chatId: string;
  messageId?: string;
  reason: string;
  note?: string;
}

export interface SessionInfo {
  userId: string;
  name?: string;
  phone?: string;
  expiresAt?: number;
}

export interface RetryPolicy {
  maxRetries: number;
  baseDelayMs: number;
  maxDelayMs: number;
}

export interface BaleErrorShape {
  code?: string | number;
  message: string;
  status?: number;
  retryable?: boolean;
}
