import { useState } from "react";
import { Link } from "react-router-dom";
import { academy, life, type Row } from "../../api/life";
import { MiniChart, Stat } from "../desk/ui";
import { fmtDate, Md, SchemaForm, State, useLoad } from "../life/kit";
import { type AMeta, type Go, nd, studyTime } from "./AcademyA";
import { ExamTaker } from "./AcademyB";

/* ───────── Knowledge Tracker ───────── */
export function Progress() {
  const { data: d, error, loading } = useLoad<Row>("/progress", [], academy);
  const st = d?.stats;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Knowledge Tracker</h2><p className="muted small">Solo actividad real: tiempo medido mientras estudias, lecciones completadas y evaluaciones corregidas.
        «Aprendido recientemente» y «consolidado» son estados distintos: consolidar exige aciertos repetidos y espaciados.</p></div>
      <State loading={loading && !d} error={error}>
        {st && <>
          <div className="stat-row"><Stat label="Tiempo de estudio" value={studyTime(st)} /><Stat label="Lecciones" value={String(st.lessons_done)} /><Stat label="Cursos finalizados" value={String(st.courses_done)} />
            <Stat label="Exámenes" value={String(st.exams)} /><Stat label="Nota media" value={nd(st.avg_score, " %")} /><Stat label="Retención" value={nd(st.retention_pct, " %")} hint={st.retention_rule} />
            <Stat label="Racha" value={`${st.streak} d`} /><Stat label="Días activos" value={String(st.active_days)} /></div>
          <div className="lg-levels">{Object.entries(st.concepts as Record<string, number>).map(([k, v]) => <span key={k} className={`ac-st-${k}`}><b>{v}</b> {k}</span>)}</div>
          {st.score_series.length > 1 && <section className="dpanel"><header className="dpanel-head"><span>EVOLUCIÓN DE NOTAS</span></header>
            <MiniChart data={st.score_series.map((p: Row, i: number) => ({ time: i + 1, value: p.score }))} height={160} /></section>}
          <section className="dpanel"><header className="dpanel-head"><span>PROGRESO POR MATERIA</span></header>
            {!d!.subjects.length ? <p className="desk-empty">Aún no has estudiado ninguna materia.</p> : <div className="table-scroll"><table className="dtable compact"><thead><tr><th>Materia</th><th>Nivel</th><th>Media</th><th>Tiempo</th><th>Lecciones</th><th>Consolidados</th><th>Recientes</th><th>Aprendiendo</th></tr></thead>
              <tbody>{d!.subjects.map((s: Row) => <tr key={s.subject_id}><td>{s.subject}</td><td>{s.level_label}</td><td className="mono">{nd(s.avg, " %")}</td><td className="mono">{s.minutes} min</td>
                <td className="mono">{s.lessons}</td><td className="mono">{s.consolidated}</td><td className="mono">{s.recent}</td><td className="mono">{s.learning}</td></tr>)}</tbody></table></div>}</section>
          <div className="mod-cols">
            {([["consolidated", "Consolidados"], ["recent", "Aprendidos recientemente"], ["learning", "En aprendizaje"]] as const).map(([k, l]) => (
              <section key={k} className="dpanel"><header className="dpanel-head"><span>{l.toUpperCase()}</span></header>
                {!d![k].length ? <p className="desk-empty">—</p> : <ul className="life-list compact">{d![k].map((c: Row) => <li key={c.id}><div className="life-item">{c.name} <small>dominio {c.mastery} · repaso {c.due_on ? fmtDate(c.due_on) : "—"}</small></div></li>)}</ul>}</section>))}
          </div>
          {d!.gamification && <section className="dpanel"><header className="dpanel-head"><span>NIVEL {d!.gamification.level} · {d!.gamification.xp} XP</span></header>
            <p className="small">{Object.entries(d!.gamification.breakdown as Record<string, number>).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
            <p className="d-tags">{d!.gamification.badges.map((b: string) => <span key={b} className="lab-tag t-commercial">{b}</span>)}</p></section>}
        </>}
      </State>
    </div>
  );
}

