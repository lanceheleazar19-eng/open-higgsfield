/** VISTAN Paper Betting — simulación con dinero FICTICIO. */
import { request } from "./client";

export type Sport = "football" | "basketball" | "tennis" | "f1" | "other";
export interface MarketDef { name: string; sports: Sport[]; picks: string[] | null; line?: boolean }
export interface Meta { sports: Record<Sport, string>; markets: Record<string, MarketDef>; pick_labels: Record<string, string>;
  competitions: Record<string, string>; csv_leagues: string[]; strategies: Record<string, string>; notice: string }
export interface Bankroll { id: number; name: string; currency: string; initial: number; balance: number; active: boolean; simulated: true;
  created_at: string; pending_stake: number; label: string }
export interface BEvent { id: number; sport: Sport; competition: string | null; name: string; home: string | null; away: string | null;
  participants: string[]; starts_at: string; status: string; result: Record<string, unknown> | null; result_source: string | null;
  provider: string | null; meta: Record<string, unknown> }
export interface LegIn { event_id: number; market: string; pick: string; line?: number | null; opponent?: string | null; odds: number;
  odds_source?: string; model_prob?: number | null }
export interface SlipAnalysis { legs: number; odds: number; implied_prob: number; model_prob: number | null; fair_odds: number | null;
  warnings: string[]; conditions: string[]; edge?: { ev_per_unit: number; edge_pct: number; fair_odds: number | null; kelly_fraction: number | null };
  stake?: number; potential_return?: number; potential_profit?: number; expected_profit?: number | null }
export interface Leg { id: number; event_id: number; event: string; sport: Sport; starts_at: string; market: string; market_name: string; pick: string;
  line: number | null; opponent: string | null; label: string; odds: number; odds_source: string; model_prob: number | null; status: string;
  result: Record<string, unknown> | null; event_status: string }
export interface Bet { id: number; kind: "single" | "combo"; stake: number; odds: number; potential_return: number; model_prob: number | null;
  user_prob: number | null; status: "pending" | "won" | "lost" | "void"; returned: number | null; profit: number | null; reasoning: string | null;
  strategy: string | null; warnings: string[]; simulated: true; created_at: string; settled_at: string | null; legs: Leg[] }
export interface Block { key?: string; bets: number; won: number; lost: number; void: number; pending: number; hit_rate: number | null;
  staked: number; profit: number | null; roi: number | null; avg_odds: number | null }
export interface Calib { n: number; brier: number | null; log_loss: number | null; bins: { bin: string; n: number; predicted: number; observed: number }[]; note?: string }
export interface BAnalytics extends Block {
  bankroll: { id: number; name: string; initial: number; balance: number; currency: string }; pending_stake: number;
  by_sport: Block[]; by_market: Block[]; by_kind: Block[]; by_strategy: Block[]; curve: { t: string; bankroll: number }[];
  max_drawdown_pct: number | null; calibration: { model: Calib; user: Calib; market: Calib; help: string }; label: string;
}
export interface Prediction {
  event_id: number; prediction_id?: number;
  data: { event: Record<string, unknown>; missing: string[]; sources: string[]; user_notes?: string;
    form_home?: Form; form_away?: Form; h2h?: { date: string; home: string; away: string; score: string }[]; standings_recent?: { race: string; top5: string[] }[] };
  model: { insufficient?: string; model?: string; probs?: Record<string, number>; intervals_80?: Record<string, [number, number]>; method?: string;
    expected_goals?: { home: number; away: number }; expected_points?: { home: number; away: number }; top_scores?: { score: string; p: number }[];
    fit?: Record<string, number>; games_used?: number; races_used?: number };
  explanation: string | null; explanation_model: string | null; explanation_error?: string;
}
export interface Form { team: string; last: string[]; goals_for: number; goals_against: number; games: number; home_ppg: number | null;
  home_games: number; away_ppg: number | null; away_games: number; rest_days: number | null; last_match: string | null }
export interface OddsRow { bookmaker: string; updated: string; market: string; margin_pct: number;
  selections: { name: string; market: string; pick: string; line?: number; odds: number; implied: number; fair_prob: number; model_prob: number | null;
    edge: { ev_per_unit: number; edge_pct: number } | null }[] }
export interface BProvider { id: string; name: string; needs_key: boolean; configured: boolean; default_key: boolean; covers: string; limits: string;
  url: string; state: string; latency_ms: number | null; ok: number; errors: number; last_error: string | null; remaining: string | null; last_at: string | null }
