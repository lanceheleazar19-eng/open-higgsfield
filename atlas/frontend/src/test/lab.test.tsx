import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Lab } from "../pages/Lab";

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
const META = { categories: { ai: "Inteligencia artificial", robotics: "Robótica" }, maturity: { academic: "Académica", prototype: "Prototipo", commercial: "Comercial", speculative: "Especulativa" },
  states: ["IDEA", "PLANNED", "RUNNING", "PAUSED", "COMPLETED", "FAILED", "ARCHIVED"], workflows: {},
  sources: [{ id: "arxiv", name: "arXiv", covers: "preprints", needs_key: false, configured: true, ok: false }] };
const go = (path: string) => render(<MemoryRouter initialEntries={[path]}><Lab /></MemoryRouter>);

test("Command Center: muestra solo datos reales y N/D cuando no hay métricas", async () => {
  stub({
    "GET /api/lab/meta": () => [200, META],
    "GET /api/lab/command": () => [200, { status: { active_research: 0, running_experiments: 0, arena_running: 0, label: "en espera" }, live: [],
      counts: { experiments: 2, running: 0, prototypes: 1, ideas_pending: 0, discoveries_7d: 0, technologies: 0, library: 0 }, running_experiments: [], recent_discoveries: [],
      emerging: [], recent_results: [], agents: [], resources_7d: { model_calls: 0, errors: 0, avg_latency_ms: null, tokens_out: null, cost_usd: null, sandbox_runs: 0 } }],
  });
  go("/lab");
  expect(await screen.findByText("En espera")).toBeInTheDocument();
  expect(screen.getByText("No hay procesos reales en ejecución ahora mismo.")).toBeInTheDocument();
  expect(screen.getAllByText("N/D")).toHaveLength(2);
});

test("Future Simulator: separa hechos, hipótesis y predicciones", async () => {
  const sc = { id: 1, question: "Robótica humanoide", horizon: "5 años", research_id: null, model: "qwen2.5:7b",
    result: { hechos: [], hipotesis: ["Bajará el coste de los actuadores"], predicciones: ["Pilotos en logística"], escenarios: [], variables: [], factores: [], oportunidades: [], riesgos: [], incertidumbres: [], fuentes: [] } };
  const calls = stub({
    "GET /api/lab/meta": () => [200, META],
    "GET /api/lab/scenarios": () => [200, []],
    "GET /api/lab/research": () => [200, []],
    "POST /api/lab/scenarios": () => [200, sc],
  });
  go("/lab?s=future");
  fireEvent.change(await screen.findByLabelText(/Escenario a estudiar/), { target: { value: "Robótica humanoide" } });
  fireEvent.click(screen.getByRole("button", { name: "Simular escenario" }));
  expect(await screen.findByText("Predicciones (no son certezas)")).toBeInTheDocument();
  expect(screen.getByText(/Sin hechos: el escenario no se apoyó/)).toBeInTheDocument();
  expect(screen.getByText("Bajará el coste de los actuadores")).toBeInTheDocument();
  await waitFor(() => expect(calls.find((c) => c.key === "POST /api/lab/scenarios")!.body).toMatchObject({ question: "Robótica humanoide", horizon: "5 años", research_id: null }));
});

test("Ideas: las generadas se marcan como sin validar y se convierten en experimento", async () => {
  let converted = false;
  const idea = () => ({ id: 7, name: "Gafas traductoras", concept: "Subtítulos en tiempo real", origin: "generated", status: converted ? "converted" : "new", difficulty: "alta", cost: "medio",
    experiment_id: converted ? 3 : null, prototype_id: null, opportunity_id: null, project_id: null });
  const calls = stub({
    "GET /api/lab/meta": () => [200, META],
    "GET /api/lab/ideas": () => [200, [idea()]],
    "POST /api/lab/ideas/7/convert": () => { converted = true; return [200, { experiment_id: 3 }]; },
  });
  go("/lab?s=ideas");
  expect(await screen.findByText("IA · sin validar")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "→ Experimento" }));
  expect(await screen.findByText(/Idea convertida en experimento/)).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByRole("button", { name: "→ Experimento" })).not.toBeInTheDocument());
  expect(calls.find((c) => c.key === "POST /api/lab/ideas/7/convert")!.body).toEqual({ to: "experiment" });
});

test("Patentes: aviso legal y enlaces oficiales sin afirmar patentabilidad", async () => {
  stub({
    "GET /api/lab/meta": () => [200, META],
    "GET /api/lab/patents": () => [200, []],
    "GET /api/lab/patents/search": () => [200, { items: [], error: "Espacenet no configurado: se muestran enlaces de búsqueda.",
      links: { google_patents: "https://patents.google.com/?q=x", espacenet: "https://worldwide.espacenet.com/searchResults?query=x", oepm: "https://consultas2.oepm.es/" } }],
  });
  go("/lab?s=patents");
  expect(await screen.findByText(/no puede afirmar que una idea sea patentable/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Buscar patentes"), { target: { value: "x" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
  expect(await screen.findByRole("link", { name: "Google Patents ↗" })).toHaveAttribute("href", "https://patents.google.com/?q=x");
  expect(screen.getByText(/Espacenet no configurado/)).toBeInTheDocument();
});