/* ───────── Practical Lab ───────── */
const LABS: [string, string][] = [["finance", "Finance Simulator"], ["business", "Business Simulator"], ["trading", "Trading Learning Lab"], ["programming", "Programming Lab"],
  ["negotiation", "Negotiation Simulator"], ["critical", "Critical Thinking Lab"]];

export function Labs() {
  const [tab, setTab] = useState("finance");
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Practical Lab</h2><p className="muted small">Práctica con fórmulas visibles y <b>dinero virtual</b>. Ningún ejercicio mueve dinero real ni envía órdenes a mercados.</p></div>
      <div className="ac-tabs">{LABS.map(([k, l]) => <button type="button" key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "finance" && <FinanceLab />}{tab === "business" && <BusinessLab />}{tab === "trading" && <TradingLab />}
      {tab === "programming" && <CodeLab />}{tab === "negotiation" && <NegotiationLab />}{tab === "critical" && <CriticalLab />}
    </div>
  );
}

function FinanceLab() {
  const [comp, setComp] = useState<Row | null>(null);
  const [bud, setBud] = useState<Row | null>(null);
  const [risk, setRisk] = useState<Row | null>(null);
  return (
    <div className="mod-cols">
      <section className="dpanel"><header className="dpanel-head"><span>INTERÉS COMPUESTO</span></header>
        <SchemaForm fields={[{ k: "start", label: "Capital inicial (€ virtuales)", type: "number", required: true }, { k: "monthly", label: "Aportación mensual", type: "number", required: true },
          { k: "rate_pct", label: "Rentabilidad anual %", type: "number", required: true }, { k: "years", label: "Años", type: "number", required: true }, { k: "inflation_pct", label: "Inflación %", type: "number" }]}
          initial={{ start: 1000, monthly: 100, rate_pct: 5, years: 10, inflation_pct: 2 }} submitLabel="Calcular" onSubmit={(v) => academy.post("/labs/finance/compound", v).then(setComp)} />
        {comp && <><p className="small">Final: <b>{comp.final.balance} €</b> (aportado {comp.final.contributed} €, intereses {comp.final.interest} €, en euros de hoy {comp.final.real} €)</p>
          <MiniChart data={comp.rows.map((r: Row) => ({ time: r.year, value: r.balance }))} height={140} /><p className="mini-note">{comp.formula}. {comp.note}</p></>}</section>
      <section className="dpanel"><header className="dpanel-head"><span>PRESUPUESTO</span></header>
        <SchemaForm fields={[{ k: "income", label: "Ingresos", type: "number", required: true }, { k: "needs", label: "Necesidades", type: "number", required: true },
          { k: "wants", label: "Deseos", type: "number", required: true }, { k: "savings", label: "Ahorro", type: "number", required: true }]} submitLabel="Analizar" onSubmit={(v) => academy.post("/labs/finance/budget", v).then(setBud)} />
        {bud && <><p className="small">{Object.entries(bud.percent as Record<string, number>).map(([k, v]) => `${k}: ${v} %`).join(" · ")} · sin asignar: {bud.unassigned}</p>
          <ul className="small">{bud.observations.map((o: string) => <li key={o}>{o}</li>)}</ul><p className="mini-note">{bud.note}</p></>}
        <header className="dpanel-head"><span>RIESGO Y RENTABILIDAD</span></header>
        <SchemaForm fields={[{ k: "amount", label: "Inversión virtual", type: "number", required: true }, { k: "mean_pct", label: "Rentabilidad media %", type: "number", required: true },
          { k: "vol_pct", label: "Volatilidad %", type: "number", required: true }, { k: "years", label: "Años", type: "number", required: true }]}
          initial={{ amount: 10000, mean_pct: 6, vol_pct: 15, years: 10 }} submitLabel="Simular" onSubmit={(v) => academy.post("/labs/finance/risk", v).then(setRisk)} />
        {risk && <><p className="small">Escenarios: pesimista (P5) {risk.p5} € · mediana {risk.median} € · optimista (P95) {risk.p95} € · probabilidad de perder: {risk.loss_prob_pct} %</p>
          <p className="mini-note">{risk.model} · {risk.runs} simulaciones (semilla {risk.seed}). {risk.note}</p></>}</section>
    </div>
  );
}

