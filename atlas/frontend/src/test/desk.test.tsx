import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { TradingDesk } from "../pages/TradingDesk";
import { atr, bollinger, ema, macd, rsi, sma, vwap } from "../lib/indicators";

// El canvas no existe en jsdom: el gráfico se sustituye por un doble que registra las series creadas.
const created: string[] = [];
vi.mock("lightweight-charts", () => {
  const series = () => ({ setData: vi.fn(), createPriceLine: vi.fn(), coordinateToPrice: () => 100 });
  const chart = () => ({
    addSeries: (def: { kind: string }) => { created.push(def.kind); return series(); },
    priceScale: () => ({ applyOptions: vi.fn() }), panes: () => [], subscribeClick: vi.fn(), remove: vi.fn(),
    takeScreenshot: () => ({ toDataURL: () => "data:image/png;base64,AAAA" }),
    timeScale: () => ({ fitContent: vi.fn(), setVisibleLogicalRange: vi.fn(), getVisibleLogicalRange: () => null,
      subscribeVisibleLogicalRangeChange: vi.fn(), unsubscribeVisibleLogicalRangeChange: vi.fn() }),
  });
  return { createChart: chart, CandlestickSeries: { kind: "candles" }, LineSeries: { kind: "line" }, AreaSeries: { kind: "area" },
    HistogramSeries: { kind: "histogram" }, ColorType: { Solid: "solid" }, CrosshairMode: { Normal: 0 }, LineStyle: { Solid: 0, Dotted: 1, Dashed: 2, LargeDashed: 3 } };
});

const acc = (id: number, kind: string, name: string) => ({ id, kind, name, currency: "EUR", initial_capital: 100000, slippage_bps: 2, commission_fixed: 1,
  commission_pct: 0.05, max_risk_pct: kind === "safe" ? 1 : 5, max_daily_loss_pct: 3, max_drawdown_pct: 10, max_exposure_pct: 60, require_stop: kind === "safe",
  enforce_limits: kind === "safe", active: true, simulated: true, created_at: "2026-11-25T10:00:00" });
const state = (a: ReturnType<typeof acc>) => ({ account: a, label: "SIMULACIÓN · dinero virtual", equity: 100000, cash: 100000, used: 0, unrealized: 0, realized: 0,
  total_pnl: 0, return_pct: 0, open_positions: 0, exposure_pct: 0, unpriced_positions: 0, day_pnl: 0, day_realized: 0,
  drawdown: { current_pct: 0, max_pct: 0, peak: 100000, points: 1 }, open_risk: 0, open_without_stop: 0, exposure_by_symbol: [], alerts: [], events: [], positions: [], pending: [] });

function stubFetch(handlers: Record<string, (init?: RequestInit) => [number, unknown]>) {
  const calls: { key: string; body?: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    calls.push({ key, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const h = handlers[key];
    const [status, body] = h ? h(init) : [404, {}];
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}

const SAFE = acc(1, "safe", "SAFE ACCOUNT"), EXP = acc(2, "experimental", "EXPERIMENTAL ACCOUNT");
const base = {
  "GET /api/desk/accounts": () => [200, [SAFE, EXP]] as [number, unknown],
  "GET /api/desk/state": () => [200, state(EXP)] as [number, unknown],
  "GET /api/desk/overview": () => [200, { rows: [{ symbol: "BTC/USDT", name: "Bitcoin", cls: "crypto", ccy: "USD", price: 64000, change_pct: 1.2, volume: 1e9, ts: 1, source: "binance", kind: "realtime", kind_label: "Tiempo real" },
    { symbol: "SPX", name: "S&P 500", cls: "index", ccy: "USD", price: null, change_pct: null, volume: null, ts: null, source: null, kind: "none", kind_label: "Sin datos" }],
  watchlist: ["BTC/USDT"], classes: { crypto: "Cripto", index: "Índices" }, priced: 1, total: 2, generated_at: "2026-11-25T10:00:00" }] as [number, unknown],
  "GET /api/desk/quote": () => [200, { symbol: "BTC/USDT", price: 64000, change_pct: 1.2, volume: 1e9, ts: Date.now() / 1000, source: "binance", kind: "realtime", name: "Bitcoin", cls: "crypto", ccy: "USD" }] as [number, unknown],
  "GET /api/desk/candles": () => [200, { symbol: "BTC/USDT", tf: "1h", candles: Array.from({ length: 60 }, (_, i) => ({ time: 1_700_000_000 + i * 3600, open: 100 + i, high: 102 + i, low: 99 + i, close: 101 + i, volume: 5 })),
    source: "binance", kind: "realtime", kind_label: "Tiempo real" }] as [number, unknown],
  "POST /api/desk/orders/preview": () => [200, { symbol: "BTC/USDT", price: 64000, kind: "realtime", source: "binance", entry: 64000, fx: 0.8, quote_ccy: "USD", account_ccy: "EUR",
    equity: 100000, notional: 5120, fees: 6.12, risk_money: null, risk_pct: null, rr: null, reward_money: null, suggested_qty: null,
    warnings: [{ code: "no_stop", level: "warn", text: "Sin stop loss: el riesgo de la operación no está limitado" }], blocking: false }] as [number, unknown],
};

beforeEach(() => { localStorage.clear(); localStorage.setItem("vistan.desk.account", JSON.stringify("experimental")); created.length = 0; });
afterEach(() => vi.unstubAllGlobals());

test("Trading Desk: terminal simulada con datos reales del motor y gráfico de velas", async () => {
  stubFetch(base);
  render(<MemoryRouter><TradingDesk /></MemoryRouter>);
  expect(await screen.findByText("PAPER · SIMULACIÓN")).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: /EXPERIMENTAL/ })).toHaveAttribute("aria-checked", "true");
  await waitFor(() => expect(created).toContain("candles"));
  expect(created).toContain("histogram"); // volumen
  expect(screen.getAllByText(/PAPER TRADING · todas las operaciones son simuladas/).length).toBe(1);
  // Indicador RSI → panel nuevo
  fireEvent.click(screen.getByText(/Indicadores/));
  fireEvent.click(screen.getByLabelText("RSI 14"));
  await waitFor(() => expect(created.filter((c) => c === "line").length).toBeGreaterThan(1));
});

