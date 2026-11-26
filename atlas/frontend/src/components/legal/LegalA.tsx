import { useEffect, useRef, useState } from "react";
import { legal, type Row } from "../../api/life";
import { Stat } from "../desk/ui";
import { fmtDate, Md, State, useLoad } from "../life/kit";

export type LMeta = { branches: Record<string, string>; jurisdictions: Record<string, string>; states: string[]; levels: string[];
  templates: Record<string, { label: string; fields: string[] }>; profiles: Record<string, string>; contract_types: Record<string, string>;
  sources: Row[]; settings: { allow_cloud: boolean }; disclaimer: string; formats: string[] };
export const LV: Record<string, string> = { critico: "CRÍTICO", alto: "ALTO", medio: "MEDIO", bajo: "BAJO" };
export const STATE_L: Record<string, string> = { nuevo: "Nuevo", investigacion: "En investigación", pendiente_doc: "Pendiente de documentación", revision: "En revisión",
  pendiente_respuesta: "Pendiente de respuesta", resuelto: "Resuelto", archivado: "Archivado" };
export const VIG: Record<string, string> = { vigente: "vigente", derogada: "DEROGADA", no_comprobada: "vigencia no comprobada" };
export const Lvl = ({ l }: { l: string }) => <span className={`lg-level l-${l}`}>{LV[l] ?? l}</span>;
const live = (s: string) => ["queued", "running"].includes(s);

/** Selector de expediente reutilizable (para no mezclar documentos entre expedientes). */
export function CasePick({ value, onChange, label = "Expediente", allowNone = true }: { value: number | null; onChange: (v: number | null) => void; label?: string; allowNone?: boolean }) {
  const cases = useLoad<Row[]>("/cases", [], legal);
  return (
    <select value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)} aria-label={label}>
      {allowNone && <option value="">Sin expediente</option>}
      {cases.data?.map((c) => <option key={c.id} value={c.id}>{c.ref} · {c.name}</option>)}
    </select>
  );
}