function BusinessLab() {
  const list = useLoad<Row[]>("/labs?kind=business", [], academy);
  const [sel, setSel] = useState<Row | null>(null);
  const reload = (id: number) => academy.get(`/labs/${id}`).then(setSel);
  return (
    <div className="mod-cols">
      <section className="dpanel meta-runs"><header className="dpanel-head"><span>TUS EMPRESAS FICTICIAS</span></header>
        <SchemaForm fields={[{ k: "name", label: "Nombre", required: true }, { k: "model", label: "Modelo de negocio", required: true }, { k: "market_demand", label: "Demanda base (ud/mes)", type: "number", required: true },
          { k: "competitor_price", label: "Precio de la competencia", type: "number", required: true }, { k: "elasticity", label: "Elasticidad precio (1,5 típica)", type: "number" }]}
          initial={{ elasticity: 1.5 }} submitLabel="Crear empresa" onSubmit={(v) => academy.post("/labs/business", v).then((x) => { setSel(x); list.reload(); })} />
        <ul className="exp-list">{list.data?.map((x) => <li key={x.id}><button type="button" className={sel?.id === x.id ? "on" : ""} onClick={() => setSel(x)}><b>{x.title}</b><small>{x.state.rounds.length} rondas · {x.status}</small></button></li>)}</ul></section>
      {sel && <section className="dpanel grow"><header className="dpanel-head"><span>{sel.title.toUpperCase()} · {sel.state.model}</span>
        {sel.status !== "done" && <button type="button" className="mini-btn" disabled={!sel.state.rounds.length} onClick={() => academy.post(`/labs/${sel.id}/finish`).then((x) => { setSel(x); list.reload(); })}>Evaluar resultados</button>}</header>
        {sel.status !== "done" && <SchemaForm fields={[{ k: "price", label: "Tu precio", type: "number", required: true }, { k: "unit_cost", label: "Coste por unidad", type: "number", required: true },
          { k: "fixed_costs", label: "Costes fijos / mes", type: "number", required: true }, { k: "marketing", label: "Marketing", type: "number" }, { k: "decision", label: "Tu razonamiento", type: "textarea" }]}
          submitLabel="Jugar ronda" onSubmit={(v) => academy.post(`/labs/${sel.id}/round`, v).then(() => reload(sel.id))} />}
        <div className="table-scroll"><table className="dtable compact"><thead><tr><th>Ronda</th><th>Precio</th><th>Unidades</th><th>Ingresos</th><th>Margen</th><th>Beneficio</th><th>Punto muerto</th></tr></thead>
          <tbody>{sel.state.rounds.map((r: Row) => <tr key={r.n}><td>{r.n}</td><td className="mono">{r.input.price}</td><td className="mono">{r.result.units}</td><td className="mono">{r.result.revenue}</td>
            <td className="mono">{r.result.gross_margin_pct} %</td><td className={`mono ${r.result.profit < 0 ? "neg" : ""}`}>{r.result.profit}</td><td className="mono">{r.result.break_even_units ?? "—"}</td></tr>)}</tbody></table></div>
        {sel.state.rounds[0] && <p className="mini-note">{sel.state.rounds[0].result.formula}. {sel.state.rounds[0].result.note}</p>}
        {sel.result && <p className="small">Resultado: <b>{sel.result.score}/100</b> · beneficio total {sel.result.total_profit} · {sel.result.profitable_rounds} rondas con beneficio · tendencia {sel.result.trend}. <small>{sel.result.rule}</small></p>}
      </section>}
    </div>
  );
}

