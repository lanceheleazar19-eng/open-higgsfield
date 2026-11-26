import { useState } from "react";
import { Link } from "react-router-dom";
import { meta, type Row } from "../../api/life";
import { Stat } from "../desk/ui";
import { fmtDate, SchemaForm, State, useLoad } from "../life/kit";
import { nd } from "./MetaA";

/* ───────── Intelligent Model Router ───────── */
export function RouterView() {
  const { data, error, loading, reload } = useLoad<Row>("/router", [], meta);
  const [msg, setMsg] = useState<string | null>(null);
  const [test, setTest] = useState<Row | null>(null);
  const PRIV: Record<string, string> = { local_only: "Solo local", local_first: "Local primero", best_quality: "Mejor calidad" };
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Intelligent Model Router</h2><p className="muted small">Solo aparecen proveedores y modelos <b>realmente accesibles</b>. Elige claves, modelos, precios y preferencias
        por tarea en <Link to="/settings">Configuración → Modelos</Link>; aquí ves qué usará el META-BRAIN, en qué orden (fallback) y cómo rinde cada modelo según el registro real de llamadas.</p></div>
      <State loading={loading && !data} error={error}>
        {data && <>
          <div className="stat-row"><Stat label="Privacidad" value={PRIV[data.privacy] ?? data.privacy} /><Stat label="Gasto del mes" value={`${data.month_cost_usd} $`} />
            <Stat label="Límite mensual" value={nd(data.monthly_limit_usd, " $")} /><Stat label="Proveedores listos" value={String(data.providers.filter((p: Row) => p.configured).length)} /></div>
          <div className="idea-grid">{data.providers.map((p: Row) => (
            <article key={p.id} className={`dpanel prov ${p.configured ? "ok" : ""}`}><header className="dpanel-head"><span>{p.label.toUpperCase()}</span>
              <span className={`lab-tag t-${p.configured ? "commercial" : "speculative"}`}>{p.configured ? "operativo" : "no configurado"}</span></header>
              {p.id === "ollama" ? (p.models?.length ? <ul className="life-list compact">{p.models.map((m: Row) => <li key={m.name}><div className="life-item"><b>{m.name}</b>
                <small> {m.params ?? ""} · {m.size_gb} GB · {m.capabilities.join(", ")}</small></div></li>)}</ul> : <p className="small">{p.note ?? "Sin modelos instalados"}</p>)
                : <p className="small">{p.model ? `Modelo: ${p.model}` : ""}{p.base_url ? ` · ${p.base_url}` : ""}{p.note ? ` ${p.note}` : ""}</p>}
            </article>))}</div>
          <section className="dpanel"><header className="dpanel-head"><span>CADENAS DE SELECCIÓN (CON FALLBACK)</span></header>
            <div className="table-scroll"><table className="dtable compact"><thead><tr><th>Tarea</th><th>Orden de modelos</th></tr></thead><tbody>
              {Object.entries(data.chains as Record<string, Row[]>).map(([t, c]) => <tr key={t}><td>{t}</td><td className="small">{c.length ? c.map((x) => `${x.id} (${x.why})`).join(" → ") : "ninguno accesible"}</td></tr>)}
              <tr><td>datos personales</td><td className="small">{data.chains_local.map((x: Row) => x.id).join(" → ") || "ninguno accesible"}</td></tr></tbody></table></div></section>
          <section className="dpanel"><header className="dpanel-head"><span>RENDIMIENTO MEDIDO (30 DÍAS)</span></header>
            {!data.stats.length ? <p className="desk-empty">Aún no hay llamadas registradas.</p> : (
              <div className="table-scroll"><table className="dtable compact"><thead><tr><th>Modelo</th><th>Llamadas</th><th>Errores</th><th>p50</th><th>p95</th><th>Tokens salida</th><th>Coste</th><th>Último error</th></tr></thead>
                <tbody>{data.stats.map((s: Row) => <tr key={s.id}><td>{s.id}</td><td className="mono">{s.calls}</td><td className="mono">{s.error_rate} %</td><td className="mono">{nd(s.p50_ms, " ms")}</td>
                  <td className="mono">{nd(s.p95_ms, " ms")}</td><td className="mono">{nd(s.tokens_out)}</td><td className="mono">{nd(s.cost_usd, " $")}</td><td className="small">{s.last_error ?? ""}</td></tr>)}</tbody></table></div>)}
            <p className="mini-note">{data.note} Para comparar modelos con las mismas pruebas, usa el Benchmark Center.</p></section>
          <section className="dpanel"><header className="dpanel-head"><span>PROVEEDOR COMPATIBLE CON OPENAI (OPCIONAL)</span></header>
            <p className="small">Groq, Mistral, OpenRouter, Together, LM Studio… Cualquier API compatible con <code>/chat/completions</code>. La clave se guarda en el Llavero.</p>
            <SchemaForm fields={[{ k: "base_url", label: "URL base", required: true, placeholder: "https://api.groq.com/openai/v1" }, { k: "model", label: "Modelo", required: true },
              { k: "label", label: "Nombre" }, { k: "api_key", label: "API key (no se muestra después)" }]} submitLabel="Guardar"
              onSubmit={(v) => meta.put("/router/compat", v).then(() => { setMsg("Proveedor guardado"); reload(); })} />
            <div className="row-btns">
              <button type="button" className="btn ghost" onClick={() => meta.post("/router/compat/test").then(setTest).catch((e: Error) => setMsg(e.message))}>Probar conexión</button>
              <button type="button" className="btn ghost" onClick={() => meta.del("/router/compat").then(() => { setMsg("Proveedor eliminado"); reload(); })}>Eliminar</button></div>
            {test && <p className="small">{test.ok ? `OK en ${test.ms} ms: «${test.reply}»` : `Falla: ${test.error}`}</p>}
            {msg && <p className="small">{msg}</p>}</section>
        </>}
      </State>
    </div>
  );
}

