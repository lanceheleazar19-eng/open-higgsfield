import { useEffect, useMemo, useState } from "react";
import {
  desk, TIMEFRAMES, type Analytics, type BacktestResult, type Block, type DeskAccount, type DeskState, type Journal, type MacroSeries,
  type NewsItem, type Overview, type Patterns, type Position, type Provider, type Strategy, type Tf,
} from "../../api/desk";
import { compact, dt, KindTag, MiniChart, money, num, pct, price, Stat, toNum, tone } from "./ui";

const iso2t = (s: string) => Math.floor(new Date(s.endsWith("Z") ? s : s + "Z").getTime() / 1000);

/* ───────────────────────── Mercados ───────────────────────── */
export function Markets({ data, onOpen, onToggleWatch, onReload }: {
  data: Overview | null; onOpen: (s: string) => void; onToggleWatch: (s: string) => void; onReload: () => void;
}) {
  const [cls, setCls] = useState("all");
  const [q, setQ] = useState("");
  const [add, setAdd] = useState({ symbol: "", name: "", cls: "stock", ccy: "USD" });
  const [err, setErr] = useState<string | null>(null);
  if (!data) return <p className="desk-empty">Cargando mercados…</p>;
  const rows = data.rows.filter((r) => (cls === "all" || r.cls === cls) && (!q || `${r.symbol} ${r.name}`.toLowerCase().includes(q.toLowerCase())));
  const groups = Object.entries(data.classes).filter(([k]) => cls === "all" || k === cls);
  const watch = new Set(data.watchlist);
  return (
    <div className="desk-module">
      <div className="mod-head">
        <h2>Market overview</h2>
        <p className="muted small">{data.priced} de {data.total} activos con precio · actualizado {dt(data.generated_at)}. Sin proveedor → N/D (no se rellena con datos inventados).</p>
      </div>
      <div className="filters">
        <select value={cls} onChange={(e) => setCls(e.target.value)} aria-label="Clase de activo">
          <option value="all">Todos</option>{Object.entries(data.classes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar activo…" aria-label="Buscar activo" />
      </div>
      <div className="mk-grid">
        {groups.map(([k, label]) => {
          const g = rows.filter((r) => r.cls === k);
          if (!g.length) return null;
          return (
            <section key={k} className="dpanel">
              <header className="dpanel-head"><span>{label.toUpperCase()}</span><span>{g.filter((r) => r.price !== null).length}/{g.length}</span></header>
              <table className="dtable compact">
                <thead><tr><th /><th>Activo</th><th>Último</th><th>Var.</th><th>Volumen</th><th>Dato</th></tr></thead>
                <tbody>{g.map((r) => (
                  <tr key={r.symbol} className="click-row" onClick={() => onOpen(r.symbol)}>
                    <td><button type="button" className={`star ${watch.has(r.symbol) ? "on" : ""}`} aria-label={watch.has(r.symbol) ? `Quitar ${r.symbol} de la watchlist` : `Añadir ${r.symbol} a la watchlist`}
                      onClick={(e) => { e.stopPropagation(); onToggleWatch(r.symbol); }}>★</button></td>
                    <td><strong>{r.symbol}</strong><span className="sub">{r.name}</span></td>
                    <td className="mono">{price(r.price)}</td>
                    <td className={`mono ${tone(r.change_pct)}`} title={r.change_basis ? `Variación ${r.change_basis}` : "Variación 24 h / diaria"}>{pct(r.change_pct)}</td>
                    <td className="mono">{compact(r.volume)}</td>
                    <td><KindTag kind={r.kind} source={r.source} /></td>
                  </tr>
                ))}</tbody>
              </table>
            </section>
          );
        })}
      </div>
      <form className="dpanel add-inst" onSubmit={(e) => {
        e.preventDefault(); setErr(null);
        desk.addInstrument(add).then(() => { setAdd({ ...add, symbol: "", name: "" }); onReload(); }).catch((x: Error) => setErr(x.message));
      }}>
        <header className="dpanel-head"><span>AÑADIR ACTIVO</span></header>
        <div className="filters">
          <input value={add.symbol} onChange={(e) => setAdd({ ...add, symbol: e.target.value })} placeholder="Símbolo (AMD, ADA/USDT…)" aria-label="Símbolo nuevo" required />
          <input value={add.name} onChange={(e) => setAdd({ ...add, name: e.target.value })} placeholder="Nombre" aria-label="Nombre del activo" />
          <select value={add.cls} onChange={(e) => setAdd({ ...add, cls: e.target.value })} aria-label="Clase del activo nuevo">
            {Object.entries(data.classes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input value={add.ccy} onChange={(e) => setAdd({ ...add, ccy: e.target.value.toUpperCase() })} maxLength={3} aria-label="Divisa" style={{ width: 70 }} />
          <button type="submit" className="btn">Añadir</button>
        </div>
        {err && <p className="error-line">{err}</p>}
      </form>
    </div>
  );
}

/* ───────────────────────── Cartera ───────────────────────── */
export function Portfolio({ account, state, analytics, onAccountChanged }: {
  account: DeskAccount; state: DeskState | null; analytics: Analytics | null; onAccountChanged: () => void;
}) {
  const ccy = account.currency;
  const [cfg, setCfg] = useState(account);
  const [nw, setNw] = useState({ capital: String(account.initial_capital), currency: account.currency });
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => setCfg(account), [account]);
  const eq = (analytics?.equity_series ?? []).map((e) => ({ time: iso2t(e.t), value: e.equity }));
  const field = (k: keyof DeskAccount, label: string, suf = "%") => (
    <label>{label}
      <span className="in-suf"><input inputMode="decimal" value={cfg[k] === null ? "" : String(cfg[k])}
        onChange={(e) => setCfg({ ...cfg, [k]: e.target.value === "" ? null : toNum(e.target.value) })} aria-label={label} />{suf}</span>
    </label>
  );
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Portfolio · {account.name}</h2><p className="muted small">Calculado a partir de las operaciones registradas en esta cuenta virtual.</p></div>
      <div className="stat-row">
        <Stat label="Saldo inicial" value={money(account.initial_capital, ccy)} />
        <Stat label="Saldo disponible" value={money(state?.cash, ccy)} />
        <Stat label="Capital utilizado" value={money(state?.used, ccy)} />
        <Stat label="Equity" value={money(state?.equity, ccy)} />
        <Stat label="P&L total" value={money(state?.total_pnl, ccy, true)} cls={tone(state?.total_pnl)} />
        <Stat label="P&L diario" value={money(state?.day_pnl, ccy, true)} cls={tone(state?.day_pnl)} hint="Equity actual menos equity al empezar el día" />
        <Stat label="Rentabilidad" value={pct(state?.return_pct)} cls={tone(state?.return_pct)} />
        <Stat label="Abiertas / cerradas" value={`${state?.open_positions ?? 0} / ${analytics?.trades ?? 0}`} />
      </div>
      <div className="mod-cols">
        <section className="dpanel grow">
          <header className="dpanel-head"><span>EVOLUCIÓN DEL CAPITAL (equity registrada)</span></header>
          <MiniChart data={eq} baseline={account.initial_capital} height={260} />
        </section>
        <section className="dpanel">
          <header className="dpanel-head"><span>EXPOSICIÓN POR ACTIVO</span><span>{pct(state?.exposure_pct, false)}</span></header>
          {!state?.exposure_by_symbol.length ? <p className="desk-empty">Sin exposición: no hay posiciones abiertas.</p> : (
            <ul className="bars">{state.exposure_by_symbol.map((x) => (
              <li key={x.symbol}><span>{x.symbol}</span><i style={{ width: `${Math.min(100, x.pct ?? 0)}%` }} /><b className="mono">{money(x.amount, ccy)} · {pct(x.pct, false, 1)}</b></li>
            ))}</ul>
          )}
        </section>
      </div>
      <section className="dpanel">
        <header className="dpanel-head"><span>RISK MANAGEMENT</span>{state?.alerts.length ? <span className="alert-chip">{state.alerts.length} alerta(s)</span> : <span className="ok-chip">dentro de límites</span>}</header>
        <div className="stat-row">
          <Stat label="Riesgo abierto (a stop)" value={money(state?.open_risk, ccy)} hint="Suma de lo que perderías si saltan todos los stops" />
          <Stat label="Riesgo abierto %" value={state && state.equity ? pct((state.open_risk / state.equity) * 100, false) : "N/D"} />
          <Stat label="Posiciones sin stop" value={String(state?.open_without_stop ?? 0)} cls={state?.open_without_stop ? "down" : ""} />
          <Stat label="Drawdown actual" value={pct(state?.drawdown.current_pct, false)} cls={state?.drawdown.current_pct ? "down" : ""} />
          <Stat label="Drawdown máximo" value={pct(state?.drawdown.max_pct, false)} />
          <Stat label="Exposición total" value={pct(state?.exposure_pct, false)} />
        </div>
        {state?.alerts.map((a) => <p key={a} className="warn-line l-block">⛔ Límite superado: {a}</p>)}
        <form className="risk-form" onSubmit={(e) => {
          e.preventDefault();
          desk.patchAccount(account.id, {
            max_risk_pct: cfg.max_risk_pct, max_daily_loss_pct: cfg.max_daily_loss_pct, max_drawdown_pct: cfg.max_drawdown_pct,
            max_exposure_pct: cfg.max_exposure_pct, slippage_bps: cfg.slippage_bps, commission_fixed: cfg.commission_fixed,
            commission_pct: cfg.commission_pct, require_stop: cfg.require_stop, enforce_limits: cfg.enforce_limits,
          }).then(() => { setMsg("Límites guardados"); onAccountChanged(); }).catch((x: Error) => setMsg(x.message));
        }}>
          {field("max_risk_pct", "Riesgo máx. por operación")}
          {field("max_daily_loss_pct", "Pérdida diaria máx.")}
          {field("max_drawdown_pct", "Drawdown máx.")}
          {field("max_exposure_pct", "Exposición máx.")}
          {field("slippage_bps", "Deslizamiento", "bps")}
          {field("commission_fixed", "Comisión fija", ccy)}
          {field("commission_pct", "Comisión variable")}
          <label className="check"><input type="checkbox" checked={cfg.require_stop} onChange={(e) => setCfg({ ...cfg, require_stop: e.target.checked })} /> Stop loss obligatorio</label>
          <label className="check"><input type="checkbox" checked={cfg.enforce_limits} onChange={(e) => setCfg({ ...cfg, enforce_limits: e.target.checked })} /> Bloquear órdenes que superen los límites (si no, solo avisa)</label>
          <button type="submit" className="btn">Guardar límites</button>
          {msg && <span className="muted small">{msg}</span>}
        </form>
      </section>
      <section className="dpanel">
        <header className="dpanel-head"><span>NUEVA CUENTA {account.kind === "safe" ? "SAFE" : "EXPERIMENTAL"}</span></header>
        <p className="muted small">Crea una cuenta virtual nueva con otro capital inicial. La actual se archiva con todo su historial (no se borra nada). Hay que cerrar antes las posiciones abiertas.</p>
        <div className="filters">
          <input inputMode="decimal" value={nw.capital} onChange={(e) => setNw({ ...nw, capital: e.target.value })} aria-label="Capital inicial" />
          <select value={nw.currency} onChange={(e) => setNw({ ...nw, currency: e.target.value })} aria-label="Divisa de la cuenta"><option>EUR</option><option>USD</option></select>
          <button type="button" className="btn ghost" onClick={() => {
            const c = toNum(nw.capital);
            if (!c) return;
            if (!window.confirm(`¿Crear una nueva ${account.name} con ${c} ${nw.currency} virtuales? La actual quedará archivada.`)) return;
            desk.newAccount({ kind: account.kind, capital: c, currency: nw.currency }).then(() => { setMsg("Cuenta creada"); onAccountChanged(); }).catch((x: Error) => setMsg(x.message));
          }}>Crear cuenta virtual</button>
        </div>
      </section>
    </div>
  );
}

/* ───────────────────────── Analytics ───────────────────────── */
function BlockTable({ title, rows, ccy }: { title: string; rows: (Block & { key: string })[]; ccy: string }) {
  return (
    <section className="dpanel">
      <header className="dpanel-head"><span>{title}</span></header>
      {!rows.length ? <p className="desk-empty">Sin operaciones cerradas.</p> : (
        <table className="dtable compact">
          <thead><tr><th /><th>Ops</th><th>Win rate</th><th>Neto</th><th>PF</th><th>Expectancy</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.key}><td>{{ manual: "Manual", stop_loss: "Stop loss", take_profit: "Take profit" }[r.key] ?? r.key}</td><td className="mono">{r.trades}</td>
              <td className="mono">{pct(r.win_rate, false, 1)}</td><td className={`mono ${tone(r.net)}`}>{money(r.net, ccy, true)}</td>
              <td className="mono">{typeof r.profit_factor === "number" ? num(r.profit_factor) : r.profit_factor ?? "N/D"}</td><td className="mono">{money(r.expectancy, ccy, true)}</td></tr>
          ))}</tbody>
        </table>
      )}
    </section>
  );
}

