/** VISTAN Trading Desk — PAPER TRADING (dinero virtual). */
import { ApiError, request } from "./client";

export type DataKind = "realtime" | "delayed" | "plan" | "historical" | "none";
export type Tf = "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d" | "1w" | "1M";
export const TIMEFRAMES: Tf[] = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"];

export interface DeskAccount {
  id: number; kind: "safe" | "experimental"; name: string; currency: string; initial_capital: number;
  slippage_bps: number; commission_fixed: number; commission_pct: number; max_risk_pct: number | null; max_daily_loss_pct: number | null;
  max_drawdown_pct: number | null; max_exposure_pct: number | null; require_stop: boolean; enforce_limits: boolean; active: boolean;
  simulated: true; created_at: string;
}
export interface Quote { symbol: string; price: number | null; change_pct: number | null; change_basis?: string; volume: number | null;
  volume_unit?: string; ts: number | null; source: string | null; kind: DataKind; error?: string; kind_label?: string; open?: boolean | null }
export interface OverviewRow extends Quote { name: string; cls: string; ccy: string; kind_label: string }
export interface Overview { rows: OverviewRow[]; watchlist: string[]; classes: Record<string, string>; priced: number; total: number; generated_at: string }
export interface Candle { time: number; open: number; high: number; low: number; close: number; volume: number }
export interface Candles { symbol: string; tf: Tf; candles: Candle[]; source: string | null; kind: DataKind; kind_label: string; error?: string }
export interface Instrument { symbol: string; name: string; cls: string; ccy: string; custom: boolean; sources: string[] }
export interface Position {
  id: number; account_id: number; symbol: string; side: "long" | "short"; qty: number; entry_price: number; sl: number | null; tp: number | null;
  status: "open" | "closed"; exit_price: number | null; realized_pnl: number | null; fees: number; reserved: number; exit_reason: string | null;
  risk_money: number | null; strategy: string | null; timeframe: string | null; data_kind: string | null; simulated: true;
  opened_at: string; closed_at: string | null; price?: number | null; price_kind?: DataKind; unrealized?: number | null; journaled?: boolean;
}
export interface Order {
  id: number; account_id: number; symbol: string; side: "buy" | "sell"; type: "market" | "limit" | "stop"; qty: number;
  limit_price: number | null; stop_price: number | null; sl: number | null; tp: number | null; status: "pending" | "filled" | "cancelled" | "rejected";
  reason: string | null; fill_price: number | null; fees: number | null; ref_price: number | null; risk_money: number | null; risk_pct: number | null;
  warnings: RiskWarning[]; data_kind: string | null; data_source: string | null; strategy: string | null; timeframe: string | null;
  position_id: number | null; simulated: true; created_at: string; filled_at: string | null;
}
export interface RiskWarning { code: string; level: "block" | "warn" | "info"; text: string }
export interface DeskState {
  account: DeskAccount; label: string; equity: number; cash: number; used: number; unrealized: number; realized: number; total_pnl: number;
  return_pct: number; open_positions: number; exposure_pct: number | null; unpriced_positions: number; day_pnl: number | null; day_realized: number;
  drawdown: { current_pct: number; max_pct: number; peak: number | null; points: number }; open_risk: number; open_without_stop: number;
  exposure_by_symbol: { symbol: string; amount: number; pct: number | null }[]; alerts: string[]; events: { type: string; text: string }[];
  positions: Position[]; pending: Order[];
}
export interface Preview {
  symbol: string; price: number | null; kind: DataKind; source: string | null; entry: number | null; fx: number | null; quote_ccy: string;
  account_ccy: string; equity: number; notional: number | null; fees: number | null; risk_money: number | null; risk_pct: number | null;
  rr: number | null; reward_money: number | null; suggested_qty: number | null; warnings: RiskWarning[]; blocking: boolean;
}
export interface OrderInput {
  account_id: number; symbol: string; side: "buy" | "sell"; type: "market" | "limit" | "stop"; qty: number;
  limit_price?: number | null; stop_price?: number | null; sl?: number | null; tp?: number | null;
  strategy?: string | null; timeframe?: string | null; note?: string | null; acknowledge_risk?: boolean;
}
export interface Block { trades: number; wins: number; losses: number; win_rate: number | null; net: number | null; gross_profit: number | null;
  gross_loss: number | null; profit_factor: number | string | null; avg_win: number | null; avg_loss: number | null; best: number | null;
  worst: number | null; expectancy: number | null }
