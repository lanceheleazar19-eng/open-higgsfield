import { useState } from "react";
import { Link } from "react-router-dom";
import { life, type Row } from "../../api/life";
import { MiniChart, Stat } from "../desk/ui";
import { AgentChat, Crud, eur, fmtDate, Md, SchemaForm, State, useLoad, type Field } from "./kit";

const t = (d: string) => Math.floor(new Date(d.length === 10 ? d + "T12:00:00Z" : d).getTime() / 1000);

/* ───────── Resumen / Growth analytics ───────── */
export function Overview({ go }: { go: (s: string) => void }) {
  const { data, error, loading } = useLoad<Row>("/overview");
  return (
    <State loading={loading} error={error}>
      {data && (
        <div className="desk-module">
          <div className="mod-head"><h2>Personal Growth Analytics</h2><p className="muted small">{data.note} Cada indicador indica cómo se calcula.</p></div>
          <div className="mod-cols">
            <section className="dpanel">
              <header className="dpanel-head"><span>HOY</span></header>
              {!data.habits_today.length ? <p className="desk-empty">Sin hábitos previstos hoy. <button type="button" className="link-btn" onClick={() => go("discipline")}>Crear hábitos</button></p> : (
                <ul className="life-checks">{data.habits_today.map((h: Row) => <li key={h.id} className={h.done ? "ok" : ""}>{h.done ? "✓" : "○"} {h.name}</li>)}</ul>
              )}
              {data.decisions_to_review.map((d: Row) => <p key={d.id} className="warn-line l-warn">Revisar decisión: {d.title} <button type="button" className="link-btn" onClick={() => go("decisions")}>abrir</button></p>)}
              {data.followups_due.map((c: Row) => <p key={c.id} className="warn-line l-warn">Seguimiento pendiente: {c.name} <button type="button" className="link-btn" onClick={() => go("crm")}>abrir</button></p>)}
              {data.overdue_commitments.map((c: Row) => <p key={c.id} className="warn-line l-block">Compromiso vencido: {c.title} ({fmtDate(c.due)})</p>)}
              {data.stalled_goals.map((g: Row) => <p key={g.id} className="warn-line l-warn">Objetivo estancado {g.idle_days} días: {g.title} <button type="button" className="link-btn" onClick={() => go("goals")}>plan</button></p>)}
              {data.discipline_findings.map((f: string) => <p key={f} className="small">• {f}</p>)}
            </section>
            <section className="dpanel">
              <header className="dpanel-head"><span>PATRIMONIO NETO</span><button type="button" className="link-btn" onClick={() => go("wealth")}>detalle</button></header>
              <div className="stat-row">
                <Stat label="Neto" value={eur(data.networth.net)} /><Stat label="Parte estimada" value={eur(data.networth.estimated_part)} />
                <Stat label="Capital de negocios" value={eur(data.networth.business_net)} />
              </div>
            </section>
          </div>
          <div className="growth-grid">{data.growth.map((a: Row) => (
            <section key={a.key} className="dpanel">
              <header className="dpanel-head"><span>{a.name.toUpperCase()}</span></header>
              <div className="ind-list">{a.indicators.map((i: Row) => (
                <div key={i.label} className="dstat" title={i.how}><span>{i.label}</span><strong className="mono">{i.value === null || i.value === undefined ? "N/D" : `${typeof i.value === "number" ? Math.round(i.value * 100) / 100 : i.value}${i.unit ? ` ${i.unit}` : ""}`}</strong><em>{i.how}</em></div>
              ))}</div>
              {a.series && a.series.values.some((v: number | null) => v !== null && v !== 0) ? (
                <div className="spark-bars" aria-label={`Evolución: ${a.series.unit}`}>{a.series.values.map((v: number | null, idx: number) => {
                  const max = Math.max(...a.series.values.map((x: number | null) => Math.abs(x ?? 0)), 1);
                  return <i key={idx} title={`${a.series.labels[idx]}: ${v ?? "N/D"}`} style={{ height: `${Math.max(2, (Math.abs(v ?? 0) / max) * 100)}%`, opacity: v === null ? 0.25 : 1 }} className={(v ?? 0) < 0 ? "neg" : ""} />;
                })}<small>{a.series.unit}</small></div>
              ) : a.series ? <p className="mini-note">Sin datos todavía para la evolución ({a.series.unit}).</p> : null}
            </section>
          ))}</div>
        </div>
      )}
    </State>
  );
}

