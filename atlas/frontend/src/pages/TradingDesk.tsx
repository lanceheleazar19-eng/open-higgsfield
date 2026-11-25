import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { desk, TIMEFRAMES, type Analytics, type Candles, type DeskAccount, type DeskState, type Order, type Overview, type Quote, type Tf } from "../api/desk";
import { Blotter } from "../components/desk/Blotter";
import { AnalyticsView, BacktestView, DataView, JournalView, Markets, NewsView, Portfolio } from "../components/desk/Modules";
import { OrderTicket } from "../components/desk/OrderTicket";
import { loadDrawings, PriceChart, saveDrawings, type ChartType, type DrawMode, type Drawings } from "../components/desk/PriceChart";
import { Tutor } from "../components/desk/Tutor";
import { ago, KindTag, money, pct, price, SimBadge, compact, tone } from "../components/desk/ui";
import { INDICATOR_HELP, INDICATORS, type IndicatorId } from "../lib/indicators";

type Tab = "terminal" | "markets" | "portfolio" | "analytics" | "journal" | "backtest" | "news" | "data";
const TABS: [Tab, string][] = [["terminal", "Terminal"], ["markets", "Mercados"], ["portfolio", "Portfolio · Riesgo"], ["analytics", "Analytics"],
  ["journal", "Diario"], ["backtest", "Backtesting"], ["news", "Noticias · Macro"], ["data", "Datos"]];

function useLocal<T>(key: string, init: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => { try { const s = localStorage.getItem(key); return s ? JSON.parse(s) as T : init; } catch { return init; } });
  const set = useCallback((x: T) => { setV(x); try { localStorage.setItem(key, JSON.stringify(x)); } catch { /* sin almacenamiento */ } }, [key]);
  return [v, set];
}

