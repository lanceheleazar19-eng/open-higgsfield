import type { Pace, Priority, TaskItem } from "../api/types";

export const PRIORITIES: Priority[] = ["critical", "high", "medium", "low"];

export const PACE_LABEL: Record<Pace, string> = {
  ahead: "Adelantado",
  on_track: "En ritmo",
  behind: "Por detrás",
  overdue: "Fuera de plazo",
  achieved: "Conseguido",
  no_deadline: "Sin fecha límite",
  not_started: "Sin progreso aún",
};

const DAY = new Intl.DateTimeFormat("es-ES", { weekday: "short", day: "numeric", month: "short" });
const DAYTIME = new Intl.DateTimeFormat("es-ES", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function localDate(iso: string): Date {
  // "YYYY-MM-DD" → fecha local sin desfase
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatDue(t: Pick<TaskItem, "due_at" | "due_date" | "all_day">, timeZone?: string): string {
  if (!t.due_at) return "Sin fecha";
  if (t.all_day && t.due_date) return DAY.format(localDate(t.due_date));
  return new Intl.DateTimeFormat("es-ES", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone })
    .format(new Date(t.due_at));
}

export function formatDayLabel(isoDate: string): string {
  return DAY.format(localDate(isoDate));
}

export function formatDateTimeLocal(iso: string): string {
  return DAYTIME.format(new Date(iso));
}

/** Agrupa tareas abiertas: atrasadas, hoy, próximas, sin fecha. `today` = "YYYY-MM-DD" local. */
export function bucketTasks(items: TaskItem[], today: string) {
  const b = { overdue: [] as TaskItem[], today: [] as TaskItem[], upcoming: [] as TaskItem[], undated: [] as TaskItem[] };
  for (const t of items) {
    if (t.overdue) b.overdue.push(t);
    else if (!t.due_date) b.undated.push(t);
    else if (t.due_date === today) b.today.push(t);
    else b.upcoming.push(t);
  }
  return b;
}

export function fmtNum(v: number | null | undefined, unit?: string | null): string {
  if (v === null || v === undefined) return "—";
  const n = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 }).format(v);
  return unit ? `${n} ${unit}` : n;
}

/** Fecha local de hoy como "YYYY-MM-DD" en la zona indicada. */
export function todayIn(timeZone?: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  return parts;
}
