import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "../App";
import { chatReply, emptyDashboard, health, mockFetch, modules, prefs, profileFx } from "./fixtures";

function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

const base = {
  "/api/profile": profileFx,
  "/api/system/metrics": { cpu_percent: 14, ram_percent: 42, ram_used_bytes: 1, ram_total_bytes: 2 },
  "/api/system/health": health,
  "/api/system/modules": modules,
  "/api/settings": prefs,
  "/api/settings/timezones": ["Europe/Madrid", "America/Mexico_City"],
};

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

test("dashboard vacío muestra estados vacíos honestos y no cifras inventadas", async () => {
  mockFetch({ ...base, "/api/dashboard": emptyDashboard });
  renderAt("/");
  expect(await screen.findByText(/Buenos días/)).toBeInTheDocument();
  expect(screen.getAllByText(/No hay tareas registradas/).length).toBeGreaterThan(0);
  expect(screen.queryByText(/^Alertas/)).not.toBeInTheDocument(); // sin alertas no se muestra la tarjeta
  expect(screen.getAllByText("Modo local").length).toBeGreaterThan(0);
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
  expect(screen.getAllByText("Pagar seguro").length).toBe(2); // columna derecha + telemetría
  expect(screen.getAllByText(/Atrasada ·/).length).toBeGreaterThan(0);
  expect(screen.getByText("Vivienda")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "1 tarea atrasada." })).toHaveAttribute("href", "/tasks");
  expect(screen.getByRole("button", { name: /Abrir Finanzas: 1500,00\s€ mes/ })).toBeInTheDocument();
});

test("backend caído muestra estado sin conexión con reintento", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("network"); }));
  renderAt("/");
  expect(await screen.findByText(/Núcleo de ATLAS sin conexión/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
});

test("sidebar marca módulos planificados con su fase y abre su página", async () => {
  mockFetch({ ...base, "/api/dashboard": emptyDashboard });
  renderAt("/trading");
  expect(await screen.findByText("F6")).toBeInTheDocument();
  expect(await screen.findByText("Fase 6 · en desarrollo")).toBeInTheDocument();
  expect(screen.getByText("Win rate y P&L")).toBeInTheDocument();
});

