import type { Dashboard, Health, ModuleInfo, Prefs } from "../api/types";

export const health: Health = {
  status: "online", version: "0.1.0", python: "3.13",
  database: { ok: true, engine: "sqlite" },
  ai: { configured: false, provider: null, model: null, models_installed: 0, note: "Ollama no detectado." },
  storage: { db_bytes: 81920, disk_free_bytes: 50e9, disk_total_bytes: 100e9, records: 12 },
};

export const modules: ModuleInfo[] = [
  { id: "dashboard", name: "Dashboard", phase: 1, status: "active", summary: "", planned: [] },
  { id: "tasks", name: "Tareas", phase: 4, status: "planned", summary: "Gestión de tareas.", planned: ["Prioridades"] },
  { id: "settings", name: "Configuración", phase: 1, status: "active", summary: "", planned: [] },
];

export const prefs: Prefs = { user_name: "Lance", timezone: "Europe/Madrid", currency: "EUR", ai_model: "" };

const days = Array.from({ length: 7 }, (_, i) => ({ date: `2026-11-${17 + i}`, sessions: 0 }));

export const emptyDashboard: Dashboard = {
  generated_at: "2026-11-23T10:00:00+01:00",
  greeting: { name: "", part_of_day: "morning", timezone: "Europe/Madrid" },
  summary: { pending_tasks: 0, overdue_tasks: 0, upcoming_events: 0, active_projects: 0, sessions_7d: 0 },
  tasks: { pending: 0, overdue: 0, due_today: 0, items: [] },
  events: { items: [] },
  finance: { has_data: false, currency: "EUR", month: "2026-11", income_cents: 0, expense_cents: 0, net_cents: 0, balance_cents: 0, top_expense_categories: [] },
  fitness: { sessions_7d: 0, minutes_7d: 0, days, last_session: null },
  projects: { active: 0, items: [] },
  activity: { items: [] },
  alerts: [],
};

export function mockFetch(routes: Record<string, unknown>) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const key = `${init?.method ?? "GET"} ${url}`;
    const body = key in routes ? routes[key] : routes[url];
    if (body === undefined) return new Response("{}", { status: 404 });
    if (body && typeof body === "object" && "ndjson" in body) {
      const lines = (body as { ndjson: unknown[] }).ndjson.map((e) => JSON.stringify(e) + "\n").join("");
      return new Response(lines, { status: 200, headers: { "Content-Type": "application/x-ndjson" } });
    }
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

/** Respuesta en streaming del cerebro, troceada como la envía el backend. */
export function chatReply(text: string, mode: "ai" | "local" = "local", model: string | null = null) {
  const chunks = mode === "ai" ? text.match(/.{1,8}/g) ?? [] : [text];
  return {
    ndjson: [
      ...(mode === "ai" ? [{ type: "status", state: "thinking", model }] : []),
      ...chunks.map((t) => ({ type: "delta", text: t })),
      { type: "done", mode, model },
    ],
  };
}
