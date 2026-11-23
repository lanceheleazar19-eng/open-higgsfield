import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "../App";
import { chatReply, emptyDashboard, health, mockFetch, modules, prefs } from "./fixtures";

function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

const base = {
  "/api/system/health": health,
  "/api/system/modules": modules,
  "/api/settings": prefs,
  "/api/settings/timezones": ["Europe/Madrid", "America/Mexico_City"],
};

afterEach(() => vi.unstubAllGlobals());

test("dashboard vacío muestra estados vacíos honestos y no cifras inventadas", async () => {
  mockFetch({ ...base, "/api/dashboard": emptyDashboard });
  renderAt("/");
  expect(await screen.findByText(/Buenos días/)).toBeInTheDocument();
  expect(screen.getAllByText(/No hay tareas registradas/).length).toBeGreaterThan(0);
  expect(screen.getByText("Sin alertas. Todo en orden.")).toBeInTheDocument();
  expect(screen.getByText("Local (sin modelo)")).toBeInTheDocument();
  expect(screen.getByText(/Aún no hay movimientos de dinero real/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Dime cómo te llamas/ })).toHaveAttribute("href", "/settings");
});

test("dashboard con datos muestra nombre, tareas atrasadas y finanzas", async () => {
  mockFetch({
    ...base,
    "/api/dashboard": {
      ...emptyDashboard,
      greeting: { ...emptyDashboard.greeting, name: "Lance" },
      summary: { ...emptyDashboard.summary, pending_tasks: 1, overdue_tasks: 1 },
      tasks: { pending: 1, overdue: 1, due_today: 0, items: [
        { id: 1, title: "Pagar seguro", priority: "high", status: "pending", due_at: "2026-11-22T09:00:00+01:00", overdue: true },
      ] },
      alerts: [{ level: "critical", module: "tasks", text: "1 tarea atrasada." }],
      finance: { ...emptyDashboard.finance, has_data: true, income_cents: 200000, expense_cents: 50000, net_cents: 150000, balance_cents: 150000,
        top_expense_categories: [{ category: "Vivienda", amount_cents: 50000 }] },
    },
  });
  renderAt("/");
  expect(await screen.findByText("Lance")).toBeInTheDocument();
  expect(screen.getAllByText("Pagar seguro").length).toBe(2); // HUD + telemetría
  expect(screen.getByText(/Atrasada ·/)).toBeInTheDocument();
  expect(screen.getByText("Vivienda")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "1 tarea atrasada." })).toHaveAttribute("href", "/tasks");
  expect(screen.getByRole("button", { name: /Abrir Finance: 1500,00\s€ mes/ })).toBeInTheDocument();
});

test("backend caído muestra estado sin conexión con reintento", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("network"); }));
  renderAt("/");
  expect(await screen.findByText(/Núcleo de ATLAS sin conexión/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
});

test("sidebar marca módulos planificados con su fase y abre su página", async () => {
  mockFetch({ ...base, "/api/dashboard": emptyDashboard });
  renderAt("/tasks");
  expect(await screen.findByText("F4")).toBeInTheDocument();
  expect(await screen.findByText("Fase 4 · en desarrollo")).toBeInTheDocument();
  expect(screen.getByText("Prioridades")).toBeInTheDocument();
});

