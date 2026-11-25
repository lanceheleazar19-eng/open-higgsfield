import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { bets, type BAnalytics, type Backtest, type Bankroll, type Bet, type BEvent, type Block, type BProvider, type Calib, type LegIn, type Meta } from "../api/betting";
import { EventAnalysis, EventList, MarketPicker, pp, Slip, sportIcon, type SlipLeg } from "../components/betting/BetParts";
import { dt, MiniChart, money, num, pct, Stat, toNum, tone } from "../components/desk/ui";

type Tab = "lab" | "history" | "analytics" | "odds" | "backtest" | "agent" | "sources";
const TABS: [Tab, string][] = [["lab", "Laboratorio"], ["history", "Historial"], ["analytics", "Analytics"], ["odds", "Odds Analyzer"],
  ["backtest", "Backtesting"], ["agent", "Betting Agent"], ["sources", "Fuentes"]];
const iso2t = (s: string) => Math.floor(new Date(s.endsWith("Z") || s.includes("+") ? s : s + "Z").getTime() / 1000);

/** VISTAN PAPER BETTING — laboratorio de pronósticos deportivos con dinero FICTICIO. */
export function Betting() {
  const [tab, setTab] = useState<Tab>("lab");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [br, setBr] = useState<Bankroll | null>(null);
  const [events, setEvents] = useState<BEvent[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [slip, setSlip] = useState<SlipLeg[]>([]);
  const [preset, setPreset] = useState<Partial<LegIn> | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const loadBr = useCallback(() => bets.bankroll().then(setBr).catch((e: Error) => setErr(e.message)), []);
  const loadEvents = useCallback(() => bets.events().then(setEvents).catch(() => undefined), []);
  useEffect(() => { bets.meta().then(setMeta).catch((e: Error) => setErr(e.message)); void loadBr(); void loadEvents(); }, [loadBr, loadEvents]);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 6000); return () => clearTimeout(t); }, [toast]);
  const ev = events.find((e) => e.id === sel) ?? null;
  const ccy = br?.currency ?? "EUR";

  if (!meta || !br) return <div className="desk"><p className="desk-empty">{err ?? "Cargando laboratorio…"}</p></div>;
  return (
    <div className="desk betting" data-testid="paper-betting">
      <header className="desk-top">
        <div className="desk-brand"><span className="desk-logo">VISTAN</span><span className="desk-title">PAPER BETTING</span>
          <span className="sim-badge" title={meta.notice}>DINERO FICTICIO</span></div>
        <div className="desk-kpis">
          <div><span>BANKROLL</span><b className="mono">{money(br.balance, ccy)}</b></div>
          <div><span>EN JUEGO</span><b className="mono">{money(br.pending_stake, ccy)}</b></div>
          <div><span>INICIAL</span><b className="mono">{money(br.initial, ccy)}</b></div>
          <div><span>RESULTADO</span><b className={`mono ${tone(br.balance + br.pending_stake - br.initial)}`}>{money(br.balance + br.pending_stake - br.initial, ccy, true)}</b></div>
        </div>
        <button type="button" className="btn ghost" onClick={() => bets.settle().then((r) => { setToast(`${r.settled.length} pronóstico(s) liquidado(s)${r.errors.length ? ` · ${r.errors.join("; ")}` : ""}`); void loadBr(); void loadEvents(); })}>
          Comprobar resultados
        </button>
      </header>
      <nav className="desk-tabs" aria-label="Secciones de Paper Betting">
        {TABS.map(([k, l]) => <button type="button" key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}
      </nav>
      <main className="desk-main">
        {tab === "lab" && (
          <div className="terminal">
            <EventList events={events} meta={meta} selected={sel} onSelect={setSel} onReload={() => void loadEvents()} />
            {ev ? (
              <div className="lab-center">
                <EventAnalysis key={ev.id} ev={ev} meta={meta} onPick={setPreset} onChanged={() => { void loadEvents(); void loadBr(); }} />
                <section className="dpanel">
                  <header className="dpanel-head"><span>AÑADIR SELECCIÓN</span></header>
                  {ev.status === "scheduled" && new Date(ev.starts_at.endsWith("Z") ? ev.starts_at : ev.starts_at + "Z").getTime() > Date.now()
                    ? <MarketPicker ev={ev} meta={meta} preset={preset} onAdd={(l) => { setSlip((s) => [...s, { ...l, eventName: ev.name }]); setPreset(null); }} />
                    : <p className="desk-empty">El evento ya ha empezado: solo se registran pronósticos antes del inicio (así no se usa información del resultado).</p>}
                </section>
              </div>
            ) : <section className="chart-col"><p className="desk-empty nodata"><strong>Elige un evento</strong>Importa calendarios reales en «Fuentes» o crea un evento manual a la izquierda.</p></section>}
            <aside className="ticket-col">
              <Slip legs={slip} onRemove={(i) => setSlip((s) => s.filter((_, j) => j !== i))} onClear={() => setSlip([])}
                onPlaced={() => { void loadBr(); setToast("Pronóstico simulado registrado"); }} balance={br.balance} ccy={ccy} />
            </aside>
          </div>
        )}
        {tab === "history" && <History ccy={ccy} />}
        {tab === "analytics" && <BetAnalytics />}
        {tab === "odds" && <OddsCalc ccy={ccy} />}
        {tab === "backtest" && <BacktestView meta={meta} />}
        {tab === "agent" && <Agent event={ev} />}
        {tab === "sources" && <Sources meta={meta} br={br} onImported={() => { void loadEvents(); }} onBankroll={() => void loadBr()} />}
      </main>
      {toast && <div className="desk-toast" role="status">{toast}</div>}
      <footer className="desk-foot">Simulación educativa · dinero ficticio · sin depósitos, retiradas ni apuestas reales · apostar dinero real en España requiere ser mayor de 18 años</footer>
    </div>
  );
}

