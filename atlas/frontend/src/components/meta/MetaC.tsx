import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { lab, makeClient, meta, type Row } from "../../api/life";

const wf = makeClient("/api/workflows");
import { Stat } from "../desk/ui";
import { fmtDate, State, useLoad } from "../life/kit";
import { nd } from "./MetaA";

/* ───────── Intelligence Benchmark Center ───────── */
export function Bench() {
  const info = useLoad<Row>("/bench", [], meta);
  const models = useLoad<Row[]>("/arena/models", [], lab);
  const [pick, setPick] = useState<string[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const running = info.data?.runs?.some((r: Row) => ["queued", "running"].includes(r.status));
  useEffect(() => {
    if (!running) return;
    const t = window.setInterval(info.reload, 3000);
    return () => clearInterval(t);
  }, [running]); // eslint-disable-line react-hooks/exhaustive-deps
  const d = info.data;
  const cats: Record<string, string> = d?.compare?.categories ?? d?.categories ?? {};
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Intelligence Benchmark Center</h2><p className="muted small">Las mismas pruebas, en el mismo orden y con la misma comprobación automática para cada concursante:
        tus modelos configurados y el propio VISTAN META-BRAIN. Puntuaciones calculadas sin IA (número exacto, regex, tests de Python en el sandbox, datos reales, consistencia).
        Nada se inventa y no se declara ganador sin resultados.</p></div>
      <State loading={info.loading && !d} error={info.error}>
        {d && !d.installed && <section className="dpanel"><p className="small">La batería «VISTAN Benchmark v1» tiene {d.tests} pruebas en {Object.keys(cats).length} categorías.</p>
          <button type="button" className="btn" onClick={() => meta.post("/bench/install").then(info.reload)}>Instalar batería</button></section>}
        {d?.installed && <>
          <section className="dpanel"><header className="dpanel-head"><span>EJECUTAR · {d.tests.length} PRUEBAS</span></header>
            {!models.data?.length ? <p className="desk-empty">No hay modelos accesibles: abre Ollama o configura un proveedor.</p> : (
              <div className="check-grid">{models.data.map((m) => <label key={m.id} className="check"><input type="checkbox" checked={pick.includes(m.id)}
                onChange={(e) => setPick(e.target.checked ? [...pick, m.id] : pick.filter((x) => x !== m.id))} /> {m.label ?? m.id}</label>)}</div>)}
            <div className="row-btns"><button type="button" className="btn" disabled={!pick.length || running}
              onClick={() => lab.post("/arena/runs", { suite_id: d.suite_id, models: pick }).then(() => { setMsg("En marcha: cada concursante resuelve todas las pruebas"); info.reload(); }).catch((e: Error) => setMsg(e.message))}>
              {running ? "Ejecutando…" : "Comparar"}</button></div>
            {msg && <p className="small">{msg}</p>}<p className="mini-note">{d.conditions}</p></section>
          {!!d.compare.table.length && <section className="dpanel"><header className="dpanel-head"><span>RESULTADOS (ÚLTIMA EJECUCIÓN DE CADA CONCURSANTE)</span></header>
            <div className="table-scroll"><table className="dtable compact bench"><thead><tr><th>Concursante</th><th>Media</th>{Object.entries(cats).map(([k, l]) => <th key={k} title={l}>{l.split(" ")[0]}</th>)}
              <th>Fiabilidad</th><th>Latencia</th><th>Tokens</th><th>Coste</th></tr></thead>
              <tbody>{d.compare.table.map((t: Row) => <tr key={t.run_id}><td><b>{t.model}</b><br /><small>{t.status}</small></td><td className="mono">{nd(t.summary.avg_score)}</td>
                {Object.keys(cats).map((k) => <td key={k} className="mono">{nd(t.by_category[k])}</td>)}
                <td className="mono">{nd(t.summary.reliability_pct, " %")}</td><td className="mono">{nd(t.summary.avg_latency_ms, " ms")}</td><td className="mono">{nd(t.summary.tokens_out)}</td><td className="mono">{nd(t.summary.cost_usd, " $")}</td></tr>)}</tbody></table></div>
            <p className="small">{d.compare.best ? <>Mejor media medida: <b>{d.compare.best.model}</b> ({d.compare.best.avg_score}/100 en {d.compare.best.tests} pruebas). {d.compare.best.note}</>
              : "Sin «mejor» declarado: hace falta comparar al menos dos concursantes con resultados distintos."}</p></section>}
          <section className="dpanel"><header className="dpanel-head"><span>HISTORIAL Y EJEMPLOS</span></header>
            <ul className="exp-list">{d.runs.map((r: Row) => <li key={r.id}><button type="button" className={open === r.id ? "on" : ""} onClick={() => setOpen(open === r.id ? null : r.id)}>
              <span className="exp-state">{r.status}</span><b>{r.model}</b><small>{fmtDate(r.created_at)} · media {nd(r.summary?.avg_score)} · errores {nd(r.summary?.errors)}{r.error ? ` · ${r.error}` : ""}</small></button>
              {open === r.id && <div className="bench-detail">{r.results.map((x: Row) => { const t = d.tests[x.i] ?? {}; return (
                <details key={x.i} className="arena-test"><summary>{cats[t.category] ?? t.category} · {t.prompt?.slice(0, 80)} — <b>{x.error ? "error" : nd(x.score)}</b> <small>{x.scored_by ?? ""}</small></summary>
                  {x.error ? <p className="warn-line l-warn">{x.error}</p> : <pre className="arena-out">{x.output}</pre>}
                  <small>{x.latency_ms} ms{x.calls ? ` · ${x.calls} llamadas` : ""}{x.meta_run ? <> · <Link to={`/meta?run=${x.meta_run}`}>traza</Link></> : null}</small></details>); })}</div>}</li>)}</ul></section>
        </>}
      </State>
    </div>
  );
}

