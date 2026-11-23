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

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });

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
  expect(screen.getByRole("button", { name: "Abrir Memory: 3 recuerdos" })).toBeInTheDocument();
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
  expect(JSON.parse(post!.init!.body as string)).toEqual({ text: "¿Qué tengo pendiente hoy?" });
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
  // la segunda petición continúa la misma conversación (el historial lo guarda el backend)
  await waitFor(() => expect(calls.filter((c) => c.url === "/api/assistant/chat").length).toBe(2));
  const body = JSON.parse(calls.filter((c) => c.url === "/api/assistant/chat")[1].init!.body as string);
  expect(body).toEqual({ text: expect.stringMatching(/resumen ejecutivo/), conversation_id: 7 });
  expect(localStorage.getItem("atlas.conversation")).toBe("7");
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

const mem = (over: Record<string, unknown> = {}) => ({
  id: 1, content: "Prefiero entrenar por la mañana", kind: "preference", permanent: true, expires_at: null, expired: false,
  project_id: null, source: "chat", created_at: "2026-11-23T10:00:00+01:00", updated_at: "2026-11-23T10:00:00+01:00", ...over,
});

test("«recuerda que…» muestra que se ha guardado en memoria", async () => {
  mockFetch({
    ...base, "/api/dashboard": emptyDashboard,
    "POST /api/assistant/chat": chatReply("Hecho. Lo recordaré.", "memory", null, [{ type: "memory", action: "saved", memory: mem() }]),
  });
  renderAt("/");
  fireEvent.change(await screen.findByLabelText("Mensaje para ATLAS"), { target: { value: "recuerda que prefiero entrenar por la mañana" } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
  expect(await screen.findByText(/Guardado en memoria/, {}, { timeout: 5000 })).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Conversación con ATLAS" })).getByText("Memoria")).toBeInTheDocument();
});

test("olvidar requiere confirmación con botón", async () => {
  const calls = mockFetch({
    ...base, "/api/dashboard": emptyDashboard,
    "POST /api/assistant/chat": chatReply("¿Quieres que olvide esto?", "memory", null, [{ type: "memory", action: "forget_candidate", memory: mem() }]),
    "DELETE /api/memory/1": {},
  });
  renderAt("/");
  fireEvent.change(await screen.findByLabelText("Mensaje para ATLAS"), { target: { value: "olvida que entreno por la mañana" } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
  const btn = await screen.findByRole("button", { name: "Olvidar «Prefiero entrenar por la mañana»" }, { timeout: 5000 });
  expect(calls.some((c) => c.init?.method === "DELETE")).toBe(false);
  fireEvent.click(btn);
  expect(await screen.findByText(/Olvidado:/)).toBeInTheDocument();
  expect(calls.some((c) => c.url === "/api/memory/1" && c.init?.method === "DELETE")).toBe(true);
});

test("la IA propone recuerdos y solo se guardan si lo apruebas", async () => {
  const calls = mockFetch({
    ...base, "/api/dashboard": emptyDashboard,
    "POST /api/assistant/chat": chatReply("¡Gran objetivo!", "ai", "qwen2.5:7b"),
    "POST /api/memory/suggest": { suggestions: [
      { content: "Quiere correr una media maratón", kind: "goal", temporary: false },
      { content: "Entrena tres días por semana", kind: "fact", temporary: false },
    ] },
    "POST /api/memory": { memory: mem({ id: 9, content: "Quiere correr una media maratón", kind: "goal" }), created: true },
  });
  renderAt("/");
  fireEvent.change(await screen.findByLabelText("Mensaje para ATLAS"), { target: { value: "Quiero correr una media maratón en primavera" } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
  expect(await screen.findByText("ATLAS propone recordar", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(calls.some((c) => c.url === "/api/memory" && c.init?.method === "POST")).toBe(false);
  const [save] = screen.getAllByRole("button", { name: "Guardar" });
  fireEvent.click(save);
  expect(await screen.findByText("Guardado")).toBeInTheDocument();
  const post = calls.find((c) => c.url === "/api/memory" && c.init?.method === "POST");
  expect(JSON.parse(post!.init!.body as string)).toEqual({ content: "Quiere correr una media maratón", kind: "goal", source: "suggested" });
  fireEvent.click(screen.getByRole("button", { name: "Descartar" }));
  await waitFor(() => expect(screen.queryByText("Entrena tres días por semana")).not.toBeInTheDocument());
});

test("al volver a abrir ATLAS retoma la última conversación", async () => {
  localStorage.setItem("atlas.conversation", "7");
  mockFetch({
    ...base, "/api/dashboard": emptyDashboard,
    "/api/conversations/7": { id: 7, title: "Hola", created_at: "", messages: [
      { id: 1, conversation_id: 7, role: "user", content: "¿Cómo voy con mis objetivos?", mode: null, model: null, created_at: "2026-11-22T10:00:00+01:00" },
      { id: 2, conversation_id: 7, role: "assistant", content: "Vas bien, sigue así.", mode: "ai", model: "qwen2.5:7b", created_at: "2026-11-22T10:00:05+01:00" },
    ] },
  });
  renderAt("/");
  expect(await screen.findByText("Vas bien, sigue así.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Nueva conversación" }));
  expect(screen.queryByText("Vas bien, sigue así.")).not.toBeInTheDocument();
  await waitFor(() => expect(localStorage.getItem("atlas.conversation")).toBeNull());
});

test("página Memoria: lista, añade y olvida recuerdos", async () => {
  const calls = mockFetch({
    ...base,
    "/api/memory?": { items: [mem(), mem({ id: 2, content: "Viaje a Lisboa", kind: "fact", permanent: false, expires_at: "2026-11-29T23:59:00+01:00" })], memories: 2, conversations: 1 },
    "POST /api/memory": { memory: mem({ id: 3, content: "Mi objetivo es ahorrar", kind: "goal" }), created: true },
    "DELETE /api/memory/1": {},
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  renderAt("/memory");
  expect(await screen.findByText("Prefiero entrenar por la mañana")).toBeInTheDocument();
  expect(screen.getByText(/Temporal · hasta/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("¿Qué debe recordar ATLAS?"), { target: { value: "Mi objetivo es ahorrar" } });
  fireEvent.change(screen.getByLabelText("Tipo"), { target: { value: "goal" } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar recuerdo" }));
  expect(await screen.findByText("Guardado.")).toBeInTheDocument();
  expect(JSON.parse(calls.find((c) => c.init?.method === "POST")!.init!.body as string))
    .toEqual({ content: "Mi objetivo es ahorrar", kind: "goal", expires_at: null });
  fireEvent.click(screen.getByRole("button", { name: "Olvidar: Prefiero entrenar por la mañana" }));
  expect(await screen.findByText("Recuerdo eliminado.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Exportar" })).toHaveAttribute("href", "/api/memory/export");
});
