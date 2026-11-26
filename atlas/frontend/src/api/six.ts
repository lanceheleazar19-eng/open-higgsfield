/** VISTAN SIX · LIVE EXPERIMENTATION — agentes autónomos de PAPER TRADING (dinero virtual) sobre el motor del Trading Desk. */
import { request } from "./client";

export interface SixMetrics {
  trades: number; verdict: "sin_datos" | "insuficiente" | "sin_ventaja" | "no_significativa" | "ventaja"; verdict_text: string;
  wins?: number; losses?: number; win_rate?: number; net?: number; profit_factor?: number | null; expectancy?: number; expectancy_r?: number | null;
  avg_win?: number | null; avg_loss?: number | null; std?: number | null; t_stat?: number | null; max_dd?: number; max_dd_pct?: number | null;
  return_pct?: number | null; costs?: number; first_half_exp?: number | null; second_half_exp?: number | null;
}
export interface SixPosition {
  id: number; symbol: string; side: "long" | "short"; qty: number; entry: number; sl: number | null; tp: number | null; status: "open" | "closed";
  strategy: string; timeframe: string | null; fees: number; realized: number | null; exit: number | null; exit_reason: string | null;
  opened_at: string; closed_at: string | null; data_kind: string | null; account: string | null; price?: number | null; unrealized?: number | null;
}
export interface SixLedger { allocation: number; realized: number; unrealized: number; equity: number; reserved: number; available: number; open: number; unpriced: number; fees: number }
export interface SixAnalyzing { at: string; timeframe: string; price?: number | null; source?: string | null; kind?: string | null; bar_time?: number | null; error?: string | null; signal?: string; values?: Record<string, number | string | boolean | null> }
export interface SixAgent {
  key: string; name: string; account: "safe" | "experimental"; family: string; family_label: string; enabled: boolean;
  status: "idle" | "running" | "paused" | "halted"; halt_reason: string | null; symbols: string[]; strategy: string;
  variant: { timeframe: string; params: Record<string, number> }; variants: { id: string; timeframe: string; params: Record<string, number> }[];
  allocation_pct: number; risk_pct: number; max_positions: number; max_dd_pct: number; max_daily_loss_pct: number; ledger: SixLedger | null;
  analyzing: Record<string, SixAnalyzing>; rotations: { at: string; from: string; to: string; evidence: Record<string, number | null> }[];
  last_run_at: string | null; last_error: string | null; metrics: SixMetrics | null; metrics_current: SixMetrics | null; open: SixPosition[];
  last_decision: SixDecision | null; next_bar_at: number | null;
}
export interface SixDecision { id: number; agent: string; strategy: string | null; symbol: string | null; action: string; status: "executed" | "skipped" | "rejected" | "error" | "info"; reason: string; data: Record<string, unknown> | null; order_id: number | null; position_id: number | null; at: string }
export interface SixAccount { id: number; name: string; initial_capital: number; equity: number; cash: number; return_pct: number | null; open_positions: number; commission_pct: number; commission_fixed: number; slippage_bps: number; enforce_limits: boolean; max_risk_pct: number | null; max_exposure_pct: number | null }
export interface SixStatus {
  config: { autonomous: boolean; interval_min: number; authorized_at: string | null }; kill: boolean; agents: SixAgent[];
  accounts: Partial<Record<"safe" | "experimental", SixAccount>>; strategies: (SixMetrics & { strategy: string; agent: string })[];
  leaderboard: (SixMetrics & { key: string; name: string; account: string; equity?: number; allocation?: number })[]; recent: SixDecision[]; rules: string[];
}
export interface SixValidation { id: number; agent: string; strategy: string; symbol: string; timeframe: string; at: string;
  result: { in_sample: SixMetrics; out_of_sample: SixMetrics; bars: number; split_bar: number; from: number; split_at: number; to: number; source: string | null; kind: string | null; costs: Record<string, number>; note: string } }
export interface SixInsights { groups: Record<string, Record<string, { trades: number; net: number; expectancy: number }>>; avg_hold_h: number | null; notes: string[]; trades: number }

const j = (body: unknown, method = "POST"): RequestInit => ({ method, body: JSON.stringify(body) });
const qs = (p: Record<string, string | undefined>) => { const s = new URLSearchParams(); Object.entries(p).forEach(([k, v]) => v && s.set(k, v)); const t = s.toString(); return t ? `?${t}` : ""; };

export const six = {
  status: () => request<SixStatus>("/api/six/status"),
  autonomy: (on: boolean, confirm?: string) => request<SixStatus["config"]>("/api/six/autonomy", j({ on, confirm })),
  config: (interval_min: number) => request<SixStatus["config"]>("/api/six/config", j({ interval_min }, "PUT")),
  tick: () => request<{ ran: boolean; reason?: string; agents?: string[] }>("/api/six/tick", j({})),
  emergency: (close_positions: boolean) => request<{ autonomous: boolean; closed: number; cancelled: number; errors: string[] }>("/api/six/emergency", j({ close_positions })),
  patch: (key: string, b: Partial<Pick<SixAgent, "enabled" | "symbols" | "risk_pct" | "max_positions">>) => request<SixAgent>(`/api/six/agents/${key}`, j(b, "PATCH")),
  resume: (key: string) => request<SixAgent>(`/api/six/agents/${key}/resume`, j({})),
  pause: (key: string) => request<SixAgent>(`/api/six/agents/${key}/pause`, j({})),
  decisions: (p: { agent?: string; status?: string } = {}) => request<SixDecision[]>(`/api/six/decisions${qs(p)}`),
  trades: (p: { agent?: string; status?: string } = {}) => request<SixPosition[]>(`/api/six/trades${qs(p)}`),
  validate: (key: string, symbol: string, variant_idx?: number) => request<SixValidation>(`/api/six/agents/${key}/validate`, j({ symbol, variant_idx })),
  validations: () => request<SixValidation[]>("/api/six/validations"),
  insights: (key: string) => request<SixInsights>(`/api/six/agents/${key}/insights`),
};