test("perfil: guarda el nombre y actualiza el saludo", async () => {
  const calls = mockFetch({ ...base, "PUT /api/profile": { ...profileFx, display_name: "Tony" } });
  renderAt("/settings");
  const input = await screen.findByPlaceholderText("Tu nombre");
  await waitFor(() => expect(input).toHaveValue("Lance"));
  fireEvent.change(input, { target: { value: "Tony" } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar perfil" }));
  await screen.findByText("Perfil guardado.");
  const put = calls.find((c) => c.url === "/api/profile" && c.init?.method === "PUT");
  expect(JSON.parse(put!.init!.body as string)).toMatchObject({ display_name: "Tony" });
});

test("perfil: rechaza formatos no permitidos y abre el recortador con JPG/PNG/WEBP", async () => {
  mockFetch({ ...base });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:foto", revokeObjectURL: () => {} }));
  renderAt("/settings");
  const input = await screen.findByLabelText("Elegir foto de perfil");
  fireEvent.change(input, { target: { files: [new File(["x"], "anim.gif", { type: "image/gif" })] } });
  expect(await screen.findByText(/Formato no permitido/)).toBeInTheDocument();
  fireEvent.change(input, { target: { files: [new File(["x"], "yo.png", { type: "image/png" })] } });
  expect(await screen.findByRole("img", { name: /Vista previa del recorte/ })).toBeInTheDocument();
  expect(screen.getByLabelText("Zoom de la foto")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
  expect(screen.getByRole("button", { name: "Subir foto" })).toBeInTheDocument();
});

test("cabecera: muestra la foto de perfil y enlaza al perfil", async () => {
  mockFetch({ ...base, "/api/dashboard": emptyDashboard, "/api/profile": { ...profileFx, has_avatar: true, avatar_version: 42 } });
  renderAt("/");
  const link = await screen.findByRole("link", { name: "Mi perfil y configuración" });
  expect(link).toHaveAttribute("href", "/settings#perfil");
  await waitFor(() => expect(link.querySelector("img")).toHaveAttribute("src", "/api/profile/avatar?v=42"));
  expect(screen.getByText("Sistema activo")).toBeInTheDocument();
});

test("los nodos del núcleo muestran datos reales y abren su módulo", async () => {
  mockFetch({ ...base, "/api/dashboard": { ...emptyDashboard, tasks: { ...emptyDashboard.tasks, pending: 3 } } });
  renderAt("/");
  const node = await screen.findByRole("button", { name: "Abrir Tareas: 3 pendientes" });
  expect(screen.getByRole("button", { name: "Abrir Memoria: 3 recuerdos" })).toBeInTheDocument();
  mockFetch({ ...base, "/api/tasks?": { items: [], categories: [] }, "/api/goals?": { items: [] },
    "/api/tasks/summary?": { period: "day", from: "", to: "", completed: 0, completed_titles: [], created: 0, due: 0, due_open: 0, overdue: 0, completion_rate: null } });
  fireEvent.click(node);
  expect(await screen.findByRole("heading", { name: /Tareas y objetivos/ })).toBeInTheDocument();
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

test("con el altavoz activo lee la respuesta por frases, con la voz y velocidad elegidas", async () => {
  const spoken: { text: string; rate: number; voice: string | undefined }[] = [];
  class FakeUtterance { text: string; rate = 1; lang = ""; voice?: { name: string }; onend?: () => void; onerror?: () => void; onstart?: () => void;
    constructor(t: string) { this.text = t; } }
  const voices = [
    { name: "Eddy (Spanish (Spain))", lang: "es-ES", voiceURI: "eddy", localService: true },
    { name: "Mónica (Mejorada)", lang: "es-ES", voiceURI: "monica-enh", localService: true },
  ];
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
  vi.stubGlobal("speechSynthesis", {
    getVoices: () => voices, cancel: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(),
    speak: (u: FakeUtterance) => { spoken.push({ text: u.text, rate: u.rate, voice: u.voice?.name }); u.onend?.(); },
  });
  localStorage.setItem("atlas.speak", "1");
  localStorage.setItem("atlas.rate", "1.2");
  mockFetch({
    ...base, "/api/dashboard": emptyDashboard,
    "POST /api/assistant/chat": chatReply("Buenos días, Lance. Hoy tienes dos tareas. ¿Empezamos por la más urgente?", "ai", "qwen2.5:7b"),
  });
  renderAt("/");
  fireEvent.change(await screen.findByLabelText("Mensaje para ATLAS"), { target: { value: "Buenos días" } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
  await waitFor(() => expect(spoken.map((s) => s.text).join(" ")).toContain("¿Empezamos por la más urgente?"), { timeout: 5000 });
  expect(spoken.map((s) => s.text).join(" ")).toBe("Buenos días, Lance. Hoy tienes dos tareas. ¿Empezamos por la más urgente?");
  expect(spoken.length).toBeGreaterThan(1); // empezó a hablar antes de terminar la respuesta
  expect(spoken.every((s) => s.rate === 1.2 && s.voice === "Mónica (Mejorada)")).toBe(true);
});

const task = (over: Record<string, unknown> = {}) => ({
  id: 1, title: "Llamar al gestor", description: null, priority: "critical", status: "pending", category: null,
  due_at: "2030-11-27T10:00:00+01:00", due_date: "2030-11-27", all_day: false, overdue: false,
  reminder_at: "2030-11-27T10:00:00+01:00", goal_id: null, goal_title: null, project_id: null, project_name: null,
  created_at: "2026-11-23T10:00:00+01:00", completed_at: null, ...over,
});
const summaryDay = { period: "day", from: "", to: "", completed: 2, completed_titles: [], created: 1, due: 3, due_open: 1, overdue: 1, completion_rate: 0.67 };

test("«apúntame…» crea la tarea y permite deshacer", async () => {
  const calls = mockFetch({
    ...base, "/api/dashboard": emptyDashboard,
    "POST /api/assistant/chat": chatReply("Apuntado: «Llamar al gestor» para el viernes 27/11 a las 10:00.", "tasks" as never, null,
      [{ type: "task", action: "created", task: task() }]),
    "DELETE /api/tasks/1": {},
  });
  renderAt("/");
  fireEvent.change(await screen.findByLabelText("Mensaje para ATLAS"), { target: { value: "apúntame llamar al gestor el viernes a las 10" } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
  expect(await screen.findByText(/Tarea creada/, {}, { timeout: 5000 })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Deshacer" }));
  expect(await screen.findByText("Tarea eliminada.")).toBeInTheDocument();
  expect(calls.some((c) => c.url === "/api/tasks/1" && c.init?.method === "DELETE")).toBe(true);
});

test("página Tareas: agrupa, completa y crea con lenguaje natural", async () => {
  const calls = mockFetch({
    ...base,
    "/api/tasks?": { items: [
      task({ id: 2, title: "Pagar seguro", priority: "high", overdue: true, due_date: "2020-01-01", due_at: "2020-01-01T23:59:59+01:00", all_day: true, reminder_at: null }),
      task({ id: 3, title: "Estudiar inglés", priority: "medium", due_at: null, due_date: null, reminder_at: null }),
    ], categories: ["trabajo"] },
    "/api/goals?": { items: [] },
    "/api/tasks/summary?": summaryDay,
    "POST /api/tasks/2/complete": task({ id: 2, status: "done" }),
    "POST /api/tasks/parse": { title: "Preparar oferta", priority: "high", category: "trabajo", all_day: true, due_local: "2030-11-27T23:59:59" },
    "POST /api/tasks/quick": task({ id: 9, title: "Preparar oferta", all_day: true, due_at: "2030-11-27T23:59:59+01:00" }),
  });
  renderAt("/tasks");
  expect(await screen.findByText("Pagar seguro")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /Atrasadas/ })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /Sin fecha/ })).toBeInTheDocument();
  expect(screen.getByText("67 %")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Marcar como hecha: Pagar seguro" }));
  expect(await screen.findByText(/Hecha: «Pagar seguro»/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Nueva tarea en lenguaje natural"), { target: { value: "preparar oferta el jueves importante #trabajo" } });
  expect(await screen.findByText("Preparar oferta", { selector: "strong" }, { timeout: 3000 })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Añadir tarea" }));
  expect(await screen.findByText(/Creada: «Preparar oferta»/)).toBeInTheDocument();
  expect(JSON.parse(calls.find((c) => c.url === "/api/tasks/quick")!.init!.body as string)).toEqual({ text: "preparar oferta el jueves importante #trabajo" });
});

test("objetivos: muestra ritmo, necesidad semanal y registra progreso", async () => {
  const goal = {
    id: 4, title: "Ahorrar 5000 €", description: null, area: "finanzas", kind: "numeric", unit: "€", start_value: 0,
    target_value: 5000, current_value: 1000, start_date: "2026-01-01", deadline: "2026-12-31", status: "active",
    tasks_total: 0, tasks_done: 0, achieved_at: null,
    metrics: { progress: 0.2, current: 1000, target: 5000, start: 0, elapsed_days: 180, pace: "behind", remaining: 4000,
      rate_per_week: 38.89, projected_date: "2028-07-01", days_left: 180, expected_progress: 0.5, required_per_week: 155.56 },
  };
  const calls = mockFetch({
    ...base, "/api/goals?": { items: [goal] },
    "POST /api/goals/4/progress": { ...goal, current_value: 1200 },
  });
  renderAt("/tasks?tab=goals");
  fireEvent.click(await screen.findByRole("tab", { name: "Objetivos" }));
  expect(await screen.findByText("🎯 Ahorrar 5000 €")).toBeInTheDocument();
  expect(screen.getByText("Por detrás")).toBeInTheDocument();
  expect(screen.getByText("20 %")).toBeInTheDocument();
  expect(screen.getByText(/155,56 €/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Registrar progreso de Ahorrar 5000 €"), { target: { value: "200" } });
  fireEvent.click(screen.getByRole("button", { name: "Registrar" }));
  expect(await screen.findByText(/Progreso registrado/)).toBeInTheDocument();
  expect(JSON.parse(calls.find((c) => c.url === "/api/goals/4/progress")!.init!.body as string)).toEqual({ delta: 200 });
});

test("recordatorio vencido aparece como aviso con acción «Hecha»", async () => {
  const calls = mockFetch({
    ...base, "/api/dashboard": emptyDashboard,
    "/api/tasks/reminders/due": { items: [task({ title: "Sacar al perro" })] },
    "POST /api/tasks/1/complete": task({ status: "done" }),
  });
  renderAt("/");
  expect(await screen.findByText("Sacar al perro")).toBeInTheDocument();
  fireEvent.click(within(screen.getByRole("region", { name: "Recordatorios" })).getByRole("button", { name: "Hecha" }));
  await waitFor(() => expect(screen.queryByText("Sacar al perro")).not.toBeInTheDocument());
  expect(calls.some((c) => c.url === "/api/tasks/1/complete")).toBe(true);
});

const routine = {
  id: 1, name: "Pecho + hombro + tríceps", weekday: 5, weekday_name: "sábado", notes: null, active: true,
  exercises: [{ id: 10, exercise_id: 1, name: "Press inclinado", muscle: "pecho", per_side: false, position: 0, warmup_sets: 2,
    sets: 2, reps_min: 8, reps_max: null, weight: 40, notes: "Objetivo: 46 kg antes de 2027", done: false,
    last: { date: "2026-11-21", sets: [{ reps: 8, weight: 40, rir: 2 }], top: { reps: 8, weight: 40 } } }],
};

test("gimnasio: importa la rutina en un clic", async () => {
  const calls = mockFetch({
    ...base,
    "/api/gym/today": { date: "2026-11-23", weekday_name: "lunes", rest_day: true, routine: null, session_id: null, next: null },
    "/api/gym/routines": { items: [], templates: [{ id: "rutina_4_dias", name: "Rutina 4 días (Sáb · Dom · Mié · Jue)", description: null,
      days: [{ name: "Pecho + hombro + tríceps", weekday: 5 }] }] },
    "/api/gym/exercises": { items: [], muscles: [] },
    "POST /api/gym/routines/import/rutina_4_dias": { items: [routine] },
  });
  renderAt("/gym");
  fireEvent.click(await screen.findByRole("tab", { name: "Rutinas" }));
  fireEvent.click(await screen.findByRole("button", { name: "Importar esta rutina" }));
  expect(await screen.findByText(/Rutina importada/)).toBeInTheDocument();
  expect(calls.some((c) => c.url === "/api/gym/routines/import/rutina_4_dias")).toBe(true);
});

test("gimnasio hoy: ver objetivo, última vez y registrar una serie", async () => {
  const calls = mockFetch({
    ...base,
    "/api/gym/today": { date: "2026-11-28", weekday_name: "sábado", rest_day: false, routine, session_id: null, next: null },
    "/api/gym/routines": { items: [routine], templates: [] },
    "POST /api/gym/sets": { id: 5, session_id: 3, e1rm: 53.3 },
    "POST /api/gym/log-text": { parsed: [{ exercise_id: 1, name: "Press inclinado", reps: [8, 8], weight: 42.5, rir: 2, warmup_sets: 0, per_side: false, notes: [] }], session: null },
  });
  renderAt("/gym");
  expect(await screen.findByText("Hoy: Pecho + hombro + tríceps")).toBeInTheDocument();
  expect(screen.getByText(/Objetivo: 2 calent\. \+ 2×8 · 40 kg/)).toBeInTheDocument();
  expect(screen.getByText(/Última vez/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Peso de Press inclinado"), { target: { value: "42,5" } });
  fireEvent.change(screen.getByLabelText("RIR de Press inclinado"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "+ Serie" }));
  const st = await screen.findByText(/^Registrado:/);
  expect(st).toHaveTextContent("Registrado: Press inclinado: 8 reps × 42,5 kg · RIR 2");
  expect(JSON.parse(calls.find((c) => c.url === "/api/gym/sets")!.init!.body as string))
    .toEqual({ exercise_id: 1, reps: 8, weight: 42.5, rir: 2, routine_id: null });
  // registro por texto con vista previa
  fireEvent.change(screen.getByLabelText("Entreno en texto"), { target: { value: "inclinado 2x8 42,5kg rir 2" } });
  expect(await screen.findByText(/2×\(8\/8\)/, {}, { timeout: 3000 })).toBeInTheDocument();
});

test("pantalla de arranque: al pulsar Iniciar, ATLAS da la bienvenida en voz alta", async () => {
  localStorage.setItem("atlas.welcome", "1");
  const spoken: string[] = [];
  class FakeUtterance { text: string; rate = 1; lang = ""; voice?: unknown; onend?: () => void; onerror?: () => void; onstart?: () => void;
    constructor(t: string) { this.text = t; } }
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
  vi.stubGlobal("speechSynthesis", { getVoices: () => [], cancel: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(),
    speak: (u: FakeUtterance) => { spoken.push(u.text); u.onend?.(); } });
  mockFetch({ ...base, "/api/dashboard": emptyDashboard,
    "/api/assistant/welcome": { intent: "welcome", mode: "local", reply: "Buenas tardes, Lance. Bienvenido de nuevo. ¿En qué te ayudo?" } });
  renderAt("/");
  expect(await screen.findByRole("dialog", { name: "Inicio de ATLAS" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Iniciar ATLAS" }));
  await waitFor(() => expect(spoken.join(" ")).toContain("Bienvenido de nuevo"), { timeout: 3000 });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(sessionStorage.getItem("atlas.booted")).toBe("1");
});

test("la bienvenida espera a que el navegador cargue las voces y usa la elegida", async () => {
  localStorage.setItem("atlas.welcome", "1");
  localStorage.setItem("atlas.voice", "monica-enh");
  const spoken: { text: string; voice?: string }[] = [];
  let voices: { name: string; lang: string; voiceURI: string; localService: boolean }[] = [];
  const listeners: (() => void)[] = [];
  class FakeUtterance { text: string; rate = 1; lang = ""; voice?: { name: string }; onend?: () => void; onerror?: () => void; onstart?: () => void;
    constructor(t: string) { this.text = t; } }
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
  vi.stubGlobal("speechSynthesis", {
    getVoices: () => voices, cancel: vi.fn(),
    addEventListener: (_: string, fn: () => void) => listeners.push(fn), removeEventListener: vi.fn(),
    speak: (u: FakeUtterance) => { spoken.push({ text: u.text, voice: u.voice?.name }); u.onend?.(); },
  });
  mockFetch({ ...base, "/api/dashboard": emptyDashboard,
    "/api/assistant/welcome": { intent: "welcome", mode: "local", reply: "Bienvenido de nuevo." } });
  renderAt("/");
  fireEvent.click(await screen.findByRole("button", { name: "Iniciar ATLAS" }));
  await new Promise((r) => setTimeout(r, 100));
  expect(spoken).toEqual([]); // aún no hay voces: espera en lugar de usar la voz por defecto
  voices = [{ name: "Eddy (Spanish (Spain))", lang: "es-ES", voiceURI: "eddy", localService: true },
    { name: "Mónica (Mejorada)", lang: "es-ES", voiceURI: "monica-enh", localService: true }];
  listeners.forEach((fn) => fn());
  await waitFor(() => expect(spoken).toEqual([{ text: "Bienvenido de nuevo.", voice: "Mónica (Mejorada)" }]));
});
