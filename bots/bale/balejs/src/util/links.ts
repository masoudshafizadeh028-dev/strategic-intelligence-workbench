/** تحلیل و ساخت لینک‌های بله. */

const LINK_RE = /^(?:https?:\/\/)?(?:ble\.ai|bale\.ai|web\.bale\.ai)\/(?:(?<type>c|b)\/)?(?<target>[A-Za-z0-9_]+)\/(?<msg>\d+)\/?$/;

export interface ParsedLink {
  target: string;
  messageId: number;
  isBot: boolean;
}

export function parseBaleLink(link: string): ParsedLink {
  const match = LINK_RE.exec(String(link ?? "").trim());
  if (!match || !match.groups) {
    throw new Error(`لینک بله نامعتبر: ${link}`);
  }
  return {
    target: match.groups.target ?? "",
    messageId: Number(match.groups.msg),
    isBot: match.groups.type === "b",
  };
}

export function buildMessageLink(target: string, messageId: number): string {
  return `https://ble.ai/${target}/${messageId}`;
}

/** تشخیص نوع رسانه از پسوند فایل. */
export function mediaKind(fileName: string): "photo" | "video" | "audio" | "document" {
  const ext = String(fileName ?? "").toLowerCase().split(".").pop() ?? "";
  if (["jpg", "jpeg", "png", "webp", "gif"].includes(ext)) return "photo";
  if (["mp4", "mkv", "mov", "webm"].includes(ext)) return "video";
  if (["mp3", "ogg", "m4a", "wav", "opus"].includes(ext)) return "audio";
  return "document";
}