export interface BtResult { strategy: string; name: string; bets: number; hit_rate: number | null; profit: number; staked: number; roi_flat: number | null;
  roi_first_half: number | null; roi_second_half: number | null; max_drawdown_pct: number; avg_odds: number | null;
  curve: { date: string; bankroll: number }[]; sample: { date: string; match: string; pick: string; odds: number; prob: number | null; won: boolean; score: string }[] }
export interface Backtest { league: string; seasons: number[]; matches: number; warmup: number; evaluated: number; model_brier_1x2: number | null;
  results: BtResult[]; source: string; warnings: string[] }

const json = (body: unknown, method = "POST"): RequestInit => ({ method, body: JSON.stringify(body) });
const qs = (p: Record<string, string | number | undefined | null>) =>
  "?" + Object.entries(p).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");

export const bets = {
  meta: () => request<Meta>("/api/betting/meta"),
  bankroll: () => request<Bankroll>("/api/betting/bankroll"),
  resetBankroll: (initial: number, currency = "EUR") => request<Bankroll>("/api/betting/bankroll", json({ initial, currency })),
  events: (p: { sport?: string; status?: string; q?: string } = {}) => request<BEvent[]>(`/api/betting/events${qs(p)}`),
  createEvent: (b: { sport: Sport; competition?: string; home?: string; away?: string; name?: string; participants?: string[]; starts_at: string; notes?: string }) =>
    request<BEvent>("/api/betting/events", json(b)),
  notes: (id: number, notes: string) => request<BEvent>(`/api/betting/events/${id}/notes`, json({ notes }, "PUT")),
  result: (id: number, status: string, result: Record<string, unknown> | null) => request<BEvent & { settled: number[] }>(`/api/betting/events/${id}/result`, json({ status, result }, "PUT")),
  sync: (b: { football: string[]; f1: boolean; nba: boolean; odds_sport?: string | null; days?: number }) => request<{ imported: number; errors: string[] }>("/api/betting/sync", json(b)),
  predict: (id: number, explain = true) => request<Prediction>(`/api/betting/events/${id}/predict${qs({ explain: explain ? "true" : "false" })}`, { method: "POST" }),
  odds: (id: number) => request<{ markets: OddsRow[]; source?: string; note: string | null }>(`/api/betting/events/${id}/odds`),
  analyzeOdds: (b: { odds: number[]; probs: (number | null)[]; stake?: number | null }) => request<{
    implied: number[]; market?: { implied: number[]; booksum: number; margin_pct: number; fair_probs: number[]; fair_odds: number[] };
    selections: { odds: number; implied: number; edge: { ev_per_unit: number; edge_pct: number; fair_odds: number | null; kelly_fraction: number | null } | null;
      return_if_win?: number; profit_if_win?: number; loss_if_lose?: number; expected_profit?: number | null }[] }>("/api/betting/odds/analyze", json(b)),
  analyzeSlip: (legs: LegIn[], stake?: number | null) => request<SlipAnalysis>("/api/betting/slip/analyze", json({ legs, stake: stake || null })),
  place: (b: { legs: LegIn[]; stake: number; reasoning?: string; strategy?: string; user_prob?: number | null }) => request<Bet>("/api/betting/bets", json(b)),
  list: (p: { status?: string; kind?: string } = {}) => request<Bet[]>(`/api/betting/bets${qs(p)}`),
  settle: () => request<{ settled: number[]; errors: string[] }>("/api/betting/settle", { method: "POST" }),
  analytics: () => request<BAnalytics>("/api/betting/analytics"),
  backtest: (b: { league: string; seasons: number[]; strategies: string[]; threshold: number; stake_mode: string; stake: number; kelly_frac: number; bankroll: number }) =>
    request<Backtest>("/api/betting/backtest", json(b)),
  agent: (b: { question: string; event_id?: number | null; history: { role: string; content: string }[] }) => request<{ answer: string; model: string }>("/api/betting/agent", json(b)),
  providers: () => request<BProvider[]>("/api/betting/providers"),
  oddsSports: () => request<{ sports: { key: string; title: string; group: string }[]; error: string | null }>("/api/betting/odds-sports"),
  setKey: (id: string, key: string) => request<{ ok: boolean }>(`/api/betting/providers/${id}/key`, json({ key }, "PUT")),
  delKey: (id: string) => request<{ ok: boolean }>(`/api/betting/providers/${id}/key`, { method: "DELETE" }),
};