/** VISTAN TRADING DESK — terminal profesional de PAPER TRADING (dinero virtual). */
export function TradingDesk() {
  const [params, setParams] = useSearchParams();
  const [tab, setTabState] = useState<Tab>((params.get("tab") as Tab) || "terminal");
  const setTab = (t: Tab) => { setTabState(t); setParams(t === "terminal" ? {} : { tab: t }, { replace: true }); };
  const [accounts, setAccounts] = useState<DeskAccount[]>([]);
  const [accKind, setAccKind] = useLocal<"safe" | "experimental">("vistan.desk.account", "safe");
  const [symbol, setSymbol] = useLocal("vistan.desk.symbol", "BTC/USDT");
  const [tf, setTf] = useLocal<Tf>("vistan.desk.tf", "1h");
  const [ctype, setCtype] = useLocal<ChartType>("vistan.desk.ctype", "candles");
  const [ind, setInd] = useLocal<IndicatorId[]>("vistan.desk.ind", ["volume", "sma20"]);
  const [state, setState] = useState<DeskState | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [candles, setCandles] = useState<Candles | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [compareSym, setCompareSym] = useState("");
  const [compare, setCompare] = useState<Candles | null>(null);
  const [drawMode, setDrawMode] = useState<DrawMode>("none");
  const [drawings, setDrawings] = useState<Drawings>(() => loadDrawings(symbol));
  const [tutorOpen, setTutorOpen] = useState(false);
  const [preset, setPreset] = useState<{ q: string; n: number } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const chartApi = useRef<{ screenshot: () => string | null; fit: () => void } | null>(null);

  const account = accounts.find((a) => a.active && a.kind === accKind) ?? accounts.find((a) => a.active) ?? null;
  const indSet = useMemo(() => new Set(ind), [ind]);

  const loadAccounts = useCallback(() => desk.accounts().then(setAccounts).catch((e: Error) => setErr(e.message)), []);
  useEffect(() => { void loadAccounts(); }, [loadAccounts]);

  const loadState = useCallback(() => {
    if (!account) return;
    desk.state(account.id).then((s) => {
      setState(s);
      if (s.events.length) setToast(s.events.map((e) => e.text).join(" · "));
    }).catch((e: Error) => setErr(e.message));
  }, [account?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { loadState(); const t = setInterval(loadState, 5000); return () => clearInterval(t); }, [loadState]);

  const loadOverview = useCallback(() => desk.overview().then(setOverview).catch(() => undefined), []);
  useEffect(() => { void loadOverview(); const t = setInterval(loadOverview, 30000); return () => clearInterval(t); }, [loadOverview]);

  useEffect(() => {
    const load = () => desk.quote(symbol).then(setQuote).catch(() => setQuote(null));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [symbol]);

  useEffect(() => {
    let alive = true;
    const load = () => desk.candles(symbol, tf).then((c) => { if (alive) setCandles(c); }).catch((e: Error) => alive && setCandles({ symbol, tf, candles: [], source: null, kind: "none", kind_label: "Sin datos", error: e.message }));
    setCandles(null);
    load();
    const t = setInterval(load, ["1m", "5m", "15m"].includes(tf) ? 20000 : 60000);
    return () => { alive = false; clearInterval(t); };
  }, [symbol, tf]);

  useEffect(() => {
    if (!compareSym) { setCompare(null); return; }
    desk.candles(compareSym, tf).then(setCompare).catch(() => setCompare(null));
  }, [compareSym, tf]);

  useEffect(() => { setDrawings(loadDrawings(symbol)); setDrawMode("none"); }, [symbol]);
  useEffect(() => {
    if (tab === "portfolio" && account) desk.analytics({ account_id: account.id }).then(setAnalytics).catch(() => undefined);
  }, [tab, account?.id, state?.open_positions]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 6000); return () => clearTimeout(t); }, [toast]);

  const onDraw = (d: Drawings) => { setDrawings(d); saveDrawings(symbol, d); };
  const openSymbol = (s: string) => { setSymbol(s); setTab("terminal"); };
  const toggleWatch = (s: string) => {
    const on = overview?.watchlist.includes(s);
    (on ? desk.watchDel(s) : desk.watchAdd(s)).then((w) => setOverview((o) => (o ? { ...o, watchlist: w } : o))).catch(() => undefined);
  };
  const askTutor = (q: string) => { setTutorOpen(true); setPreset({ q, n: Date.now() }); };
  const snapToJournal = (pid: number) => {
    const img = chartApi.current?.screenshot();
    if (!img) { setToast("No hay gráfico que capturar"); return; }
    desk.journalImage(pid, img).then(() => setToast("Captura del gráfico guardada en el diario")).catch((e: Error) => setToast(e.message));
  };
  const onApi = useCallback((a: { screenshot: () => string | null; fit: () => void } | null) => { chartApi.current = a; }, []);
  const symPositions = useMemo(() => (state?.positions ?? []).filter((p) => p.symbol === symbol), [state, symbol]);

  const rows = overview?.rows ?? [];
  const watch = (overview?.watchlist.length ? overview.watchlist : ["BTC/USDT", "ETH/USDT", "SPY", "NVDA", "EUR/USD", "XAU/USD"]);
  const row = (s: string) => rows.find((r) => r.symbol === s);
  const cur = row(symbol);
  const ccy = account?.currency ?? "EUR";

  if (!account) {
    return <div className="desk"><p className="desk-empty">{err ?? "Preparando las cuentas virtuales…"}</p></div>;
  }

  return (
    <div className="desk" data-testid="trading-desk">
      <header className="desk-top">
        <div className="desk-brand">
          <span className="desk-logo">VISTAN</span><span className="desk-title">TRADING DESK</span><SimBadge />
        </div>
        <div className="acc-switch" role="radiogroup" aria-label="Cuenta virtual">
          {(["safe", "experimental"] as const).map((k) => {
            const a = accounts.find((x) => x.active && x.kind === k);
            return (
              <button type="button" key={k} role="radio" aria-checked={accKind === k} className={`${k} ${accKind === k ? "on" : ""}`} onClick={() => setAccKind(k)}>
                {k === "safe" ? "SAFE" : "EXPERIMENTAL"}<small>{a ? money(a.initial_capital, a.currency) : ""}</small>
              </button>
            );
          })}
        </div>
        <div className="desk-kpis">
          <div><span>EQUITY</span><b className="mono">{money(state?.equity, ccy)}</b></div>
          <div><span>DISPONIBLE</span><b className="mono">{money(state?.cash, ccy)}</b></div>
          <div><span>P&L DÍA</span><b className={`mono ${tone(state?.day_pnl)}`}>{money(state?.day_pnl, ccy, true)}</b></div>
          <div><span>P&L TOTAL</span><b className={`mono ${tone(state?.total_pnl)}`}>{pct(state?.return_pct)}</b></div>
          <div><span>DD</span><b className="mono">{pct(state?.drawdown.current_pct, false)}</b></div>
          <div><span>MERCADO</span><b className="mono">{overview ? `${overview.priced}/${overview.total}` : "…"}</b></div>
        </div>
        <button type="button" className={`btn tutor-btn ${tutorOpen ? "on" : ""}`} onClick={() => setTutorOpen(!tutorOpen)}>Tutor IA</button>
      </header>
      {!!state?.alerts.length && <p className="desk-alert" role="alert">⛔ {account.name}: límite de riesgo superado — {state.alerts.join(" · ")}</p>}
      <nav className="desk-tabs" aria-label="Secciones de la Trading Desk">
        {TABS.map(([k, l]) => <button type="button" key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}
        <Link to="/trading/legacy" className="legacy-link">Registro manual anterior</Link>
      </nav>

      <div className={`desk-body ${tutorOpen ? "with-tutor" : ""}`}>
        <main className="desk-main">
          {tab === "terminal" && (
            <div className="terminal">
              <aside className="watch">
                <header className="dpanel-head"><span>WATCHLIST</span><button type="button" className="link-btn" onClick={() => setTab("markets")}>+ activos</button></header>
                <ul>{watch.map((s) => {
                  const r = row(s);
                  return (
                    <li key={s}><button type="button" className={s === symbol ? "on" : ""} onClick={() => setSymbol(s)}>
                      <span className="w-sym">{s}</span>
                      <span className="mono w-px">{price(r?.price)}</span>
                      <span className={`mono w-ch ${tone(r?.change_pct)}`}>{pct(r?.change_pct)}</span>
                    </button></li>
                  );
                })}</ul>
                <header className="dpanel-head"><span>POPULARES</span></header>
                <ul>{["SPX", "NDX", "DAX", "ETH/USDT", "AAPL", "TSLA", "GBP/USD", "WTI"].filter((s) => !watch.includes(s)).map((s) => {
                  const r = row(s);
                  return (
                    <li key={s}><button type="button" className={s === symbol ? "on" : ""} onClick={() => setSymbol(s)}>
                      <span className="w-sym">{s}</span><span className="mono w-px">{price(r?.price)}</span><span className={`mono w-ch ${tone(r?.change_pct)}`}>{pct(r?.change_pct)}</span>
                    </button></li>
                  );
                })}</ul>
              </aside>

              <section className="chart-col">
                <div className="sym-head">
                  <div>
                    <h1>{symbol}<button type="button" className={`star ${overview?.watchlist.includes(symbol) ? "on" : ""}`} onClick={() => toggleWatch(symbol)}
                      aria-label={overview?.watchlist.includes(symbol) ? "Quitar de la watchlist" : "Añadir a la watchlist"}>★</button></h1>
                    <span className="sub">{cur?.name ?? ""} · {cur?.ccy ?? ""}</span>
                  </div>
                  <div className="sym-px">
                    <b className="mono">{price(quote?.price)}</b>
                    <span className={`mono ${tone(quote?.change_pct)}`}>{pct(quote?.change_pct)}</span>
                  </div>
                  <div className="sym-meta">
                    <span>Vol. {compact(quote?.volume)}</span>
                    <span><KindTag kind={quote?.kind} source={quote?.source} /> {quote?.source ?? "sin fuente"} · hace {ago(quote?.ts)}</span>
                    {quote?.open === false && <span>Mercado cerrado</span>}
                    {quote?.error && <span className="error-line small">{quote.error}</span>}
                  </div>
                  <div className="sym-actions">
                    <button type="button" className="mini-btn ghost" onClick={() => askTutor(`¿Qué está pasando en ${symbol} y cómo interpreto su gráfico en ${tf}?`)}>Explicar gráfico</button>
                    <button type="button" className="mini-btn ghost" onClick={() => desk.research(symbol).then(() => setToast("Investigación iniciada: la verás en Research")).catch((e: Error) => setToast(e.message))}>Investigar</button>
                  </div>
                </div>
                <div className="chart-tools">
                  <div className="seg tfs" role="group" aria-label="Temporalidad">
                    {TIMEFRAMES.map((t) => <button type="button" key={t} className={tf === t ? "on" : ""} onClick={() => setTf(t)}>{t}</button>)}
                  </div>
                  <div className="seg" role="group" aria-label="Tipo de gráfico">
                    {(["candles", "line", "area"] as ChartType[]).map((t) => <button type="button" key={t} className={ctype === t ? "on" : ""} onClick={() => setCtype(t)}>{{ candles: "Velas", line: "Línea", area: "Área" }[t]}</button>)}
                  </div>
                  <details className="ind-menu">
                    <summary>Indicadores ({ind.length})</summary>
                    <div>{(Object.keys(INDICATORS) as IndicatorId[]).map((k) => (
                      <label key={k} title={INDICATOR_HELP[k]}><input type="checkbox" checked={indSet.has(k)} onChange={() => setInd(indSet.has(k) ? ind.filter((x) => x !== k) : [...ind, k])} /> {INDICATORS[k]}</label>
                    ))}</div>
                  </details>
                  <div className="seg" role="group" aria-label="Dibujo">
                    <button type="button" className={drawMode === "trend" ? "on" : ""} onClick={() => setDrawMode(drawMode === "trend" ? "none" : "trend")} title="Línea de tendencia: haz clic en dos puntos">╱ Tendencia</button>
                    <button type="button" className={drawMode === "hline" ? "on" : ""} onClick={() => setDrawMode(drawMode === "hline" ? "none" : "hline")} title="Soporte o resistencia: haz clic en un precio">═ S/R</button>
                    <button type="button" onClick={() => onDraw({ hlines: [], trends: [] })} disabled={!drawings.hlines.length && !drawings.trends.length}>Borrar</button>
                  </div>
                  <select value={compareSym} onChange={(e) => setCompareSym(e.target.value)} aria-label="Comparar con">
                    <option value="">Comparar con…</option>{rows.filter((r) => r.symbol !== symbol).map((r) => <option key={r.symbol}>{r.symbol}</option>)}
                  </select>
                  <button type="button" className="mini-btn ghost" onClick={() => chartApi.current?.fit()}>Ajustar</button>
                </div>
                {drawMode !== "none" && <p className="mini-note draw-hint">{drawMode === "trend" ? "Haz clic en dos puntos del gráfico para trazar la tendencia." : "Haz clic en el precio del soporte o resistencia."}</p>}
                <div className="chart-wrap">
                  {!candles ? <p className="desk-empty">Cargando velas…</p>
                    : !candles.candles.length ? (
                      <div className="desk-empty nodata">
                        <strong>Sin datos de gráfico para {symbol} en {tf}</strong>
                        <p>{candles.error ?? "Ningún proveedor ha devuelto velas."}</p>
                        <p className="muted small">VISTAN no dibuja datos inventados. Conecta un proveedor en <button type="button" className="link-btn" onClick={() => setTab("data")}>Datos</button> o prueba otra temporalidad.</p>
                      </div>
                    ) : (
                      <PriceChart candles={candles.candles} symbol={symbol} tf={tf} type={ctype} indicators={indSet} compare={compare?.candles}
                        compareLabel={compareSym} positions={symPositions} drawings={drawings} drawMode={drawMode} onDraw={onDraw} onApi={onApi} />
                    )}
                  {candles?.candles.length ? (
                    <span className="chart-src">{candles.candles.length} velas · {candles.source} · <KindTag kind={candles.kind} source={candles.source} /> · rueda: zoom · arrastrar: desplazar</span>
                  ) : null}
                </div>
                <Blotter account={account} state={state} accounts={accounts} onChange={loadState} onSelect={setSymbol} onSnap={snapToJournal} />
              </section>

              <aside className="ticket-col">
                <OrderTicket account={account} symbol={symbol} quote={quote} tf={tf} onPlaced={(o: Order) => { loadState(); if (o.status === "rejected") setToast(`Orden rechazada: ${o.reason}`); }} />
              </aside>
            </div>
          )}
          {tab === "markets" && <Markets data={overview} onOpen={openSymbol} onToggleWatch={toggleWatch} onReload={() => void loadOverview()} />}
          {tab === "portfolio" && <Portfolio account={account} state={state} analytics={analytics} onAccountChanged={() => { void loadAccounts(); loadState(); }} />}
          {tab === "analytics" && <AnalyticsView account={account} />}
          {tab === "journal" && <JournalView account={account} onAskTutor={askTutor} />}
          {tab === "backtest" && <BacktestView symbols={rows.length ? rows.map((r) => r.symbol) : [symbol]} />}
          {tab === "news" && <NewsView />}
          {tab === "data" && <DataView />}
        </main>
        <Tutor account={account} symbol={symbol} tf={tf} open={tutorOpen} onClose={() => setTutorOpen(false)} preset={preset} />
      </div>
      {toast && <div className="desk-toast" role="status">{toast}</div>}
      <footer className="desk-foot">PAPER TRADING · todas las operaciones son simuladas con dinero virtual · ningún bróker conectado · {account.name}</footer>
    </div>
  );
}