test("configuración guarda el nombre vía PUT", async () => {
  const calls = mockFetch({ ...base, "PUT /api/settings": { ...prefs, user_name: "Tony" } });
  renderAt("/settings");
  const input = await screen.findByPlaceholderText("Tu nombre");
  await waitFor(() => expect(input).toHaveValue("Lance"));
  fireEvent.change(input, { target: { value: "Tony" } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
  await screen.findByText("Preferencias guardadas.");
  const put = calls.find((c) => c.init?.method === "PUT");
  expect(JSON.parse(put!.init!.body as string)).toMatchObject({ user_name: "Tony" });
});

test("los nodos del núcleo muestran datos reales y abren su módulo", async () => {
  mockFetch({ ...base, "/api/dashboard": { ...emptyDashboard, tasks: { ...emptyDashboard.tasks, pending: 3 } } });
  renderAt("/");
  const node = await screen.findByRole("button", { name: "Abrir Tasks: 3 pendientes" });
  expect(screen.getByRole("button", { name: "Abrir Memory: 12 registros" })).toBeInTheDocument();
  fireEvent.click(node);
  expect(await screen.findByText("Fase 4 · en desarrollo")).toBeInTheDocument();
});

test("comando rápido consulta al asistente y muestra la respuesta", async () => {
  const calls = mockFetch({
    ...base, "/api/dashboard": emptyDashboard,
    "POST /api/assistant/chat": chatReply("No tienes tareas pendientes registradas."),
  });
  renderAt("/");
  fireEvent.click(await screen.findByRole("button", { name: "¿Qué tengo pendiente hoy?" }));
  expect(await screen.findByText("No tienes tareas pendientes registradas.", {}, { timeout: 5000 })).toBeInTheDocument();
  const post = calls.find((c) => c.init?.method === "POST");
  expect(JSON.parse(post!.init!.body as string)).toEqual({ text: "¿Qué tengo pendiente hoy?", history: [] });
  expect(within(screen.getByRole("region", { name: "Conversación con ATLAS" })).getByText("Modo local")).toBeInTheDocument();
});

test("barra de conversación: texto libre y resumen ejecutivo", async () => {
  const calls = mockFetch({
    ...base, "/api/dashboard": emptyDashboard,
    "POST /api/assistant/chat": chatReply("Hola, Lance. Todo en orden.", "ai", "qwen2.5:7b"),
  });
  renderAt("/");
  const input = await screen.findByLabelText("Mensaje para ATLAS");
  const send = screen.getByRole("button", { name: "Enviar" });
  expect(send).toBeDisabled();
  fireEvent.change(input, { target: { value: "Hola ATLAS" } });
  fireEvent.click(send);
  expect(await screen.findByText("Hola, Lance. Todo en orden.", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByText("IA · qwen2.5:7b")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Resumen" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Resumen" }));
  // la segunda petición lleva el hilo de la conversación
  await waitFor(() => expect(calls.filter((c) => c.init?.method === "POST").length).toBe(2));
  const body = JSON.parse(calls.filter((c) => c.init?.method === "POST")[1].init!.body as string);
  expect(body.text).toMatch(/resumen ejecutivo/);
  expect(body.history).toEqual([
    { role: "user", content: "Hola ATLAS" },
    { role: "assistant", content: "Hola, Lance. Todo en orden." },
  ]);
});

test("micrófono deshabilitado y explicado si el navegador no soporta voz", async () => {
  mockFetch({ ...base, "/api/dashboard": emptyDashboard });
  renderAt("/");
  const mic = await screen.findByRole("button", { name: "Micrófono no disponible en este navegador" });
  expect(mic).toBeDisabled();
});

test("página de IA: estado de Ollama, modelos y selección", async () => {
  const calls = mockFetch({
    ...base,
    "/api/ai/status": {
      provider: "ollama", url: "http://127.0.0.1:11434", reachable: true, configured: true, model: "qwen2.5:7b",
      preferred: null, error: null, note: null,
      models: [
        { name: "qwen2.5:7b", size_bytes: 4.7e9, parameter_size: "7.6B", family: "qwen2" },
        { name: "llama3.2:3b", size_bytes: 2e9, parameter_size: "3.2B", family: "llama" },
      ],
    },
    "PUT /api/settings": { ...prefs, ai_model: "llama3.2:3b" },
  });
  renderAt("/ai");
  expect(await screen.findByText("Conectado")).toBeInTheDocument();
  const select = await screen.findByLabelText("Modelo que usa ATLAS");
  expect(screen.getByRole("option", { name: "Automático (qwen2.5:7b)" })).toBeInTheDocument();
  fireEvent.change(select, { target: { value: "llama3.2:3b" } });
  await screen.findByText("Modelo fijado: llama3.2:3b");
  const put = calls.find((c) => c.init?.method === "PUT");
  expect(JSON.parse(put!.init!.body as string)).toEqual({ ai_model: "llama3.2:3b" });
});

test("página de IA sin Ollama explica cómo activarlo", async () => {
  mockFetch({
    ...base,
    "/api/ai/status": { provider: "ollama", url: "http://127.0.0.1:11434", reachable: false, configured: false, model: null,
      preferred: null, error: "x", note: "Ollama no detectado.", models: [] },
  });
  renderAt("/ai");
  expect(await screen.findByText("No detectado")).toBeInTheDocument();
  expect(screen.getByText("ollama pull qwen2.5:7b")).toBeInTheDocument();
});
