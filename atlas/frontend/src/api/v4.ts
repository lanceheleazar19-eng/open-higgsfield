/** ATLAS 4.0 — tipos y llamadas a la API (agentes, conocimiento, investigación, workflows, modelos, seguridad…). */
import { ApiError, request, requestEmpty } from "./client";
import type { MemoryItem, TaskItem } from "./types";

export type Level = "READ" | "WRITE" | "EXECUTE" | "ADMIN";
export interface AgentStep { agent: string; tool: string; level: Level; ok: boolean; ms: number; summary: string; shared?: boolean }
export interface AgentRunItem {
  id: number; request: string; agents: string[]; agent_names: string[]; intent: string | null; status: string;
  steps: AgentStep[]; result: string | null; model: string | null; duration_ms: number | null; source: string; created_at: string;
}
export interface AgentInfo {
  id: string; name: string; role: string; limits: string; runs: number; last: string | null;
  tools: { name: string; level: Level; description: string }[]; actions: { name: string; level: Level; description: string }[];
}
export interface AgentCatalog { core: { name: string; role: string }; agents: AgentInfo[]; levels: Record<Level, string>; policy: Record<Level, string> }
export interface ApprovalItem {
  id: number; action: string; level: Level; summary: string; payload: Record<string, unknown>; status: string;
  result: string | null; workflow_run_id: number | null; created_at: string; decided_at: string | null;
}
export interface DocItem {
  id: number; title: string; filename: string | null; kind: string; url: string | null; project_id: number | null;
  size_bytes: number; chars: number; chunks: number; embedded: boolean; status: string; error: string | null; created_at: string;
  preview?: string;
}
export interface DocHit { document_id: number; title: string; kind: string; url: string | null; chunk: number; text: string; score: number; flagged: boolean }
export interface GraphNode { id: string; type: string; kind: string; label: string; degree: number; status?: string; project_id?: number | null }
export interface GraphEdge { source: string; target: string; label: string; origin: string }
export interface GraphData { nodes: GraphNode[]; edges: GraphEdge[]; types: Record<string, string> }
export interface ResearchSource {
  id: number; url: string; title: string; domain: string; engine: string; reliability: "alta" | "media" | "baja";
  snippet: string; excerpt: string; read?: boolean; error?: string; accessed_at?: string; claims?: string[];
  relevant?: boolean | null; published?: string | null; flagged?: boolean; subquestion?: string;
}
export interface ResearchReport {
  summary: string; conclusions: { text: string; sources: number[]; confidence: string }[];
  contradictions: { text: string; sources: number[] }[]; unconfirmed: string[]; confidence: string; mode: "ai" | "extractive"; subquestions: string[];
}
export interface ResearchItem {
  id: number; question: string; status: string; step: string | null; step_label: string | null; progress: number;
  confidence: string | null; model: string | null; error: string | null; project_id: number | null; created_at: string;
  updated_at: string | null; sources_count: number; report?: ResearchReport | null; sources?: ResearchSource[];
  subquestions?: string[]; search_errors?: string[];
}
export interface WfStep { type: string; params?: Record<string, unknown> }
export interface WorkflowItem {
  id: number; key: string | null; name: string; description: string | null; steps: WfStep[]; schedule: string | null;
  enabled: boolean; builtin: boolean; last_run_at: string | null; needs: string[];
}
export interface WfRun {
  id: number; workflow_id: number; workflow: string | null; status: string; trigger: string; params: Record<string, unknown>;
  log: { step: number; type: string; level: Level; ok: boolean | null; output: string; ms?: number }[]; output: string | null;
  started_at: string; finished_at: string | null;
}
export interface StepType { level: Level; label: string; params: string[] }
export interface ProviderInfo { id: string; label: string; local: boolean; configured: boolean; connected: boolean | null; model: string | null; models: string[]; note: string | null }
export interface RouterConfig {
  privacy: "local_only" | "local_first" | "best_quality"; tasks: Record<string, { provider: string; model: string }>;
  providers: Record<string, { model: string }>; prices: Record<string, { in: number; out: number }>; monthly_limit_usd: number | null;
}
export interface ModelsStatus {
  config: RouterConfig; tasks: Record<string, string>; privacy_options: Record<string, string>; providers: ProviderInfo[];
  routes: Record<string, string>; month_cost_usd: number;
}
export interface ModelUsage {
  by_model: { provider: string; model: string; calls: number; avg_ms: number; errors: number; cost_usd: number | null; tokens_in: number | null; tokens_out: number | null }[];
  recent: { provider: string; model: string; task: string; ok: boolean; error: string | null; latency_ms: number; cost_usd: number | null; created_at: string }[];
}
export interface SecurityInfo { levels: Record<Level, string>; policy: Record<Level, string>; never: string[]; backups: { name: string; size: number; created_at: string }[]; backups_dir: string }
export interface Insight { id: string; rule: string; level: string; module: string; link: string; title: string; what: string; why: string; data: string; recommendation: string }
export interface NotificationItem { id: number; title: string; body: string; level: string; link: string | null; read: boolean; created_at: string }
export interface ProjectItem {
  id: number; name: string; description: string | null; status: string; created_at: string; updated_at: string | null;
  tasks_total: number; tasks_done: number; tasks_open: number; tasks_overdue: number; progress: number | null;
  notes: number; documents: number; research: number;
}
export interface ProjectDetail extends Omit<ProjectItem, "notes" | "documents" | "research"> {
  tasks: TaskItem[]; notes: MemoryItem[]; documents: DocItem[]; research: ResearchItem[];
  entities: { id: number; name: string; kind: string }[]; history: { module: string; summary: string; created_at: string }[];
}
export interface CommandCenter {
  core: { state: string; ai_reachable: boolean; model: string | null; note: string | null; privacy: string };
  model_calls_24h: { count: number; avg_ms: number; errors: number }; agents_active_24h: string[];
  recent_agent_runs: AgentRunItem[]; memory: Record<string, number>; processes: { kind: string; id: number; label: string; step: string | null; status: string }[];
  research_total: number; research_running: number; agent_runs_24h: number;
  pending_tasks: number; approvals_pending: number; notifications_unread: number; insights: Insight[];
  recent_conversations: { id: number; title: string; updated_at: string }[];
  activity: { module: string; summary: string; created_at: string }[]; workflows_scheduled: { id: number; name: string; schedule: string }[];
}
export interface Analytics {
  fitness: { weeks: { week: string; sessions: number; tonnage: number }[]; has_data: boolean };
  finance: { months: { month: string; income_cents: number; expense_cents: number }[]; current: { income_cents: number; expense_cents: number; net_cents: number; savings_rate: number | null }; has_data: boolean };
  trading: { overall: { trades: number; win_rate: number | null; pnl: number; profit_factor: number | null; avg_r: number | null }; curve: { date: string; equity: number }[];
    by_strategy: { strategy: string; trades: number; pnl: number; win_rate: number | null }[]; max_drawdown: number; has_data: boolean; simulation: true };
  projects: { items: { id: number; name: string; total: number; done: number; overdue: number; progress: number | null }[]; done_by_week: { week: string; done: number }[]; has_data: boolean };
}
export interface SearchResults {
  tasks: { id: number; title: string; status: string }[]; memories: { id: number; content: string }[];
  documents: { id: number; title: string; snippet: string }[]; projects: { id: number; name: string }[]; research: { id: number; question: string }[];
}