export function AnalyticsView({ account }: { account: DeskAccount }) {
  const [f, setF] = useState({ symbol: "", strategy: "", start: "", end: "" });
  const [a, setA] = useState<Analytics | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    desk.analytics({ account_id: account.id, symbol: f.symbol || undefined, strategy: f.strategy || undefined, start: f.start || undefined, end: f.end || undefined })
      .then(setA).catch((e: Error) => setErr(e.message));
  }, [account.id, f]);
  const ccy = account.currency;
  const curve = useMemo(() => (a?.curve ?? []).map((c) => ({ time: iso2t(c.t), value: c.equity })), [a]);
  const pnlBars = useMemo(() => (a?.curve ?? []).map((c) => ({ time: iso2t(c.t), value: c.pnl })), [a]);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Trading analytics · {account.name}</h2><p className="muted small">Solo operaciones cerradas registradas. Sin operaciones no hay estadísticas (N/D).</p></div>
      <div className="filters">
        <input value={f.symbol} onChange={(e) => setF({ ...f, symbol: e.target.value })} placeholder="Activo (p. ej. BTC/USDT)" aria-label="Filtrar activo" />
        <input value={f.strategy} onChange={(e) => setF({ ...f, strategy: e.target.value })} placeholder="Estrategia" aria-label="Filtrar estrategia" />
        <input type="date" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} aria-label="Desde" />
        <input type="date" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} aria-label="Hasta" />
      </div>
      {err && <p className="error-line">{err}</p>}
      {a && (
        <>
          <div className="stat-row">
            <Stat label="Operaciones" value={String(a.trades)} />
            <Stat label="Win rate" value={pct(a.win_rate, false, 1)} />
            <Stat label="Profit factor" value={typeof a.profit_factor === "number" ? num(a.profit_factor) : a.profit_factor ?? "N/D"} hint="Ganancias brutas / pérdidas brutas" />
            <Stat label="Beneficio neto" value={money(a.net, ccy, true)} cls={tone(a.net)} />
            <Stat label="Ganancia bruta" value={money(a.gross_profit, ccy)} />
            <Stat label="Pérdida bruta" value={money(a.gross_loss, ccy)} />
            <Stat label="Media ganadoras" value={money(a.avg_win, ccy)} cls="up" />
            <Stat label="Media perdedoras" value={money(a.avg_loss, ccy)} cls="down" />
            <Stat label="Mejor operación" value={money(a.best, ccy, true)} />
            <Stat label="Peor operación" value={money(a.worst, ccy, true)} />
            <Stat label="Drawdown máx." value={pct(a.max_drawdown_pct, false)} hint="Sobre la curva de operaciones cerradas" />
            <Stat label="Expectancy" value={money(a.expectancy, ccy, true)} hint="Resultado medio esperado por operación" />
            <Stat label="R medio" value={a.avg_r !== null ? `${num(a.avg_r)} R` : "N/D"} hint="Resultado medido en múltiplos del riesgo inicial" />
            <Stat label="Duración media" value={a.avg_hours !== null ? `${num(a.avg_hours, 1)} h` : "N/D"} />
          </div>
          <div className="mod-cols">
            <section className="dpanel grow"><header className="dpanel-head"><span>CURVA DE CAPITAL (operaciones cerradas)</span></header>
              <MiniChart data={curve} baseline={account.initial_capital} /></section>
            <section className="dpanel grow"><header className="dpanel-head"><span>RESULTADO POR OPERACIÓN</span></header>
              <MiniChart data={pnlBars} area={false} color="#f1e6e2" baseline={0} /></section>
          </div>
          <div className="mod-cols">
            <BlockTable title="POR ACTIVO" rows={a.by_symbol} ccy={ccy} />
            <BlockTable title="POR ESTRATEGIA" rows={a.by_strategy} ccy={ccy} />
            <BlockTable title="POR TEMPORALIDAD" rows={a.by_timeframe} ccy={ccy} />
            <BlockTable title="POR TIPO DE SALIDA" rows={a.by_exit} ccy={ccy} />
          </div>
        </>
      )}
    </div>
  );
}

