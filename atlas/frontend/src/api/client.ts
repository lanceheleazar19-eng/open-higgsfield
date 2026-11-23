import type {
  AiStatus, AssistantReply, ChatEvent, ConversationSummary, Dashboard, Health, MemoryItem, MemoryKind,
  MemorySuggestion, ModuleInfo, Prefs, StoredMessage,
} from "./types";

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
