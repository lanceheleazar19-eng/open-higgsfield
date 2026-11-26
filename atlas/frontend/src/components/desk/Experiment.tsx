import { useCallback, useEffect, useState } from "react";
import { desk } from "../../api/desk";
import { six, type SixAccount, type SixAgent, type SixDecision, type SixInsights, type SixMetrics, type SixPosition, type SixStatus, type SixValidation } from "../../api/six";
import { dt, money, num, pct, price, tone } from "./ui";

const STATUS: Record<SixAgent["status"], string> = { idle: "En espera", running: "Analizando", paused: "Pausado", halted: "Detenido" };
const VERDICT: Record<SixMetrics["verdict"], string> = {
  sin_datos: "SIN DATOS", insuficiente: "MUESTRA INSUFICIENTE", sin_ventaja: "SIN VENTAJA", no_significativa: "NO SIGNIFICATIVA", ventaja: "VENTAJA",
};
const DEC: Record<SixDecision["status"], string> = { executed: "Ejecutada", skipped: "Descartada", rejected: "Rechazada", error: "Error", info: "Info" };
const EXIT: Record<string, string> = { agent: "agente", stop_loss: "stop", take_profit: "objetivo", manual: "manual", emergency: "emergencia" };

function Verdict({ m }: { m: SixMetrics | null | undefined }) {
  if (!m) return <span className="sx-verdict v-sin_datos">N/D</span>;
  return <span className={`sx-verdict v-${m.verdict}`} title={m.verdict_text}>{VERDICT[m.verdict]}</span>;
}

function MetricsRow({ m }: { m: SixMetrics | null | undefined }) {
  const has = !!m && m.trades > 0;
  return (
    <div className="sx-metrics">
      <div><span>Ops</span><b>{m?.trades ?? 0}</b></div>
      <div><span>Neto</span><b className={tone(m?.net)}>{has ? money(m!.net, "EUR", true) : "N/D"}</b></div>
      <div><span>Win rate</span><b>{has ? pct(m!.win_rate, false, 1) : "N/D"}</b></div>
      <div><span>PF</span><b>{has ? num(m!.profit_factor) : "N/D"}</b></div>
      <div><span>Expectativa</span><b className={tone(m?.expectancy)}>{has ? money(m!.expectancy, "EUR", true) : "N/D"}</b></div>
      <div><span>Max DD</span><b>{has ? pct(m!.max_dd_pct, false) : "N/D"}</b></div>
      <div><span>t</span><b>{has ? num(m!.t_stat) : "N/D"}</b></div>
      <div><span>Costes</span><b>{has ? money(m!.costs) : "N/D"}</b></div>
    </div>
  );
}

function Costs({ kind, acc, onSaved }: { kind: string; acc: SixAccount; onSaved: () => void }) {
  const [v, setV] = useState({ slippage_bps: String(acc.slippage_bps), commission_pct: String(acc.commission_pct), commission_fixed: String(acc.commission_fixed) });
  const [msg, setMsg] = useState<string | null>(null);
  const save = async () => {
    const b = { slippage_bps: Number(v.slippage_bps), commission_pct: Number(v.commission_pct), commission_fixed: Number(v.commission_fixed) };
    if (Object.values(b).some((x) => !Number.isFinite(x) || x < 0)) { setMsg("Valores no válidos"); return; }
    try { await desk.patchAccount(acc.id, b); setMsg("Guardado"); onSaved(); } catch (e) { setMsg((e as Error).message); }
  };
  return (
    <section className="dpanel sx-account">
      <header className="dpanel-head"><span>{kind === "safe" ? "SAFE ACCOUNT" : "EXPERIMENTAL ACCOUNT"}</span><span>{acc.name}</span></header>
      <div className="sx-metrics">
        <div><span>Capital inicial</span><b>{money(acc.initial_capital)}</b></div>
        <div><span>Equity</span><b>{money(acc.equity)}</b></div>
        <div><span>Rentabilidad</span><b className={tone(acc.return_pct)}>{pct(acc.return_pct)}</b></div>
        <div><span>Posiciones</span><b>{acc.open_positions}</b></div>
      </div>
      <div className="filters sx-costs">
        <label>Slippage (bps)<input aria-label={`Slippage ${kind}`} inputMode="decimal" value={v.slippage_bps} onChange={(e) => setV({ ...v, slippage_bps: e.target.value })} /></label>
        <label>Comisión %<input aria-label={`Comisión porcentual ${kind}`} inputMode="decimal" value={v.commission_pct} onChange={(e) => setV({ ...v, commission_pct: e.target.value })} /></label>
        <label>Comisión fija €<input aria-label={`Comisión fija ${kind}`} inputMode="decimal" value={v.commission_fixed} onChange={(e) => setV({ ...v, commission_fixed: e.target.value })} /></label>
        <button type="button" className="btn" onClick={() => void save()}>Guardar costes</button>
      </div>
      {msg && <p className="muted small">{msg}</p>}
    </section>
  );
}

