import { BaleValidationError } from "../errors.ts";

export function assertNonEmpty(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new BaleValidationError(`فیلد «${field}» باید متن غیرخالی باشد.`);
  }
  return value;
}

export function assertChatId(chatId: unknown): string {
  if (typeof chatId === "string" && /^-?\d+$/.test(chatId.trim())) return chatId.trim();
  if (typeof chatId === "string" && /^@[A-Za-z0-9_]{3,64}$/.test(chatId.trim())) return chatId.trim();
  throw new BaleValidationError("شناسه‌ی چت باید عدد یا @نام‌کاربری باشد.");
}

export function assertPhone(phone: unknown): string {
  const value = String(phone ?? "").replace(/[\s\-()]/g, "");
  if (/^\+?98\d{10}$/.test(value)) return value.startsWith("+") ? value : `+${value}`;
  if (/^0\d{10}$/.test(value)) return `+98${value.slice(1)}`;
  if (/^\+?\d{8,15}$/.test(value)) return value.startsWith("+") ? value : `+${value}`;
  throw new BaleValidationError("شماره‌ی تلفن نامعتبر است؛ نمونه‌ی معتبر: 09123456789 یا +989123456789.");
}

export function assertPositiveInt(value: unknown, field: string): number {
  const n = Number(value);
  if (!Number.isInteger(n) || n <= 0) {
    throw new BaleValidationError(`فیلد «${field}» باید عدد صحیح مثبت باشد.`);
  }
  return n;
}

/** اعتبارسنجی قرارداد نشست ذخیره‌شده. */
export function assertSession(session: unknown): string {
  const value = assertNonEmpty(session, "session");
  if (!value.includes(":")) {
    throw new BaleValidationError("نشست باید قالب «userId:token» داشته باشد.");
  }
  return value;
}

export function parseSession(session: string): { userId: string; token: string } {
  const value = assertSession(session);
  const index = value.indexOf(":");
  return { userId: value.slice(0, index), token: value.slice(index + 1) };
}
