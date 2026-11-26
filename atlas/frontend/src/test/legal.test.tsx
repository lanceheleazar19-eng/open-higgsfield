import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Legal } from "../pages/Legal";

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
const go = (path: string) => render(<MemoryRouter initialEntries={[path]}><Legal /></MemoryRouter>);
const META = { branches: { inmobiliario: "Derecho inmobiliario" }, jurisdictions: { es: "España", "es-ct": "Cataluña", eu: "Unión Europea" },
  states: ["nuevo", "archivado"], levels: ["critico", "alto", "medio", "bajo"], templates: { nda: { label: "NDA", fields: ["parte_receptora"] } },
  profiles: { ecommerce: "Tienda online" }, contract_types: {}, sources: [], settings: { allow_cloud: false }, disclaimer: "No es asesoramiento profesional.", formats: [] };
const base = { "GET /api/life/lock": (): [number, unknown] => [200, { enabled: false, unlocked: true }], "GET /api/legal/meta": (): [number, unknown] => [200, META] };

test("Bloqueado con el PIN de LIFE OS", async () => {
  stub({ "GET /api/life/lock": () => [200, { enabled: true, unlocked: false }] });
  go("/legal");
  expect(await screen.findByText("VISTAN LEGAL bloqueado")).toBeInTheDocument();
  expect(screen.getByLabelText("PIN")).toBeInTheDocument();
});

test("Command Center: datos reales y buscador que detecta jurisdicción y pide lo que falta", async () => {
  const calls = stub({ ...base,
    "GET /api/legal/dashboard": () => [200, { counts: { active_cases: 1, documents: 2, pending_review: 1, open_alerts: 1, research: 0, drafts: 0 },
      alerts_by_level: { critico: 1, alto: 0, medio: 0, bajo: 0 }, cases: [], pending_review: [], alerts: [{ id: 1, level: "critico", title: "Posible riesgo CRÍTICO en «Contrato»" }],
      deadlines: [{ id: 1, title: "Responder requerimiento", due_on: "2026-12-01", days: 3, kind: "administrativo", verified: false }], research: [], recent_docs: [], queries: [], agent: [] }],
    "POST /api/legal/research/precheck": () => [200, { jurisdiction: "es", jurisdiction_label: "España", branches: ["inmobiliario"], branch_labels: ["Derecho inmobiliario"],
      questions: ["¿En qué comunidad autónoma está el inmueble?"] }],
  });
  go("/legal");
  expect(await screen.findByText(/SIN VERIFICAR/)).toBeInTheDocument();
  expect(screen.getByText("Posible riesgo CRÍTICO en «Contrato»")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("BUSCADOR JURÍDICO"), { target: { value: "¿Pueden quedarse mi fianza del alquiler?" } });
  fireEvent.click(screen.getByRole("button", { name: "Analizar" }));
  expect(await screen.findByText(/comunidad autónoma/)).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /api/legal/research")).toBe(false); // no investiga sin que lo pidas
});

test("Investigación: vigencia, citas no verificadas y fuentes oficiales", async () => {
  const R = { id: 4, question: "¿Fianza?", status: "done", jurisdiction: "es", progress: 100, sources_count: 1, created_at: "2026-11-26T10:00:00",
    verification: { citas: 2, verificadas: 1, nota: "Verificación literal." },
    report: { resumen: "Resumen", problema: "Fianza", jurisdiccion: "España", legislacion: [
      { norma: "Código Civil", articulos: ["1544"], vigencia: "vigente", vigencia_via: "API BOE", verificada_en_fuente: true, articulos_no_encontrados: [], url: "https://www.boe.es/x", fuente_oficial: "BOE" },
      { norma: "Ley inventada", articulos: ["5"], vigencia: "no_comprobada", verificada_en_fuente: false, articulos_no_encontrados: ["5"] }],
      jurisprudencia: [], riesgos: [], incertidumbres: ["No se ha podido comprobar la vigencia de alguna norma"], conclusion: "c",
      fuentes: [{ id: 1, titulo: "Código Civil", url: "https://www.boe.es/x", organismo: "BOE", tipo: "legislacion", consultada: "2026-11-26T10:00" }], aviso: "No es asesoramiento." } };
  stub({ ...base, "GET /api/legal/research": () => [200, [R]], "GET /api/legal/research/4": () => [200, R], "GET /api/legal/cases": () => [200, []] });
  go("/legal?s=research&id=4");
  expect(await screen.findByTestId("legal-research")).toBeInTheDocument();
  expect(screen.getByText(/vigente \(API BOE\)/)).toBeInTheDocument();
  expect(screen.getByText("NO verificada en las fuentes leídas")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "PDF" })).toHaveAttribute("href", "/api/legal/reports/research/4?fmt=pdf");
});

test("Riesgos: un plazo verificado sin regla se rechaza en el servidor y se muestra el motivo", async () => {
  stub({ ...base, "GET /api/legal/alerts": () => [200, []], "GET /api/legal/deadlines": () => [200, []], "GET /api/legal/cases": () => [200, []],
    "POST /api/legal/deadlines": () => [422, { detail: "Para marcarlo como verificado indica la regla o fuente aplicada" }] });
  go("/legal?s=risks");
  fireEvent.change(await screen.findByLabelText(/^Plazo/), { target: { value: "Recurso" } });
  fireEvent.change(screen.getByLabelText(/Fecha límite/), { target: { value: "2026-12-10" } });
  fireEvent.click(screen.getByLabelText(/Verificado/));
  fireEvent.click(screen.getByRole("button", { name: /Registrar plazo/ }));
  await waitFor(() => expect(screen.getByText(/indica la regla o fuente aplicada/)).toBeInTheDocument());
});
