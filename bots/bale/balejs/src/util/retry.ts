import { BaleError, BaleTransportError } from "../errors.ts";
import type { RetryPolicy } from "../types.ts";

export const DEFAULT_RETRY: RetryPolicy = { maxRetries: 3, baseDelayMs: 400, maxDelayMs: 8000 };

/** تأخیر نمایی با jitter، محدود به maxDelayMs. */
export function backoffDelay(attempt: number, policy: RetryPolicy, random: () => number = Math.random): number {
  const base = Math.min(policy.maxDelayMs, policy.baseDelayMs * Math.pow(2, Math.max(0, attempt)));
  return Math.round(base * (0.5 + random() * 0.5));
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function isRetryable(error: unknown): boolean {
  if (error instanceof BaleTransportError) return true;
  if (error instanceof BaleError) return error.retryable;
  if (error instanceof Error) return /timeout|ECONNRESET|ETIMEDOUT|EAI_AGAIN/i.test(error.message);
  return false;
}

/** اجرای یک عملیات با سیاست تلاش دوباره. */
export async function withRetry<T>(
  operation: (attempt: number) => Promise<T>,
  policy: Partial<RetryPolicy> = {},
  onRetry?: (attempt: number, error: unknown, delayMs: number) => void,
): Promise<T> {
  const effective: RetryPolicy = { ...DEFAULT_RETRY, ...policy };
  let lastError: unknown;
  for (let attempt = 0; attempt <= effective.maxRetries; attempt += 1) {
    try {
      return await operation(attempt);
    } catch (error) {
      lastError = error;
      if (attempt === effective.maxRetries || !isRetryable(error)) break;
      const delay = backoffDelay(attempt, effective);
      if (onRetry) onRetry(attempt, error, delay);
      await sleep(delay);
    }
  }
  throw lastError;
}