/* ───────── Multi-agent system ───────── */
export function AgentsView() {
  const { data, error, loading, reload } = useLoad<Row>("/agents", [], meta);
  const set = (id: string, k: string, v: boolean) => meta.put(`/agents/${id}/perms`, { [k]: v }).then(reload);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Advanced Multi-Agent System</h2><p className="muted small">Cada agente tiene responsabilidades, herramientas con nivel de permiso y límites. Aquí decides si está activo,
        si puede leer tu memoria y si sus datos pueden ir a modelos en la nube. Los agentes de datos sensibles no salen a la nube por defecto. Toda operación queda en la traza y en la auditoría.</p></div>
      <State loading={loading && !data} error={error}>
        {data && <>
          <section className="dpanel"><header className="dpanel-head"><span>AGENTES DEL META-BRAIN</span></header>
            <div className="idea-grid">{data.internal.map((a: Row) => <div key={a.id} className="sc-card"><b>{a.name}</b><p className="small">{a.role}</p><small>{a.permissions}</small></div>)}</div></section>
          <section className="dpanel"><header className="dpanel-head"><span>AGENTES ESPECIALIZADOS ({data.agents.length})</span></header>
            <div className="table-scroll"><table className="dtable compact"><thead><tr><th>Agente</th><th>Herramientas (nivel)</th><th>Colabora con</th><th>Activo</th><th>Memoria</th><th>Nube</th></tr></thead>
              <tbody>{data.agents.map((a: Row) => <tr key={a.id}><td><b>{a.name}</b><br /><small>{a.role}</small></td>
                <td className="small">{a.tools.map((t: Row) => `${t.name} (${t.level})`).join(", ")}</td><td className="small">{a.helpers.join(", ") || "—"}</td>
                {(["enabled", "memory", "cloud"] as const).map((k) => <td key={k}><input type="checkbox" checked={!!a.perms[k]} aria-label={`${a.name}: ${k}`} onChange={(e) => void set(a.id, k, e.target.checked)} /></td>)}
              </tr>)}</tbody></table></div></section>
        </>}
      </State>
    </div>
  );
}

