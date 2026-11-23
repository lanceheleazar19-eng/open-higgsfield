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
