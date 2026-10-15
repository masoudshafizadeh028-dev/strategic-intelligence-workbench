import type { BaleErrorShape } from "./types.ts";

/** خطای پایه‌ی کتابخانه. */
export class BaleError extends Error {
  code?: string | number;
  status?: number;
  retryable: boolean;

  constructor(message: string, options: { code?: string | number; status?: number; retryable?: boolean } = {}) {
    super(message);
    this.name = "BaleError";
    this.code = options.code;
    this.status = options.status;
    this.retryable = options.retryable ?? false;
  }

  static from(shape: BaleErrorShape): BaleError {
    return new BaleError(shape.message, { code: shape.code, status: shape.status, retryable: shape.retryable });
  }

  toJSON(): BaleErrorShape {
    return { code: this.code, message: this.message, status: this.status, retryable: this.retryable };
  }
}

/** خطای احراز هویت / نشست نامعتبر. */
export class BaleAuthError extends BaleError {
  constructor(message: string) {
    super(message, { code: "AUTH", retryable: false });
    this.name = "BaleAuthError";
  }
}

/** خطای اعتبارسنجی ورودی پیش از ارسال درخواست. */
export class BaleValidationError extends BaleError {
  constructor(message: string) {
    super(message, { code: "VALIDATION", retryable: false });
    this.name = "BaleValidationError";
  }
}

/** خطای شبکه/سرویس که ارزش تلاش دوباره دارد. */
export class BaleTransportError extends BaleError {
  constructor(message: string, status?: number) {
    super(message, { code: "TRANSPORT", status, retryable: true });
    this.name = "BaleTransportError";
  }
}
