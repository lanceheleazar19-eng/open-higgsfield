import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Betting } from "../pages/Betting";

vi.mock("lightweight-charts", () => ({ createChart: () => ({ addSeries: () => ({ setData: vi.fn(), createPriceLine: vi.fn() }), timeScale: () => ({ fitContent: vi.fn() }), remove: vi.fn() }),
  AreaSeries: {}, LineSeries: {}, ColorType: { Solid: "solid" } }));

const future = new Date(Date.now() + 86_400_000).toISOString().replace("Z", "");
const meta = {
  sports: { football: "Fútbol", basketball: "Baloncesto", tennis: "Tenis", f1: "Fórmula 1", other: "Otros" },
  markets: { "1x2": { name: "Ganador (1X2)", sports: ["football"], picks: ["home", "draw", "away"] },
    total: { name: "Más/menos goles o puntos", sports: ["football"], picks: ["over", "under"], line: true } },
  pick_labels: { home: "Local", draw: "Empate", away: "Visitante", over: "Más de", under: "Menos de" },
  competitions: { PL: "Premier League" }, csv_leagues: ["PL"], strategies: { home: "Siempre local" }, notice: "Simulación educativa",
};
const ev = { id: 5, sport: "football", competition: "Premier League", name: "Arsenal – Chelsea", home: "Arsenal", away: "Chelsea", participants: [],
  starts_at: future, status: "scheduled", result: null, result_source: null, provider: "football-data", meta: {} };

function stub() {
  const calls: { key: string; body?: unknown }[] = [];
  const routes: Record<string, (b?: unknown) => [number, unknown]> = {
    "GET /api/betting/meta": () => [200, meta],
    "GET /api/betting/bankroll": () => [200, { id: 1, name: "BANKROLL VIRTUAL", currency: "EUR", initial: 10000, balance: 10000, active: true, simulated: true, created_at: "", pending_stake: 0, label: "DINERO FICTICIO" }],
    "GET /api/betting/events": () => [200, [ev]],
    "GET /api/betting/events/5/odds": () => [200, { markets: [], note: "Introduce las cuotas manualmente." }],
    "POST /api/betting/slip/analyze": () => [200, { legs: 1, odds: 2.1, implied_prob: 0.476, model_prob: null, fair_odds: null, warnings: [], conditions: ["Arsenal – Chelsea: Gana Arsenal"], stake: 50, potential_return: 105, potential_profit: 55, expected_profit: null }],
    "POST /api/betting/bets": () => [201, { id: 77, kind: "single", legs: [] }],
    "POST /api/betting/events/5/predict": () => [200, { event_id: 5, data: { event: {}, missing: ["Lesiones y bajas confirmadas: ningún proveedor"], sources: [] },
      model: { insufficient: "Hacen falta al menos 20 partidos previos" }, explanation: null, explanation_model: null }],
  };
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ key, body });
    const [status, out] = routes[key]?.(body) ?? [404, {}];
    return new Response(JSON.stringify(out), { status, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}
afterEach(() => vi.unstubAllGlobals());

test("Paper Betting: pronóstico simulado con cuota manual y datos insuficientes sin inventar", async () => {
  const calls = stub();
  render(<MemoryRouter><Betting /></MemoryRouter>);
  expect(await screen.findByText("DINERO FICTICIO")).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: /Arsenal – Chelsea/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Calcular probabilidades" }));
  expect(await screen.findByText(/Datos insuficientes: Hacen falta al menos 20 partidos previos/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Selección"), { target: { value: "home" } });
  fireEvent.change(screen.getByLabelText("Cuota decimal"), { target: { value: "2,10" } });
  fireEvent.click(screen.getByRole("button", { name: "Añadir al boleto" }));
  fireEvent.change(screen.getByLabelText("Importe ficticio"), { target: { value: "50" } });
  fireEvent.change(screen.getByLabelText("Razonamiento"), { target: { value: "Mejor forma" } });
  await waitFor(() => expect(screen.getByText(/105,00/)).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /Registrar pronóstico/ }));
  expect(await screen.findByText(/Pronóstico #77 registrado \(simulado\)/)).toBeInTheDocument();
  const placed = calls.find((c) => c.key === "POST /api/betting/bets")!.body as { legs: unknown[]; stake: number; reasoning: string };
  expect(placed).toMatchObject({ stake: 50, reasoning: "Mejor forma", legs: [{ event_id: 5, market: "1x2", pick: "home", odds: 2.1, odds_source: "manual" }] });
  const foot = screen.getByText(/sin depósitos, retiradas ni apuestas reales/);
  expect(within(foot).getByText(/mayor de 18/)).toBeInTheDocument();
});