/* ───────────────────────── Diario ───────────────────────── */
const EMOTIONS = ["tranquilo", "confiado", "ansiedad", "miedo", "euforia", "aburrimiento", "frustración", "impaciencia"];
const MISTAKES = ["sin stop", "moví el stop", "FOMO", "sobreoperar", "entrada tardía", "salida anticipada", "riesgo excesivo", "contra tendencia", "revancha", "sin plan"];
const EMPTY_J: Omit<Journal, "position_id" | "image" | "updated_at"> = { entry_reason: "", strategy: "", analysis: "", emotion: "", exit_reason: "", mistakes: [], lessons: "", notes: "" };

export function JournalView({ account, onAskTutor }: { account: DeskAccount; onAskTutor: (q: string) => void }) {
  const [list, setList] = useState<Position[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [j, setJ] = useState(EMPTY_J);
  const [img, setImg] = useState(false);
  const [remember, setRemember] = useState(false);
  const [pat, setPat] = useState<Patterns | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [imgTick, setImgTick] = useState(0);
  const load = () => {
    Promise.all([desk.positions({ account_id: account.id, status: "closed" }), desk.positions({ account_id: account.id, status: "open" })])
      .then(([c, o]) => setList([...o, ...c])).catch(() => setList([]));
    desk.patterns(account.id).then(setPat).catch(() => setPat(null));
  };
  useEffect(load, [account.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (sel === null) return;
    desk.journal(sel).then((r) => {
      const { position_id: _p, image, updated_at: _u, ...rest } = r.journal;
      setJ({ ...EMPTY_J, ...Object.fromEntries(Object.entries(rest).map(([k, v]) => [k, v ?? (k === "mistakes" ? [] : "")])) } as typeof EMPTY_J);
      setImg(image);
    });
    setMsg(null);
  }, [sel]);
  const p = list.find((x) => x.id === sel);
  const ccy = account.currency;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Trading journal · {account.name}</h2>
        <p className="muted small">Registra el porqué de cada operación. VISTAN cuenta tus errores y emociones para detectar patrones (solo con lo que anotes).</p></div>
      <div className="mod-cols">
        <section className="dpanel journal-list">
          <header className="dpanel-head"><span>OPERACIONES</span><span>{list.length}</span></header>
          {!list.length ? <p className="desk-empty">Aún no hay operaciones en esta cuenta.</p> : (
            <ul>{list.map((x) => (
              <li key={x.id}><button type="button" className={sel === x.id ? "on" : ""} onClick={() => setSel(x.id)}>
                <span>{x.symbol} · {x.side === "long" ? "LARGO" : "CORTO"} {x.status === "open" ? "· abierta" : ""}</span>
                <b className={`mono ${tone(x.realized_pnl)}`}>{x.status === "closed" ? money(x.realized_pnl, ccy, true) : "—"}</b>
                <small>{dt(x.closed_at ?? x.opened_at)} {x.journaled ? "· ✎" : ""}</small>
              </button></li>
            ))}</ul>
          )}
        </section>
        <section className="dpanel grow">
          {!p ? <p className="desk-empty">Elige una operación para escribir o revisar su entrada en el diario.</p> : (
            <form className="journal-form" onSubmit={(e) => {
              e.preventDefault();
              desk.saveJournal(p.id, { ...j, remember }).then((r) => { setMsg(r.remembered ? "Guardado. La lección queda en la memoria de VISTAN." : "Guardado en el diario."); load(); })
                .catch((x: Error) => setMsg(x.message));
            }}>
              <header className="dpanel-head"><span>{p.symbol} · entrada {price(p.entry_price)} · salida {price(p.exit_price)} · {money(p.realized_pnl, ccy, true)}</span></header>
              <label>Motivo de entrada<textarea value={j.entry_reason ?? ""} onChange={(e) => setJ({ ...j, entry_reason: e.target.value })} rows={2} /></label>
              <div className="filters">
                <label>Estrategia<input value={j.strategy ?? ""} onChange={(e) => setJ({ ...j, strategy: e.target.value })} /></label>
                <label>Emoción / estado mental<select value={j.emotion ?? ""} onChange={(e) => setJ({ ...j, emotion: e.target.value })}>
                  <option value="">—</option>{EMOTIONS.map((x) => <option key={x}>{x}</option>)}</select></label>
              </div>
              <label>Análisis previo<textarea value={j.analysis ?? ""} onChange={(e) => setJ({ ...j, analysis: e.target.value })} rows={3} /></label>
              <label>Motivo de salida<textarea value={j.exit_reason ?? ""} onChange={(e) => setJ({ ...j, exit_reason: e.target.value })} rows={2} /></label>
              <fieldset className="chips"><legend>Errores cometidos</legend>
                {MISTAKES.map((m) => (
                  <button type="button" key={m} className={`chip ${j.mistakes.includes(m) ? "on" : ""}`} aria-pressed={j.mistakes.includes(m)}
                    onClick={() => setJ({ ...j, mistakes: j.mistakes.includes(m) ? j.mistakes.filter((x) => x !== m) : [...j.mistakes, m] })}>{m}</button>
                ))}
              </fieldset>
              <label>Lecciones aprendidas<textarea value={j.lessons ?? ""} onChange={(e) => setJ({ ...j, lessons: e.target.value })} rows={2} /></label>
              <label>Notas<textarea value={j.notes ?? ""} onChange={(e) => setJ({ ...j, notes: e.target.value })} rows={2} /></label>
              <div className="filters">
                <label className="file-btn">Adjuntar captura del gráfico
                  <input type="file" accept="image/png,image/jpeg" hidden onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    const r = new FileReader();
                    r.onload = () => desk.journalImage(p.id, String(r.result)).then(() => { setImg(true); setImgTick((t) => t + 1); }).catch((x: Error) => setMsg(x.message));
                    r.readAsDataURL(f);
                  }} />
                </label>
                <label className="check"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Recordar la lección en VISTAN</label>
                <button type="submit" className="btn">Guardar en el diario</button>
              </div>
              {img && <img className="journal-img" src={`/api/desk/journal/${p.id}/image?t=${imgTick}`} alt={`Captura del gráfico de ${p.symbol}`} />}
              {msg && <p className="ok-line">{msg}</p>}
            </form>
          )}
        </section>
        <section className="dpanel">
          <header className="dpanel-head"><span>PATRONES DETECTADOS</span></header>
          {!pat || !pat.closed ? <p className="desk-empty">Sin operaciones cerradas todavía.</p> : (
            <>
              <p className="muted small">{pat.journaled} de {pat.closed} operaciones cerradas tienen diario.</p>
              {pat.findings.length ? <ul className="findings">{pat.findings.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="desk-empty">No se detectan patrones negativos con los datos actuales.</p>}
              {!!pat.mistakes.length && (
                <ul className="bars">{pat.mistakes.map(([m, n]) => (
                  <li key={m}><span>{m}</span><i style={{ width: `${(n / pat.mistakes[0][1]) * 100}%` }} /><b className="mono">{n} · {money(pat.mistake_pnl[m], ccy, true)}</b></li>
                ))}</ul>
              )}
            </>
          )}
          <button type="button" className="btn ghost" onClick={() => onAskTutor("Analiza mi diario de trading y mis últimas operaciones: ¿qué errores repito, qué patrones de comportamiento ves y qué puedo aprender?")}>
            Analizar mi diario con VISTAN
          </button>
        </section>
      </div>
    </div>
  );
}