export interface Analytics extends Block {
  account: DeskAccount; label: string; max_drawdown_pct: number | null; avg_r: number | null; avg_hours: number | null;
  curve: { t: string; equity: number; symbol: string; pnl: number }[]; equity_series: { t: string; equity: number; event: string | null }[];
  by_symbol: (Block & { key: string })[]; by_strategy: (Block & { key: string })[]; by_timeframe: (Block & { key: string })[]; by_exit: (Block & { key: string })[];
}
export interface Journal { position_id: number; entry_reason: string | null; strategy: string | null; analysis: string | null; emotion: string | null;
  exit_reason: string | null; mistakes: string[]; lessons: string | null; notes: string | null; image: boolean; updated_at: string | null }
export interface Patterns { closed: number; journaled: number; mistakes: [string, number][]; mistake_pnl: Record<string, number>;
  emotions: Record<string, { trades: number; net: number }>; no_stop: number; over_risk: number; size_up_after_loss: number; findings: string[] }
export interface Provider { id: string; name: string; needs_key: boolean; configured: boolean; kind: DataKind; kind_label: string; covers: string;
  limits: string; url: string; state: string; latency_ms: number | null; ok: number; errors: number; last_error: string | null; last_at: string | null }
export interface NewsItem { title: string; summary: string | null; url: string; source: string | null; provider: string; published: string | null;
  sentiment: string | null; tickers: string[] }
export interface MacroSeries { id: string; name: string; unit: string; data: { date: string; value: number }[]; error: string | null }
export interface Strategy { name: string; params: Record<string, number>; help: string }
export interface BacktestResult {
  id: number; strategy: string; strategy_name: string; params: Record<string, number>; capital: number; final_equity: number; return_pct: number;
  max_drawdown_pct: number; trades: number; win_rate: number | null; profit_factor: number | string | null; open_at_end: boolean; buy_hold_pct: number;
  bars: number; from: number; to: number; curve: { time: number; equity: number }[]; trade_list: { entry_t: number; exit_t: number; entry: number; exit: number; pnl: number; ret_pct: number }[];
  warning: string; symbol: string; tf: Tf; source: string;
}

export class RiskAckError extends Error {
  constructor(public warnings: RiskWarning[]) { super("La orden necesita tu confirmación de riesgo"); }
}

const json = (body: unknown, method = "POST"): RequestInit => ({ method, body: JSON.stringify(body) });
const qs = (p: Record<string, string | number | null | undefined>) =>
  "?" + Object.entries(p).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");