/* ───────── Self-Evaluation ───────── */
export function Evaluation() {
  const [days, setDays] = useState(30);
  const { data, error, loading } = useLoad<Row>(`/eval?days=${days}`, [days], meta);
  const m = data?.metrics;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Self-Evaluation Engine</h2><p className="muted small">Métricas calculadas solo con registros reales. Las recomendaciones proponen qué probar; nada cambia código,
        configuración ni modelos por sí solo.</p></div>
      <div className="filters"><select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Periodo">{[7, 30, 90, 365].map((n) => <option key={n} value={n}>Últimos {n} días</option>)}</select></div>
      <State loading={loading && !data} error={error}>
        {m && <>
          <div className="stat-row">
            <Stat label="Ejecuciones" value={String(m.runs)} /><Stat label="Completadas" value={nd(m.completion_pct, " %")} /><Stat label="Errores" value={nd(m.error_pct, " %")} />
            <Stat label="Latencia media" value={m.avg_latency_ms != null ? `${(m.avg_latency_ms / 1000).toFixed(1)} s` : "N/D"} /><Stat label="p95" value={m.p95_latency_ms != null ? `${(m.p95_latency_ms / 1000).toFixed(1)} s` : "N/D"} />
            <Stat label="Hechos con respaldo" value={nd(m.supported_pct, " %")} hint={`${m.verified_claims} hechos verificados`} /><Stat label="Con avisos graves" value={nd(m.runs_with_high_issues_pct, " %")} />
            <Stat label="Coste" value={nd(m.cost_usd, " $")} /><Stat label="Satisfacción" value={nd(m.feedback.positive_pct, " %")} hint={`${m.feedback.count} valoraciones`} />
            <Stat label="Fuentes fiables" value={nd(m.source_quality.high_pct, " %")} hint={`alta ${m.source_quality.alta} · media ${m.source_quality.media} · baja ${m.source_quality.baja}`} />
          </div>
          <section className="dpanel"><header className="dpanel-head"><span>RECOMENDACIONES (BASADAS EN DATOS)</span></header><ul className="small">{data!.recommendations.map((r: string) => <li key={r}>{r}</li>)}</ul></section>
          <div className="mod-cols">
            <section className="dpanel"><header className="dpanel-head"><span>POR MODO</span></header>
              {!Object.keys(data!.by_mode).length ? <p className="desk-empty">Sin ejecuciones en el periodo.</p> : <div className="table-scroll"><table className="dtable compact"><thead><tr><th>Modo</th><th>Ejecuciones</th><th>Completadas</th><th>Media</th></tr></thead>
                <tbody>{Object.entries(data!.by_mode as Record<string, Row>).map(([k, v]) => <tr key={k}><td>{k}</td><td className="mono">{v.runs}</td><td className="mono">{nd(v.completion_pct, " %")}</td><td className="mono">{v.avg_ms ? `${(v.avg_ms / 1000).toFixed(1)} s` : "N/D"}</td></tr>)}</tbody></table></div>}</section>
            <section className="dpanel"><header className="dpanel-head"><span>BENCHMARKS RECIENTES</span></header>
              {!data!.benchmarks.length ? <p className="desk-empty">Sin benchmarks: ve al Benchmark Center.</p> : <div className="table-scroll"><table className="dtable compact"><thead><tr><th>Batería</th><th>Modelo</th><th>Media</th><th>Fiabilidad</th></tr></thead>
                <tbody>{data!.benchmarks.slice(0, 10).map((b: Row, i: number) => <tr key={i}><td className="small">{b.suite}</td><td className="small">{b.model}</td><td className="mono">{nd(b.avg_score)}</td><td className="mono">{nd(b.reliability_pct, " %")}</td></tr>)}</tbody></table></div>}</section>
          </div>
          <p className="mini-note">{data!.note}</p>
        </>}
      </State>
    </div>
  );
}