/* ───────────────────────── Backtesting ───────────────────────── */
export function BacktestView({ symbols }: { symbols: string[] }) {
  const [strats, setStrats] = useState<Record<string, Strategy>>({});
  const today = new Date().toISOString().slice(0, 10);
  const yearAgo = new Date(Date.now() - 365 * 86400_000).toISOString().slice(0, 10);
  const [f, setF] = useState({ symbol: symbols[0] ?? "BTC/USDT", tf: "1d" as Tf, start: yearAgo, end: today, strategy: "sma_cross", capital: "10000", commission_pct: "0.1", slippage_bps: "5", position_pct: "100" });
  const [params, setParams] = useState<Record<string, string>>({});
  const [res, setRes] = useState<BacktestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [hist, setHist] = useState<Awaited<ReturnType<typeof desk.backtests>>>([]);
  useEffect(() => { desk.strategies().then(setStrats).catch(() => undefined); desk.backtests().then(setHist).catch(() => undefined); }, []);
  useEffect(() => { const s = strats[f.strategy]; if (s) setParams(Object.fromEntries(Object.entries(s.params).map(([k, v]) => [k, String(v)]))); }, [f.strategy, strats]);
  const run = () => {
    setBusy(true); setErr(null);
    desk.backtest({ symbol: f.symbol, tf: f.tf, start: f.start, end: f.end, strategy: f.strategy,
      params: Object.fromEntries(Object.entries(params).map(([k, v]) => [k, toNum(v) ?? 0])),
      capital: toNum(f.capital) ?? 10000, commission_pct: toNum(f.commission_pct) ?? 0, slippage_bps: toNum(f.slippage_bps) ?? 0, position_pct: toNum(f.position_pct) ?? 100 })
      .then((r) => { setRes(r); desk.backtests().then(setHist); }).catch((e: Error) => setErr(e.message)).finally(() => setBusy(false));
  };
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Backtesting</h2><p className="callout small">⚠ Los resultados históricos <strong>no garantizan</strong> resultados futuros. Se usan velas reales del proveedor; sin datos históricos no hay backtest.</p></div>
      <section className="dpanel">
        <div className="bt-form">
          <label>Activo<select value={f.symbol} onChange={(e) => setF({ ...f, symbol: e.target.value })}>{symbols.map((s) => <option key={s}>{s}</option>)}</select></label>
          <label>Temporalidad<select value={f.tf} onChange={(e) => setF({ ...f, tf: e.target.value as Tf })}>{TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}</select></label>
          <label>Desde<input type="date" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} /></label>
          <label>Hasta<input type="date" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} /></label>
          <label>Estrategia<select value={f.strategy} onChange={(e) => setF({ ...f, strategy: e.target.value })}>{Object.entries(strats).map(([k, s]) => <option key={k} value={k}>{s.name}</option>)}</select></label>
          {Object.entries(params).map(([k, v]) => <label key={k}>{k}<input inputMode="decimal" value={v} onChange={(e) => setParams({ ...params, [k]: e.target.value })} /></label>)}
          <label>Capital<input inputMode="decimal" value={f.capital} onChange={(e) => setF({ ...f, capital: e.target.value })} /></label>
          <label>Comisión %<input inputMode="decimal" value={f.commission_pct} onChange={(e) => setF({ ...f, commission_pct: e.target.value })} /></label>
          <label>Deslizamiento bps<input inputMode="decimal" value={f.slippage_bps} onChange={(e) => setF({ ...f, slippage_bps: e.target.value })} /></label>
          <label>% del capital por operación<input inputMode="decimal" value={f.position_pct} onChange={(e) => setF({ ...f, position_pct: e.target.value })} /></label>
          <button type="button" className="btn" disabled={busy} onClick={run}>{busy ? "Simulando…" : "Ejecutar backtest"}</button>
        </div>
        {strats[f.strategy] && <p className="muted small">{strats[f.strategy].help}</p>}
        {err && <p className="error-line" role="alert">{err}</p>}
      </section>
      {res && (
        <section className="dpanel">
          <header className="dpanel-head"><span>{res.strategy_name} · {res.symbol} {res.tf} · {res.bars} velas ({res.source}, histórico)</span></header>
          <div className="stat-row">
            <Stat label="Rentabilidad" value={pct(res.return_pct)} cls={tone(res.return_pct)} />
            <Stat label="Comprar y mantener" value={pct(res.buy_hold_pct)} cls={tone(res.buy_hold_pct)} />
            <Stat label="Drawdown máx." value={pct(res.max_drawdown_pct, false)} />
            <Stat label="Operaciones" value={String(res.trades)} />
            <Stat label="Win rate" value={pct(res.win_rate, false, 1)} />
            <Stat label="Profit factor" value={typeof res.profit_factor === "number" ? num(res.profit_factor) : res.profit_factor ?? "N/D"} />
            <Stat label="Capital final" value={num(res.final_equity)} />
          </div>
          <MiniChart data={res.curve.map((c) => ({ time: c.time, value: c.equity }))} baseline={res.capital} height={260} />
          <p className="callout small">{res.warning}{res.open_at_end ? " La última posición sigue abierta y se valora al último cierre." : ""}</p>
        </section>
      )}
      {!!hist.length && (
        <section className="dpanel">
          <header className="dpanel-head"><span>BACKTESTS ANTERIORES</span></header>
          <table className="dtable compact"><thead><tr><th>Fecha</th><th>Activo</th><th>Estrategia</th><th>Rent.</th><th>DD</th><th>Ops</th></tr></thead>
            <tbody>{hist.map((h) => (
              <tr key={h.id}><td className="mono">{dt(h.created_at)}</td><td>{String(h.params.symbol)} {String(h.params.tf)}</td><td>{String(h.summary.strategy_name)}</td>
                <td className={`mono ${tone(h.summary.return_pct as number)}`}>{pct(h.summary.return_pct as number)}</td><td className="mono">{pct(h.summary.max_drawdown_pct as number, false)}</td>
                <td className="mono">{String(h.summary.trades)}</td></tr>
            ))}</tbody></table>
        </section>
      )}
    </div>
  );
}