/* ───────── Security & Governance ───────── */
export function Governance() {
  const gov = useLoad<Row>("/governance", [], meta);
  const audit = useLoad<Row>("/governance/audit", [], meta);
  const [msg, setMsg] = useState<string | null>(null);
  const m = gov.data?.meta;
  const toggle = (k: string, v: boolean) => meta.put("/governance", { [k]: v }).then(gov.reload);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Security & Governance</h2><p className="muted small">Kill switch, límites de recursos, privacidad, permisos y auditoría. Las claves están en el Llavero del sistema.
        Copias de seguridad y política de autorizaciones (escritura/ejecución) en <Link to="/security">Seguridad</Link>.</p></div>
      <State loading={gov.loading && !gov.data} error={gov.error}>
        {m && <>
          <section className={`dpanel kill ${m.kill ? "on" : ""}`}><header className="dpanel-head"><span>KILL SWITCH</span><span>{m.kill ? "ACTIVADO" : "desactivado"}</span></header>
            <p className="small">Detiene al momento el META-BRAIN, las automatizaciones, el Arena, las investigaciones y el sandbox. El chat normal sigue funcionando.</p>
            <button type="button" className={`btn ${m.kill ? "" : "danger"}`} onClick={() => { if (m.kill || window.confirm("¿Activar el kill switch y detener todos los procesos autónomos?"))
              void meta.post("/governance/kill", { on: !m.kill }).then((r) => { setMsg(r.kill ? `Detenidos: ${r.stopped.meta} ejecuciones, ${r.stopped.workflows} automatizaciones, ${r.stopped.arena} pruebas` : "Reanudado"); gov.reload(); audit.reload(); }); }}>
              {m.kill ? "Desactivar kill switch" : "Activar kill switch"}</button>{msg && <p className="small">{msg}</p>}</section>
          <div className="mod-cols">
            <section className="dpanel"><header className="dpanel-head"><span>LÍMITES POR EJECUCIÓN</span></header>
              <SchemaForm key={JSON.stringify(m.limits)} fields={[{ k: "max_calls", label: "Llamadas a modelos (máx.)", type: "number" }, { k: "max_seconds", label: "Tiempo (s)", type: "number" },
                { k: "max_cost_usd", label: "Coste (US$, vacío = sin límite)", type: "number" }]} initial={m.limits} submitLabel="Guardar límites"
                onSubmit={(v) => meta.put("/governance", { limits: v, clear_cost_limit: v.max_cost_usd == null }).then(gov.reload)} /></section>
            <section className="dpanel"><header className="dpanel-head"><span>CONSEJO Y PRIVACIDAD</span></header>
              <label className="check"><span>Especialistas máximos</span><select value={m.council_size} onChange={(e) => void meta.put("/governance", { council_size: Number(e.target.value) }).then(gov.reload)} aria-label="Especialistas máximos">
                {[2, 3, 4].map((n) => <option key={n}>{n}</option>)}</select></label>
              {[["diverse_models", "Repartir especialistas entre proveedores distintos (si hay varios)"], ["auto_research", "El crítico puede pedir una investigación nueva"],
                ["allow_cloud_personal", "Permitir datos personales en modelos en la nube"]].map(([k, l]) => (
                <label key={k} className="check"><input type="checkbox" checked={!!m[k]} onChange={(e) => void toggle(k, e.target.checked)} /> {l}</label>))}
            </section>
          </div>
        </>}
      </State>
      <section className="dpanel"><header className="dpanel-head"><span>AUDITORÍA</span><button type="button" className="link-btn" onClick={audit.reload}>actualizar</button></header>
        {audit.data && <>
          {!!audit.data.pending_approvals.length && <p className="warn-line l-warn">{audit.data.pending_approvals.length} acción(es) esperan tu autorización · <Link to="/agents?tab=approvals">revisar</Link></p>}
          {!!audit.data.injections.length && <p className="small">Contenido externo con posibles instrucciones maliciosas neutralizado en {audit.data.injections.length} ejecución(es): {audit.data.injections.map((i: Row) => `#${i.run_id}`).join(", ")}</p>}
          <ul className="life-list compact audit">{audit.data.log.map((a: Row, i: number) => <li key={i}><div className="life-item"><small>{fmtDate(a.at)} {a.at.slice(11, 16)} · {a.module}/{a.action}</small> {a.summary}</div></li>)}</ul>
        </>}</section>
    </div>
  );
}