function TradingLab() {
  const [res, setRes] = useState<Row | null>(null);
  const [err, setErr] = useState<string | null>(null);
  return (
    <section className="dpanel">
      <p className="small">Backtesting educativo de estrategias (cruce de medias o RSI) sobre datos históricos del Trading Desk o una serie de precios que pegues. Para practicar con precios en vivo usa el
        {" "}<Link to="/trading">Trading Desk</Link> en modo simulado.</p>
      <SchemaForm fields={[{ k: "symbol", label: "Símbolo del Trading Desk (p. ej. BTCUSDT)" }, { k: "closes", label: "…o precios de cierre separados por comas", type: "textarea" },
        { k: "strategy", label: "Estrategia", type: "select", options: [["sma", "Cruce de medias (SMA)"], ["rsi", "RSI 30/70"]], required: true },
        { k: "fast", label: "Media rápida", type: "number" }, { k: "slow", label: "Media lenta", type: "number" }, { k: "capital", label: "Capital virtual", type: "number" }]}
        initial={{ strategy: "sma", fast: 10, slow: 30, capital: 10000 }} submitLabel="Ejecutar backtest"
        onSubmit={(v) => { setErr(null); return academy.post("/labs/trading/backtest", { ...v, symbol: v.symbol || null, closes: v.closes ? String(v.closes).split(/[,;\s]+/).map(Number).filter((n) => !Number.isNaN(n)) : null })
          .then((x) => setRes(x.result)).catch((e: Error) => setErr(e.message)); }} />
      {err && <p className="error-line">{err}</p>}
      {res && <><div className="stat-row"><Stat label="Rentabilidad" value={`${res.return_pct} %`} /><Stat label="Comprar y mantener" value={`${res.buy_hold_pct} %`} /><Stat label="Máx. drawdown" value={`${res.max_drawdown_pct} %`} />
        <Stat label="Operaciones" value={String(res.trades)} /><Stat label="Acierto" value={nd(res.win_rate_pct, " %")} /></div>
        <MiniChart data={res.equity.map((v: number, i: number) => ({ time: i + 1, value: v }))} height={160} /><p className="mini-note">{res.note}</p></>}
    </section>
  );
}

function CodeLab() {
  const [ex, setEx] = useState<Row | null>(null);
  const [code, setCode] = useState("");
  const [last, setLast] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <section className="dpanel">
      <p className="small">Retos generados con su solución de referencia <b>comprobada en el sandbox aislado</b> antes de dártelos. Tu código se corrige ejecutando los tests en el sandbox (sin red ni acceso a tus archivos).</p>
      <SchemaForm fields={[{ k: "topic", label: "Tema", required: true }, { k: "level", label: "Nivel 1-5", type: "number" }]} initial={{ topic: "funciones", level: 1 }} submitLabel={busy ? "Generando…" : "Nuevo reto"}
        onSubmit={(v) => { setBusy(true); setErr(null); return academy.post("/labs/programming", v).then((x) => { setEx(x); setCode(x.state.template || ""); setLast(null); }).catch((e: Error) => setErr(e.message)).finally(() => setBusy(false)); }} />
      {err && <p className="error-line">{err}</p>}
      {ex && <div><h4>{ex.title}</h4><Md text={ex.state.statement} /><pre className="arena-out">{ex.state.tests}</pre>
        <textarea className="code" rows={12} value={code} onChange={(e) => setCode(e.target.value)} aria-label="Tu código" spellCheck={false} />
        <div className="row-btns"><button type="button" className="btn" disabled={!code.trim()} onClick={() => academy.post(`/labs/${ex.id}/submit`, { code }).then((r) => { setLast(r.last); setEx(r); })}>Ejecutar tests</button>
          {ex.state.hint && <details><summary>Pista</summary><p className="small">{ex.state.hint}</p></details>}</div>
        {last && <p className={`small ${last.score === 100 ? "" : "neg"}`}>{last.score === 100 ? "✓ Todos los tests superados" : `✗ ${last.feedback}`}</p>}
        {ex.status === "done" && ex.state.solution && <details><summary>Solución de referencia</summary><pre className="arena-out">{ex.state.solution}</pre></details>}</div>}
    </section>
  );
}

