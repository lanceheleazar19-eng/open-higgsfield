import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { Experiment } from "../components/desk/Experiment";

type H = (body: unknown) => [number, unknown];
function stub(routes: Record<string, H>) {
  const calls: { key: string; body?: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url}`;
    const body = init?.body && typeof init.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ key, body });
    const h = routes[key] ?? routes[`${init?.method ?? "GET"} ${url.split("?")[0]}`];
    const [status, out] = h ? h(body) : [404, { detail: "no" }];
    return new Response(JSON.stringify(out), { status, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}
afterEach(() => vi.unstubAllGlobals());

const EMPTY = { trades: 0, verdict: "sin_datos", verdict_text: "Sin operaciones cerradas todavía" };
const agent = (key: string, extra = {}) => ({
  key, name: key.toUpperCase(), account: "safe", family: "ema_trend", family_label: "Tendencia EMA", enabled: true, status: "idle", halt_reason: null,
  symbols: ["BTC/USDT"], strategy: `SIX:${key}:ema_trend:1h:v1`, variant: { timeframe: "1h", params: { fast: 20 } }, variants: [{ id: `SIX:${key}:ema_trend:1h:v1`, timeframe: "1h", params: { fast: 20 } }],
  allocation_pct: 30, risk_pct: 0.5, max_positions: 2, max_dd_pct: 8, max_daily_loss_pct: 2,
  ledger: { allocation: 30000, realized: 0, unrealized: 0, equity: 30000, reserved: 0, available: 30000, open: 0, unpriced: 0, fees: 0 },
  analyzing: {}, rotations: [], last_run_at: null, last_error: null, metrics: EMPTY, metrics_current: EMPTY, open: [], ...extra,
});
const ACC = { id: 1, name: "Safe", initial_capital: 100000, equity: 100000, cash: 100000, return_pct: 0, open_positions: 0, commission_pct: 0.05, commission_fixed: 1, slippage_bps: 2, enforce_limits: true, max_risk_pct: 1, max_exposure_pct: 60 };
const status = (autonomous: boolean, agents = [agent("orion")]) => ({
  config: { autonomous, interval_min: 5, authorized_at: autonomous ? "2026-11-26T10:00:00" : null }, kill: false, agents, accounts: { safe: ACC },
  strategies: [], leaderboard: agents.map((a) => ({ key: a.key, name: a.name, account: a.account, ...EMPTY })), recent: [], rules: ["Todas las órdenes pasan por el motor de Paper Trading"],
});
const lists = { "GET /api/six/decisions": (): [number, unknown] => [200, []], "GET /api/six/trades": (): [number, unknown] => [200, []], "GET /api/six/validations": (): [number, unknown] => [200, []] };

test("Activar el modo autónomo exige escribir ACTIVAR y sin operaciones no inventa métricas", async () => {
  let on = false;
  const calls = stub({ ...lists, "GET /api/six/status": () => [200, status(on)], "POST /api/six/autonomy": (b) => { on = (b as { on: boolean }).on; return [200, status(on).config]; } });
  render(<Experiment />);
  expect(await screen.findByTestId("autonomy-state")).toHaveTextContent("DESACTIVADO");
  expect(screen.getAllByText("N/D").length).toBeGreaterThan(4);
  expect(screen.getByText(/Todavía no hay operaciones cerradas/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Activar modo autónomo/ }));
  const ok = screen.getByRole("button", { name: "Confirmar activación" });
  expect(ok).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Confirmación de activación"), { target: { value: "activar" } });
  fireEvent.click(ok);
  await waitFor(() => expect(screen.getByTestId("autonomy-state")).toHaveTextContent("ACTIVO"));
  expect(calls.find((c) => c.key === "POST /api/six/autonomy")?.body).toEqual({ on: true, confirm: "activar" });
});

test("Muestra qué analiza cada agente, posiciones, decisiones descartadas y operaciones perdedoras", async () => {
  const a = agent("nova", {
    account: "experimental", analyzing: { "BTC/USDT": { at: "2026-11-26T10:00:00", timeframe: "1h", price: 50000, source: "binance", kind: "realtime", error: null, signal: "short" } },
    open: [{ id: 3, symbol: "BTC/USDT", side: "short", qty: 0.1, entry: 50000, sl: 51000, tp: 48000, status: "open", strategy: "SIX:nova:breakout:1h:v1", timeframe: "1h", fees: 3.5, realized: null, exit: null, exit_reason: null, opened_at: "2026-11-26T09:00:00", closed_at: null, data_kind: "realtime", account: "experimental", price: 50100, unrealized: -10 }],
  });
  stub({ ...lists, "GET /api/six/status": () => [200, status(true, [a])],
    "GET /api/six/decisions": () => [200, [{ id: 9, agent: "nova", strategy: "SIX:nova:breakout:1h:v1", symbol: "ETH/USDT", action: "analyze", status: "skipped", reason: "Datos desactualizados: la última vela cerrada tiene 300 min", data: null, order_id: null, position_id: null, at: "2026-11-26T10:00:00" }]],
    "GET /api/six/trades": () => [200, [{ id: 2, symbol: "BTC/USDT", side: "long", qty: 0.1, entry: 50000, sl: 49000, tp: null, status: "closed", strategy: "SIX:nova:breakout:1h:v1", timeframe: "1h", fees: 6, realized: -106, exit: 49000, exit_reason: "stop_loss", opened_at: "2026-11-25T09:00:00", closed_at: "2026-11-25T12:00:00", data_kind: "realtime", account: "experimental" }]] });
  render(<Experiment />);
  const card = await screen.findByTestId("agent-nova");
  expect(within(card).getByText(/señal: short/)).toBeInTheDocument();
  expect(within(card).getByText("SHORT")).toBeInTheDocument();
  expect(screen.getByText(/Datos desactualizados/)).toBeInTheDocument();
  expect(screen.getByText("stop")).toBeInTheDocument();
  expect(screen.getByText(/1 cerradas \(ganadoras y perdedoras\)/)).toBeInTheDocument();
});

test("Parada de emergencia pide confirmación y puede cerrar posiciones", async () => {
  const calls = stub({ ...lists, "GET /api/six/status": () => [200, status(true)], "POST /api/six/emergency": () => [200, { autonomous: false, closed: 2, cancelled: 1, errors: [] }] });
  const confirm = vi.fn().mockReturnValueOnce(true).mockReturnValueOnce(true);
  vi.stubGlobal("confirm", confirm);
  render(<Experiment />);
  fireEvent.click(await screen.findByRole("button", { name: "Parada de emergencia" }));
  expect(await screen.findByText(/2 posiciones cerradas, 1 órdenes canceladas/)).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /api/six/emergency")?.body).toEqual({ close_positions: true });
  expect(confirm).toHaveBeenCalledTimes(2);
});
