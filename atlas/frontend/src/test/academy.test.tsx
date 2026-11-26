import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Academy } from "../pages/Academy";

vi.mock("lightweight-charts", () => ({ createChart: () => ({ addSeries: () => ({ setData: vi.fn(), createPriceLine: vi.fn() }), timeScale: () => ({ fitContent: vi.fn() }), remove: vi.fn() }),
  AreaSeries: {}, LineSeries: {}, ColorType: { Solid: "solid" } }));


type H = (body: unknown) => [number, unknown];
function stub(routes: Record<string, H>) {
  const calls: { key: string; body?: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url}`;
    const body = init?.body && typeof init.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ key, body });
    const h = routes[key] ?? routes[`${init?.method ?? "GET"} ${url.split("?")[0]}`];
    const [status, out] = h ? h(body) : [404, { detail: "no" }];
    return new Response(JSON.stringify(out), { status, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}
afterEach(() => vi.unstubAllGlobals());
const go = (path: string) => render(<MemoryRouter initialEntries={[path]}><Academy /></MemoryRouter>);
const META = { categories: { economia: "Economía y finanzas" }, teachers: [], coordinator: "Academy Coordinator", question_types: ["mcq", "tf", "numeric", "open", "case", "code"],
  actions: { cero: "Enséñame desde cero." }, settings: { gamification: true, weekly_minutes: 180, weekly_lessons: 3, style: "equilibrado", voice_autoplay: false },
  criteria_note: "Tipo test: 1 punto.", states: {} };
const base = { "GET /api/life/lock": (): [number, unknown] => [200, { enabled: false, unlocked: true }], "GET /api/academy/meta": (): [number, unknown] => [200, META] };
const STATS = { hours: 0, minutes_week: 0, weekly: [{ day: "2026-11-20", minutes: 0 }], lessons_done: 0, courses_active: 0, courses_done: 0, exams: 0, avg_score: null,
  retention_pct: null, retention_rule: "r", streak: 0, active_days: 0, concepts: { nuevo: 0 }, due_reviews: 0, time_by_subject: [], score_series: [] };

test("Dashboard sin actividad: no inventa progreso y ofrece continuar", async () => {
  stub({ ...base, "GET /api/academy/dashboard": () => [200, { greeting: "Ana", overall_level: null, stats: STATS, courses: [], upcoming_exams: [], goals: [],
    weekly_target: { minutes: 180, lessons: 3 }, lessons_week: 0, recommendations: [{ kind: "start", text: "Empieza un curso" }], recent: [], continue: null, gamification: null, subjects: [] }] });
  go("/academy");
  expect(await screen.findByText("Hola, Ana")).toBeInTheDocument();
  expect(screen.getByText(/sin evaluar todavía/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /CONTINUAR APRENDIZAJE/ })).toBeInTheDocument();
  expect(screen.getAllByText("N/D").length).toBeGreaterThanOrEqual(2); // nota media y retención sin datos
});

test("Examen: corrige con criterios y muestra nota, evolución y rúbrica", async () => {
  const EX = { id: 5, kind: "exam", difficulty: 2, subject_id: 1, course_id: null, score: null, criteria: { note: "Criterios definidos" },
    questions: [{ type: "mcq", q: "¿2+2?", options: ["3", "4"], topic: "Suma" }, { type: "open", q: "Explica", topic: "Teoría", criteria: [{ criterio: "Define", puntos: 5 }, { criterio: "Ejemplo", puntos: 5 }] }] };
  const calls = stub({ ...base, "GET /api/academy/library": () => [200, [{ id: 1, name: "Matemáticas" }]], "GET /api/academy/exams": () => [200, [{ id: 5, subject: "Matemáticas", kind: "exam", difficulty: 2, score: null, created_at: "2026-11-26T10:00:00" }]],
    "GET /api/academy/exams/5": () => [200, EX],
    "POST /api/academy/exams/5/submit": () => [200, { ...EX, score: 71.4, answers: [1, "Es…"], evolution: 5, feedback: { grade_10: 7.1, correct: 1, incorrect: 1, mastered_topics: ["Suma"], weak_topics: ["Teoría"], previous: 66.4,
      results: [{ score: 100, correct: true, answer: 1, explanation: "4" }, { score: 50, correct: false, criteria: [{ criterio: "Define", puntos: 5, cumple: true, porque: "ok" }, { criterio: "Ejemplo", puntos: 5, cumple: false, porque: "falta" }] }] } }] });
  go("/academy?s=exams&subject=1");
  fireEvent.click(await screen.findByRole("button", { name: "Continuar" }));
  fireEvent.click(await screen.findByLabelText("4"));
  fireEvent.change(screen.getByLabelText("Respuesta 2"), { target: { value: "Es…" } });
  fireEvent.click(screen.getByRole("button", { name: "Entregar y corregir" }));
  expect(await screen.findByText("7.1/10")).toBeInTheDocument();
  expect(screen.getByText("+5 pts")).toBeInTheDocument();
  expect(screen.getByText(/✗ Ejemplo \(5 p\) — falta/)).toBeInTheDocument();
  await waitFor(() => expect(calls.find((c) => c.key === "POST /api/academy/exams/5/submit")!.body).toMatchObject({ answers: [1, "Es…"] }));
});

test("Laboratorio de trading: solo backtest con dinero virtual", async () => {
  stub({ ...base, "POST /api/academy/labs/trading/backtest": () => [201, { result: { return_pct: 4.2, buy_hold_pct: 3, max_drawdown_pct: 2, trades: 3, win_rate_pct: 66.7, equity: [1, 2, 3],
    note: "Backtesting educativo… Nunca se ejecutan órdenes reales desde la academia." } }] });
  go("/academy?s=labs");
  fireEvent.click(await screen.findByRole("button", { name: "Trading Learning Lab" }));
  fireEvent.change(screen.getByLabelText(/precios de cierre/), { target: { value: "1,2,3" } });
  fireEvent.click(screen.getByRole("button", { name: "Ejecutar backtest" }));
  expect(await screen.findByText(/Nunca se ejecutan órdenes reales/)).toBeInTheDocument();
});