function NegotiationLab() {
  const sc = useLoad<Record<string, Row>>("/scenarios", [], life);
  const [sim, setSim] = useState<Row | null>(null);
  const [say, setSay] = useState("");
  const [busy, setBusy] = useState(false);
  const neg = Object.entries(sc.data ?? {}).filter(([, v]) => ["negotiation", "leadership"].includes(v.area) && /negoci|contrat|sueldo|socio|alquiler|proveedor|inversor|cliente/i.test(v.title));
  return (
    <section className="dpanel">
      <p className="small">La IA interpreta a la otra parte; al terminar recibes una evaluación de tu estrategia (usa el simulador de LIFE OS).</p>
      {!sim ? <div className="ac-grid">{neg.map(([k, v]) => <button type="button" key={k} className="ac-subject" onClick={() => { setBusy(true); life.post("/sims", { scenario: k }).then(setSim).finally(() => setBusy(false)); }}><b>{v.title}</b><small>{v.brief}</small></button>)}</div> : (
        <div><ul className="life-list compact">{sim.transcript.map((m: Row, i: number) => <li key={i}><div className="life-item"><b>{m.role === "user" ? "Tú" : "Otra parte"}:</b> {m.content}</div></li>)}</ul>
          {!sim.debrief ? <form className="tutor-in" onSubmit={(e) => { e.preventDefault(); setBusy(true); life.post(`/sims/${sim.id}/say`, { text: say }).then((x) => { setSim(x); setSay(""); }).finally(() => setBusy(false)); }}>
            <input value={say} onChange={(e) => setSay(e.target.value)} placeholder="Tu respuesta…" aria-label="Tu respuesta en la negociación" />
            <button type="submit" className="btn" disabled={busy || !say.trim()}>Responder</button>
            <button type="button" className="btn ghost" disabled={busy} onClick={() => { setBusy(true); life.post(`/sims/${sim.id}/finish`).then(setSim).finally(() => setBusy(false)); }}>Terminar y evaluar</button></form>
            : <div className="sc-block"><h4>Evaluación</h4><p className="small">{sim.debrief.resumen}</p><p className="small">{Object.entries(sim.debrief.criterios ?? {}).map(([k, v]) => `${k}: ${v}/5`).join(" · ")}</p>
              <button type="button" className="btn ghost" onClick={() => setSim(null)}>Otra negociación</button></div>}</div>)}
    </section>
  );
}

function CriticalLab() {
  const [exam, setExam] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return exam ? <section className="dpanel"><ExamTaker exam={exam} onClose={() => setExam(null)} /></section> : (
    <section className="dpanel"><p className="small">Falacias, lógica, interpretación de datos y resolución de problemas. Corrección exacta con explicación.</p>
      <button type="button" className="btn" disabled={busy} onClick={() => { setBusy(true); setErr(null); academy.post("/labs/critical").then(setExam).catch((e: Error) => setErr(e.message)).finally(() => setBusy(false)); }}>{busy ? "Preparando…" : "Nuevo desafío"}</button>
      {err && <p className="error-line">{err}</p>}</section>
  );
}