/* ─────────── Historial ─────────── */
function History({ ccy }: { ccy: string }) {
  const [st, setSt] = useState("");
  const [kind, setKind] = useState("");
  const [list, setList] = useState<Bet[] | null>(null);
  useEffect(() => { bets.list({ status: st || undefined, kind: kind || undefined }).then(setList).catch(() => setList([])); }, [st, kind]);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Historial de pronósticos</h2><p className="muted small">Todos los pronósticos simulados del bankroll actual, con su razonamiento y cómo se liquidaron.</p></div>
      <div className="filters">
        <select value={st} onChange={(e) => setSt(e.target.value)} aria-label="Estado"><option value="">Todos</option><option value="pending">Pendientes</option>
          <option value="won">Acertados</option><option value="lost">Fallados</option><option value="void">Anulados</option></select>
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Tipo"><option value="">Simples y combinadas</option><option value="single">Simples</option><option value="combo">Combinadas</option></select>
      </div>
      {!list?.length ? <p className="desk-empty">Sin pronósticos con estos filtros.</p> : (
        <div className="bet-cards">{list.map((b) => (
          <article key={b.id} className={`dpanel bet-card s-${b.status}`}>
            <header className="dpanel-head"><span>#{b.id} · {b.kind === "combo" ? `COMBINADA (${b.legs.length})` : "SIMPLE"} · {dt(b.created_at)}</span>
              <span className={`st st-${b.status === "won" ? "filled" : b.status === "lost" ? "rejected" : b.status === "void" ? "cancelled" : "pending"}`}>
                {{ pending: "Pendiente", won: "Acertado", lost: "Fallado", void: "Anulado" }[b.status]}</span></header>
            <ul className="slip-legs">{b.legs.map((l) => (
              <li key={l.id}><div><b>{sportIcon(l.sport)} {l.event}</b><span>{l.label}</span>
                <small>{l.market_name} · {l.odds_source}{l.model_prob != null ? ` · modelo ${pp(l.model_prob)}` : ""}{l.result && "home" in l.result ? ` · ${String(l.result.home)}-${String(l.result.away)}` : ""}</small></div>
                <b className="mono">{num(l.odds, 2)}</b><span className={`leg-st ls-${l.status}`}>{{ pending: "…", won: "✓", lost: "✕", void: "nula" }[l.status]}</span></li>
            ))}</ul>
            <div className="bet-nums">
              <span>Importe <b className="mono">{money(b.stake, ccy)}</b></span><span>Cuota <b className="mono">{num(b.odds, 2)}</b></span>
              <span>Retorno potencial <b className="mono">{money(b.potential_return, ccy)}</b></span>
              {b.profit !== null && <span>Resultado <b className={`mono ${tone(b.profit)}`}>{money(b.profit, ccy, true)}</b></span>}
              {b.model_prob !== null && <span>Modelo <b className="mono">{pp(b.model_prob)}</b></span>}
              {b.user_prob !== null && <span>Tu estimación <b className="mono">{pp(b.user_prob)}</b></span>}
            </div>
            {b.reasoning && <p className="small reasoning">«{b.reasoning}»</p>}
            {b.warnings.map((w) => <p key={w} className="mini-note">⚠ {w}</p>)}
          </article>
        ))}</div>
      )}
    </div>
  );
}

