import { request } from "./client";

export interface TelemetryData {
  generated_at: string;
  system: { cpu_percent?: number; cpu_count?: number; load?: number[] | null; ram_percent?: number; ram_used?: number; ram_total?: number;
    swap_percent?: number; process_rss?: number; process_threads?: number; uptime_s?: number; db_bytes?: number | null; disk_free?: number; disk_percent?: number };
  core: { online: boolean; ai_configured: boolean; model: string | null; provider: string | null; privacy: string };
  ollama: { reachable: boolean; ping_ms: number | null; installed: number | null; loaded: { name: string; vram: number; size: number }[] | null };
  latency: { last_ms: number | null; last_model: string | null; last_at: string | null; avg_24h: number | null; max_24h: number | null;
    calls_24h: number; errors_24h: number; tokens_out_24h: number; series: number[] };
  memory: { memories: number; documents: number; chunks: number; entities: number; relations: number; recalled_24h: number; recalled: { text: string; at: string }[] };
  agents: { runs_24h: number; active: string[]; last: { request: string; agents: string[]; status: string; ms: number | null; at: string } | null };
  processes: { kind: string; label: string; state: string }[];
  connections: { name: string; state: "ok" | "off" | "key" | "error"; detail: string | null }[];
  events: { ts: string; module: string; action: string; text: string }[];
  today: { by_module: Record<string, number>; events: number; tasks_done: number; messages: number; model_calls: number; notifications: number };
}

export const telemetry = () => request<TelemetryData>("/api/telemetry");