/* ───────── Autonomous Execution ───────── */
export function Execution() {
  const list = useLoad<Row[]>("/exec", [], meta);
  const [goal, setGoal] = useState("");
  const [plan, setPlan] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const active = list.data?.some((w) => w.runs.some((r: Row) => ["running", "awaiting_approval"].includes(r.status)));
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(list.reload, 2500);
    return () => clearInterval(t);
  }, [active]); // eslint-disable-line react-hooks/exhaustive-deps
  const act = (p: Promise<unknown>) => p.then(list.reload).catch((e: Error) => setMsg(e.message));
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Autonomous Execution Engine</h2><p className="muted small">Objetivo → plan con pasos <b>reales</b> del motor de Automatizaciones → revisas → ejecutas.
        Los pasos de escritura o ejecución piden tu autorización según tu política; hay reintentos, checkpoints, cancelación y kill switch. No existen pasos para pagar, comprar, publicar ni enviar mensajes.</p></div>
      <section className="dpanel">
        <form className="meta-ask" onSubmit={(e) => { e.preventDefault(); setBusy(true); setMsg(null); setPlan(null);
          meta.post("/exec/plan", { goal }).then(setPlan).catch((x: Error) => setMsg(x.message)).finally(() => setBusy(false)); }}>
          <textarea rows={2} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="Objetivo (p. ej. «Prepárame la semana de exámenes: tareas, investigación del temario y recordatorio el domingo»)" aria-label="Objetivo" required minLength={6} />
          <div className="row-btns"><button type="submit" className="btn" disabled={busy || goal.trim().length < 6}>{busy ? "Planificando…" : "Crear plan"}</button></div>
        </form>
        {msg && <p className="error-line" role="alert">{msg}</p>}
        {plan && <div className="meta-plan">
          <p className="small"><b>{plan.name}</b> · {plan.understanding} <small>({plan.model})</small></p>
          <ol className="plan-steps">{plan.steps.map((s: Row, i: number) => <li key={i}><b>{s.label}</b> <span className={`lab-tag t-${s.level === "READ" ? "commercial" : "prototype"}`}>{s.level}</span>
            {s.needs_approval && <span className="lab-tag t-speculative">pedirá autorización</span>} <small>{Object.entries(s.params).map(([k, v]) => `${k}: ${v}`).join(" · ")}</small>
            {s.why && <p className="mini-note">{s.why}</p>}
            <button type="button" className="mini-btn ghost" aria-label={`Quitar paso ${i + 1}`} onClick={() => setPlan({ ...plan, steps: plan.steps.filter((_: Row, j: number) => j !== i) })}>✕</button></li>)}</ol>
          {!!plan.problems.length && <p className="warn-line l-warn">{plan.problems.join(" · ")}</p>}
          {!!plan.limitations.length && <p className="mini-note">Limitaciones: {plan.limitations.join(" · ")}</p>}
          {plan.verification && <p className="mini-note">Verificación prevista: {plan.verification}</p>}
          <div className="row-btns"><button type="button" className="btn" disabled={!plan.steps.length}
            onClick={() => meta.post("/exec", { goal, name: plan.name, steps: plan.steps }).then(() => { setPlan(null); setGoal(""); list.reload(); }).catch((e: Error) => setMsg(e.message))}>Ejecutar plan</button>
            <button type="button" className="btn ghost" onClick={() => setPlan(null)}>Descartar</button></div></div>}
      </section>
      <State loading={list.loading && !list.data} error={list.error} empty={list.data && !list.data.length ? "Aún no has lanzado objetivos." : false}>
        {list.data?.map((w) => <section key={w.id} className="dpanel"><header className="dpanel-head"><span>{w.name.toUpperCase()}</span><Link className="link-btn" to="/workflows">automatizaciones</Link></header>
          <p className="small">{w.goal}</p>
          {w.runs.map((r: Row) => <div key={r.id} className="exec-run">
            <p className="small"><b>{r.status}</b> · {fmtDate(r.started_at)}
              {["running", "awaiting_approval"].includes(r.status) && <button type="button" className="mini-btn ghost" onClick={() => act(wf.post(`/runs/${r.id}/cancel`))}>Cancelar</button>}
              {["error", "cancelled"].includes(r.status) && <button type="button" className="mini-btn ghost" onClick={() => act(wf.post(`/runs/${r.id}/retry`))}>Reintentar desde el checkpoint</button>}
              {r.status === "awaiting_approval" && <> · <Link to="/agents?tab=approvals">autorizar</Link></>}</p>
            <ol className="trace">{r.log.map((l: Row, i: number) => <li key={i} className={l.ok === false ? "bad" : ""}><b>{l.type}</b><span>{l.level}</span><p>{String(l.output ?? "").slice(0, 300)}</p></li>)}</ol>
          </div>)}</section>)}
      </State>
    </div>
  );
}

/* ───────── Multimodal ───────── */
export function Multimodal() {
  const { data, error, loading } = useLoad<Row[]>("/multimodal", [], meta);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Multimodal Intelligence</h2><p className="muted small">Comprobado ahora mismo con los componentes instalados. Una modalidad no se ofrece si no hay un proveedor real que la soporte.</p></div>
      <State loading={loading && !data} error={error}>
        <div className="idea-grid">{data?.map((m) => <article key={m.id} className="dpanel"><header className="dpanel-head"><span>{m.label.toUpperCase()}</span>
          <span className={`lab-tag t-${m.available ? "commercial" : "speculative"}`}>{m.available ? "disponible" : "no disponible"}</span></header>
          {m.via && <p className="small">Con: {m.via}</p>}{m.where && <p className="mini-note">Dónde: {m.where}</p>}{m.missing && <p className="small">{m.missing}</p>}</article>)}</div>
      </State>
    </div>
  );
}
