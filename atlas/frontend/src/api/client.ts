import type {
  AiStatus, AssistantReply, ChatEvent, ConversationSummary, Dashboard, Health, MemoryItem, MemoryKind,
  MemorySuggestion, ModuleInfo, Prefs, StoredMessage, GoalItem, Priority, TaskItem, TaskSummary, WeekPlan,
} from "./types";

export interface TaskInput {
  title?: string; description?: string | null; priority?: Priority; category?: string | null;
  due_at?: string | null; due_date?: string | null; reminder_at?: string | null; goal_id?: number | null;
}
export interface GoalInput {
  title: string; description?: string | null; area?: string | null; kind: "numeric" | "milestones"; unit?: string | null;
  start_value?: number; target_value?: number | null; current_value?: number | null; deadline?: string | null;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "No se puede conectar con el núcleo de ATLAS");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

async function requestEmpty(path: string, init?: RequestInit): Promise<void> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "No se puede conectar con el núcleo de ATLAS");
  }
  if (!res.ok) throw new ApiError(res.status, `Error ${res.status}`);
}

export const api = {
  health: () => request<Health>("/api/system/health"),
  modules: () => request<ModuleInfo[]>("/api/system/modules"),
  dashboard: () => request<Dashboard>("/api/dashboard"),
  prefs: () => request<Prefs>("/api/settings"),
  updatePrefs: (p: Partial<Prefs>) => request<Prefs>("/api/settings", { method: "PUT", body: JSON.stringify(p) }),
  ask: (text: string) => request<AssistantReply>("/api/assistant/query", { method: "POST", body: JSON.stringify({ text }) }),
  briefing: () => request<AssistantReply>("/api/assistant/briefing"),
  aiStatus: () => request<AiStatus>("/api/ai/status"),
  chat: chatStream,
  memories: (p: { q?: string; kind?: string; include_expired?: boolean } = {}) => {
    const qs = new URLSearchParams();
    if (p.q) qs.set("q", p.q);
    if (p.kind) qs.set("kind", p.kind);
    if (p.include_expired) qs.set("include_expired", "true");
    return request<{ items: MemoryItem[]; memories: number; conversations: number }>(`/api/memory?${qs}`);
  },
  createMemory: (m: { content: string; kind: MemoryKind; expires_at?: string | null; source?: "manual" | "suggested" }) =>
    request<{ memory: MemoryItem; created: boolean }>("/api/memory", { method: "POST", body: JSON.stringify(m) }),
  updateMemory: (id: number, p: { content?: string; kind?: MemoryKind; expires_at?: string | null; permanent?: boolean }) =>
    request<MemoryItem>(`/api/memory/${id}`, { method: "PATCH", body: JSON.stringify(p) }),
  deleteMemory: (id: number) => requestEmpty(`/api/memory/${id}`, { method: "DELETE" }),
  purgeExpired: () => request<{ deleted: number }>("/api/memory/purge-expired", { method: "POST" }),
  suggestMemories: (conversation_id: number) =>
    request<{ suggestions: MemorySuggestion[] }>("/api/memory/suggest", { method: "POST", body: JSON.stringify({ conversation_id }) }),
  conversations: () => request<{ items: ConversationSummary[] }>("/api/conversations"),
  searchConversations: (q: string) => request<{ hits: StoredMessage[] }>(`/api/conversations?q=${encodeURIComponent(q)}`),
  conversation: (id: number) => request<{ id: number; title: string; created_at: string; messages: StoredMessage[] }>(`/api/conversations/${id}`),
  deleteConversation: (id: number) => requestEmpty(`/api/conversations/${id}`, { method: "DELETE" }),
  exportUrl: "/api/memory/export",
  tasks: (p: { status?: "open" | "done" | "all"; q?: string; goal_id?: number; category?: string } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== "") qs.set(k, String(v)); });
    return request<{ items: TaskItem[]; categories: string[] }>(`/api/tasks?${qs}`);
  },
  createTask: (t: TaskInput) => request<TaskItem>("/api/tasks", { method: "POST", body: JSON.stringify(t) }),
  quickTask: (text: string) => request<TaskItem>("/api/tasks/quick", { method: "POST", body: JSON.stringify({ text }) }),
  parseTask: (text: string) => request<{ title: string; priority: Priority; category: string | null; all_day: boolean; due_local: string | null }>(
    "/api/tasks/parse", { method: "POST", body: JSON.stringify({ text }) }),
  updateTask: (id: number, t: TaskInput) => request<TaskItem>(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(t) }),
  completeTask: (id: number) => request<TaskItem>(`/api/tasks/${id}/complete`, { method: "POST" }),
  reopenTask: (id: number) => request<TaskItem>(`/api/tasks/${id}/reopen`, { method: "POST" }),
  deleteTask: (id: number) => requestEmpty(`/api/tasks/${id}`, { method: "DELETE" }),
  taskSummary: (period: "day" | "week") => request<TaskSummary>(`/api/tasks/summary?period=${period}`),
  weekPlan: (perDay = 4) => request<WeekPlan>(`/api/tasks/plan?per_day=${perDay}`),
  applyPlan: (assignments: { task_id: number; date: string }[]) =>
    request<{ scheduled: number }>("/api/tasks/plan/apply", { method: "POST", body: JSON.stringify({ assignments }) }),
  dueReminders: () => request<{ items: TaskItem[] }>("/api/tasks/reminders/due"),
  goals: (status: "active" | "all" = "active") => request<{ items: GoalItem[] }>(`/api/goals?status=${status}`),
  goal: (id: number) => request<GoalItem>(`/api/goals/${id}`),
  createGoal: (g: GoalInput) => request<GoalItem>("/api/goals", { method: "POST", body: JSON.stringify(g) }),
  updateGoal: (id: number, g: Partial<GoalInput> & { status?: GoalItem["status"] }) =>
    request<GoalItem>(`/api/goals/${id}`, { method: "PATCH", body: JSON.stringify(g) }),
  goalProgress: (id: number, p: { value?: number; delta?: number; note?: string }) =>
    request<GoalItem>(`/api/goals/${id}/progress`, { method: "POST", body: JSON.stringify(p) }),
  deleteGoal: (id: number) => requestEmpty(`/api/goals/${id}`, { method: "DELETE" }),
  timezones: () => request<string[]>("/api/settings/timezones"),
};

/** Conversación en streaming (NDJSON): llama a `onEvent` por cada evento recibido. */
async function chatStream(text: string, conversationId: number | null, onEvent: (e: ChatEvent) => void, signal?: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(conversationId ? { text, conversation_id: conversationId } : { text }),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "No se puede conectar con el núcleo de ATLAS");
  }
  if (!res.ok || !res.body) throw new ApiError(res.status, `Error ${res.status} del núcleo`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (value) buf += decoder.decode(value, { stream: true });
    let nl: number;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (line) onEvent(JSON.parse(line) as ChatEvent);
    }
    if (done) break;
  }
  if (buf.trim()) onEvent(JSON.parse(buf) as ChatEvent);
}
