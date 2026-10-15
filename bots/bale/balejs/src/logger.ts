import type { Logger } from "./types.ts";

const LEVELS: Record<string, number> = { debug: 10, info: 20, warn: 30, error: 40 };

/** لاگر ساده با سطح قابل تنظیم از متغیر محیطی BALEJS_LOG_LEVEL. */
export function createLogger(level?: string): Logger {
  const current = LEVELS[(level || process.env.BALEJS_LOG_LEVEL || "warn").toLowerCase()] ?? 30;
  const emit = (name: string, fn: (...a: unknown[]) => void) => (msg: string, meta?: unknown): void => {
    if ((LEVELS[name] ?? 99) < current) return;
    fn(`[balejs:${name}] ${msg}`, meta ?? "");
  };
  return {
    debug: emit("debug", console.debug),
    info: emit("info", console.info),
    warn: emit("warn", console.warn),
    error: emit("error", console.error),
  };
}

/** لاگر خاموش برای آزمون و کتابخانه‌های مصرف‌کننده. */
export const silentLogger: Logger = {
  debug: () => undefined,
  info: () => undefined,
  warn: () => undefined,
  error: () => undefined,
};