/* ───────── Legal Command Center ───────── */
export function Command({ go }: { go: (s: string, extra?: Record<string, string>) => void }) {
  const { data: d, error, loading, reload } = useLoad<Row>("/dashboard", [], legal);
  const [q, setQ] = useState("");
  const [pre, setPre] = useState<Row | null>(null);
  const [facts, setFacts] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="desk-module">
      <section className="dpanel lg-search">
        <form onSubmit={(e) => { e.preventDefault(); setMsg(null); legal.post("/research/precheck", { question: q }).then(setPre).catch((x: Error) => setMsg(x.message)); }}>
          <label htmlFor="lg-q" className="lg-search-label">BUSCADOR JURÍDICO</label>
          <div className="lg-search-row">
            <input id="lg-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Escribe tu pregunta jurídica o pide una investigación (p. ej. «¿Qué debe incluir el aviso legal de mi tienda online?»)" minLength={8} required />
            <button type="submit" className="btn">Analizar</button>
          </div>
        </form>
        {pre && (
          <div className="meta-plan">
            <p className="small">Jurisdicción detectada: <b>{pre.jurisdiction_label}</b> · Ramas: {pre.branch_labels.join(", ")}</p>
            {!!pre.questions.length && <><p className="small"><b>Falta información esencial:</b></p><ul className="small">{pre.questions.map((x: string) => <li key={x}>{x}</li>)}</ul>
              <textarea rows={2} value={facts} onChange={(e) => setFacts(e.target.value)} placeholder="Añade aquí los datos que faltan" aria-label="Datos adicionales" /></>}
            <div className="row-btns">
              <button type="button" className="btn" onClick={() => legal.post("/research", { question: q, facts: facts || null }).then((r) => { setPre(null); setQ(""); go("research", { id: String(r.id) }); })}>Investigar en fuentes oficiales</button>
              <button type="button" className="btn ghost" onClick={() => go("agent", { q })}>Preguntar al Legal Agent</button>
            </div>
          </div>
        )}
        {msg && <p className="error-line" role="alert">{msg}</p>}
      </section>
      <State loading={loading && !d} error={error}>
        {d && <>
          <div className="stat-row">
            <Stat label="Expedientes activos" value={String(d.counts.active_cases)} /><Stat label="Documentos" value={String(d.counts.documents)} />
            <Stat label="Contratos sin revisar" value={String(d.counts.pending_review)} /><Stat label="Alertas abiertas" value={String(d.counts.open_alerts)} />
            <Stat label="Investigaciones" value={String(d.counts.research)} /><Stat label="Borradores" value={String(d.counts.drafts)} />
          </div>
          <div className="lg-levels">{Object.entries(d.alerts_by_level as Record<string, number>).map(([k, v]) => <span key={k} className={`l-${k}`}><b>{v}</b> {LV[k]}</span>)}</div>
          <div className="mod-cols">
            <section className="dpanel grow">
              <header className="dpanel-head"><span>PRÓXIMOS VENCIMIENTOS (60 DÍAS)</span><button type="button" className="link-btn" onClick={() => go("risks")}>plazos</button></header>
              {!d.deadlines.length ? <p className="desk-empty">Sin vencimientos registrados.</p> : <ul className="life-list compact">{d.deadlines.map((x: Row) => <li key={x.id}><div className="life-item">
                <b className={x.days < 0 ? "neg" : x.days <= 7 ? "warn" : ""}>{x.days < 0 ? `vencido hace ${-x.days} d` : `${x.days} d`}</b> {x.title} <small>{fmtDate(x.due_on)} · {x.kind}{x.verified ? " · verificado" : " · SIN VERIFICAR"}</small></div></li>)}</ul>}
              <header className="dpanel-head"><span>ALERTAS JURÍDICAS</span><button type="button" className="link-btn" onClick={() => go("risks")}>riesgos</button></header>
              {!d.alerts.length ? <p className="desk-empty">Sin alertas abiertas.</p> : <ul className="life-list compact">{d.alerts.map((a: Row) => <li key={a.id}><div className="life-item"><Lvl l={a.level} /> {a.title}</div></li>)}</ul>}
              <header className="dpanel-head"><span>EXPEDIENTES ACTIVOS</span><button type="button" className="link-btn" onClick={() => go("cases")}>todos</button></header>
              {!d.cases.length ? <p className="desk-empty">Aún no hay expedientes.</p> : <ul className="life-list compact">{d.cases.map((c: Row) => <li key={c.id}><div className="life-item">
                <button type="button" className="link-btn plain" onClick={() => go("cases", { id: String(c.id) })}>{c.ref} · {c.name}</button> <small>{STATE_L[c.status]} · prioridad {c.priority}</small></div></li>)}</ul>}
            </section>
            <section className="dpanel">
              <header className="dpanel-head"><span>CONTRATOS PENDIENTES DE REVISIÓN</span></header>
              {!d.pending_review.length ? <p className="desk-empty">Ninguno.</p> : <ul className="life-list compact">{d.pending_review.map((x: Row) => <li key={x.id}><div className="life-item">
                <button type="button" className="link-btn plain" onClick={() => go("contracts", { doc: String(x.id) })}>{x.title}</button></div></li>)}</ul>}
              <header className="dpanel-head"><span>INVESTIGACIONES RECIENTES</span></header>
              {!d.research.length ? <p className="desk-empty">Ninguna.</p> : <ul className="life-list compact">{d.research.map((r: Row) => <li key={r.id}><div className="life-item">
                <button type="button" className="link-btn plain" onClick={() => go("research", { id: String(r.id) })}>{r.question.slice(0, 90)}</button> <small>{r.status}</small></div></li>)}</ul>}
              <header className="dpanel-head"><span>ÚLTIMOS DOCUMENTOS</span></header>
              {!d.recent_docs.length ? <p className="desk-empty">Ninguno.</p> : <ul className="life-list compact">{d.recent_docs.map((x: Row) => <li key={x.id}><div className="life-item">{x.title} <small>{x.origin === "ia" ? "conclusión IA" : x.origin} · {fmtDate(x.updated_at)}</small></div></li>)}</ul>}
              <header className="dpanel-head"><span>ACTIVIDAD DEL LEGAL AGENT Y CONSULTAS</span></header>
              {!d.queries.length && !d.agent.length ? <p className="desk-empty">Sin consultas.</p> : <ul className="life-list compact">
                {d.queries.map((x: Row) => <li key={`q${x.id}`}><div className="life-item"><small>{x.kind} · {fmtDate(x.created_at)}</small> {x.question.slice(0, 110)}</div></li>)}
                {d.agent.map((x: Row, i: number) => <li key={`a${i}`}><div className="life-item"><small>VISTAN CORE · {fmtDate(x.at)}</small> {x.request}</div></li>)}</ul>}
            </section>
          </div>
          <button type="button" className="link-btn" onClick={() => legal.post("/alerts/scan").then(reload)}>Revisar plazos, contratos y cumplimiento ahora</button>
        </>}
      </State>
    </div>
  );
}