/* ───────── Entrepreneur Intelligence ───────── */
const STATUS: [string, string][] = [["idea", "Idea"], ["research", "Investigando"], ["validating", "Validando"], ["building", "Construyendo"], ["launched", "Lanzada"], ["paused", "En pausa"], ["discarded", "Descartada"]];
const OPP_FIELDS: Field[] = [
  { k: "name", label: "Nombre", required: true }, { k: "status", label: "Estado", type: "select", options: STATUS, required: true },
  { k: "description", label: "Descripción", type: "textarea" }, { k: "problem", label: "Problema que resuelve", type: "textarea" },
  { k: "solution", label: "Solución", type: "textarea" }, { k: "market", label: "Mercado", type: "textarea" }, { k: "customer", label: "Cliente objetivo", type: "textarea" },
  { k: "competition", label: "Competencia", type: "textarea" }, { k: "suppliers", label: "Proveedores", type: "textarea" },
  { k: "business_model", label: "Modelo de negocio", type: "textarea" }, { k: "marketing", label: "Marketing y ventas", type: "textarea" },
  { k: "launch_plan", label: "Plan de lanzamiento", type: "textarea" }, { k: "risks", label: "Riesgos", type: "textarea" },
  { k: "resources", label: "Recursos necesarios", type: "textarea" }, { k: "next_actions", label: "Próximas acciones (una por línea)", type: "textarea" },
];
const ECON: [string, string][] = [["price", "Precio de venta (€/ud)"], ["unit_cost", "Coste variable (€/ud)"], ["fixed_monthly", "Costes fijos (€/mes)"], ["units_month", "Ventas estimadas (ud/mes)"], ["initial_investment", "Inversión inicial (€)"]];