/* ───────────────────────── Noticias y macro ───────────────────────── */
export function NewsView() {
  const [n, setN] = useState<{ items: NewsItem[]; errors: string[]; note: string | null } | null>(null);
  const [m, setM] = useState<{ series: MacroSeries[]; source?: string; kind?: string; note: string | null } | null>(null);
  const [c, setC] = useState<Awaited<ReturnType<typeof desk.calendar>> | null>(null);
  useEffect(() => { desk.news().then(setN).catch(() => undefined); desk.macro().then(setM).catch(() => undefined); desk.calendar().then(setC).catch(() => undefined); }, []);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Market news & economic calendar</h2>
        <p className="muted small">Cada noticia muestra su medio, el proveedor y la fecha. VISTAN no verifica el contenido de las noticias: contrasta antes de tomar decisiones.</p></div>
      <div className="mod-cols">
        <section className="dpanel grow">
          <header className="dpanel-head"><span>NOTICIAS FINANCIERAS</span><span>{n?.items.length ?? 0}</span></header>
          {n?.note && <p className="callout small">{n.note}</p>}
          {n?.errors.map((e) => <p key={e} className="error-line">{e}</p>)}
          <ul className="news">{n?.items.map((x) => (
            <li key={x.url}>
              <a href={x.url} target="_blank" rel="noreferrer noopener">{x.title}</a>
              <span className="sub">{x.source} · vía {x.provider} · {dt(x.published)}{x.sentiment ? ` · sentimiento: ${x.sentiment}` : ""} · <em>no verificada por VISTAN</em></span>
              {x.summary && <p>{x.summary.slice(0, 260)}{x.summary.length > 260 ? "…" : ""}</p>}
            </li>
          ))}</ul>
        </section>
        <section className="dpanel">
          <header className="dpanel-head"><span>MACRO (TIPOS, INFLACIÓN, EMPLEO)</span></header>
          {m?.note && <p className="callout small">{m.note}</p>}
          {m?.source && <p className="muted small">{m.source} · {m.kind}</p>}
          <ul className="macro">{m?.series.map((s) => (
            <li key={s.id}>
              <span>{s.name}</span>
              {s.error ? <em className="error-line">{s.error}</em> : s.data[0]
                ? <b className="mono">{num(s.data[0].value, 2)} {s.unit === "%" ? "%" : ""}<small> · {s.data[0].date}{s.data[1] ? ` (antes ${num(s.data[1].value, 2)})` : ""}</small></b> : <em>N/D</em>}
            </li>
          ))}</ul>
          <header className="dpanel-head"><span>CALENDARIO ECONÓMICO (14 días)</span></header>
          {c?.note && <p className="callout small">{c.note}</p>}
          {!!c?.events.length && (
            <table className="dtable compact"><thead><tr><th>Fecha</th><th>País</th><th>Evento</th><th>Impacto</th><th>Prev.</th><th>Est.</th><th>Real</th></tr></thead>
              <tbody>{c.events.slice(0, 80).map((e, i) => (
                <tr key={i}><td className="mono">{e.time}</td><td>{e.country}</td><td>{e.event}</td><td>{e.impact}</td><td className="mono">{e.prev ?? "—"}</td><td className="mono">{e.estimate ?? "—"}</td><td className="mono">{e.actual ?? "—"}</td></tr>
              ))}</tbody></table>
          )}
        </section>
      </div>
    </div>
  );
}

