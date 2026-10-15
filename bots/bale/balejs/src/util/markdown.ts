/** تبدیل مارک‌داون سبک به متن ساده/HTML برای ارسال در بله. */

export function escapeHtml(text: string): string {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function toPlainText(markdown: string): string {
  return String(markdown ?? "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/(^|\W)\*(?!\s)(.+?)\*(?=\W|$)/g, "$1$2")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)")
    .replace(/^\s*[-*+]\s+/gm, "• ")
    .trim();
}

export function toHtml(markdown: string): string {
  const blocks = String(markdown ?? "").split(/\n{2,}/);
  return blocks
    .map((block) => {
      const escaped = escapeHtml(block)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
        .replace(/(^|\W)\*(?!\s)(.+?)\*(?=\W|$)/g, "$1<i>$2</i>");
      const heading = /^#{1,6}\s+/.test(block);
      return heading ? `<b>${escaped.replace(/^#{1,6}\s+/, "")}</b>` : escaped;
    })
    .join("\n\n");
}

/** بریدن متن با احترام به مرز واژه و محدودیت طول. */
export function truncate(text: string, max: number): string {
  const value = String(text ?? "");
  if (value.length <= max) return value;
  const cut = value.slice(0, max - 1);
  const boundary = cut.lastIndexOf(" ");
  return `${boundary > max * 0.6 ? cut.slice(0, boundary) : cut}…`;
}

/** تقسیم متن بلند به قطعات، برای پیام‌های طولانی. */
export function chunkText(text: string, max = 4000): string[] {
  const value = String(text ?? "");
  if (value.length <= max) return value ? [value] : [];
  const chunks: string[] = [];
  let rest = value;
  while (rest.length > max) {
    const window = rest.slice(0, max);
    const boundary = Math.max(window.lastIndexOf("\n"), window.lastIndexOf(" "));
    const cut = boundary > max * 0.5 ? boundary : max;
    chunks.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trim();
  }
  if (rest) chunks.push(rest);
  return chunks;
}