/* ─────────── Analytics ─────────── */
function BlockTable({ title, rows, ccy }: { title: string; rows: Block[]; ccy: string }) {
  return (
    <section className="dpanel"><header className="dpanel-head"><span>{title}</span></header>
      {!rows.length ? <p className="desk-empty">Sin pronósticos.</p> : (
        <table className="dtable compact"><thead><tr><th /><th>Pron.</th><th>✓/✕</th><th>Acierto</th><th>Neto</th><th>ROI</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.key}><td>{({ football: "Fútbol", basketball: "Baloncesto", tennis: "Tenis", f1: "Fórmula 1", other: "Otros", combinada: "Combinadas" } as Record<string, string>)[r.key ?? ""] ?? r.key}</td>
              <td className="mono">{r.bets}</td><td className="mono">{r.won}/{r.lost}</td><td className="mono">{pct(r.hit_rate, false, 1)}</td>
              <td className={`mono ${tone(r.profit)}`}>{money(r.profit, ccy, true)}</td><td className={`mono ${tone(r.roi)}`}>{pct(r.roi)}</td></tr>
          ))}</tbody></table>
      )}
    </section>
  );
}

function CalibCard({ title, c }: { title: string; c: Calib }) {
  return (
    <section className="dpanel"><header className="dpanel-head"><span>{title}</span><span>n = {c.n}</span></header>
      <div className="stat-row"><Stat label="Brier Score" value={c.brier !== null ? num(c.brier, 3) : "N/D"} /><Stat label="Log loss" value={c.log_loss !== null ? num(c.log_loss, 3) : "N/D"} /></div>
      {c.note && <p className="mini-note">{c.note}</p>}
      {!!c.bins.length && (
        <table className="dtable compact"><thead><tr><th>Rango</th><th>n</th><th>Predicho</th><th>Observado</th></tr></thead>
          <tbody>{c.bins.map((b) => <tr key={b.bin}><td>{b.bin}</td><td className="mono">{b.n}</td><td className="mono">{pp(b.predicted)}</td><td className="mono">{pp(b.observed)}</td></tr>)}</tbody></table>
      )}
    </section>
  );
}