function AgentCard({ a, onChange, onValidated }: { a: SixAgent; onChange: () => void; onValidated: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [vsym, setVsym] = useState(a.symbols[0] ?? "");
  const [ins, setIns] = useState<SixInsights | null>(null);
  const act = async (fn: () => Promise<unknown>, after?: () => void) => {
    setBusy(true); setErr(null);
    try { await fn(); onChange(); after?.(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const lg = a.ledger;
  return (
    <article className={`dpanel sx-agent st-${a.status} ${a.enabled ? "" : "off"}`} data-testid={`agent-${a.key}`}>
      <header className="dpanel-head">
        <span>{a.name}</span>
        <span className={`sx-status st-${a.status}`}>{a.enabled ? STATUS[a.status] : "Desactivado"}</span>
      </header>
      <p className="muted small mono">{a.strategy} · {a.account === "safe" ? "SAFE" : "EXPERIMENTAL"} · riesgo {a.risk_pct}% · asignación {a.allocation_pct}%</p>
      <p className="small">{a.family_label} · {a.variant.timeframe} <span className="muted">· {Object.entries(a.variant.params).map(([k, v]) => `${k}=${v}`).join(" ")}</span></p>
      {a.halt_reason && <p className="error-line">{a.halt_reason}</p>}
      {a.last_error && <p className="error-line">Error: {a.last_error}</p>}
      <div className="sx-metrics">
        <div><span>Asignación</span><b>{money(lg?.allocation)}</b></div>
        <div><span>Equity</span><b>{money(lg?.equity)}</b></div>
        <div><span>Realizado</span><b className={tone(lg?.realized)}>{money(lg?.realized, "EUR", true)}</b></div>
        <div><span>No realizado</span><b className={tone(lg?.unrealized)}>{lg && lg.unpriced ? "N/D" : money(lg?.unrealized, "EUR", true)}</b></div>
      </div>
      <h4 className="sx-h">Qué analiza ahora</h4>
      {Object.keys(a.analyzing).length === 0 ? <p className="muted small">Aún no ha analizado (se activa con el modo autónomo o «Ejecutar ciclo»).</p> : (
        <ul className="sx-analyzing">
          {a.symbols.map((s) => {
            const x = a.analyzing[s];
            if (!x) return <li key={s}><b>{s}</b> <span className="muted">pendiente</span></li>;
            return (
              <li key={s}>
                <b>{s}</b> <span className="mono">{price(x.price)}</span> <span className="muted">{x.timeframe} · {x.source ?? "sin fuente"}{x.kind && x.kind !== "none" ? ` · ${x.kind}` : ""}</span>
                {x.error ? <span className="sx-err"> {x.error}</span> : <span className="sx-sig"> señal: {x.signal ?? "—"}</span>}
                <span className="muted small"> · {dt(x.at)}</span>
              </li>
            );
          })}
        </ul>
      )}
      <h4 className="sx-h">Rendimiento total <Verdict m={a.metrics} /></h4>
      <MetricsRow m={a.metrics} />
      {a.variants.length > 1 && <p className="muted small">Variante actual: {a.metrics_current?.trades ?? 0} ops · {a.metrics_current?.verdict_text}</p>}
      {a.open.length > 0 && (
        <table className="dtable compact">
          <thead><tr><th>Activo</th><th>Lado</th><th>Entrada</th><th>SL / TP</th><th>P&L</th></tr></thead>
          <tbody>{a.open.map((p) => (
            <tr key={p.id}><td>{p.symbol}</td><td className={p.side === "long" ? "up" : "down"}>{p.side.toUpperCase()}</td><td className="mono">{price(p.entry)}</td>
              <td className="mono">{price(p.sl)} / {price(p.tp)}</td><td className={`mono ${tone(p.unrealized)}`}>{money(p.unrealized, "EUR", true)}</td></tr>
          ))}</tbody>
        </table>
      )}
      {a.rotations.length > 0 && <p className="muted small">Última rotación: {a.rotations[a.rotations.length - 1].from} → {a.rotations[a.rotations.length - 1].to} ({dt(a.rotations[a.rotations.length - 1].at)})</p>}
      <div className="sx-actions">
        <button type="button" className="btn" disabled={busy} onClick={() => void act(() => six.patch(a.key, { enabled: !a.enabled }))}>{a.enabled ? "Desactivar" : "Activar"}</button>
        {a.status === "paused" || a.status === "halted"
          ? <button type="button" className="btn" disabled={busy} onClick={() => void act(() => six.resume(a.key))}>Reanudar</button>
          : <button type="button" className="btn" disabled={busy} onClick={() => void act(() => six.pause(a.key))}>Pausar</button>}
        <button type="button" className="btn" disabled={busy} onClick={() => void act(async () => setIns(ins ? null : await six.insights(a.key)))}>{ins ? "Ocultar análisis" : "Autoanálisis"}</button>
      </div>
      <div className="sx-actions">
        <select aria-label={`Activo para validar ${a.name}`} value={vsym} onChange={(e) => setVsym(e.target.value)}>{a.symbols.map((s) => <option key={s}>{s}</option>)}</select>
        <button type="button" className="btn" disabled={busy || !vsym} onClick={() => void act(() => six.validate(a.key, vsym), onValidated)}>Validar en histórico (70/30)</button>
      </div>
      {busy && <p className="muted small">Procesando…</p>}
      {err && <p className="error-line">{err}</p>}
      {ins && (
        <div className="sx-insights">
          <p className="small">{ins.trades} operaciones cerradas · duración media {ins.avg_hold_h === null ? "N/D" : `${ins.avg_hold_h} h`}</p>
          <ul>{ins.notes.map((n) => <li key={n} className="small">{n}</li>)}</ul>
          {Object.entries(ins.groups).map(([g, rows]) => Object.keys(rows).length > 0 && (
            <p key={g} className="small muted">{g}: {Object.entries(rows).map(([k, m]) => `${k} ${m.trades} ops / ${m.net >= 0 ? "+" : ""}${m.net}`).join(" · ")}</p>
          ))}
        </div>
      )}
    </article>
  );
}

export function Experiment() {
  const [s, setS] = useState<SixStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [confirm, setConfirm] = useState("");
  const [asking, setAsking] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [decs, setDecs] = useState<SixDecision[]>([]);
  const [fAgent, setFAgent] = useState("");
  const [fStatus, setFStatus] = useState("");
  const [trades, setTrades] = useState<SixPosition[]>([]);
  const [vals, setVals] = useState<SixValidation[]>([]);

  const load = useCallback(async () => {
    try {
      const [st, d, t, v] = await Promise.all([six.status(), six.decisions({ agent: fAgent || undefined, status: fStatus || undefined }),
        six.trades({ status: "closed" }), six.validations()]);
      setS(st); setDecs(d); setTrades(t); setVals(v); setErr(null);
    } catch (e) { setErr((e as Error).message); }
  }, [fAgent, fStatus]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 20_000);
    return () => window.clearInterval(id);
  }, [load]);

  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    try { await fn(); if (ok) setNote(ok); await load(); } catch (e) { setNote((e as Error).message); }
  };

  if (!s) return <p className="desk-empty">{err ? `No se pudo cargar VISTAN SIX: ${err}` : "Cargando LIVE EXPERIMENTATION…"}</p>;
  const on = s.config.autonomous;
  return (
    <div className="desk-module sx">
      <div className="mod-head">
        <h2>LIVE EXPERIMENTATION · VISTAN SIX</h2>
        <p className="muted small">Seis agentes experimentan en <b>PAPER TRADING</b> con el motor del Trading Desk: dinero virtual, sin brókers reales y sin mezclar balances. Las métricas solo usan operaciones registradas.</p>
      </div>
      {s.kill && <p className="desk-alert" role="alert">⛔ Kill switch de VISTAN activo (META-BRAIN): los agentes no operan.</p>}

      <section className={`dpanel sx-control ${on ? "on" : ""}`}>
        <header className="dpanel-head"><span>MODO AUTÓNOMO</span><span data-testid="autonomy-state">{on ? "ACTIVO" : "DESACTIVADO"}</span></header>
        {on ? (
          <p className="small">Activado {s.config.authorized_at ? `el ${dt(s.config.authorized_at)}` : ""}. Los agentes abren, gestionan y cierran posiciones simuladas sin pedir permiso por operación. Ciclo cada {s.config.interval_min} min.</p>
        ) : (
          <p className="small">Desactivado: ningún agente opera por su cuenta. Al activarlo autorizas que operen <b>solo con dinero virtual</b> sin pedirte permiso en cada operación simulada.</p>
        )}
        <div className="sx-actions">
          {on ? <button type="button" className="btn" onClick={() => void run(() => six.autonomy(false), "Modo autónomo desactivado")}>Desactivar modo autónomo</button>
            : asking ? (
              <>
                <input aria-label="Confirmación de activación" placeholder="Escribe ACTIVAR" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
                <button type="button" className="btn primary" disabled={confirm.trim().toUpperCase() !== "ACTIVAR"}
                  onClick={() => void run(async () => { await six.autonomy(true, confirm); setAsking(false); setConfirm(""); }, "Modo autónomo ACTIVADO (paper trading)")}>Confirmar activación</button>
                <button type="button" className="btn" onClick={() => { setAsking(false); setConfirm(""); }}>Cancelar</button>
              </>
            ) : <button type="button" className="btn primary" onClick={() => setAsking(true)}>Activar modo autónomo…</button>}
          <label className="small">Intervalo
            <select aria-label="Intervalo del ciclo" value={s.config.interval_min} onChange={(e) => void run(() => six.config(Number(e.target.value)))}>
              {[1, 2, 5, 10, 15, 30, 60].map((m) => <option key={m} value={m}>{m} min</option>)}
            </select>
          </label>
          <button type="button" className="btn" onClick={() => void run(async () => { const r = await six.tick(); setNote(r.ran ? `Ciclo ejecutado: ${r.agents?.length ?? 0} agentes` : `No se ejecutó: ${r.reason}`); })}>Ejecutar ciclo ahora</button>
          <button type="button" className="btn danger" onClick={() => {
            if (!window.confirm("Parada de emergencia: desactiva el modo autónomo y pausa a los seis agentes. ¿Continuar?")) return;
            const close = window.confirm("¿Cerrar también todas las posiciones y cancelar las órdenes de los agentes al precio actual? (Aceptar = sí, Cancelar = solo pausar)");
            void run(async () => { const r = await six.emergency(close); setNote(`Parada de emergencia: ${r.closed} posiciones cerradas, ${r.cancelled} órdenes canceladas${r.errors.length ? ` · ${r.errors.join("; ")}` : ""}`); });
          }}>Parada de emergencia</button>
        </div>
        {note && <p className="small" role="status">{note}</p>}
        <ul className="sx-rules">{s.rules.map((r) => <li key={r} className="small muted">{r}</li>)}</ul>
      </section>

      <div className="sx-accounts">
        {(["safe", "experimental"] as const).map((k) => s.accounts[k] && <Costs key={k} kind={k} acc={s.accounts[k]!} onSaved={() => void load()} />)}
      </div>

      <div className="sx-grid">
        {s.agents.map((a) => <AgentCard key={a.key} a={a} onChange={() => void load()} onValidated={() => void load()} />)}
      </div>

      <section className="dpanel">
        <header className="dpanel-head"><span>COMPETICIÓN POR AGENTE</span><span>asignaciones virtuales separadas</span></header>
        <div className="table-scroll">
          <table className="dtable compact">
            <thead><tr><th>Agente</th><th>Cuenta</th><th>Ops</th><th>Neto</th><th>Rent.</th><th>Max DD</th><th>PF</th><th>Win</th><th>Expect.</th><th>Costes</th><th>Estab. (1ª/2ª mitad)</th><th>Veredicto</th></tr></thead>
            <tbody>{s.leaderboard.map((r) => (
              <tr key={r.key}><td>{r.name}</td><td>{r.account === "safe" ? "SAFE" : "EXP"}</td><td>{r.trades}</td>
                <td className={tone(r.net)}>{r.trades ? money(r.net, "EUR", true) : "N/D"}</td><td>{r.trades ? pct(r.return_pct, true, 3) : "N/D"}</td>
                <td>{r.trades ? pct(r.max_dd_pct, false) : "N/D"}</td><td>{r.trades ? num(r.profit_factor) : "N/D"}</td><td>{r.trades ? pct(r.win_rate, false, 1) : "N/D"}</td>
                <td>{r.trades ? money(r.expectancy, "EUR", true) : "N/D"}</td><td>{r.trades ? money(r.costs) : "N/D"}</td>
                <td>{r.trades ? `${num(r.first_half_exp)} / ${num(r.second_half_exp)}` : "N/D"}</td><td><Verdict m={r} /></td></tr>
            ))}</tbody>
          </table>
        </div>
      </section>

      <section className="dpanel">
        <header className="dpanel-head"><span>RENDIMIENTO POR ESTRATEGIA</span><span>{s.strategies.length} con operaciones cerradas</span></header>
        {s.strategies.length === 0 ? <p className="muted small">Todavía no hay operaciones cerradas: sin estadísticas que mostrar.</p> : (
          <div className="table-scroll">
            <table className="dtable compact">
              <thead><tr><th>Estrategia</th><th>Ops</th><th>Neto</th><th>PF</th><th>Win</th><th>Expect.</th><th>t</th><th>Veredicto</th></tr></thead>
              <tbody>{s.strategies.map((r) => (
                <tr key={r.strategy}><td className="mono">{r.strategy}</td><td>{r.trades}</td><td className={tone(r.net)}>{money(r.net, "EUR", true)}</td>
                  <td>{num(r.profit_factor)}</td><td>{pct(r.win_rate, false, 1)}</td><td>{money(r.expectancy, "EUR", true)}</td><td>{num(r.t_stat)}</td><td><Verdict m={r} /></td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>

      <section className="dpanel">
        <header className="dpanel-head"><span>REGISTRO DE DECISIONES</span><span>incluye descartadas y errores</span></header>
        <div className="filters">
          <select aria-label="Filtrar por agente" value={fAgent} onChange={(e) => setFAgent(e.target.value)}>
            <option value="">Todos los agentes</option>{s.agents.map((a) => <option key={a.key} value={a.key}>{a.name}</option>)}
          </select>
          <select aria-label="Filtrar por estado" value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
            <option value="">Todos los estados</option>{Object.entries(DEC).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </div>
        {decs.length === 0 ? <p className="muted small">Sin decisiones registradas.</p> : (
          <ul className="sx-log">{decs.map((d) => (
            <li key={d.id} className={`d-${d.status}`}>
              <span className="mono muted">{dt(d.at)}</span> <b>{d.agent}</b> {d.symbol && <span className="mono">{d.symbol}</span>} <span className={`sx-dec d-${d.status}`}>{DEC[d.status]}</span> {d.reason}
            </li>
          ))}</ul>
        )}
      </section>

      <section className="dpanel">
        <header className="dpanel-head"><span>HISTORIAL DE OPERACIONES</span><span>{trades.length} cerradas (ganadoras y perdedoras)</span></header>
        {trades.length === 0 ? <p className="muted small">Sin operaciones cerradas.</p> : (
          <div className="table-scroll">
            <table className="dtable compact">
              <thead><tr><th>Cierre</th><th>Estrategia</th><th>Activo</th><th>Lado</th><th>Entrada</th><th>Salida</th><th>Motivo</th><th>Costes</th><th>P&L</th></tr></thead>
              <tbody>{trades.map((p) => (
                <tr key={p.id}><td>{dt(p.closed_at)}</td><td className="mono small">{p.strategy}</td><td>{p.symbol}</td><td className={p.side === "long" ? "up" : "down"}>{p.side.toUpperCase()}</td>
                  <td className="mono">{price(p.entry)}</td><td className="mono">{price(p.exit)}</td><td>{EXIT[p.exit_reason ?? ""] ?? p.exit_reason ?? "—"}</td>
                  <td className="mono">{money(p.fees)}</td><td className={`mono ${tone(p.realized)}`}>{money(p.realized, "EUR", true)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>

      <section className="dpanel">
        <header className="dpanel-head"><span>VALIDACIÓN FUERA DE MUESTRA</span><span>datos históricos reales · 70 % / 30 %</span></header>
        {vals.length === 0 ? <p className="muted small">Sin validaciones. Usa «Validar en histórico» en un agente (necesita conexión a internet para descargar velas).</p> : (
          <div className="table-scroll">
            <table className="dtable compact">
              <thead><tr><th>Fecha</th><th>Estrategia</th><th>Activo</th><th>Velas</th><th>Dentro de muestra</th><th>Fuera de muestra</th><th>Fuente</th></tr></thead>
              <tbody>{vals.map((v) => (
                <tr key={v.id}><td>{dt(v.at)}</td><td className="mono small">{v.strategy}</td><td>{v.symbol}</td><td>{v.result.bars}</td>
                  <td>{v.result.in_sample.trades} ops · {v.result.in_sample.trades ? money(v.result.in_sample.expectancy, "EUR", true) : "N/D"} <Verdict m={v.result.in_sample} /></td>
                  <td>{v.result.out_of_sample.trades} ops · {v.result.out_of_sample.trades ? money(v.result.out_of_sample.expectancy, "EUR", true) : "N/D"} <Verdict m={v.result.out_of_sample} /></td>
                  <td>{v.result.source ?? "N/D"}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
        <p className="muted small">Se aplica la misma lógica y los costes de su cuenta. Resultados pasados no garantizan resultados futuros; solo se habla de ventaja con ≥ 30 operaciones, t ≥ 2, PF ≥ 1,2 y ambas mitades positivas.</p>
      </section>
    </div>
  );
}