/* ───────── Research & Knowledge ───────── */
export function ResearchView() {
  const list = useLoad<Row[]>("/research", [], academy);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Row | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const m = sel?.result;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Research & Knowledge Engine</h2><p className="muted small">Usa el Research Engine de VISTAN (fuentes web con fiabilidad y fecha). El material de estudio separa lo
        <b> verificado con fuente</b>, las interpretaciones, las hipótesis y la explicación generada por IA. Sin bibliografía inventada: solo las fuentes leídas.</p></div>
      <form className="filters" onSubmit={(e) => { e.preventDefault(); academy.post("/research", { question: q }).then(() => { setQ(""); list.reload(); }).catch((x: Error) => setMsg(x.message)); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="¿Qué quieres investigar para estudiar?" aria-label="Tema a investigar" minLength={6} required /><button type="submit" className="btn">Investigar</button></form>
      {msg && <p className="error-line">{msg}</p>}
      <div className="mod-cols">
        <section className="dpanel meta-runs"><ul className="exp-list">{list.data?.map((x) => <li key={x.id}><button type="button" className={sel?.id === x.id ? "on" : ""} onClick={() => setSel(x)}>
          <span className="exp-state">{x.research?.status}</span><b>{x.title}</b><small>{x.research?.sources_count ?? 0} fuentes · {fmtDate(x.created_at)}</small></button></li>)}</ul>
          <button type="button" className="link-btn" onClick={list.reload}>actualizar</button></section>
        {sel && <section className="dpanel grow"><header className="dpanel-head"><span>{sel.title.toUpperCase()}</span>
          {!m && <button type="button" className="mini-btn" disabled={sel.research?.status !== "done"} onClick={() => academy.post(`/research/${sel.id}/material`).then((x) => { setSel({ ...sel, ...x }); list.reload(); }).catch((e: Error) => setMsg(e.message))}>
            {sel.research?.status === "done" ? "Crear material de estudio" : `Investigación: ${sel.research?.status}`}</button>}</header>
          {sel.research?.error && <p className="warn-line l-warn">{sel.research.error}</p>}
          {m && <>
            <div className="sc-block facts"><h4>Verificado (con fuente)</h4><ul>{m.verificado.map((v: Row, i: number) => <li key={i}>{v.texto} <small>[{v.fuentes.join(", ")}]</small></li>)}</ul>
              {m.sin_fuente_descartado > 0 && <p className="mini-note">{m.sin_fuente_descartado} afirmación(es) sin fuente válida se descartaron.</p>}</div>
            {!!m.interpretaciones.length && <div className="sc-block hyp"><h4>Interpretaciones</h4><ul>{m.interpretaciones.map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
            {!!m.hipotesis.length && <div className="sc-block pred"><h4>Hipótesis</h4><ul>{m.hipotesis.map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
            <div className="sc-block"><h4>Explicación generada por IA</h4><Md text={m.explicacion_ia} /></div>
            <h4>Bibliografía (fuentes leídas)</h4><ol className="small">{m.bibliografia.map((s: Row) => <li key={s.id}><a href={s.url} target="_blank" rel="noreferrer noopener">{s.titulo}</a> <small>fiabilidad {s.fiabilidad}</small></li>)}</ol>
          </>}</section>}
      </div>
    </div>
  );
}

/* ───────── Learning Paths ───────── */
export function Paths({ go }: { go: Go }) {
  const list = useLoad<Row[]>("/paths", [], academy);
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const examples = ["De principiante a emprendedor", "De principiante a programador", "Formación completa en inteligencia artificial", "Economía y finanzas desde cero", "Inglés profesional"];
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Personal Learning Paths</h2><p className="muted small">Itinerarios con objetivo, competencias, orden, evaluación, proyecto y criterio para avanzar. Cada paso se desbloquea al superar el anterior.</p></div>
      <form className="filters" onSubmit={(e) => { e.preventDefault(); setBusy("new"); setErr(null); academy.post("/paths", { goal }).then(() => { setGoal(""); list.reload(); }).catch((x: Error) => setErr(x.message)).finally(() => setBusy(null)); }}>
        <input value={goal} onChange={(e) => setGoal(e.target.value)} list="ac-path-ex" placeholder="Tu objetivo final" aria-label="Objetivo del itinerario" required minLength={6} />
        <datalist id="ac-path-ex">{examples.map((x) => <option key={x} value={x} />)}</datalist><button type="submit" className="btn" disabled={!!busy}>{busy === "new" ? "Diseñando…" : "Crear itinerario"}</button></form>
      {err && <p className="error-line">{err}</p>}
      <State loading={list.loading && !list.data} error={list.error} empty={list.data && !list.data.length ? "Aún no hay itinerarios." : false}>
        {list.data?.map((p) => <section key={p.id} className="dpanel"><header className="dpanel-head"><span>{p.title.toUpperCase()}</span>
          <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar el itinerario? Los cursos creados se conservan.")) void academy.del(`/paths/${p.id}`).then(list.reload); }}>✕</button></header>
          <p className="small">Objetivo: {p.goal} · Competencias: {p.competencies.join(", ") || "—"}</p>
          <ol className="ac-path">{p.steps.map((s: Row, i: number) => <li key={i} className={s.passed ? "done" : s.unlocked ? "open" : "locked"}><b>{s.title}</b> <small>{s.subject} · avanzar con ≥ {s.min_score} %{s.best_score != null ? ` · mejor ${s.best_score} %` : ""}</small>
            <p className="mini-note">{s.why}{s.project ? ` · Proyecto: ${s.project}` : ""}</p>
            {s.course_id ? <button type="button" className="mini-btn ghost" onClick={() => go("courses", { id: String(s.course_id) })}>Abrir curso</button>
              : <button type="button" className="mini-btn" disabled={!s.unlocked || !!busy} onClick={() => { setBusy(`${p.id}-${i}`); academy.post(`/paths/${p.id}/steps/${i}/course`).then(list.reload).catch((x: Error) => setErr(x.message)).finally(() => setBusy(null)); }}>
                {busy === `${p.id}-${i}` ? "Creando…" : s.unlocked ? "Crear curso de este paso" : "Bloqueado"}</button>}
            <button type="button" className="mini-btn ghost" onClick={() => void academy.patch(`/paths/${p.id}`, { steps: p.steps.filter((_: Row, j: number) => j !== i) }).then(list.reload)} aria-label="Quitar paso">✕</button></li>)}</ol>
        </section>)}
      </State>
    </div>
  );
}

/* ───────── Learning Memory y ajustes ───────── */
export function MemoryView({ meta, onChange }: { meta: AMeta; onChange: () => void }) {
  const { data: d, reload } = useLoad<Row>("/memory", [], academy);
  const st = meta.settings;
  const set = (v: Row) => academy.put("/settings", v).then(() => { onChange(); reload(); });
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Learning Memory</h2><p className="muted small">Todo lo que la academia recuerda de ti para adaptar las clases. Puedes exportarlo o borrarlo. Los profesores consultan tu perfil
        (nivel, conceptos, errores, ritmo) sin repetir toda la información.</p></div>
      {d && <div className="stat-row">{[["courses", "Cursos"], ["lessons", "Lecciones"], ["exams", "Evaluaciones"], ["concepts", "Conceptos"], ["tutor_messages", "Mensajes con profesores"],
        ["sessions", "Sesiones de estudio"], ["labs", "Laboratorios"], ["paths", "Itinerarios"]].map(([k, l]) => <Stat key={k} label={l} value={String(d[k])} />)}</div>}
      <div className="row-btns"><a className="btn ghost" href="/api/academy/export">Exportar mis datos (JSON)</a>
        <button type="button" className="btn ghost" onClick={() => { if (window.confirm("¿Borrar todo el historial con los profesores?")) void academy.del("/tutor/history").then(reload); }}>Borrar historial del profesor</button>
        <Link className="btn ghost" to="/academy?s=progress">Ver y reiniciar conceptos</Link></div>
      <p className="mini-note">{d?.note}</p>
      <section className="dpanel"><header className="dpanel-head"><span>PREFERENCIAS EDUCATIVAS</span></header>
        <label className="check"><input type="checkbox" checked={!!st.gamification} onChange={(e) => void set({ gamification: e.target.checked })} /> Gamificación (XP, niveles e insignias)</label>
        <label className="check"><input type="checkbox" checked={!!st.voice_autoplay} onChange={(e) => void set({ voice_autoplay: e.target.checked })} /> Leer en voz alta las respuestas del profesor</label>
        <label className="check"><span>Estilo</span><select value={st.style} onChange={(e) => void set({ style: e.target.value })} aria-label="Estilo de aprendizaje">
          {["equilibrado", "practico", "teorico", "visual"].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label className="check"><span>Minutos por semana</span><input type="number" defaultValue={st.weekly_minutes} onBlur={(e) => void set({ weekly_minutes: Number(e.target.value) })} aria-label="Minutos por semana" /></label>
        <label className="check"><span>Lecciones por semana</span><input type="number" defaultValue={st.weekly_lessons} onBlur={(e) => void set({ weekly_lessons: Number(e.target.value) })} aria-label="Lecciones por semana" /></label>
      </section>
    </div>
  );
}
