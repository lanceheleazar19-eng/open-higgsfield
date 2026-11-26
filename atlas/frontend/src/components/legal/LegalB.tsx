import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { legal, makeClient, type Row } from "../../api/life";

const core = makeClient("/api");
import { fmtDate, SchemaForm, State, useLoad } from "../life/kit";
import { CasePick, type LMeta, Lvl, STATE_L } from "./LegalA";

/* ───────── Legal Document Studio ───────── */
export function Studio({ meta }: { meta: LMeta }) {
  const list = useLoad<Row[]>("/drafts", [], legal);
  const [sel, setSel] = useState<number | null>(null);
  const [gen, setGen] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Legal Document Studio</h2><p className="muted small">Borradores con IA local que <b>no inventan</b> nombres, DNI, direcciones, fechas ni importes:
        lo que no aportas queda como <code>[[PENDIENTE: …]]</code>. Todo documento es un BORRADOR sujeto a revisión profesional.</p></div>
      <div className="row-btns"><button type="button" className="btn" onClick={() => setGen(!gen)}>{gen ? "Cerrar" : "+ Nuevo borrador"}</button>
        <button type="button" className="btn ghost" onClick={() => legal.post("/drafts", { title: "Documento en blanco", content: "" }).then((d) => { setSel(d.id); list.reload(); })}>Documento en blanco</button></div>
      {gen && <Generate meta={meta} onDone={(id, m) => { setGen(false); setSel(id); setMsg(m); list.reload(); }} />}
      {msg && <p className="small">{msg}</p>}
      <div className="mod-cols">
        <section className="dpanel meta-runs"><header className="dpanel-head"><span>BORRADORES</span></header>
          <State loading={list.loading && !list.data} error={list.error} empty={list.data && !list.data.length ? "Aún no hay borradores." : false}>
            <ul className="exp-list">{list.data?.map((d) => <li key={d.id}><button type="button" className={sel === d.id ? "on" : ""} onClick={() => setSel(d.id)}>
              <span className="exp-state">{meta.templates[d.doc_type]?.label ?? d.doc_type}</span><b>{d.title}</b>
              <small>{d.pending.length} pendientes · {fmtDate(d.updated_at)}{d.tags?.length ? ` · #${d.tags.join(" #")}` : ""}</small></button></li>)}</ul>
          </State></section>
        {sel ? <Editor key={sel} id={sel} onChange={list.reload} onDeleted={() => { setSel(null); list.reload(); }} onDuplicate={(id) => { setSel(id); list.reload(); }} />
          : <section className="dpanel grow"><p className="desk-empty">Elige o crea un borrador.</p></section>}
      </div>
    </div>
  );
}