async function placeOrder(o: OrderInput): Promise<Order> {
  let res: Response;
  try {
    res = await fetch("/api/desk/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(o) });
  } catch {
    throw new ApiError(0, "No se puede conectar con el núcleo de VISTAN");
  }
  const body = await res.json().catch(() => ({}));
  if (res.status === 409 && body?.detail?.needs_ack) throw new RiskAckError(body.detail.warnings);
  if (!res.ok) throw new ApiError(res.status, typeof body?.detail === "string" ? body.detail : `Error ${res.status}`);
  return body as Order;
}

export const desk = {
  accounts: () => request<DeskAccount[]>("/api/desk/accounts"),
  newAccount: (b: { kind: string; capital: number; currency: string; name?: string }) => request<DeskAccount>("/api/desk/accounts", json(b)),
  patchAccount: (id: number, b: Partial<DeskAccount>) => request<DeskAccount>(`/api/desk/accounts/${id}`, json(b, "PATCH")),
  state: (account_id: number) => request<DeskState>(`/api/desk/state${qs({ account_id })}`),
  instruments: () => request<{ classes: Record<string, string>; timeframes: Tf[]; popular: string[]; instruments: Instrument[] }>("/api/desk/instruments"),
  addInstrument: (b: { symbol: string; name: string; cls: string; ccy: string }) => request<{ symbol: string }>("/api/desk/instruments", json(b)),
  overview: () => request<Overview>("/api/desk/overview"),
  quote: (symbol: string) => request<Quote & { name: string; cls: string; ccy: string }>(`/api/desk/quote${qs({ symbol })}`),
  candles: (symbol: string, tf: Tf, limit = 500) => request<Candles>(`/api/desk/candles${qs({ symbol, tf, limit })}`),
  watchAdd: (symbol: string) => request<string[]>("/api/desk/watchlist", json({ symbol })),
  watchDel: (symbol: string) => request<string[]>(`/api/desk/watchlist${qs({ symbol })}`, { method: "DELETE" }),
  watchOrder: (symbols: string[]) => request<string[]>("/api/desk/watchlist", json({ symbols }, "PUT")),
  preview: (o: OrderInput) => request<Preview>("/api/desk/orders/preview", json(o)),
  placeOrder,
  cancelOrder: (id: number) => request<Order>(`/api/desk/orders/${id}/cancel`, { method: "POST" }),
  orders: (p: { account_id?: number; status?: string; symbol?: string; start?: string; end?: string }) => request<Order[]>(`/api/desk/orders${qs(p)}`),
  positions: (p: { account_id?: number; status?: string; symbol?: string; start?: string; end?: string; result?: string; strategy?: string }) =>
    request<Position[]>(`/api/desk/positions${qs(p)}`),
  modify: (id: number, sl: number | null, tp: number | null) => request<Position>(`/api/desk/positions/${id}`, json({ sl, tp }, "PATCH")),
  close: (id: number, qty?: number | null) => request<Position>(`/api/desk/positions/${id}/close`, json({ qty: qty ?? null })),
  analytics: (p: { account_id: number; symbol?: string; strategy?: string; start?: string; end?: string }) => request<Analytics>(`/api/desk/analytics${qs(p)}`),
  patterns: (account_id: number) => request<Patterns>(`/api/desk/patterns${qs({ account_id })}`),
  journal: (pid: number) => request<{ position: Position; journal: Journal }>(`/api/desk/journal/${pid}`),
  saveJournal: (pid: number, b: Omit<Journal, "position_id" | "image" | "updated_at"> & { remember: boolean }) =>
    request<{ journal: Journal; remembered: boolean }>(`/api/desk/journal/${pid}`, json(b, "PUT")),
  journalImage: (pid: number, data_url: string) => request<{ ok: boolean }>(`/api/desk/journal/${pid}/image`, json({ data_url })),
  tutor: (b: { question: string; account_id: number; symbol?: string | null; timeframe?: string | null; history: { role: string; content: string }[] }) =>
    request<{ answer: string; model: string; used: string[] }>("/api/desk/tutor", json(b)),
  news: () => request<{ items: NewsItem[]; errors: string[]; providers: string[]; note: string | null }>("/api/desk/news"),
  macro: () => request<{ series: MacroSeries[]; source?: string; kind?: string; note: string | null }>("/api/desk/macro"),
  calendar: () => request<{ events: { time: string; country: string; event: string; impact: string; actual: number | null; estimate: number | null; prev: number | null; unit: string }[]; note: string | null; source?: string }>("/api/desk/calendar"),
  providers: (test = false) => request<Provider[]>(`/api/desk/providers${qs({ test: test ? "true" : null })}`),
  setKey: (id: string, key: string) => request<{ ok: boolean; stored_in: string }>(`/api/desk/providers/${id}/key`, json({ key }, "PUT")),
  delKey: (id: string) => request<{ ok: boolean }>(`/api/desk/providers/${id}/key`, { method: "DELETE" }),
  strategies: () => request<Record<string, Strategy>>("/api/desk/backtest/strategies"),
  backtest: (b: { symbol: string; tf: Tf; start: string; end: string; strategy: string; params: Record<string, number>; capital: number; commission_pct: number; slippage_bps: number; position_pct: number }) =>
    request<BacktestResult>("/api/desk/backtest", json(b)),
  backtests: () => request<{ id: number; created_at: string; params: Record<string, unknown>; summary: Record<string, unknown> }[]>("/api/desk/backtests"),
  research: (symbol: string) => request<{ id: number }>("/api/desk/research", json({ symbol })),
};