const json = (body: unknown, method = "POST") => ({ method, body: JSON.stringify(body) });

async function upload<T>(path: string, files: File[], extra: Record<string, string> = {}): Promise<T> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
  let res: Response;
  try { res = await fetch(path, { method: "POST", body: fd }); } catch { throw new ApiError(0, "No se puede conectar con el núcleo de ATLAS"); }
  if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail; } catch { /* */ } throw new ApiError(res.status, String(d)); }
  return res.json();
}

export const v4 = {
  agents: () => request<AgentCatalog>("/api/agents"),
  runAgents: (text: string, agents?: string[]) => request<AgentRunItem>("/api/agents/run", json({ text, agents })),
  agentRuns: () => request<AgentRunItem[]>("/api/agents/runs"),
  approvals: (status = "pending") => request<ApprovalItem[]>(`/api/agents/approvals?status=${status}`),
  decide: (id: number, approve: boolean) => request<ApprovalItem>(`/api/agents/approvals/${id}`, json({ approve })),

  documents: (projectId?: number) => request<DocItem[]>(`/api/knowledge/documents${projectId ? `?project_id=${projectId}` : ""}`),
  document: (id: number) => request<DocItem>(`/api/knowledge/documents/${id}`),
  uploadDocs: (files: File[], projectId?: number | null) => upload<DocItem[]>("/api/knowledge/documents", files, projectId ? { project_id: String(projectId) } : {}),
  addUrl: (url: string, project_id?: number | null) => request<DocItem>("/api/knowledge/documents/url", json({ url, project_id })),
  addNote: (title: string, text: string, project_id?: number | null) => request<DocItem>("/api/knowledge/documents/note", json({ title, text, project_id })),
  deleteDoc: (id: number) => requestEmpty(`/api/knowledge/documents/${id}`, { method: "DELETE" }),
  searchDocs: (q: string) => request<DocHit[]>(`/api/knowledge/search?q=${encodeURIComponent(q)}`),
  graph: (projectId?: number | null) => request<GraphData>(`/api/knowledge/graph${projectId ? `?project_id=${projectId}` : ""}`),
  addEntity: (name: string, kind: string, project_id?: number | null) => request<{ id: number; node: string }>("/api/knowledge/entities", json({ name, kind, project_id })),
  deleteEntity: (id: number) => requestEmpty(`/api/knowledge/entities/${id}`, { method: "DELETE" }),
  addRelation: (source: string, target: string, label: string) => request<{ id: number }>("/api/knowledge/relations", json({ source, target, label })),
  deleteRelation: (id: number) => requestEmpty(`/api/knowledge/relations/${id}`, { method: "DELETE" }),
  importMarkdown: (files: File[]) => upload<{ documents: number; links: number }>("/api/knowledge/markdown/import", files),

  research: () => request<ResearchItem[]>("/api/research"),
  researchOne: (id: number) => request<ResearchItem>(`/api/research/${id}`),
  startResearch: (question: string, project_id?: number | null) => request<ResearchItem>("/api/research", json({ question, project_id })),
  resumeResearch: (id: number) => request<ResearchItem>(`/api/research/${id}/resume`, { method: "POST" }),
  saveResearch: (id: number) => request<{ memory_id: number; created: boolean }>(`/api/research/${id}/save`, { method: "POST" }),
  deleteResearch: (id: number) => requestEmpty(`/api/research/${id}`, { method: "DELETE" }),

  workflows: () => request<{ workflows: WorkflowItem[]; step_types: Record<string, StepType> }>("/api/workflows"),
  saveWorkflow: (w: Omit<WorkflowItem, "id" | "key" | "builtin" | "last_run_at" | "needs">, id?: number) =>
    request<WorkflowItem>(id ? `/api/workflows/${id}` : "/api/workflows", json(w, id ? "PUT" : "POST")),
  deleteWorkflow: (id: number) => requestEmpty(`/api/workflows/${id}`, { method: "DELETE" }),
  runWorkflow: (id: number, params: Record<string, unknown> = {}) => request<WfRun>(`/api/workflows/${id}/run`, json({ params })),
  wfRuns: () => request<WfRun[]>("/api/workflows/runs"),

  models: () => request<ModelsStatus>("/api/models"),
  testProvider: (p: string) => request<{ connected: boolean; error: string | null; models: string[] }>(`/api/models/${p}/test`, { method: "POST" }),
  saveKey: (p: string, api_key: string) => request<{ configured: boolean; stored_in: string }>(`/api/models/${p}/key`, json({ api_key }, "PUT")),
  deleteKey: (p: string) => requestEmpty(`/api/models/${p}/key`, { method: "DELETE" }),
  saveRouter: (c: Partial<RouterConfig> & { clear_limit?: boolean }) => request<RouterConfig>("/api/models/config", json(c, "PUT")),
  usage: () => request<ModelUsage>("/api/models/usage"),

  security: () => request<SecurityInfo>("/api/security"),
  savePolicy: (WRITE: string, EXECUTE: string) => request<Record<Level, string>>("/api/security/policy", json({ WRITE, EXECUTE }, "PUT")),
  activity: () => request<{ id: number; module: string; action: string; summary: string; created_at: string }[]>("/api/security/activity"),
  backup: () => request<{ name: string }>("/api/security/backups", { method: "POST" }),

  insights: () => request<{ items: Insight[]; config: { enabled: boolean; rules: Record<string, boolean> }; rules: Record<string, string> }>("/api/insights"),
  insightsConfig: (enabled: boolean, rules: Record<string, boolean>) => request<{ enabled: boolean }>("/api/insights/config", json({ enabled, rules }, "PUT")),
  dismissInsight: (id: string) => request<{ ok: boolean }>(`/api/insights/${encodeURIComponent(id)}/dismiss`, { method: "POST" }),
  notifications: () => request<{ unread: number; items: NotificationItem[] }>("/api/notifications"),
  readNotifications: () => request<{ marked: number }>("/api/notifications/read", { method: "POST" }),

  projects: () => request<ProjectItem[]>("/api/projects"),
  project: (id: number) => request<ProjectDetail>(`/api/projects/${id}`),
  saveProject: (p: { name: string; description?: string | null; status?: string }, id?: number) =>
    request<ProjectItem>(id ? `/api/projects/${id}` : "/api/projects", json({ status: "active", ...p }, id ? "PUT" : "POST")),
  deleteProject: (id: number) => requestEmpty(`/api/projects/${id}`, { method: "DELETE" }),
  projectNote: (id: number, content: string, kind = "note") => request<{ id: number }>(`/api/projects/${id}/notes`, json({ content, kind })),
  projectTask: (id: number, title: string, priority = "medium") => request<TaskItem>(`/api/projects/${id}/tasks`, json({ title, priority })),
  projectAnalysis: (id: number) => request<{ report: string }>(`/api/projects/${id}/analysis`, { method: "POST" }),

  commandCenter: () => request<CommandCenter>("/api/command-center"),
  analytics: () => request<Analytics>("/api/analytics"),
  search: (q: string) => request<SearchResults>(`/api/search?q=${encodeURIComponent(q)}`),
};