function BetAnalytics() {
  const [a, setA] = useState<BAnalytics | null>(null);
  useEffect(() => { bets.analytics().then(setA).catch(() => undefined); }, []);
  if (!a) return <p className="desk-empty">Cargando…</p>;
  const ccy = a.bankroll.currency;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Analytics · {a.bankroll.name}</h2><p className="muted small">Solo pronósticos registrados y liquidados con resultados reales. Sin datos → N/D.</p></div>
      <div className="stat-row">
        <Stat label="Pronósticos" value={String(a.bets)} /><Stat label="Aciertos" value={String(a.won)} cls="up" /><Stat label="Fallos" value={String(a.lost)} cls="down" />
        <Stat label="Pendientes" value={String(a.pending)} /><Stat label="Anulados" value={String(a.void)} />
        <Stat label="% de aciertos" value={pct(a.hit_rate, false, 1)} /><Stat label="ROI simulado" value={pct(a.roi)} cls={tone(a.roi)} hint="Beneficio / importe apostado (liquidados)" />
        <Stat label="Beneficio neto" value={money(a.profit, ccy, true)} cls={tone(a.profit)} /><Stat label="Cuota media" value={a.avg_odds !== null ? num(a.avg_odds, 2) : "N/D"} />
        <Stat label="Drawdown máx." value={pct(a.max_drawdown_pct, false)} />
      </div>
      <section className="dpanel"><header className="dpanel-head"><span>EVOLUCIÓN DEL BANKROLL</span></header>
        <MiniChart data={a.curve.map((c) => ({ time: iso2t(c.t), value: c.bankroll }))} baseline={a.bankroll.initial} height={240} /></section>
      <div className="mod-cols">
        <BlockTable title="POR DEPORTE" rows={a.by_sport} ccy={ccy} /><BlockTable title="POR MERCADO" rows={a.by_market} ccy={ccy} />
        <BlockTable title="SIMPLES VS COMBINADAS" rows={a.by_kind} ccy={ccy} /><BlockTable title="POR ESTRATEGIA" rows={a.by_strategy} ccy={ccy} />
      </div>
      <div className="mod-head"><h2>Calibración probabilística</h2><p className="muted small">{a.calibration.help} Si dices «60 %», debería acertarse ~6 de cada 10.</p></div>
      <div className="mod-cols">
        <CalibCard title="MODELO DE VISTAN" c={a.calibration.model} /><CalibCard title="TUS ESTIMACIONES" c={a.calibration.user} /><CalibCard title="CUOTAS DEL MERCADO" c={a.calibration.market} />
      </div>
    </div>
  );
}