/* ───────────────────────── Datos y conexiones ───────────────────────── */
export function DataView() {
  const [ps, setPs] = useState<Provider[] | null>(null);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const load = (test = false) => { setBusy(test); desk.providers(test).then(setPs).catch((e: Error) => setMsg(e.message)).finally(() => setBusy(false)); };
  useEffect(() => load(false), []);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Datos de mercado y conexiones</h2>
        <p className="muted small">Solo proveedores de <strong>datos</strong>. No hay integración con ningún bróker ni forma de operar con dinero real. Las claves se guardan en el llavero de tu Mac, nunca en la base de datos.</p></div>
      <div className="legend">
        <span><b className="kind-tag k-realtime">TR</b> Tiempo real</span><span><b className="kind-tag k-plan">TR/RET</b> Según tu plan</span>
        <span><b className="kind-tag k-delayed">RET</b> Con retraso</span><span><b className="kind-tag k-historical">HIST</b> Histórico</span><span><b className="kind-tag k-none">N/D</b> Sin datos</span>
      </div>
      <button type="button" className="btn ghost" disabled={busy} onClick={() => load(true)}>{busy ? "Probando…" : "Probar conexiones"}</button>
      {msg && <p className="muted small">{msg}</p>}
      <div className="prov-grid">{ps?.map((p) => (
        <section key={p.id} className="dpanel">
          <header className="dpanel-head"><span>{p.name.toUpperCase()}</span><span className={`prov-state s-${p.state.replace(/\s/g, "-")}`}>{p.state}</span></header>
          <p className="small">{p.covers}</p>
          <p className="muted small">Datos: <b className={`kind-tag k-${p.kind}`}>{p.kind_label}</b> · {p.limits}</p>
          <p className="muted small mono">Latencia: {p.latency_ms !== null ? `${p.latency_ms} ms` : "N/D"} · OK {p.ok} · errores {p.errors}{p.last_at ? ` · ${dt(p.last_at)}` : ""}</p>
          {p.last_error && <p className="error-line small">Último error: {p.last_error}</p>}
          {p.needs_key && (
            <div className="filters">
              <input type="password" autoComplete="off" value={keys[p.id] ?? ""} onChange={(e) => setKeys({ ...keys, [p.id]: e.target.value })}
                placeholder={p.configured ? "•••••• (guardada)" : "API key"} aria-label={`API key de ${p.name}`} />
              <button type="button" className="mini-btn" disabled={!keys[p.id]} onClick={() => desk.setKey(p.id, keys[p.id]).then(() => { setKeys({ ...keys, [p.id]: "" }); setMsg(`Clave de ${p.name} guardada`); load(true); }).catch((e: Error) => setMsg(e.message))}>Guardar</button>
              {p.configured && <button type="button" className="mini-btn ghost" onClick={() => desk.delKey(p.id).then(() => load()).catch(() => undefined)}>Quitar</button>}
              <a className="small" href={p.url} target="_blank" rel="noreferrer noopener">Obtener clave gratuita ↗</a>
            </div>
          )}
        </section>
      ))}</div>
    </div>
  );
}
