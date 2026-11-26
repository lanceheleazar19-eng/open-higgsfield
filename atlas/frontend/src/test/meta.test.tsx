import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { MetaBrain } from "../pages/MetaBrain";

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
const go = (path: string) => render(<MemoryRouter initialEntries={[path]}><MetaBrain /></MemoryRouter>);

const RUN = { id: 7, request: "¿Me conviene estudiar por la mañana?", mode: "council", requested_mode: "council", source: "console", status: "done", phase: null,
  complexity: { label: "compleja", score: 62 }, answer: "Prueba por la mañana dos semanas [E1].", models: ["ollama:qwen2.5:7b"], local_only: false, calls: 5,
  tokens_in: null, tokens_out: null, cost_usd: null, duration_ms: 41000, research_id: null, error: null, feedback: null,
  phases: ["understand", "formulate", "context", "specialists", "critic", "research", "integrate", "verify"],
  done_phases: ["understand", "formulate", "context", "specialists", "critic", "research", "integrate", "verify"], created_at: "2026-11-26T10:00:00",
  issues: 2, verification_rate: 0,
  trace: [{ t: "2026-11-26T10:00:01", phase: "critic", actor: "Critic Agent", msg: "2 problema(s) · veredicto: revisar", ok: true }],
  evidence: [{ id: "E1", kind: "memory", label: "Memoria (preferencia)", text: "Prefiero estudiar temprano" }],
  critique: { issues: [{ tipo: "cálculo", gravedad: "alta", detalle: "«120 + 35 = 165» es incorrecto: el resultado es 155", por: "verificador", afecta: "respuesta final" },
    { tipo: "consenso no es verdad", gravedad: "media", detalle: "Coinciden sin fuentes", por: "comprobación automática", afecta: "" }], veredicto: "revisar" },
  verification: { checked: 1, supported: 0, claims: [{ claim: "Rindes un 30 % más", status: "sin_fuente", score: 0, refs: [] }], rate: 0, note: "Soporte textual, no verdad absoluta." },
  result: { hechos: [{ texto: "Rindes un 30 % más", evidencia: "" }], hipotesis: ["Menos interrupciones"], inferencias: [], opiniones: [], incertidumbres: ["1 afirmación sin respaldo"], siguientes_pasos: [] },
  specialists: { learning: { agent: "Learning Agent", model: "ollama:qwen2.5:7b", analisis: "Mejor por la mañana", confianza: "alta", riesgos: [], incertidumbres: [] } } };

test("Consola: analiza sin ejecutar y muestra modo, agentes, fases y modelos reales", async () => {
  const calls = stub({
    "GET /api/meta/runs": () => [200, []],
    "POST /api/meta/analyze": () => [200, { score: 62, label: "compleja", reasons: ["comparación", "decisión"], agents: ["learning"], agent_names: ["Learning Agent"],
      mode: "council", personal: false, local_only: false, local_reason: null, phases: ["understand", "formulate", "critic", "verify"],
      route: { chat: [{ id: "ollama:qwen2.5:7b" }], agents: [{ id: "ollama:qwen2.5:7b" }], json: [] } }],
  });
  go("/meta");
  fireEvent.change(await screen.findByLabelText("Petición para el META-BRAIN"), { target: { value: "¿Estudio por la mañana o por la noche?" } });
  fireEvent.click(screen.getByRole("button", { name: "Analizar sin ejecutar" }));
  expect(await screen.findByText(/Complejidad compleja \(62\/100\)/)).toBeInTheDocument();
  expect(screen.getByText(/Comprender → Formular → Crítico → Verificar/)).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /api/meta/runs")).toBe(false); // analizar no ejecuta nada
});

test("Traza: hechos con su verificación, avisos del crítico y acciones", async () => {
  const calls = stub({
    "GET /api/meta/runs": () => [200, [RUN]],
    "GET /api/meta/runs/7": () => [200, RUN],
    "POST /api/meta/runs/7/feedback": () => [200, { ...RUN, feedback: 1 }],
  });
  go("/meta?run=7");
  expect(await screen.findByTestId("meta-run")).toBeInTheDocument();
  expect(screen.getByText("sin fuente")).toBeInTheDocument();
  expect(screen.getByText(/120 \+ 35 = 165» es incorrecto/)).toBeInTheDocument();
  expect(screen.getByText("consenso no es verdad")).toBeInTheDocument();
  expect(screen.getByText("Coste").nextSibling).toHaveTextContent("N/D"); // sin precios: N/D, nunca 0 inventado
  fireEvent.click(screen.getByRole("button", { name: "Útil" }));
  await waitFor(() => expect(calls.find((c) => c.key === "POST /api/meta/runs/7/feedback")!.body).toEqual({ value: 1 }));
});

test("Gobierno: el kill switch pide confirmación y detiene procesos", async () => {
  let kill = false;
  const calls = stub({
    "GET /api/meta/governance": () => [200, { meta: { kill, limits: { max_calls: 12, max_seconds: 600, max_cost_usd: null }, council_size: 3, diverse_models: true,
      allow_cloud_personal: false, auto_research: true } }],
    "GET /api/meta/governance/audit": () => [200, { log: [], injections: [], pending_approvals: [] }],
    "POST /api/meta/governance/kill": (b) => { kill = (b as { on: boolean }).on; return [200, { kill, stopped: { meta: 1, workflows: 0, arena: 0 } }]; },
  });
  vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
  go("/meta?s=governance");
  const btn = await screen.findByRole("button", { name: "Activar kill switch" });
  fireEvent.click(btn);
  expect(calls.some((c) => c.key === "POST /api/meta/governance/kill")).toBe(false);
  fireEvent.click(btn);
  expect(await screen.findByText(/Detenidos: 1 ejecuciones/)).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Desactivar kill switch" })).toBeInTheDocument();
});

test("Benchmark: tabla por categorías y sin «mejor» con un solo concursante", async () => {
  stub({
    "GET /api/meta/bench": () => [200, { installed: true, suite_id: 3, tests: [{ category: "math", prompt: "17 × 23" }], conditions: "Mismas pruebas.",
      runs: [{ id: 1, model: "ollama:qwen2.5:7b", status: "done", summary: { avg_score: 40, errors: 0 }, results: [{ i: 0, score: 0, scored_by: "número", output: "390", latency_ms: 900 }], created_at: "2026-11-26T10:00:00" }],
      compare: { categories: { math: "Matemáticas" }, best: null, table: [{ model: "ollama:qwen2.5:7b", run_id: 1, status: "done", summary: { avg_score: 40, reliability_pct: 100 }, by_category: { math: 0 } }] } }],
    "GET /api/lab/arena/models": () => [200, [{ id: "ollama:qwen2.5:7b" }, { id: "vistan:meta-brain", label: "VISTAN META-BRAIN" }]],
  });
  go("/meta?s=bench");
  expect(await screen.findByText(/Sin «mejor» declarado/)).toBeInTheDocument();
  expect(screen.getByLabelText(/VISTAN META-BRAIN/)).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "Matemáticas" })).toBeInTheDocument();
});