/* ─────────── Odds Analyzer ─────────── */
function OddsCalc({ ccy }: { ccy: string }) {
  const [rows, setRows] = useState([{ o: "", p: "" }, { o: "", p: "" }, { o: "", p: "" }]);
  const [stake, setStake] = useState("10");
  const [res, setRes] = useState<Awaited<ReturnType<typeof bets.analyzeOdds>> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const odds = rows.map((r) => toNum(r.o)).filter((x): x is number => x !== null);
  const combined = odds.length ? odds.reduce((a, b) => a * b, 1) : null;
  const calc = () => {
    const valid = rows.filter((r) => toNum(r.o));
    bets.analyzeOdds({ odds: valid.map((r) => toNum(r.o)!), probs: valid.map((r) => (toNum(r.p) !== null ? toNum(r.p)! / 100 : null)), stake: toNum(stake) })
      .then(setRes).catch((e: Error) => setErr(e.message));
  };
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Odds Analyzer</h2><p className="muted small">Introduce las cuotas decimales de un mercado completo (p. ej. 1, X y 2) para ver el margen de la casa, o de selecciones sueltas para ver su probabilidad implícita.</p></div>
      <section className="dpanel">
        <table className="dtable"><thead><tr><th>#</th><th>Cuota decimal</th><th>Tu probabilidad % (opcional)</th><th>Implícita</th><th>Justa (sin margen)</th><th>Diferencia</th><th>Si aciertas</th><th>Valor esperado</th></tr></thead>
          <tbody>{rows.map((r, i) => {
            const s = res?.selections[i];
            return (
              <tr key={i}>
                <td>{i + 1}</td>
                <td><input className="cell-in" inputMode="decimal" value={r.o} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, o: e.target.value } : x)))} aria-label={`Cuota ${i + 1}`} /></td>
                <td><input className="cell-in" inputMode="decimal" value={r.p} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, p: e.target.value } : x)))} aria-label={`Probabilidad ${i + 1}`} /></td>
                <td className="mono">{s ? pp(s.implied) : "—"}</td><td className="mono">{res?.market ? pp(res.market.fair_probs[i]) : "—"}</td>
                <td className={`mono ${s?.edge ? (s.edge.edge_pct > 0 ? "up" : "down") : ""}`}>{s?.edge ? `${num(s.edge.edge_pct, 1)} pp` : "—"}</td>
                <td className="mono">{s?.profit_if_win !== undefined ? money(s.profit_if_win, ccy, true) : "—"}</td>
                <td className="mono">{s?.expected_profit != null ? money(s.expected_profit, ccy, true) : "—"}</td>
              </tr>
            );
          })}</tbody></table>
        <div className="filters">
          <button type="button" className="mini-btn ghost" onClick={() => setRows([...rows, { o: "", p: "" }])}>+ fila</button>
          <label>Importe ficticio<input inputMode="decimal" value={stake} onChange={(e) => setStake(e.target.value)} aria-label="Importe" /></label>
          <button type="button" className="btn" disabled={!odds.length} onClick={calc}>Calcular</button>
        </div>
        {err && <p className="error-line">{err}</p>}
        {res?.market && <div className="stat-row"><Stat label="Suma de implícitas" value={pp(res.market.booksum, 2)} /><Stat label="Margen de la casa" value={`${num(res.market.margin_pct, 2)} %`} hint="Válido si las cuotas son de UN mismo mercado completo" /></div>}
        {combined && odds.length > 1 && <p className="small">Si estas selecciones fueran de eventos <b>independientes</b>, la cuota combinada sería <b className="mono">{num(combined, 2)}</b> (retorno {money((toNum(stake) ?? 0) * combined, ccy)}). Si están relacionadas, su probabilidad conjunta no es el producto.</p>}
      </section>
    </div>
  );
}