function Generate({ meta, onDone }: { meta: LMeta; onDone: (id: number, msg: string) => void }) {
  const [type, setType] = useState("nda");
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [caseId, setCaseId] = useState<number | null>(null);
  const [rid, setRid] = useState("");
  const research = useLoad<Row[]>("/research", [], legal);
  const t = meta.templates[type];
  return (
    <section className="dpanel"><form className="life-form" onSubmit={(e) => { e.preventDefault(); setBusy(true); setErr(null);
      const fd = new FormData(e.currentTarget);
      legal.post("/drafts/generate", { doc_type: type, jurisdiction: fd.get("jur"), request: fd.get("req"), inputs, case_id: caseId, research_id: rid ? Number(rid) : null })
        .then((d) => onDone(d.id, `Borrador generado. Faltan: ${d.missing_inputs.join(", ") || "ningún dato obligatorio"}.${d.scrubbed.length ? ` Se retiraron ${d.scrubbed.length} dato(s) no aportados.` : ""}`))
        .catch((x: Error) => setErr(x.message)).finally(() => setBusy(false)); }}>
      <label><span>Tipo de documento</span><select value={type} onChange={(e) => { setType(e.target.value); setInputs({}); }} aria-label="Tipo de documento">
        {Object.entries(meta.templates).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
      <label><span>Jurisdicción</span><select name="jur" defaultValue="es" aria-label="Jurisdicción del borrador"><option value="es">España</option><option value="es-ct">Cataluña</option><option value="eu">UE</option></select></label>
      <label><span>Expediente</span><CasePick value={caseId} onChange={setCaseId} /></label>
      <label><span>Normativa verificada (investigación)</span><select value={rid} onChange={(e) => setRid(e.target.value)} aria-label="Investigación de apoyo"><option value="">Ninguna</option>
        {research.data?.filter((r) => r.status === "done").map((r) => <option key={r.id} value={r.id}>{r.question.slice(0, 60)}</option>)}</select></label>
      <label className="wide"><span>Qué necesitas *</span><textarea name="req" rows={2} required minLength={4} aria-label="Qué necesitas" placeholder="Describe el documento y su finalidad" /></label>
      {t.fields.map((f) => <label key={f}><span>{f.replace(/_/g, " ")}</span><input value={inputs[f] ?? ""} onChange={(e) => setInputs({ ...inputs, [f]: e.target.value })} aria-label={f.replace(/_/g, " ")} placeholder="vacío = quedará PENDIENTE" /></label>)}
      <div className="wide row-btns"><button type="submit" className="btn" disabled={busy}>{busy ? "Redactando con IA local…" : "Generar borrador"}</button></div>
      {err && <p className="error-line wide" role="alert">{err}</p>}
    </form></section>
  );
}

function Editor({ id, onChange, onDeleted, onDuplicate }: { id: number; onChange: () => void; onDeleted: () => void; onDuplicate: (id: number) => void }) {
  const { data: d, reload } = useLoad<Row>(`/drafts/${id}`, [id], legal);
  const [text, setText] = useState<string | null>(null);
  const [saved, setSaved] = useState<string>("");
  const [cmp, setCmp] = useState<Row | null>(null);
  const [comment, setComment] = useState("");
  const timer = useRef<number | null>(null);
  useEffect(() => { if (d && text === null) setText(d.content); }, [d]); // eslint-disable-line react-hooks/exhaustive-deps
  const edit = (v: string) => {
    setText(v); setSaved("sin guardar…");
    if (timer.current) clearTimeout(timer.current);
    timer.current = window.setTimeout(() => legal.patch(`/drafts/${id}`, { content: v }).then(() => { setSaved(`guardado ${new Date().toLocaleTimeString("es-ES")}`); onChange(); }), 1200);
  };
  if (!d || text === null) return <section className="dpanel grow"><State loading error={null} /></section>;
  const pend = [...new Set([...text.matchAll(/\[\[PENDIENTE:\s*([^\]]+)\]\]/g)].map((m) => m[1].trim()))];
  return (
    <section className="dpanel grow lg-editor" data-testid="draft-editor">
      <header className="dpanel-head"><input className="title-in" defaultValue={d.title} aria-label="Título" onBlur={(e) => e.target.value !== d.title && void legal.patch(`/drafts/${id}`, { title: e.target.value }).then(onChange)} />
        <span className="row-actions">
          <button type="button" className="mini-btn" onClick={() => legal.post(`/drafts/${id}/versions`, { note: window.prompt("Nota de la versión") || undefined }).then(reload)}>Guardar versión</button>
          <a className="mini-btn ghost" href={`/api/legal/drafts/${id}/export?fmt=docx`}>DOCX</a><a className="mini-btn ghost" href={`/api/legal/drafts/${id}/export?fmt=pdf`}>PDF</a>
          <button type="button" className="mini-btn ghost" onClick={() => legal.post(`/drafts/${id}/duplicate`).then((x) => onDuplicate(x.id))}>Duplicar</button>
          <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar el borrador y sus versiones?")) void legal.del(`/drafts/${id}`).then(onDeleted); }}>✕</button>
        </span></header>
      <p className="mini-note">{saved || "Guardado automático activado"} · {pend.length ? `Pendiente de completar: ${pend.join(", ")}` : "Sin campos pendientes"}</p>
      <textarea className="code doc" rows={22} value={text} onChange={(e) => edit(e.target.value)} aria-label="Contenido del documento" spellCheck />
      {!!d.review?.length && <div className="sc-block pred"><h4>Cláusulas a revisar</h4><ul>{d.review.map((r: Row, i: number) => <li key={i}><b>{r.clausula}</b>: {r.motivo}</li>)}</ul></div>}
      <label className="check"><span>Etiquetas</span><input defaultValue={(d.tags ?? []).join(", ")} aria-label="Etiquetas" onBlur={(e) => void legal.patch(`/drafts/${id}`, { tags: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) }).then(onChange)} /></label>
      <details className="meta-sec"><summary>Versiones ({d.versions.length})</summary><ul className="life-list compact">{d.versions.map((v: Row) => <li key={v.id}><div className="life-item">{fmtDate(v.created_at)} {v.created_at.slice(11, 16)} · {v.note}</div>
        <button type="button" className="mini-btn ghost" onClick={() => legal.get(`/drafts/${id}/versions/${v.id}`).then((x) => setCmp(x.compare))}>Comparar</button>
        <button type="button" className="mini-btn ghost" onClick={() => legal.post(`/drafts/${id}/restore/${v.id}`).then((x) => { setText(x.content); reload(); })}>Restaurar</button></li>)}</ul>
        {cmp && <div className="small">{cmp.changes.length ? cmp.changes.map((ch: Row, i: number) => <div key={i} className={`diff-card k-${ch.kind}`}><b>{ch.kind}: {ch.clause}</b>
          <p className="diff">{ch.kind === "modificada" ? ch.diff.map((o: Row, j: number) => o.op === "equal" ? <span key={j}>{o.a} </span> : <span key={j}>{o.a && <del>{o.a}</del>} {o.b && <ins>{o.b}</ins>} </span>) : ch.kind === "añadida" ? <ins>{ch.after}</ins> : <del>{ch.before}</del>}</p></div>)
          : "Sin diferencias con la versión actual."}</div>}</details>
      <details className="meta-sec"><summary>Comentarios ({d.comments.length})</summary>
        <form className="filters" onSubmit={(e) => { e.preventDefault(); void legal.post(`/comments?target=draft&target_id=${id}`, { text: comment }).then(() => { setComment(""); reload(); }); }}>
          <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Añadir comentario" aria-label="Comentario" /><button type="submit" className="btn ghost" disabled={!comment.trim()}>Comentar</button></form>
        <ul className="life-list compact">{d.comments.map((c: Row) => <li key={c.id}><div className="life-item"><small>{fmtDate(c.created_at)}</small> {c.text}</div></li>)}</ul></details>
    </section>
  );
}