export function Entrepreneur() {
  const { data, error, loading, reload } = useLoad<Row>("/opportunities");
  const [sel, setSel] = useState<number | null>(null);
  const [mode, setMode] = useState<"view" | "edit" | "new">("view");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const items: Row[] = data?.items ?? [];
  const o = items.find((x) => x.id === sel);
  const act = (label: string, fn: () => Promise<unknown>) => { setBusy(label); setMsg(null); fn().then(() => reload()).catch((e: Error) => setMsg(e.message)).finally(() => setBusy(null)); };
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Entrepreneur Intelligence</h2><p className="muted small">Tus oportunidades de negocio. Las cifras son <b>tus supuestos</b> (estimaciones), nunca datos confirmados.</p></div>
      <State loading={loading && !data} error={error}>
        <section className="dpanel">
          <header className="dpanel-head"><span>COMPARATIVA DE OPORTUNIDADES</span><button type="button" className="link-btn" onClick={() => { setMode("new"); setSel(null); }}>+ nueva</button></header>
          {!items.length ? <p className="desk-empty">Registra tu primera idea de negocio.</p> : (
            <div className="table-scroll"><table className="dtable">
              <thead><tr><th>Oportunidad</th><th>Estado</th><th>Puntuación</th><th>Margen bruto</th><th>Beneficio/mes (est.)</th><th>Punto muerto</th><th>Recuperación</th></tr></thead>
              <tbody>{items.map((x) => (
                <tr key={x.id} className={`click-row ${sel === x.id ? "sel" : ""}`} onClick={() => { setSel(x.id); setMode("view"); }}>
                  <td><strong>{x.name}</strong></td><td>{STATUS.find((s) => s[0] === x.status)?.[1]}</td>
                  <td className="mono">{x.score.score !== null ? `${x.score.score}/100 (${x.score.rated}/${x.score.of})` : "sin puntuar"}</td>
                  <td className="mono">{x.calc.gross_margin_pct != null ? `${x.calc.gross_margin_pct} %` : "—"}</td>
                  <td className="mono">{x.calc.profit_month != null ? eur(x.calc.profit_month) : "—"}</td>
                  <td className="mono">{x.calc.breakeven_units_month != null ? `${x.calc.breakeven_units_month} ud/mes` : "—"}</td>
                  <td className="mono">{x.calc.payback_months != null ? `${x.calc.payback_months} meses` : "—"}</td>
                </tr>
              ))}</tbody></table></div>
          )}
        </section>
        {mode === "new" && (
          <section className="dpanel"><header className="dpanel-head"><span>NUEVA OPORTUNIDAD</span></header>
            <SchemaForm fields={OPP_FIELDS} initial={{ status: "idea" }} onCancel={() => setMode("view")} submitLabel="Crear"
              onSubmit={(v) => life.post("/opportunities", v).then((r) => { setSel(r.id as number); setMode("view"); reload(); })} /></section>
        )}
        {o && mode === "edit" && (
          <section className="dpanel"><header className="dpanel-head"><span>EDITAR · {o.name}</span></header>
            <SchemaForm fields={OPP_FIELDS} initial={o} onCancel={() => setMode("view")} onSubmit={(v) => life.patch(`/opportunities/${o.id}`, v).then(() => { setMode("view"); reload(); })} /></section>
        )}
        {o && mode === "view" && (
          <div className="mod-cols">
            <section className="dpanel grow">
              <header className="dpanel-head"><span>{o.name.toUpperCase()}</span>
                <span className="row-actions">
                  <button type="button" className="mini-btn ghost" onClick={() => setMode("edit")}>Editar</button>
                  <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar esta oportunidad?")) act("del", () => life.del(`/opportunities/${o.id}`).then(() => setSel(null))); }}>Eliminar</button>
                </span></header>
              <dl className="opp-dl">{OPP_FIELDS.slice(2).filter((f) => o[f.k]).map((f) => <div key={f.k}><dt>{f.label}</dt><dd>{o[f.k]}</dd></div>)}</dl>
              <div className="filters">
                <button type="button" className="btn ghost" disabled={!!busy} onClick={() => act("research", () => life.post(`/opportunities/${o.id}/research`).then(() => setMsg("Investigación iniciada en Research (con fuentes). Cuando termine, genera el informe.")))}>
                  {o.research_id ? "Repetir investigación de mercado" : "Investigar mercado (web)"}</button>
                <button type="button" className="btn" disabled={!!busy} onClick={() => act("report", () => life.post(`/opportunities/${o.id}/analyze`))}>{busy === "report" ? "Analizando…" : "Informe del Business Agent"}</button>
                {o.project_id ? <Link className="btn ghost" to="/projects">Ver proyecto</Link>
                  : <button type="button" className="btn ghost" disabled={!!busy} onClick={() => act("project", () => life.post(`/opportunities/${o.id}/project`).then(() => setMsg("Proyecto creado con sus próximas acciones como tareas")))}>Convertir en proyecto</button>}
              </div>
              {msg && <p className="small">{msg}</p>}
              {o.report && (
                <div className="ai-text">
                  <p className="callout small">{o.report.label} · {o.report.model} · {fmtDate(o.report.generated_at)}{o.report.used_research ? " · con investigación web" : " · sin investigación web"}</p>
                  <p>{o.report.resumen}</p>
                  {o.report.dafo && <div className="swot">{[["fortalezas", "Fortalezas"], ["debilidades", "Debilidades"], ["oportunidades", "Oportunidades"], ["amenazas", "Amenazas"]].map(([k, l]) => (
                    <div key={k}><b>{l}</b><ul>{(o.report.dafo[k] ?? []).map((x: string) => <li key={x}>{x}</li>)}</ul></div>))}</div>}
                  {[["mercado", "Mercado"], ["clientes", "Clientes"], ["competencia", "Competencia"], ["modelo_negocio", "Modelo de negocio"], ["marketing_ventas", "Marketing y ventas"], ["viabilidad", "Viabilidad"]].map(([k, l]) => o.report[k] ? <p key={k}><b>{l}:</b> {o.report[k]}</p> : null)}
                  {!!o.report.plan_lanzamiento?.length && <><b>Plan de lanzamiento</b><ol>{o.report.plan_lanzamiento.map((x: string) => <li key={x}>{x}</li>)}</ol></>}
                  {!!o.report.riesgos?.length && <><b>Riesgos</b><ul>{o.report.riesgos.map((r: Row, i: number) => <li key={i}>{r.riesgo} → {r.mitigacion}</li>)}</ul></>}
                  {!!o.report.supuestos_criticos?.length && <><b>Supuestos críticos a validar</b><ul>{o.report.supuestos_criticos.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                  {!!o.report.experimentos_validacion?.length && <><b>Experimentos de validación</b><ul>{o.report.experimentos_validacion.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                  {!!o.report.datos_que_faltan?.length && <><b>Datos que faltan</b><ul>{o.report.datos_que_faltan.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                  {!!o.report.fuentes?.length && <><b>Fuentes</b><ul>{o.report.fuentes.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                </div>
              )}
            </section>
            <section className="dpanel">
              <header className="dpanel-head"><span>COSTES, MÁRGENES Y RENTABILIDAD (ESTIMADO)</span></header>
              <SchemaForm key={`e${o.id}${o.updated_at}`} fields={ECON.map(([k, l]) => ({ k, label: l, type: "number" as const }))} initial={o.economics ?? {}} submitLabel="Recalcular"
                onSubmit={(v) => life.patch(`/opportunities/${o.id}`, { economics: v }).then(reload)} />
              <div className="stat-row">
                <Stat label="Margen de contribución" value={o.calc.contribution_margin != null ? eur(o.calc.contribution_margin) : "—"} />
                <Stat label="Margen bruto" value={o.calc.gross_margin_pct != null ? `${o.calc.gross_margin_pct} %` : "—"} />
                <Stat label="Punto muerto" value={o.calc.breakeven_units_month != null ? `${o.calc.breakeven_units_month} ud/mes` : "—"} />
                <Stat label="Ingresos/mes" value={o.calc.revenue_month != null ? eur(o.calc.revenue_month) : "—"} />
                <Stat label="Beneficio/mes" value={o.calc.profit_month != null ? eur(o.calc.profit_month) : "—"} />
                <Stat label="Margen neto" value={o.calc.net_margin_pct != null ? `${o.calc.net_margin_pct} %` : "—"} />
                <Stat label="Recuperación" value={o.calc.payback_months != null ? `${o.calc.payback_months} meses` : "—"} />
                <Stat label="ROI anual" value={o.calc.roi_year_pct != null ? `${o.calc.roi_year_pct} %` : "—"} />
              </div>
              <p className="mini-note">{o.calc.basis}. {o.calc.note ?? ""}</p>
              <header className="dpanel-head"><span>EVALUACIÓN (TÚ PUNTÚAS 1-5)</span></header>
              <div className="score-grid">{Object.entries(data!.criteria as Record<string, string>).map(([k, l]) => (
                <label key={k}><span>{l}</span>
                  <select value={o.scores?.[k] ?? ""} aria-label={l} onChange={(e) => act("score", () => life.patch(`/opportunities/${o.id}`, { scores: { ...o.scores, [k]: e.target.value ? Number(e.target.value) : null } }))}>
                    <option value="">—</option>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
              ))}</div>
              <p className="small"><b>{o.score.score !== null ? `${o.score.score}/100` : "Sin puntuar"}</b> · <span className="mini-note">{o.score.formula}</span></p>
            </section>
          </div>
        )}
        <AgentChat area="entrepreneur" title="Entrepreneur Agent" quick={["Compara mis oportunidades y dime cuál validar primero y por qué",
          "¿Qué supuestos de mis números son más arriesgados?", "Diseña un experimento barato para validar mi mejor idea esta semana"]} />
      </State>
    </div>
  );
}

/* ───────── Wealth Management ───────── */
const ASSET_FIELDS: Field[] = [
  { k: "side", label: "Tipo", type: "select", options: [["asset", "Activo"], ["liability", "Pasivo / deuda"]], required: true },
  { k: "name", label: "Nombre", required: true }, { k: "category", label: "Categoría", placeholder: "cuenta, efectivo, inversión, préstamo…", required: true },
  { k: "value", label: "Valor (€)", type: "number", required: true },
  { k: "basis", label: "Base", type: "select", options: [["real", "Real (comprobado)"], ["estimated", "Estimado"]], required: true },
  { k: "scope", label: "Ámbito", type: "select", options: [["personal", "Personal"], ["business", "Negocio"]], required: true },
  { k: "notes", label: "Notas", type: "textarea" },
];

export function Wealth() {
  const { data, error, loading, reload } = useLoad<Row>("/wealth");
  const [sim, setSim] = useState<Row | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Wealth Management</h2><p className="muted small">Los ingresos, gastos y presupuestos reales se registran en <Link to="/finance">Finanzas</Link> (no se duplican). Aquí: patrimonio, simulaciones y capital de negocio. VISTAN nunca mueve dinero.</p></div>
      <State loading={loading && !data} error={error}>
        {data && (
          <>
            <div className="legend">{Object.entries(data.labels as Record<string, string>).map(([k, v]) => <span key={k} className={`basis b-${k}`}>{v}</span>)}</div>
            <div className="stat-row">
              <Stat label="Activos" value={eur(data.networth.assets)} /><Stat label="Pasivos" value={eur(data.networth.liabilities)} />
              <Stat label="Patrimonio neto" value={eur(data.networth.net)} /><Stat label="…de ello estimado" value={eur(data.networth.estimated_part)} />
              <Stat label="Personal" value={eur(data.networth.personal_net)} /><Stat label="Capital de negocios" value={eur(data.networth.business_net)} />
            </div>
            <div className="mod-cols">
              <section className="dpanel grow"><header className="dpanel-head"><span>EVOLUCIÓN DEL PATRIMONIO (registros)</span></header>
                <MiniChart data={data.history.map((h: Row) => ({ time: t(h.day), value: h.net }))} height={220} /></section>
              <section className="dpanel"><header className="dpanel-head"><span>AHORRO REAL MENSUAL (Finanzas)</span></header>
                <table className="dtable compact"><thead><tr><th>Mes</th><th>Ingresos</th><th>Gastos</th><th>Ahorro</th><th>Tasa</th></tr></thead>
                  <tbody>{data.savings.months.map((m: Row) => <tr key={m.month}><td>{m.month}</td><td className="mono">{eur(m.income)}</td><td className="mono">{eur(m.expense)}</td>
                    <td className={`mono ${m.saved >= 0 ? "up" : "down"}`}>{eur(m.saved)}</td><td className="mono">{m.rate != null ? `${m.rate} %` : "—"}</td></tr>)}</tbody></table></section>
            </div>
            <Crud title="Activos y pasivos" path="/wealth/items" fields={ASSET_FIELDS} newDefaults={{ side: "asset", basis: "real", scope: "personal" }}
              onChanged={reload} editPath={(r) => `/wealth/items/${r.id}`}
              render={(r) => <><b>{r.name}</b> <span className={`basis b-${r.basis}`}>{r.basis === "real" ? "real" : "estimado"}</span> <span className="basis b-business">{r.scope === "business" ? "negocio" : "personal"}</span>
                <span className={`mono ${r.side === "liability" ? "down" : "up"}`}> {r.side === "liability" ? "−" : ""}{eur(r.value)}</span><small> · {r.category}</small></>} />
            <section className="dpanel"><header className="dpanel-head"><span>DINERO VIRTUAL (NO CUENTA EN EL PATRIMONIO)</span></header>
              {!data.virtual.length ? <p className="desk-empty">Sin cuentas virtuales activas.</p> : <ul className="life-checks">{data.virtual.map((v: Row) => <li key={v.name + v.kind}>{v.kind}: {v.name} · <span className="mono">{eur(v.value)}</span></li>)}</ul>}</section>
            <section className="dpanel"><header className="dpanel-head"><span>SIMULADOR DE ESCENARIOS (no es una previsión)</span></header>
              <SchemaForm fields={[{ k: "start", label: "Capital inicial (€)", type: "number", required: true }, { k: "monthly", label: "Aportación mensual (€)", type: "number", required: true },
                { k: "annual_return_pct", label: "Rentabilidad anual supuesta %", type: "number", required: true }, { k: "years", label: "Años", type: "number", required: true },
                { k: "inflation_pct", label: "Inflación supuesta %", type: "number" }]} initial={{ start: data.networth.net > 0 ? data.networth.net : 0, monthly: 100, annual_return_pct: 4, years: 10, inflation_pct: 2 }}
                submitLabel="Simular" onSubmit={(v) => life.post("/wealth/simulate", v).then(setSim)} />
              {sim && (<><MiniChart data={sim.rows.map((r: Row) => ({ time: Date.UTC(2000 + r.year, 0, 1) / 1000, value: r.balance }))} height={200} area={false} color="#f1e6e2" />
                <div className="stat-row"><Stat label="Saldo final" value={eur(sim.final.balance)} /><Stat label="Aportado" value={eur(sim.final.contributed)} />
                  <Stat label="Crecimiento" value={eur(sim.final.growth)} /><Stat label="En euros de hoy" value={eur(sim.final.real_balance)} /></div>
                <p className="mini-note">{sim.basis}.</p></>)}
            </section>
          </>
        )}
        <AgentChat area="wealth" title="Wealth Agent" quick={["¿En qué estoy gastando más de lo que debería?", "¿Cómo puedo aumentar mi tasa de ahorro?", "Explícame interés compuesto con mis números"]} />
      </State>
    </div>
  );
}

/* ───────── Opportunity Radar ───────── */
const LENSES: [string, string][] = [["trends", "Tendencias"], ["problems", "Problemas que pueden ser negocios"], ["digital", "Oportunidades digitales"],
  ["models", "Modelos de negocio emergentes"], ["markets", "Comparar mercados"], ["advantages", "Ventajas competitivas"]];

export function Radar() {
  const { data, error, loading, reload } = useLoad<Row[]>("/radar");
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Opportunity Radar</h2><p className="muted small">Usa el motor de investigación de VISTAN: busca en webs públicas, cita fuentes con fecha y marca la confianza. Nada se presenta como seguro.</p></div>
      <section className="dpanel"><header className="dpanel-head"><span>NUEVA EXPLORACIÓN</span></header>
        <SchemaForm fields={[{ k: "query", label: "Sector, mercado o tema", required: true, placeholder: "p. ej. suplementos deportivos en España" },
          { k: "lens", label: "Enfoque", type: "select", options: LENSES, required: true }]} initial={{ lens: "trends" }} submitLabel="Investigar"
          onSubmit={(v) => life.post("/radar", v).then(reload)} /></section>
      <State loading={loading && !data} error={error} empty={data && !data.length ? "Aún no hay exploraciones." : false}>
        {data?.map((r) => (
          <section key={r.id} className="dpanel">
            <header className="dpanel-head"><span>{LENSES.find((l) => l[0] === r.lens)?.[1].toUpperCase()} · {r.query}</span>
              <span>{r.research?.status === "done" ? `confianza ${r.research.confidence ?? "N/D"}` : r.research?.step_label ?? r.research?.status}</span></header>
            {r.research?.status !== "done" ? <p className="desk-empty">{r.research?.status === "error" ? `Error: ${r.research.error}` : `En curso (${r.research?.progress ?? 0} %)…`} <button type="button" className="link-btn" onClick={reload}>actualizar</button></p> : (
              <div className="ai-text">
                <Md text={r.research.report?.summary} />
                {!!r.research.sources?.length && <><b>Fuentes (consultadas el {fmtDate(r.research.updated_at)})</b>
                  <ul>{r.research.sources.slice(0, 10).map((s: Row) => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer noopener">{s.title || s.url}</a> {s.reliability ? `· fiabilidad ${s.reliability}` : ""}</li>)}</ul></>}
              </div>
            )}
          </section>
        ))}
      </State>
      <AgentChat area="opportunity" title="Opportunity Agent" quick={["Resume lo que ha encontrado el radar y qué falta comprobar", "¿Qué ventaja competitiva podría tener yo con mis recursos?"]} />
    </div>
  );
}

/* ───────── Goal Engine (sobre los Objetivos existentes) ───────── */
export function Goals() {
  const { data, error, loading, reload } = useLoad<Row>("/goals");
  const [plan, setPlan] = useState<Record<number, Row>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [advice, setAdvice] = useState<Row | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Goal Engine</h2><p className="muted small">Usa tus <Link to="/tasks">objetivos y tareas</Link> de VISTAN (no se duplican). Crea objetivos allí con su fecha límite: el horizonte (1 mes … 10 años) se calcula solo.</p></div>
      <State loading={loading && !data} error={error} empty={data && !data.items.length ? "No hay objetivos activos. Créalos en Tareas → Objetivos." : false}>
        {!!data?.stalled.length && (
          <section className="dpanel"><header className="dpanel-head"><span>ESTANCADOS (≥14 DÍAS SIN AVANCE)</span>
            <button type="button" className="link-btn" onClick={() => life.post("/goals/stalled/advice").then(setAdvice).catch((e: Error) => setMsg(e.message))}>proponer acciones</button></header>
            {data.stalled.map((g: Row) => <p key={g.id} className="warn-line l-warn">{g.title}: {g.idle_days} días sin avance · {g.pending_tasks} tareas pendientes</p>)}
            {advice?.acciones?.map((a: Row) => <div key={a.objetivo} className="small"><b>{a.objetivo}</b><ul>{a.acciones.map((x: string) => <li key={x}>{x}</li>)}</ul><em>{a.por_que}</em></div>)}
          </section>
        )}
        {msg && <p className="error-line">{msg}</p>}
        {data?.items.map((g: Row) => (
          <section key={g.id} className="dpanel">
            <header className="dpanel-head"><span>{g.title.toUpperCase()} · {g.horizon}</span><span>{g.tasks_done}/{g.tasks} tareas · {g.deadline ? fmtDate(g.deadline) : "sin fecha"}</span></header>
            <div className="progress-bar"><i style={{ width: `${Math.round((g.metrics?.progress ?? 0) * 100)}%` }} /></div>
            <div className="filters">
              <button type="button" className="btn ghost" disabled={busy === g.id} onClick={() => { setBusy(g.id); life.post(`/goals/${g.id}/plan`).then((p) => setPlan({ ...plan, [g.id]: p })).catch((e: Error) => setMsg(e.message)).finally(() => setBusy(null)); }}>
                {busy === g.id ? "Planificando…" : "Descomponer con el Planning Agent"}</button>
            </div>
            {plan[g.id] && (
              <div className="ai-text">
                <p className="callout small">{plan[g.id].note} · {plan[g.id].model}</p>
                <b>Metas intermedias</b><ul>{(plan[g.id].metas_intermedias ?? []).map((m: Row) => <li key={m.titulo}>{m.titulo} · {m.fecha}</li>)}</ul>
                <b>Tareas</b><ul>{(plan[g.id].tareas ?? []).map((x: Row) => <li key={x.titulo}>{x.titulo} · {x.fecha} · {x.prioridad}</li>)}</ul>
                {!!plan[g.id].indicadores?.length && <><b>Indicadores</b><ul>{plan[g.id].indicadores.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                {!!plan[g.id].recursos?.length && <><b>Recursos</b><ul>{plan[g.id].recursos.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                <button type="button" className="btn" onClick={() => life.post(`/goals/${g.id}/plan/apply`, { tasks: [...(plan[g.id].metas_intermedias ?? []).map((m: Row) => ({ ...m, milestone: true })), ...(plan[g.id].tareas ?? [])] })
                  .then((r) => { setMsg(`${r.created} tareas creadas y vinculadas al objetivo`); setPlan({ ...plan, [g.id]: undefined as unknown as Row }); reload(); })}>Crear estas tareas</button>
              </div>
            )}
          </section>
        ))}
      </State>
      <AgentChat area="planning" title="Planning Agent" quick={["¿Qué objetivo debería priorizar esta semana?", "¿Mis objetivos son realistas con mi tiempo actual?"]} />
    </div>
  );
}