/* ─────────── Backtesting ─────────── */
function BacktestView({ meta }: { meta: Meta }) {
  const y = new Date().getFullYear();
  const [f, setF] = useState({ league: "PL", s1: String(y - 2), s2: String(y - 1), threshold: "5", stake_mode: "flat", stake: "100", kelly: "25", bankroll: "10000" });
  const [st, setSt] = useState<string[]>(["model_value_1x2", "favourite", "home"]);
  const [res, setRes] = useState<Backtest | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const run = () => {
    setBusy(true); setErr(null);
    bets.backtest({ league: f.league, seasons: [...new Set([Number(f.s1), Number(f.s2)])].filter(Boolean), strategies: st, threshold: (toNum(f.threshold) ?? 5) / 100,
      stake_mode: f.stake_mode, stake: toNum(f.stake) ?? 100, kelly_frac: (toNum(f.kelly) ?? 25) / 100, bankroll: toNum(f.bankroll) ?? 10000 })
      .then(setRes).catch((e: Error) => setErr(e.message)).finally(() => setBusy(false));
  };
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Backtesting de estrategias</h2><p className="callout small">Usa resultados y cuotas históricas reales (football-data.co.uk). Cada pronóstico se calcula solo con partidos anteriores a su fecha. Los resultados pasados no garantizan los futuros.</p></div>
      <section className="dpanel">
        <div className="bt-form">
          <label>Liga<select value={f.league} onChange={(e) => setF({ ...f, league: e.target.value })}>{meta.csv_leagues.map((l) => <option key={l} value={l}>{meta.competitions[l] ?? l}</option>)}</select></label>
          <label>Temporada (inicio)<input value={f.s1} onChange={(e) => setF({ ...f, s1: e.target.value })} inputMode="numeric" /></label>
          <label>y siguiente<input value={f.s2} onChange={(e) => setF({ ...f, s2: e.target.value })} inputMode="numeric" /></label>
          <label>Umbral de valor %<input value={f.threshold} onChange={(e) => setF({ ...f, threshold: e.target.value })} inputMode="decimal" /></label>
          <label>Importe<select value={f.stake_mode} onChange={(e) => setF({ ...f, stake_mode: e.target.value })}><option value="flat">Fijo</option><option value="kelly">Kelly fraccional</option></select></label>
          {f.stake_mode === "flat" ? <label>Importe fijo<input value={f.stake} onChange={(e) => setF({ ...f, stake: e.target.value })} inputMode="decimal" /></label>
            : <label>Fracción Kelly %<input value={f.kelly} onChange={(e) => setF({ ...f, kelly: e.target.value })} inputMode="decimal" /></label>}
          <label>Bankroll<input value={f.bankroll} onChange={(e) => setF({ ...f, bankroll: e.target.value })} inputMode="decimal" /></label>
        </div>
        <div className="filters">{Object.entries(meta.strategies).map(([k, v]) => (
          <label key={k} className="check"><input type="checkbox" checked={st.includes(k)} onChange={() => setSt(st.includes(k) ? st.filter((x) => x !== k) : [...st, k])} /> {v}</label>
        ))}</div>
        <button type="button" className="btn" disabled={busy || !st.length} onClick={run}>{busy ? "Simulando…" : "Comparar estrategias"}</button>
        {err && <p className="error-line">{err}</p>}
      </section>
      {res && (
        <>
          <section className="dpanel">
            <header className="dpanel-head"><span>{res.matches} PARTIDOS · {res.evaluated} EVALUADOS (tras {res.warmup} de calentamiento) · BRIER 1X2 DEL MODELO {res.model_brier_1x2 ?? "N/D"}</span></header>
            <table className="dtable"><thead><tr><th>Estrategia</th><th>Pron.</th><th>Acierto</th><th>Beneficio</th><th>ROI</th><th>ROI 1.ª mitad</th><th>ROI 2.ª mitad</th><th>DD máx.</th><th>Cuota media</th></tr></thead>
              <tbody>{res.results.map((r) => (
                <tr key={r.strategy}><td>{r.name}</td><td className="mono">{r.bets}</td><td className="mono">{pct(r.hit_rate, false, 1)}</td>
                  <td className={`mono ${tone(r.profit)}`}>{num(r.profit, 2)}</td><td className={`mono ${tone(r.roi_flat)}`}>{pct(r.roi_flat)}</td>
                  <td className="mono">{pct(r.roi_first_half)}</td><td className="mono">{pct(r.roi_second_half)}</td>
                  <td className="mono">{pct(r.max_drawdown_pct, false)}</td><td className="mono">{r.avg_odds !== null ? num(r.avg_odds, 2) : "—"}</td></tr>
              ))}</tbody></table>
            <p className="mini-note">Fuente: {res.source}</p>
          </section>
          <div className="mod-cols">{res.results.map((r) => (
            <section key={r.strategy} className="dpanel"><header className="dpanel-head"><span>{r.name.toUpperCase().slice(0, 60)}</span></header>
              <MiniChart data={r.curve.map((c) => ({ time: iso2t(c.date), value: c.bankroll }))} baseline={toNum(f.bankroll) ?? 10000} height={180} area={false} color="#f1e6e2" /></section>
          ))}</div>
          <ul className="findings">{res.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </>
      )}
    </div>
  );
}