/* ───────── Gestión de expedientes ───────── */
export function Cases({ meta, initial }: { meta: LMeta; initial: number | null }) {
  const [q, setQ] = useState("");
  const [st, setSt] = useState("");
  const list = useLoad<Row[]>(`/cases?${new URLSearchParams(Object.entries({ q, status: st }).filter(([, v]) => v) as [string, string][])}`, [q, st], legal);
  const [sel, setSel] = useState<number | null>(initial);
  const [neu, setNeu] = useState(false);
  const fields = [{ k: "name", label: "Nombre", required: true }, { k: "category", label: "Categoría jurídica", type: "select" as const, options: Object.entries(meta.branches) },
    { k: "jurisdiction", label: "Jurisdicción", type: "select" as const, options: Object.entries(meta.jurisdictions) },
    { k: "priority", label: "Prioridad", type: "select" as const, options: ["baja", "media", "alta", "urgente"].map((x) => [x, x] as [string, string]) },
    { k: "opened_on", label: "Fecha de apertura", type: "date" as const }, { k: "description", label: "Descripción", type: "textarea" as const }];
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Legal Case Management</h2><p className="muted small">Cada expediente tiene su propia documentación, investigaciones, plazos y cronología, y no se mezclan entre sí.
        Se puede vincular a un proyecto de VISTAN o a una empresa/oportunidad de LIFE OS.</p></div>
      <div className="filters"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar expediente" aria-label="Buscar expediente" />
        <select value={st} onChange={(e) => setSt(e.target.value)} aria-label="Estado"><option value="">Todos los estados</option>{meta.states.map((s) => <option key={s} value={s}>{STATE_L[s]}</option>)}</select>
        <button type="button" className="btn" onClick={() => setNeu(!neu)}>{neu ? "Cerrar" : "+ Expediente"}</button></div>
      {neu && <section className="dpanel"><SchemaForm fields={fields} initial={{ jurisdiction: "es", priority: "media" }} submitLabel="Abrir expediente"
        onSubmit={(v) => legal.post("/cases", v).then((c) => { setNeu(false); setSel(c.id); list.reload(); })} /></section>}
      <div className="mod-cols">
        <section className="dpanel meta-runs"><State loading={list.loading && !list.data} error={list.error} empty={list.data && !list.data.length ? "Sin expedientes." : false}>
          <ul className="exp-list">{list.data?.map((c) => <li key={c.id}><button type="button" className={sel === c.id ? "on" : ""} onClick={() => setSel(c.id)}>
            <span className={`exp-state s-${c.status === "resuelto" ? "COMPLETED" : c.status === "archivado" ? "ARCHIVED" : "RUNNING"}`}>{STATE_L[c.status]}</span><b>{c.ref} · {c.name}</b>
            <small>{meta.branches[c.category] ?? "—"} · {c.documents} docs · {c.open_alerts} alertas · {c.priority}</small></button></li>)}</ul></State></section>
        {sel ? <CaseDetail key={sel} id={sel} meta={meta} onChange={list.reload} onDeleted={() => { setSel(null); list.reload(); }} /> : <section className="dpanel grow"><p className="desk-empty">Elige un expediente.</p></section>}
      </div>
    </div>
  );
}