/* ───────── Memory Intelligence ───────── */
export function MemoryIntel() {
  const { data, error, loading, reload } = useLoad<Row>("/memory", [], meta);
  const [check, setCheck] = useState<Record<string, Row>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const act = (p: Promise<unknown>, ok: string) => p.then(() => { setMsg(ok); reload(); }).catch((e: Error) => setMsg(e.message));
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Memory Intelligence</h2><p className="muted small">Sobre la memoria de VISTAN: tipos, duplicados, contradicciones e historial. Nada se guarda solo a partir de
        las conversaciones. Consulta, corrige o elimina recuerdos y cambia su nivel de acceso en <Link to="/memory">Memoria</Link>.</p></div>
      <State loading={loading && !data} error={error}>
        {data && <>
          <div className="stat-row">{Object.entries(data.types as Record<string, string>).map(([k, l]) => <Stat key={k} label={l.split(":")[0]} value={String(data.counts[k] ?? 0)} hint={l} />)}
            <Stat label="Conversaciones" value={String(data.counts.episodic_conversations)} /><Stat label="Documentos" value={String(data.documents)} />
            <Stat label="Grafo" value={`${data.graph.entities} nodos · ${data.graph.relations} rel.`} /></div>
          <p className="small">Acceso: {data.access.all} para cualquier modelo · {data.access.local} solo locales · {data.access.private} privados (nunca entran en el contexto de la IA) · {data.superseded} históricos (reemplazados) · {data.revisions} cambios registrados</p>
          {msg && <p className="small">{msg}</p>}
          <section className="dpanel"><header className="dpanel-head"><span>POSIBLES CONTRADICCIONES ({data.contradictions.length})</span></header>
            {!data.contradictions.length ? <p className="desk-empty">No se detectan contradicciones.</p> : <ul className="disc-list">{data.contradictions.map((c: Row) => { const key = `${c.newer}-${c.older}`; return (
              <li key={key}><small>{c.reason}</small><p className="small"><b>Más reciente:</b> {c.newer_text}</p><p className="small"><b>Anterior:</b> {c.older_text}</p>
                <div className="row-actions wrap">
                  <button type="button" className="mini-btn" onClick={() => act(meta.post("/memory/resolve", { keep_id: c.newer, other_id: c.older }), "El anterior queda como histórico")}>Vale el reciente</button>
                  <button type="button" className="mini-btn ghost" onClick={() => act(meta.post("/memory/resolve", { keep_id: c.older, other_id: c.newer }), "El reciente queda como histórico")}>Vale el anterior</button>
                  <button type="button" className="mini-btn ghost" onClick={() => meta.post("/memory/check", { keep_id: c.newer, other_id: c.older }).then((r) => setCheck({ ...check, [key]: r })).catch((e: Error) => setMsg(e.message))}>Comprobar con IA local</button>
                </div>{check[key] && <p className="mini-note">{check[key].contradiccion ? "Sí se contradicen" : "No se contradicen"}: {check[key].explicacion} ({check[key].model})</p>}</li>); })}</ul>}
            <p className="mini-note">{data.note}</p></section>
          <section className="dpanel"><header className="dpanel-head"><span>POSIBLES DUPLICADOS ({data.duplicates.length})</span></header>
            {!data.duplicates.length ? <p className="desk-empty">Sin duplicados.</p> : <ul className="disc-list">{data.duplicates.map((d: Row) => <li key={`${d.a}-${d.b}`}>
              <p className="small">{d.a_text}</p><p className="small">{d.b_text}</p><small>similitud {Math.round(d.similarity * 100)} %</small>
              <button type="button" className="mini-btn ghost" onClick={() => act(meta.post("/memory/merge", { keep_id: d.a, other_id: d.b }), "Fusionados")}>Fusionar</button></li>)}</ul>}</section>
        </>}
      </State>
    </div>
  );
}