/* ─────────── Agente ─────────── */
const QUICK = ["Analiza el evento seleccionado y dime qué información falta", "¿Cómo de precisas han sido mis estimaciones? Explícame mi Brier Score",
  "Revisa mis últimos pronósticos: ¿qué errores de razonamiento ves?", "¿Qué es el margen de la casa y por qué importa?",
  "¿Por qué no puedo multiplicar probabilidades de selecciones del mismo partido?", "Explícame el valor esperado con un ejemplo"];

function Agent({ event }: { event: BEvent | null }) {
  const [msgs, setMsgs] = useState<{ role: "user" | "assistant"; content: string; meta?: string }[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [msgs, busy]);
  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    const history = msgs.map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: question }]); setQ(""); setBusy(true);
    try {
      const r = await bets.agent({ question, event_id: event?.id ?? null, history });
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, meta: r.model }]);
    } catch (e) { setMsgs((m) => [...m, { role: "assistant", content: `⚠ ${(e as Error).message}` }]); } finally { setBusy(false); }
  };
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>VISTAN Betting Agent</h2><p className="muted small">Analiza con tus datos registrados{event ? ` y el evento «${event.name}»` : ""}. No promete ganancias, no recomienda perseguir pérdidas y te avisa cuando falta información.</p></div>
      <section className="tutor agent-full">
        <div className="tutor-log">
          {!msgs.length && <div className="quick">{QUICK.map((x) => <button type="button" key={x} className="chip" onClick={() => void ask(x)}>{x}</button>)}</div>}
          {msgs.map((m, i) => <div key={i} className={`tmsg ${m.role}`}><div className="tbody">{m.content.split("\n").map((l, j) => <p key={j}>{l}</p>)}</div>{m.meta && <small>{m.meta}</small>}</div>)}
          {busy && <div className="tmsg assistant"><div className="tbody"><p className="muted">Analizando…</p></div></div>}
          <div ref={end} />
        </div>
        <form className="tutor-in" onSubmit={(e) => { e.preventDefault(); void ask(q); }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Pregunta al Betting Agent…" aria-label="Pregunta al agente" maxLength={2000} />
          <button type="submit" className="btn" disabled={busy || !q.trim()}>Preguntar</button>
        </form>
      </section>
    </div>
  );
}