function CaseDetail({ id, meta, onChange, onDeleted }: { id: number; meta: LMeta; onChange: () => void; onDeleted: () => void }) {
  const { data: c, reload } = useLoad<Row>(`/cases/${id}`, [id], legal);
  const projects = useLoad<Row[]>("/projects", [], core);
  const [note, setNote] = useState("");
  const [task, setTask] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  if (!c) return <section className="dpanel grow"><State loading error={null} /></section>;
  const patch = (v: Row) => legal.patch(`/cases/${id}`, v).then(() => { reload(); onChange(); }).catch((e: Error) => setMsg(e.message));
  return (
    <section className="dpanel grow" data-testid="case-detail">
      <header className="dpanel-head"><span>{c.ref} · {c.name.toUpperCase()}</span><span className="row-actions">
        <a className="mini-btn ghost" href={`/api/legal/reports/case/${id}?fmt=pdf`}>Exportar PDF</a><a className="mini-btn ghost" href={`/api/legal/reports/case/${id}?fmt=docx`}>DOCX</a>
        <button type="button" className="mini-btn ghost" onClick={() => { const r = window.prompt(`Para eliminar escribe ${c.ref} (o cancela y archívalo)`); if (r) void legal.del(`/cases/${id}?confirm=${encodeURIComponent(r)}`).then(onDeleted).catch((e: Error) => setMsg(e.message)); }}>Eliminar</button>
      </span></header>
      <div className="filters">
        <select value={c.status} onChange={(e) => void patch({ status: e.target.value })} aria-label="Estado del expediente">{meta.states.map((s) => <option key={s} value={s}>{STATE_L[s]}</option>)}</select>
        <select value={c.priority} onChange={(e) => void patch({ priority: e.target.value })} aria-label="Prioridad">{["baja", "media", "alta", "urgente"].map((x) => <option key={x}>{x}</option>)}</select>
        <select value={c.project_id ?? ""} onChange={(e) => void patch({ project_id: e.target.value ? Number(e.target.value) : null })} aria-label="Proyecto vinculado">
          <option value="">Sin proyecto</option>{projects.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
      </div>
      {msg && <p className="error-line">{msg}</p>}
      <p className="small">{meta.branches[c.category] ?? "Sin categoría"} · {meta.jurisdictions[c.jurisdiction] ?? c.jurisdiction} · abierto {fmtDate(c.opened_on)}
        {c.opportunity ? <> · empresa LIFE OS: <Link to="/life?s=entrepreneur">{c.opportunity.name}</Link></> : null}</p>
      {c.description && <p className="small">{c.description}</p>}
      <details className="meta-sec"><summary>Partes ({c.parties.length})</summary>
        <ul className="small">{c.parties.map((p: Row, i: number) => <li key={i}>{p.name} — {p.role}</li>)}</ul>
        <form className="filters" onSubmit={(e) => { e.preventDefault(); const f = new FormData(e.currentTarget); void patch({ parties: [...c.parties, { name: f.get("pn"), role: f.get("pr") }] }); e.currentTarget.reset(); }}>
          <input name="pn" placeholder="Nombre de la parte" aria-label="Nombre de la parte" required /><input name="pr" placeholder="Rol" aria-label="Rol de la parte" /><button type="submit" className="btn ghost">Añadir</button></form></details>
      <div className="mod-cols">
        <div className="grow">
          <h4>Documentos ({c.documents.length})</h4><ul className="life-list compact">{c.documents.map((d: Row) => <li key={d.id}><div className="life-item">{d.title} <small>{d.origin === "ia" ? "conclusión IA" : d.origin} · {d.kind} · v{d.version}</small></div></li>)}</ul>
          <h4>Investigaciones ({c.research.length})</h4><ul className="life-list compact">{c.research.map((r: Row) => <li key={r.id}><div className="life-item">{r.question.slice(0, 90)} <small>{r.status}</small></div></li>)}</ul>
          <h4>Plazos</h4><ul className="life-list compact">{c.deadlines.map((d: Row) => <li key={d.id}><div className="life-item">{fmtDate(d.due_on)} · {d.title} <small>{d.verified ? "verificado" : "SIN VERIFICAR"}</small></div></li>)}</ul>
          <h4>Alertas</h4><ul className="life-list compact">{c.alerts.map((a: Row) => <li key={a.id}><div className="life-item"><Lvl l={a.level} /> {a.title}</div></li>)}</ul>
        </div>
        <div className="grow">
          <form className="filters" onSubmit={(e) => { e.preventDefault(); void legal.post(`/comments?target=case&target_id=${id}`, { text: note }).then(() => { setNote(""); reload(); }); }}>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Nota o comentario" aria-label="Nota del expediente" /><button type="submit" className="btn ghost" disabled={!note.trim()}>Añadir nota</button></form>
          <form className="filters" onSubmit={(e) => { e.preventDefault(); void legal.post(`/cases/${id}/tasks`, { title: task }).then(() => { setTask(""); setMsg("Tarea creada en Tareas"); reload(); }); }}>
            <input value={task} onChange={(e) => setTask(e.target.value)} placeholder="Nueva tarea del expediente" aria-label="Tarea del expediente" /><button type="submit" className="btn ghost" disabled={task.trim().length < 2}>Crear tarea</button></form>
          <h4>Cronología</h4><ol className="trace">{c.timeline.map((e: Row) => <li key={e.id}><time>{e.created_at.slice(0, 16).replace("T", " ")}</time><b>{e.kind}</b><span /><p>{e.summary}</p></li>)}</ol>
        </div>
      </div>
    </section>
  );
}

/* ───────── Riesgos y plazos ───────── */
export function Risks() {
  const [st, setSt] = useState("abierta");
  const alerts = useLoad<Row[]>(`/alerts?status=${st}`, [st], legal);
  const dls = useLoad<Row[]>("/deadlines", [], legal);
  const [msg, setMsg] = useState<string | null>(null);
  const [caseId, setCaseId] = useState<number | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Legal Risk Detection</h2><p className="muted small">Alertas generadas a partir de contratos analizados, plazos y cumplimiento. Siempre «posible riesgo», nunca «infracción».
        VISTAN <b>no calcula plazos</b>: tú los registras con su regla y los marcas como verificados.</p></div>
      <div className="filters"><select value={st} onChange={(e) => setSt(e.target.value)} aria-label="Estado de alertas"><option value="abierta">Abiertas</option><option value="resuelta">Resueltas</option><option value="descartada">Descartadas</option></select>
        <button type="button" className="btn ghost" onClick={() => legal.post("/alerts/scan").then((r) => { setMsg(`${r.new} alerta(s) nueva(s)`); alerts.reload(); })}>Escanear ahora</button>
        <a className="btn ghost" href="/api/legal/reports/risks/0?fmt=pdf">Informe de riesgos PDF</a></div>
      {msg && <p className="small">{msg}</p>}
      <State loading={alerts.loading && !alerts.data} error={alerts.error} empty={alerts.data && !alerts.data.length ? "Sin alertas." : false}>
        <ul className="disc-list">{alerts.data?.map((a) => <li key={a.id} className={`risk l-${a.level}`}><div className="d-tags"><Lvl l={a.level} /><b>{a.title}</b><small>{fmtDate(a.detected_at)} · {a.source}</small></div>
          <p className="small">{a.description}</p>{a.evidence && <blockquote>«{a.evidence.slice(0, 400)}»</blockquote>}
          {a.consequence && <p className="small">Consecuencia posible: {a.consequence}</p>}{a.action && <p className="small">→ {a.action}</p>}
          {a.status === "abierta" && <div className="row-actions"><button type="button" className="mini-btn" onClick={() => legal.patch(`/alerts/${a.id}`, { status: "resuelta" }).then(alerts.reload)}>Resuelta</button>
            <button type="button" className="mini-btn ghost" onClick={() => legal.patch(`/alerts/${a.id}`, { status: "descartada" }).then(alerts.reload)}>Descartar</button></div>}</li>)}</ul>
      </State>
      <section className="dpanel"><header className="dpanel-head"><span>PLAZOS Y VENCIMIENTOS</span></header>
        <SchemaForm fields={[{ k: "title", label: "Plazo", required: true }, { k: "due_on", label: "Fecha límite", type: "date", required: true },
          { k: "kind", label: "Tipo", type: "select", options: [["contractual", "Contractual"], ["procesal", "Procesal"], ["administrativo", "Administrativo"], ["fiscal", "Fiscal"], ["otro", "Otro"]], required: true },
          { k: "basis", label: "Regla / fuente aplicada (cómputo, días hábiles, suspensiones)", type: "textarea" }, { k: "verified", label: "Verificado (lo he comprobado con su regla)", type: "checkbox" }]}
          initial={{ kind: "contractual" }} submitLabel="Registrar plazo (y crear recordatorio en Tareas)"
          extra={<label><span>Expediente</span><CasePick value={caseId} onChange={setCaseId} /></label>}
          onSubmit={(v) => legal.post("/deadlines", { ...v, case_id: caseId }).then((r) => { setMsg(r.warning ?? "Plazo registrado"); dls.reload(); alerts.reload(); })} />
        <ul className="life-list compact">{dls.data?.map((d) => <li key={d.id}><div className="life-item"><b className={d.days < 0 ? "neg" : d.days <= 7 ? "warn" : ""}>{d.days} d</b> {d.title}
          <small> {fmtDate(d.due_on)} · {d.kind} · {d.verified ? "verificado" : "SIN VERIFICAR"} · {d.status}</small></div>
          {d.status === "pendiente" && <button type="button" className="mini-btn ghost" onClick={() => legal.patch(`/deadlines/${d.id}`, { status: "cumplido" }).then(dls.reload)}>Cumplido</button>}</li>)}</ul></section>
    </div>
  );
}

