import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Life } from "../pages/Life";

vi.mock("lightweight-charts", () => ({ createChart: () => ({ addSeries: () => ({ setData: vi.fn(), createPriceLine: vi.fn() }), timeScale: () => ({ fitContent: vi.fn() }), remove: vi.fn() }),
  AreaSeries: {}, LineSeries: {}, ColorType: { Solid: "solid" } }));

type H = (body: unknown) => [number, unknown];
function stub(routes: Record<string, H>) {
  const calls: { key: string; body?: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url}`;
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ key, body });
    const h = routes[key] ?? routes[`${init?.method ?? "GET"} ${url.split("?")[0]}`];
    const [status, out] = h ? h(body) : [404, { detail: "no" }];
    return new Response(JSON.stringify(out), { status, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}
afterEach(() => vi.unstubAllGlobals());
const go = (path: string) => render(<MemoryRouter initialEntries={[path]}><Life /></MemoryRouter>);

test("LIFE OS bloqueado: pide el PIN y desbloquea", async () => {
  let unlocked = false;
  stub({
    "GET /api/life/lock": () => [200, { enabled: true, unlocked }],
    "POST /api/life/lock/unlock": (b) => ((b as { pin: string }).pin === "4821" ? (unlocked = true, [200, { unlocked: true }]) : [401, { detail: "PIN incorrecto" }]),
    "GET /api/life/overview": () => [200, { growth: [], stalled_goals: [], discipline_findings: [], habits_today: [], decisions_to_review: [], followups_due: [],
      overdue_commitments: [], networth: { net: 0, estimated_part: 0, business_net: 0 }, note: "Indicadores observables; ninguno mide tu valor como persona." }],
  });
  go("/life");
  fireEvent.change(await screen.findByLabelText("PIN"), { target: { value: "1111" } });
  fireEvent.click(screen.getByRole("button", { name: "Desbloquear" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("PIN incorrecto");
  fireEvent.change(screen.getByLabelText("PIN"), { target: { value: "4821" } });
  fireEvent.click(screen.getByRole("button", { name: "Desbloquear" }));
  expect(await screen.findByText("Personal Growth Analytics")).toBeInTheDocument();
  expect(screen.getByText(/ninguno mide tu valor como persona/)).toBeInTheDocument();
});

test("Disciplina: registrar un hábito y ver errores de validación del servidor", async () => {
  const today = new Date().toLocaleDateString("sv-SE");
  const disc = (done: boolean) => ({ habits: [{ id: 1, name: "Leer", category: "reading", due_today: true, done_today: done, today_value: done ? 1 : null, compliance_30d: 50,
    due_30d: 10, met_30d: 5, streak: done ? 3 : 2, best_streak: 4, weekday: {}, calendar: [] }], overdue_commitments: [], commitment_rate_90d: null, findings: ["«Leer»: cumplido 5 de 10 días previstos (50 %)."],
    auto: { sleep_avg_7d: null, sleep_days: 0, workouts_7d: 0, sources: "" }, habit_defs: [{ id: 1, name: "Leer", kind: "check", days: [0, 1, 2, 3, 4, 5, 6], limit: false }], commitments: [], today });
  let done = false;
  const calls = stub({
    "GET /api/life/lock": () => [200, { enabled: false, unlocked: true }],
    "GET /api/life/discipline": () => [200, disc(done)],
    "PUT /api/life/habits/1/log": () => { done = true; return [200, {}]; },
    "POST /api/life/commitments": () => [422, { detail: [{ loc: ["body", "title"], msg: "Field required" }] }],
    "POST /api/life/coach": () => [200, { answer: "x", model: "m", used: [] }],
  });
  go("/life?s=discipline");
  expect(await screen.findByText(/cumplido 5 de 10 días/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Marcar hecho" }));
  expect(await screen.findByRole("button", { name: "✓ Hecho" })).toBeInTheDocument();
  expect(calls.find((c) => c.key === "PUT /api/life/habits/1/log")!.body).toEqual({ day: today, value: 1 });
  fireEvent.change(screen.getByLabelText("Compromiso verificable"), { target: { value: "x" } });
  fireEvent.click(screen.getByRole("button", { name: "Añadir" }));
  expect(await screen.findByText(/title: Field required/)).toBeInTheDocument();
});

test("Academia: el test no muestra respuestas hasta corregir y actualiza el nivel", async () => {
  const subj = { id: 3, key: "economia", name: "Economía", topics: 0, mastery: { level: 0, label: "Sin evaluar", avg: null, assessments: 0, lessons_done: 0 } };
  const calls = stub({
    "GET /api/life/lock": () => [200, { enabled: false, unlocked: true }],
    "GET /api/life/academy": () => [200, [subj]],
    "GET /api/life/academy/3": () => [200, { subject: { id: 3, name: "Economía", syllabus: [] }, mastery: { ...subj.mastery, rule: "Solo evaluaciones" }, lessons: [], assessments: [] }],
    "POST /api/life/academy/3/assessments": () => [201, { id: 9, kind: "exam", difficulty: 2, questions: [{ type: "mcq", q: "¿Qué es la inflación?", options: ["Subida general de precios", "Bajada de impuestos"] }] }],
    "POST /api/life/assessments/9/submit": () => [200, { score: 100, feedback: { results: [{ score: 100, answer: 0, explanation: "Correcto" }], weak_topics: [] }, mastery: { label: "Avanzado" } }],
    "POST /api/life/coach": () => [200, { answer: "x", model: "m", used: [] }],
  });
  go("/life?s=academy");
  fireEvent.click(await screen.findByRole("button", { name: /Economía/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Examen adaptativo" }));
  expect(await screen.findByText("1. ¿Qué es la inflación?")).toBeInTheDocument();
  expect(screen.queryByText("Correcto")).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Subida general de precios"));
  fireEvent.click(screen.getByRole("button", { name: "Entregar y corregir" }));
  expect(await screen.findByText("Avanzado")).toBeInTheDocument();
  await waitFor(() => expect(calls.find((c) => c.key === "POST /api/life/assessments/9/submit")!.body).toEqual({ answers: [0] }));
});