/* ─────────── Fuentes, importación y bankroll ─────────── */
function Sources({ meta, br, onImported, onBankroll }: { meta: Meta; br: Bankroll; onImported: () => void; onBankroll: () => void }) {
  const [ps, setPs] = useState<BProvider[]>([]);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [comp, setComp] = useState<string[]>(["PL", "PD"]);
  const [f1, setF1] = useState(true);
  const [nba, setNba] = useState(false);
  const [os, setOs] = useState("");
  const [sports, setSports] = useState<{ key: string; title: string; group: string }[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [initial, setInitial] = useState(String(br.initial));
  const load = () => bets.providers().then(setPs).catch(() => undefined);
  useEffect(() => { void load(); bets.oddsSports().then((r) => setSports(r.sports)).catch(() => undefined); }, []);
  const groups = useMemo(() => [...new Set(sports.map((s) => s.group))], [sports]);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Fuentes de datos e importación</h2><p className="muted small">Solo datos (calendarios, resultados, cuotas). Ninguna fuente permite apostar. Las claves se guardan en el llavero de tu Mac.</p></div>
      <section className="dpanel">
        <header className="dpanel-head"><span>IMPORTAR PRÓXIMOS EVENTOS REALES</span></header>
        <div className="filters">{Object.entries(meta.competitions).map(([k, v]) => (
          <label key={k} className="check"><input type="checkbox" checked={comp.includes(k)} onChange={() => setComp(comp.includes(k) ? comp.filter((x) => x !== k) : [...comp, k])} /> {v}</label>
        ))}</div>
        <div className="filters">
          <label className="check"><input type="checkbox" checked={f1} onChange={(e) => setF1(e.target.checked)} /> Fórmula 1 (Jolpica)</label>
          <label className="check"><input type="checkbox" checked={nba} onChange={(e) => setNba(e.target.checked)} /> NBA (TheSportsDB)</label>
          <select value={os} onChange={(e) => setOs(e.target.value)} aria-label="Deporte con cuotas">
            <option value="">Eventos con cuotas (The Odds API)…</option>
            {groups.map((g) => <optgroup key={g} label={g}>{sports.filter((s) => s.group === g).map((s) => <option key={s.key} value={s.key}>{s.title}</option>)}</optgroup>)}
          </select>
          <button type="button" className="btn" disabled={busy} onClick={() => {
            setBusy(true);
            bets.sync({ football: comp, f1, nba, odds_sport: os || null }).then((r) => { setMsg(`${r.imported} eventos importados${r.errors.length ? ` · ${r.errors.join(" · ")}` : ""}`); onImported(); load(); })
              .catch((e: Error) => setMsg(e.message)).finally(() => setBusy(false));
          }}>{busy ? "Importando…" : "Importar"}</button>
        </div>
        {msg && <p className="small">{msg}</p>}
        <p className="mini-note">Tenis y otros deportes: vía The Odds API (cuotas y resultados recientes) o como evento manual.</p>
      </section>
      <div className="prov-grid">{ps.map((p) => (
        <section key={p.id} className="dpanel">
          <header className="dpanel-head"><span>{p.name.toUpperCase()}</span><span className={`prov-state s-${p.state.replace(/\s/g, "-")}`}>{p.state}</span></header>
          <p className="small">{p.covers}</p>
          <p className="muted small">{p.limits}{p.remaining ? ` · créditos restantes: ${p.remaining}` : ""}{p.default_key ? " · usando la clave pública" : ""}</p>
          <p className="muted small mono">Latencia {p.latency_ms !== null ? `${p.latency_ms} ms` : "N/D"} · OK {p.ok} · errores {p.errors}</p>
          {p.last_error && <p className="error-line small">Último error: {p.last_error}</p>}
          {(p.needs_key || p.default_key || p.configured) && p.id !== "jolpica" && p.id !== "football-data.co.uk" && (
            <div className="filters">
              <input type="password" autoComplete="off" value={keys[p.id] ?? ""} onChange={(e) => setKeys({ ...keys, [p.id]: e.target.value })} placeholder={p.configured && !p.default_key ? "•••••• (guardada)" : "API key"} aria-label={`API key de ${p.name}`} />
              <button type="button" className="mini-btn" disabled={!keys[p.id]} onClick={() => bets.setKey(p.id, keys[p.id]).then(() => { setKeys({ ...keys, [p.id]: "" }); void load(); })}>Guardar</button>
              {p.configured && !p.default_key && <button type="button" className="mini-btn ghost" onClick={() => bets.delKey(p.id).then(() => void load())}>Quitar</button>}
              <a className="small" href={p.url} target="_blank" rel="noreferrer noopener">Obtener clave gratuita ↗</a>
            </div>
          )}
        </section>
      ))}</div>
      <section className="dpanel">
        <header className="dpanel-head"><span>BANKROLL FICTICIO</span></header>
        <p className="muted small">Empieza un bankroll nuevo con otro saldo inicial. El actual se archiva con su historial (no se borra). Debe no tener pronósticos pendientes.</p>
        <div className="filters">
          <input inputMode="decimal" value={initial} onChange={(e) => setInitial(e.target.value)} aria-label="Saldo inicial" />
          <button type="button" className="btn ghost" onClick={() => {
            const v = toNum(initial);
            if (!v || !window.confirm(`¿Empezar un bankroll ficticio nuevo de ${v}?`)) return;
            bets.resetBankroll(v).then(() => { setMsg("Bankroll nuevo creado"); onBankroll(); }).catch((e: Error) => setMsg(e.message));
          }}>Nuevo bankroll</button>
        </div>
      </section>
    </div>
  );
}