/* ───────── Cumplimiento ───────── */
export function Compliance({ meta }: { meta: LMeta }) {
  const [profile, setProfile] = useState("ecommerce");
  const list = useLoad<Row[]>(`/compliance?profile=${profile}`, [profile], legal);
  const [vig, setVig] = useState<Row | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const AP: Record<string, string> = { confirmada: "Obligaciones confirmadas", potencial: "Potencialmente aplicables", asesoramiento: "Requieren asesoramiento profesional" };
  const set = (id: number, v: Row) => legal.patch(`/compliance/${id}`, v).then(list.reload);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Legal Compliance</h2><p className="muted small">Listas de comprobación por tipo de negocio con norma, artículo y fuente oficial.
        Son referencias de partida: comprueba su vigencia (botón) y su aplicación a tu caso.</p></div>
      <div className="filters"><select value={profile} onChange={(e) => setProfile(e.target.value)} aria-label="Tipo de negocio">{Object.entries(meta.profiles).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <button type="button" className="btn" onClick={() => legal.post("/compliance/generate", { profile }).then((r) => { setMsg(`${r.length} obligaciones añadidas`); list.reload(); })}>Generar lista</button>
        <button type="button" className="btn ghost" onClick={() => { setMsg("Consultando BOE y EUR-Lex…"); legal.post("/compliance/vigencia").then((r) => { setVig(r); setMsg(null); }).catch((e: Error) => setMsg(e.message)); }}>Comprobar vigencia</button>
        <a className="btn ghost" href="/api/legal/reports/compliance/0?fmt=pdf">Informe PDF</a></div>
      {msg && <p className="small">{msg}</p>}
      {vig && <p className="small">Vigencia: {Object.values(vig as Record<string, Row>).map((x) => `${x.id}: ${x.status}${x.error ? ` (${x.error})` : ""}`).join(" · ") || "sin normas identificables"}</p>}
      {(["confirmada", "potencial", "asesoramiento"] as const).map((ap) => (
        <section key={ap} className="dpanel"><header className="dpanel-head"><span>{AP[ap].toUpperCase()}</span></header>
          <div className="table-scroll"><table className="dtable compact"><thead><tr><th>Obligación</th><th>Norma</th><th>Estado</th><th>Responsable</th><th>Límite</th><th>Acreditación</th></tr></thead>
            <tbody>{list.data?.filter((x) => x.applicability === ap).map((x) => <tr key={x.id}><td className="small">{x.obligation}</td>
              <td className="small">{x.source_url ? <a href={x.source_url} target="_blank" rel="noreferrer noopener">{x.norm} {x.article}</a> : `${x.norm} ${x.article ?? ""}`}</td>
              <td><select value={x.status} onChange={(e) => void set(x.id, { status: e.target.value })} aria-label="Estado de cumplimiento">{["pendiente", "en_curso", "cumplida", "no_aplica"].map((s) => <option key={s}>{s}</option>)}</select></td>
              <td><input defaultValue={x.owner ?? ""} onBlur={(e) => e.target.value !== (x.owner ?? "") && void set(x.id, { owner: e.target.value })} aria-label="Responsable" /></td>
              <td><input type="date" defaultValue={x.due_on ?? ""} onBlur={(e) => void set(x.id, { due_on: e.target.value || null })} aria-label="Fecha límite" /></td>
              <td><input defaultValue={x.evidence ?? ""} onBlur={(e) => e.target.value !== (x.evidence ?? "") && void set(x.id, { evidence: e.target.value })} aria-label="Documentación acreditativa" /></td></tr>)}</tbody></table></div>
        </section>))}
    </div>
  );
}