/* ───────── Legal Research Engine ───────── */
export function Research({ initial }: { initial: number | null }) {
  const list = useLoad<Row[]>("/research", [], legal);
  const [sel, setSel] = useState<number | null>(initial);
  const det = useLoad<Row>(sel ? `/research/${sel}` : null, [sel], legal);
  const [q, setQ] = useState("");
  const [facts, setFacts] = useState("");
  const [jur, setJur] = useState("auto");
  const [caseId, setCaseId] = useState<number | null>(null);
  const [pre, setPre] = useState<Row | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const t = useRef<number | null>(null);
  useEffect(() => {
    if (list.data?.some((r) => live(r.status))) t.current = window.setInterval(() => { list.reload(); if (sel) det.reload(); }, 3000);
    return () => { if (t.current) clearInterval(t.current); };
  }, [list.data, sel]); // eslint-disable-line react-hooks/exhaustive-deps
  const r = det.data;
  const rp = r?.report ?? {};
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Legal Research Engine</h2><p className="muted small">Solo fuentes oficiales (BOE, Portal Jurídic, EUR-Lex, CURIA, TC, CENDOJ, AEPD, AEAT, Seguridad Social…).
        Antes de investigar detecta la jurisdicción y te pregunta lo esencial. Cada cita se comprueba contra la fuente leída y la vigencia contra el BOE/EUR-Lex.</p></div>
      <section className="dpanel"><form className="life-form" onSubmit={(e) => { e.preventDefault(); setMsg(null);
        if (!pre) { legal.post("/research/precheck", { question: q, facts }).then(setPre).catch((x: Error) => setMsg(x.message)); return; }
        legal.post("/research", { question: q, facts: facts || null, jurisdiction: jur, case_id: caseId }).then((x) => { setSel(x.id); setPre(null); setQ(""); setFacts(""); list.reload(); }).catch((x: Error) => setMsg(x.message)); }}>
        <label className="wide"><span>Pregunta jurídica *</span><textarea rows={2} value={q} onChange={(e) => { setQ(e.target.value); setPre(null); }} required minLength={8} aria-label="Pregunta jurídica" /></label>
        <label className="wide"><span>Hechos relevantes (lugar, fechas, tipo de relación…)</span><textarea rows={2} value={facts} onChange={(e) => setFacts(e.target.value)} aria-label="Hechos relevantes" /></label>
        <label><span>Jurisdicción</span><select value={jur} onChange={(e) => setJur(e.target.value)} aria-label="Jurisdicción"><option value="auto">Detectar</option><option value="es">España</option><option value="es-ct">Cataluña</option><option value="eu">Unión Europea</option></select></label>
        <label><span>Expediente</span><CasePick value={caseId} onChange={setCaseId} /></label>
        {pre && <div className="wide meta-plan"><p className="small">Detectado: <b>{pre.jurisdiction_label}</b> · {pre.branch_labels.join(", ")}</p>
          {pre.questions.length ? <ul className="small">{pre.questions.map((x: string) => <li key={x}>{x}</li>)}</ul> : <p className="small">No falta información esencial evidente.</p>}</div>}
        <div className="wide row-btns"><button type="submit" className="btn" disabled={q.trim().length < 8}>{pre ? "Investigar" : "Comprobar antes de investigar"}</button></div>
      </form>{msg && <p className="error-line" role="alert">{msg}</p>}</section>
      <div className="mod-cols">
        <section className="dpanel meta-runs"><header className="dpanel-head"><span>HISTORIAL</span></header>
          <ul className="exp-list">{list.data?.map((x) => <li key={x.id}><button type="button" className={sel === x.id ? "on" : ""} onClick={() => setSel(x.id)}>
            <span className={`exp-state s-${x.status === "done" ? "COMPLETED" : x.status === "error" ? "FAILED" : "RUNNING"}`}>{x.status}{live(x.status) ? ` ${x.progress}%` : ""}</span>
            <b>{x.question.slice(0, 80)}</b><small>{x.jurisdiction} · {x.sources_count} fuentes · {fmtDate(x.created_at)}</small></button></li>)}</ul></section>
        {r ? <section className="dpanel grow lg-report" data-testid="legal-research">
          <header className="dpanel-head"><span>#{r.id} · {r.status.toUpperCase()}{r.step ? ` · ${r.step}` : ""}</span>
            <span className="row-actions">
              {r.status === "error" && <button type="button" className="mini-btn" onClick={() => legal.post(`/research/${r.id}/resume`).then(det.reload)}>Reanudar</button>}
              {r.status === "done" && <><a className="mini-btn ghost" href={`/api/legal/reports/research/${r.id}?fmt=pdf`}>PDF</a><a className="mini-btn ghost" href={`/api/legal/reports/research/${r.id}?fmt=docx`}>DOCX</a>
                <button type="button" className="mini-btn ghost" onClick={() => legal.post(`/research/${r.id}/save`).then(() => setMsg("Guardado en la base de conocimiento como conclusión de IA"))}>Guardar en conocimiento</button></>}
            </span></header>
          <p className="meta-q">{r.question}</p>
          {r.error && <p className="warn-line l-warn">{r.error}</p>}
          {r.status === "done" && <>
            <div className="ai-text"><h4>Resumen ejecutivo</h4><Md text={rp.resumen} /></div>
            <p className="small"><b>Problema jurídico:</b> {rp.problema} · <b>Jurisdicción:</b> {rp.jurisdiccion}</p>
            <h4>Legislación aplicable</h4>
            {!rp.legislacion?.length ? <p className="desk-empty">Las fuentes leídas no permitieron identificar legislación.</p> : <ul className="disc-list">{rp.legislacion.map((x: Row, i: number) => (
              <li key={i}><b>{x.norma}</b> <span className={`lg-vig v-${x.vigencia}`}>{VIG[x.vigencia] ?? x.vigencia}{x.vigencia_via ? ` (${x.vigencia_via})` : ""}</span>
                {x.verificada_en_fuente ? <span className="lg-ok">en la fuente</span> : <span className="lg-bad">NO verificada en las fuentes leídas</span>}
                <small>Artículos citados: {(x.articulos ?? []).join(", ") || "—"}{x.articulos_no_encontrados?.length ? ` · no encontrados en el texto: ${x.articulos_no_encontrados.join(", ")}` : ""}</small>
                <p className="small">{x.contenido}</p>{x.url && <a className="small" href={x.url} target="_blank" rel="noreferrer noopener">{x.fuente_oficial} ↗</a>}</li>))}</ul>}
            <h4>Jurisprudencia</h4>
            {!rp.jurisprudencia?.length ? <p className="desk-empty">No se localizó jurisprudencia en las fuentes leídas.</p> : <ul className="disc-list">{rp.jurisprudencia.map((x: Row, i: number) => <li key={i}><b>{x.resolucion}</b>
              {x.verificada_en_fuente ? <span className="lg-ok">en la fuente</span> : <span className="lg-bad">NO verificada</span>}<p className="small">{x.criterio}</p></li>)}</ul>}
            {[["Interpretación jurídica", rp.interpretacion], ["Aplicación al caso", rp.aplicacion], ["Conclusión", rp.conclusion]].map(([l, t]) => t ? <div key={l as string}><h4>{l}</h4><p className="small">{t}</p></div> : null)}
            {(rp.riesgos?.length || rp.incertidumbres?.length) && <div className="sc-block pred"><h4>Riesgos e incertidumbres</h4><ul>{[...(rp.riesgos ?? []), ...(rp.incertidumbres ?? [])].map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
            {rp.requiere_abogado && <p className="warn-line l-warn">La complejidad o las consecuencias aconsejan consultar con un abogado.</p>}
            <h4>Fuentes consultadas</h4><ol className="small">{rp.fuentes?.map((s: Row) => <li key={s.id}><a href={s.url} target="_blank" rel="noreferrer noopener">{s.organismo} · {s.titulo}</a> <small>({s.tipo}, consultada {s.consultada ?? "—"})</small></li>)}</ol>
            <p className="mini-note">{r.verification?.nota} {r.verification?.verificadas}/{r.verification?.citas} citas verificadas. {rp.aviso}</p>
          </>}
          {msg && <p className="small">{msg}</p>}
        </section> : <section className="dpanel grow"><p className="desk-empty">Elige una investigación.</p></section>}
      </div>
    </div>
  );
}

/* ───────── Contract Analyzer ───────── */
export function Contracts({ initialDoc }: { initialDoc: number | null }) {
  const [caseId, setCaseId] = useState<number | null>(null);
  const docs = useLoad<Row[]>(`/documents${caseId ? `?case_id=${caseId}` : ""}`, [caseId], legal);
  const [sel, setSel] = useState<number | null>(initialDoc);
  const det = useLoad<Row>(sel ? `/documents/${sel}` : null, [sel], legal);
  const [aid, setAid] = useState<number | null>(null);
  const an = useLoad<Row>(aid ? `/analyses/${aid}` : null, [aid], legal);
  const [cmp, setCmp] = useState<number[]>([]);
  const [cres, setCres] = useState<Row | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { const last = det.data?.analyses?.[0]; setAid(last ? last.id : null); }, [det.data?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    // Sondeo encadenado: tras cada respuesta, si sigue en curso, se programa la siguiente consulta
    if (!an.data || an.data.id !== aid || !live(an.data.status)) return;
    const t = window.setTimeout(an.reload, 1200);
    return () => clearTimeout(t);
  }, [an.data, aid]); // eslint-disable-line react-hooks/exhaustive-deps
  const up = (f: File) => { setBusy(true); setMsg(null); const fd = new FormData(); fd.append("file", f); fd.append("kind", "contract"); if (caseId) fd.append("case_id", String(caseId));
    fetch("/api/legal/documents", { method: "POST", body: fd, credentials: "same-origin" }).then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail);
      setMsg(j.created ? `«${j.title}» extraído (${j.extraction}, ${j.chars} caracteres)` : "Ya estaba en este expediente (duplicado)"); setSel(j.id); docs.reload(); })
      .catch((e: Error) => setMsg(e.message)).finally(() => setBusy(false)); };
  const a = an.data?.result;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Contract Analyzer</h2><p className="muted small">PDF, DOCX, DOC, TXT, RTF, ODT y escaneados (OCR con el modelo de visión local). El original se guarda cifrado.
        Reglas explicables + IA local; un riesgo cuyo fragmento no existe en el contrato se descarta. Nunca se declara un contrato legal, ilegal, válido o nulo.</p></div>
      <section className="dpanel"><div className="filters">
        <CasePick value={caseId} onChange={(v) => { setCaseId(v); setSel(null); setCmp([]); }} />
        <label className="btn file-btn">{busy ? "Procesando…" : "Subir contrato"}<input type="file" hidden accept=".pdf,.docx,.doc,.txt,.rtf,.odt,.png,.jpg,.jpeg,.webp" onChange={(e) => { const f = e.target.files?.[0]; if (f) up(f); e.target.value = ""; }} /></label>
        <button type="button" className="btn ghost" disabled={cmp.length !== 2} onClick={() => { const [x, y] = [...cmp].sort((m, n) => m - n); return legal.post("/compare", { a_id: x, b_id: y }).then(setCres).catch((e: Error) => setMsg(e.message)); }}>Comparar 2 versiones (antigua → nueva)</button>
      </div>{msg && <p className="small">{msg}</p>}</section>
      <div className="mod-cols">
        <section className="dpanel meta-runs"><header className="dpanel-head"><span>DOCUMENTOS</span></header>
          <State loading={docs.loading && !docs.data} error={docs.error} empty={docs.data && !docs.data.length ? "Sin documentos en este expediente." : false}>
            <ul className="exp-list">{docs.data?.map((x) => <li key={x.id} className="cmp-item">
              <input type="checkbox" aria-label={`Comparar ${x.title}`} checked={cmp.includes(x.id)} onChange={(e) => setCmp(e.target.checked ? [...cmp, x.id].slice(-2) : cmp.filter((y) => y !== x.id))} />
              <button type="button" className={sel === x.id ? "on" : ""} onClick={() => { setSel(x.id); setCres(null); }}><span className="exp-state">{x.kind}</span><b>{x.title}</b>
                <small>{x.origin} · {x.extraction} · v{x.version} · {fmtDate(x.created_at)}</small></button></li>)}</ul>
          </State></section>
        {cres ? <CompareView c={cres} onClose={() => setCres(null)} /> : det.data ? (
          <section className="dpanel grow" data-testid="contract-view">
            <header className="dpanel-head"><span>{det.data.title.toUpperCase()}</span><span className="row-actions">
              <button type="button" className="mini-btn" disabled={!!an.data && live(an.data.status)} onClick={() => legal.post(`/documents/${det.data!.id}/analyze`).then((x) => setAid(x.id))}>Analizar</button>
              {det.data.has_original && <a className="mini-btn ghost" href={`/api/legal/documents/${det.data.id}/download`}>Original</a>}
              {a && <><a className="mini-btn ghost" href={`/api/legal/reports/analysis/${aid}?fmt=pdf`}>Informe PDF</a><a className="mini-btn ghost" href={`/api/legal/reports/analysis/${aid}?fmt=docx`}>DOCX</a></>}
              <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar el documento, su original cifrado y su texto?")) void legal.del(`/documents/${det.data!.id}?confirm=true`).then(() => { setSel(null); docs.reload(); }); }}>✕</button>
            </span></header>
            {an.data && live(an.data.status) && <p className="small">Analizando… (IA local)</p>}
            {an.data?.status === "error" && <p className="warn-line l-warn">{an.data.error}</p>}
            {a && an.data?.id === aid && !live(an.data.status) ? <>
              <div className="stat-row"><Stat label="Tipo" value={a.type_label} />{["critico", "alto", "medio", "bajo"].map((l) => <Stat key={l} label={LV[l]} value={String(a.counts[l])} cls={`l-${l}`} />)}</div>
              {a.summary && <p className="small">{a.summary}</p>}
              <p className="small">Partes: {(a.entities.parties.length ? a.entities.parties : a.parties_ai).join(" · ") || "no identificadas"} · Fechas: {a.entities.dates.join(", ") || "—"} · Importes: {a.entities.amounts.join(", ") || "—"} · Plazos: {a.entities.periods.join(", ") || "—"}</p>
              {a.ai_error && <p className="warn-line l-warn">Solo reglas: la IA local no respondió ({a.ai_error}).</p>}
              <h4>Riesgos</h4>
              <ul className="disc-list">{a.risks.map((r: Row, i: number) => <li key={i} className={`risk l-${r.nivel}`}><div className="d-tags"><Lvl l={r.nivel} /><b>{r.clausula}</b><small>{r.origen === "ia" ? "IA local" : "regla"}</small></div>
                <blockquote>«{r.fragmento}»</blockquote><p className="small">{r.problema}</p>{r.consecuencia && <p className="small">Consecuencia posible: {r.consecuencia}</p>}
                {r.norma && <p className="mini-note">Norma sugerida (no verificada): {r.norma}</p>}<p className="small">→ {r.recomendacion}</p>
                {r.redaccion_alternativa && <p className="small lg-alt">Propuesta: {r.redaccion_alternativa}</p>}</li>)}</ul>
              {!!a.contradictions.length && <><h4>Posibles contradicciones</h4><ul className="small">{a.contradictions.map((c: Row) => <li key={c.detalle}>{c.tema}: {c.detalle}</li>)}</ul></>}
              {!!a.missing.length && <><h4>Información ausente</h4><p className="small">{a.missing.join(" · ")}</p></>}
              {!!a.obligations.length && <><h4>Obligaciones</h4><ul className="small">{a.obligations.map((o: Row, i: number) => <li key={i}><b>{o.parte}</b>: {o.obligacion} {o.plazo ? `(${o.plazo})` : ""}</li>)}</ul></>}
              {a.termination && <p className="small"><b>Terminación y renovación:</b> {a.termination}</p>}
              <p className="mini-note">{a.note}</p>
            </> : !an.data && <p className="desk-empty">Pulsa «Analizar» para revisar el contrato.</p>}
            <details className="meta-sec"><summary>Texto extraído ({det.data.chars} caracteres · {det.data.extraction})</summary><pre className="arena-out">{det.data.text}</pre></details>
          </section>) : <section className="dpanel grow"><p className="desk-empty">Sube o elige un documento.</p></section>}
      </div>
    </div>
  );
}