test("Trading Desk: una orden con riesgo pide confirmación y se envía como simulada", async () => {
  let n = 0;
  const calls = stubFetch({
    ...base,
    "POST /api/desk/orders": () => (++n === 1
      ? [409, { detail: { message: "x", needs_ack: true, warnings: [{ code: "no_stop", level: "warn", text: "Sin stop loss: el riesgo de la operación no está limitado" }] } }]
      : [201, { id: 9, status: "filled", fill_price: 64012.8, type: "market", reason: null }]),
  });
  render(<MemoryRouter><TradingDesk /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText("Cantidad"), { target: { value: "0,08" } });
  expect(await screen.findByText(/Nominal/)).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText(/5\.?120,00/)).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /COMPRAR 0,08 BTC\/USDT · simulada/ }));
  expect(await screen.findByRole("alertdialog", { name: "Confirmar riesgo" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Enviar igualmente (simulada)" }));
  expect(await screen.findByText(/Ejecutada \(simulada\)/)).toBeInTheDocument();
  const posts = calls.filter((c) => c.key === "POST /api/desk/orders");
  expect(posts[0].body).toMatchObject({ account_id: 2, symbol: "BTC/USDT", side: "buy", type: "market", qty: 0.08, acknowledge_risk: false });
  expect(posts[1].body).toMatchObject({ acknowledge_risk: true });
});

test("Trading Desk: sin velas muestra el motivo, nunca un gráfico inventado", async () => {
  stubFetch({ ...base, "GET /api/desk/candles": () => [200, { symbol: "BTC/USDT", tf: "1h", candles: [], source: null, kind: "none", kind_label: "Sin datos", error: "Binance: sin conexión" }] });
  render(<MemoryRouter><TradingDesk /></MemoryRouter>);
  expect(await screen.findByText(/Sin datos de gráfico para BTC\/USDT/)).toBeInTheDocument();
  expect(screen.getByText("Binance: sin conexión")).toBeInTheDocument();
  expect(created).not.toContain("candles");
});

test("indicadores técnicos", () => {
  expect(sma([1, 2, 3, 4], 2)).toEqual([null, 1.5, 2.5, 3.5]);
  expect(ema([1, 1, 1, 1], 3)).toEqual([null, null, 1, 1]);
  expect(rsi(Array.from({ length: 30 }, (_, i) => i)).at(-1)).toBe(100);
  const b = bollinger(Array(25).fill(5));
  expect(b.upper.at(-1)).toBe(5);
  const m = macd(Array.from({ length: 60 }, (_, i) => i));
  expect(m.macd.at(-1)).toBeGreaterThan(0);
  const c = Array.from({ length: 20 }, (_, i) => ({ time: i * 60, open: 10, high: 12, low: 8, close: 10, volume: 1 }));
  expect(atr(c).at(-1)).toBeCloseTo(4);
  expect(vwap(c).at(-1)).toBeCloseTo(10);
});