/* ───────── Base de conocimiento ───────── */
export function Knowledge() {
  const [q, setQ] = useState("");
  const [caseId, setCaseId] = useState<number | null>(null);
  const [all, setAll] = useState(false);
  const [hits, setHits] = useState<Row[] | null>(null);
  const docs = useLoad<Row[]>(`/documents${caseId ? `?case_id=${caseId}` : ""}`, [caseId], legal);
  const [txt, setTxt] = useState({ title: "", text: "" });
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Legal Knowledge Base</h2><p className="muted small">Búsqueda semántica y por texto (RAG) en la bóveda jurídica, separada de la base general de VISTAN.
        Distingue <b>documentos originales</b> de <b>conclusiones de IA</b>; por defecto solo busca en el expediente elegido.</p></div>
      <form className="filters" onSubmit={(e) => { e.preventDefault(); legal.get(`/kb/search?q=${encodeURIComponent(q)}${caseId ? `&case_id=${caseId}` : ""}${all ? "&all_cases=true" : ""}`).then((r) => setHits(r as unknown as Row[])); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar en la base jurídica" aria-label="Buscar en la base jurídica" />
        <CasePick value={caseId} onChange={setCaseId} /><label className="check"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> todos los expedientes</label>
        <button type="submit" className="btn" disabled={q.trim().length < 2}>Buscar</button></form>
      {hits && <section className="dpanel">{!hits.length ? <p className="desk-empty">Sin resultados.</p> : <ul className="disc-list">{hits.map((h, i) => <li key={i}>
        <div className="d-tags"><b>{h.title}</b><span className={`lab-tag t-${h.origin === "ia" ? "speculative" : "commercial"}`}>{h.origin === "ia" ? "conclusión IA" : h.origin === "nota" ? "nota" : "original"}</span><small>v{h.version} · {fmtDate(h.created_at)}</small></div>
        <p className="small">{h.text.slice(0, 500)}</p></li>)}</ul>}</section>}
      <section className="dpanel"><header className="dpanel-head"><span>AÑADIR NOTA JURÍDICA O TEXTO</span></header>
        <form className="filters" onSubmit={(e) => { e.preventDefault(); void legal.post("/documents/text", { ...txt, case_id: caseId, kind: "note" }).then(() => { setTxt({ title: "", text: "" }); docs.reload(); }); }}>
          <input value={txt.title} onChange={(e) => setTxt({ ...txt, title: e.target.value })} placeholder="Título" aria-label="Título de la nota" required minLength={2} />
          <textarea value={txt.text} onChange={(e) => setTxt({ ...txt, text: e.target.value })} rows={2} placeholder="Texto (mín. 10 caracteres)" aria-label="Texto de la nota" required minLength={10} />
          <button type="submit" className="btn ghost">Guardar</button></form></section>
      <section className="dpanel"><header className="dpanel-head"><span>DOCUMENTOS ({docs.data?.length ?? 0})</span></header>
        <ul className="life-list compact">{docs.data?.map((d) => <li key={d.id}><div className="life-item">{d.title} <small>{d.origin === "ia" ? "conclusión IA" : d.origin} · {d.kind} · v{d.version} · {d.extraction} · {fmtDate(d.created_at)}</small></div></li>)}</ul></section>
    </div>
  );
}

/* ───────── Legal Agent ───────── */
export function Agent({ initialQ }: { initialQ: string }) {
  const [caseId, setCaseId] = useState<number | null>(null);
  const [q, setQ] = useState(initialQ);
  const [log, setLog] = useState<{ q: string; a: string; meta?: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const ask = () => { if (!q.trim()) return; const qq = q; setBusy(true); setQ("");
    legal.post<{ answer: string; model: string; fragments: Row[] }>("/agent", { question: qq, case_id: caseId })
      .then((r) => setLog((l) => [...l, { q: qq, a: r.answer, meta: `${r.model} · ${r.fragments.map((f) => `${f.id} ${f.title} (${f.origin})`).join(" · ") || "sin fragmentos"}` }]))
      .catch((e: Error) => setLog((l) => [...l, { q: qq, a: `⚠ ${e.message}` }])).finally(() => setBusy(false)); };
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>VISTAN LEGAL AGENT</h2><p className="muted small">Responde con los datos del expediente elegido y su documentación (nunca de otros expedientes), con IA local.
        Colabora con VISTAN CORE: en el chat general interviene cuando hablas de contratos, leyes, plazos o cumplimiento. No ejecuta acciones jurídicas externas.</p></div>
      <div className="filters"><CasePick value={caseId} onChange={setCaseId} /></div>
      <section className="tutor agent-full"><div className="tutor-log">
        {log.map((m, i) => <div key={i}><div className="tmsg user"><div className="tbody"><p>{m.q}</p></div></div>
          <div className="tmsg assistant"><div className="tbody">{m.a.split("\n").map((l, j) => <p key={j}>{l}</p>)}</div>{m.meta && <small>{m.meta}</small>}</div></div>)}
        {busy && <div className="tmsg assistant"><div className="tbody"><p className="muted">Revisando el expediente…</p></div></div>}</div>
        <form className="tutor-in" onSubmit={(e) => { e.preventDefault(); ask(); }}><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Pregunta al Legal Agent…" aria-label="Pregunta al Legal Agent" maxLength={3000} />
          <button type="submit" className="btn" disabled={busy || q.trim().length < 3}>Preguntar</button></form></section>
    </div>
  );
}

/* ───────── Seguridad ───────── */
export function Security({ meta, onChange }: { meta: LMeta; onChange: () => void }) {
  const cloud = meta.settings.allow_cloud;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Seguridad y privacidad</h2></div>
      <section className="dpanel"><ul className="small">
        <li>Acceso protegido con el PIN y la sesión de LIFE OS (configúralo en <Link to="/life?s=security">LIFE OS → Seguridad</Link>).</li>
        <li>Originales cifrados en disco (Fernet/AES); la clave vive en el Llavero del sistema, nunca en el navegador ni en el repositorio.</li>
        <li>Bóveda legal aislada: fuera de la búsqueda general, del grafo y del chat; búsqueda y agente limitados al expediente elegido.</li>
        <li>Contenido de documentos tratado como dato: se neutralizan las instrucciones ocultas (prompt injection).</li>
        <li>Registro de actividad en la auditoría de VISTAN; eliminación controlada (confirmación con el número de expediente); copias de seguridad en <Link to="/security">Seguridad</Link>.</li>
        <li>El Legal Agent no tiene permiso de nube por defecto (META-BRAIN → Multi-Agent System).</li>
      </ul></section>
      <section className={`dpanel kill ${cloud ? "on" : ""}`}><header className="dpanel-head"><span>MODELOS EN LA NUBE PARA ASUNTOS JURÍDICOS</span><span>{cloud ? "AUTORIZADO" : "solo local"}</span></header>
        <p className="small">Por defecto, contratos y documentos solo se procesan con modelos locales (Ollama). Si lo autorizas, el texto podrá enviarse a los proveedores en la nube configurados.</p>
        <button type="button" className={`btn ${cloud ? "" : "danger"}`} onClick={() => { if (cloud || window.confirm("¿Autorizar el envío de documentos jurídicos confidenciales a proveedores de IA en la nube?"))
          void legal.put("/settings", { allow_cloud: !cloud }).then(onChange); }}>{cloud ? "Volver a solo local" : "Autorizar la nube"}</button></section>
      <section className="dpanel"><header className="dpanel-head"><span>FUENTES JURÍDICAS</span></header>
        <div className="table-scroll"><table className="dtable compact"><tbody>{meta.sources.map((s) => <tr key={s.id}><td>{s.name}</td><td className="small">{s.covers}</td><td>{s.needs_key ? "requiere suscripción" : "sin clave"}</td></tr>)}</tbody></table></div></section>
      <p className="mini-note">{meta.disclaimer}</p>
    </div>
  );
}