export function CompareView({ c, onClose }: { c: Row; onClose: () => void }) {
  const r = c.result;
  return (
    <section className="dpanel grow" data-testid="compare-view">
      <header className="dpanel-head"><span>{c.a_title} → {c.b_title}</span><span className="row-actions">
        <a className="mini-btn ghost" href={`/api/legal/reports/comparison/${c.id}?fmt=pdf`}>PDF</a><a className="mini-btn ghost" href={`/api/legal/reports/comparison/${c.id}?fmt=docx`}>DOCX</a>
        <button type="button" className="mini-btn ghost" onClick={onClose}>Cerrar</button></span></header>
      <p className="small">{r.counts.añadida} añadidas · {r.counts.eliminada} eliminadas · {r.counts.modificada} modificadas · similitud {r.similarity ?? "N/D"} %</p>
      <p className="small">{Object.entries(r.summary as Record<string, number>).filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`).join(" · ") || "Sin cambios clasificados"}</p>
      {r.changes.map((ch: Row, i: number) => <div key={i} className={`diff-card k-${ch.kind}`}><b>{ch.kind.toUpperCase()} · {ch.clause}</b> <small>{ch.categories.join(", ")}</small>
        {ch.kind === "modificada" ? <p className="diff">{ch.diff.map((o: Row, j: number) => o.op === "equal" ? <span key={j}>{o.a} </span> : <span key={j}>{o.a && <del>{o.a}</del>} {o.b && <ins>{o.b}</ins>} </span>)}</p>
          : <p className="diff">{ch.kind === "añadida" ? <ins>{ch.after}</ins> : <del>{ch.before}</del>}</p>}</div>)}
    </section>
  );
}
