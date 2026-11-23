const LOCALE = "es-ES";

export function formatMoney(cents: number, currency = "EUR"): string {
  return new Intl.NumberFormat(LOCALE, { style: "currency", currency }).format(cents / 100);
}

export function formatDateTime(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone,
  }).format(new Date(iso));
}

export function formatDay(isoDate: string): string {
  // isoDate = "YYYY-MM-DD" (fecha local, sin hora)
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Intl.DateTimeFormat(LOCALE, { weekday: "short", day: "numeric", month: "short" }).format(
    new Date(y, m - 1, d),
  );
}

export function weekdayInitial(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Intl.DateTimeFormat(LOCALE, { weekday: "narrow" }).format(new Date(y, m - 1, d));
}

export function relativeTime(iso: string, now = new Date()): string {
  const diff = (new Date(iso).getTime() - now.getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  const abs = Math.abs(diff);
  if (abs < 60) return rtf.format(Math.round(diff), "second");
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}

export function greetingFor(part: "morning" | "afternoon" | "night"): string {
  return { morning: "Buenos días", afternoon: "Buenas tardes", night: "Buenas noches" }[part];
}

export const PRIORITY_LABEL = { low: "Baja", medium: "Media", high: "Alta", critical: "Crítica" } as const;

/** «12,50», «12.5», «1.234,56» → céntimos. null si no es un importe válido. */
export function parseMoneyInput(s: string): number | null {
  let t = s.trim().replace(/[€\s]/g, "");
  if (!t) return null;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(t)) return null;
  const c = Math.round(parseFloat(t) * 100);
  return c > 0 ? c : null;
}

export function parseNum(s: string): number | null {
  const t = s.trim().replace(",", ".");
  if (!t) return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
}
