import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { lab, type Row } from "../../api/life";
import { Crud, fmtDate, SchemaForm, State, useLoad } from "../life/kit";
import { catOpts, Tag, type Meta } from "./LabA";

/* ───────── Scientific Knowledge Base ───────── */
const KINDS: [string, string][] = [["paper", "Paper"], ["article", "Artículo"], ["patent", "Patente"], ["report", "Informe"], ["docs", "Documentación"], ["book", "Libro"],
  ["publication", "Publicación"], ["experiment", "Experimento"], ["note", "Nota"], ["discovery", "Descubrimiento"], ["link", "Enlace"]];

export function Library({ meta }: { meta: Meta }) {
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [rag, setRag] = useState<Row | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [key, setKey] = useState(0);
  const path = `/library?${new URLSearchParams(Object.entries({ q, kind }).filter(([, v]) => v) as [string, string][])}`;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Scientific Knowledge Base</h2><p className="muted small">Papers, patentes, informes, libros, notas y enlaces. «Indexar» los añade al RAG y al grafo de conocimiento de VISTAN marcados como [Lab]. Siempre se distingue lo <b>propio</b> de las <b>fuentes externas</b>.</p></div>
      <div className="filters">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar en la biblioteca…" aria-label="Buscar en la biblioteca" />
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Tipo"><option value="">Todos los tipos</option>{KINDS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <button type="button" className="btn ghost" disabled={!q.trim()} onClick={() => lab.get(`/library/search/rag?q=${encodeURIComponent(q)}`).then(setRag)}>Buscar en todo el conocimiento (RAG)</button>
        <a className="btn ghost" href="/api/security/export">Exportar</a>
      </div>
      {rag && <section className="dpanel"><header className="dpanel-head"><span>RESULTADOS RAG</span><button type="button" className="link-btn" onClick={() => setRag(null)}>cerrar</button></header>
        <p className="mini-note">{rag.note}</p>
        {!rag.hits.length ? <p className="desk-empty">Sin fragmentos relevantes.</p> : <ul className="disc-list">{rag.hits.map((h: Row, i: number) => <li key={i}><b>{h.title}</b> <Tag kind={h.title.startsWith("[Lab]") ? "academic" : "prototype"}>{h.title.startsWith("[Lab]") ? "laboratorio" : "documento propio"}</Tag><p className="small">{h.text.slice(0, 400)}</p></li>)}</ul>}
      </section>}
      {msg && <p className="small">{msg}</p>}
      <Crud key={`${path}${key}`} api={lab} title="Biblioteca" path={path} editPath={(r) => `/library/${r.id}`}
        fields={[{ k: "kind", label: "Tipo", type: "select", options: KINDS, required: true }, { k: "title", label: "Título", required: true },
          { k: "origin", label: "Origen", type: "select", options: [["external", "Fuente externa"], ["own", "Propio"]], required: true },
          { k: "authors", label: "Autores", type: "tags" }, { k: "url", label: "URL", placeholder: "https://…" }, { k: "published_on", label: "Fecha", type: "date" },
          { k: "category", label: "Categoría", type: "select", options: catOpts(meta) }, { k: "tags", label: "Etiquetas", type: "tags" },
          { k: "summary", label: "Resumen", type: "textarea" }, { k: "notes", label: "Notas / texto", type: "textarea" }]}
        newDefaults={{ kind: "paper", origin: "external" }}
        render={(i) => <><Tag kind={i.origin === "own" ? "prototype" : "academic"}>{i.origin === "own" ? "propio" : "externo"}</Tag> <b>{i.url ? <a href={i.url} target="_blank" rel="noreferrer noopener">{i.title}</a> : i.title}</b>
          <small> · {KINDS.find((k) => k[0] === i.kind)?.[1]}{i.authors?.length ? ` · ${i.authors.slice(0, 3).join(", ")}` : ""}{i.published_on ? ` · ${fmtDate(i.published_on)}` : ""}{i.document_id ? " · indexado (RAG)" : ""}</small>
          {!!i.concepts?.length && <p className="small">Conceptos: {i.concepts.join(" · ")}</p>}{!!i.tags?.length && <small>#{i.tags.join(" #")}</small>}</>}
        actions={(i, reload) => <>
          <button type="button" className="mini-btn ghost" onClick={() => lab.post(`/library/${i.id}/extract`).then(() => { setMsg("Resumen y conceptos extraídos del texto"); reload(); }).catch((e: Error) => setMsg(e.message))}>Conceptos</button>
          {!i.document_id && <button type="button" className="mini-btn ghost" onClick={() => lab.post(`/library/${i.id}/index`).then(() => { setMsg("Añadido al RAG y al grafo de conocimiento"); setKey(key + 1); }).catch((e: Error) => setMsg(e.message))}>Indexar</button>}
          <button type="button" className="mini-btn ghost" onClick={() => lab.post("/remember", { text: `${i.title}: ${(i.summary ?? "").slice(0, 600)}`, ref: "biblioteca" }).then(() => setMsg("Guardado en la memoria"))}>Recordar</button>
        </>} />
    </div>
  );
}

/* ───────── Idea Generator ───────── */
const SRC: [string, string][] = [["daily", "Problema cotidiano"], ["business", "Necesidad empresarial"], ["advance", "Avance tecnológico"], ["material", "Nuevo material"],
  ["emerging", "Tecnología emergente"], ["combo", "Combinación de tecnologías"], ["market", "Oportunidad de mercado"], ["science", "Investigación científica"]];

export function Ideas({ meta }: { meta: Meta }) {
  const list = useLoad<Row[]>("/ideas", [], lab);
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const convert = (id: number, to: string) => lab.post(`/ideas/${id}/convert`, { to }).then(() => { setMsg(`Idea convertida en ${{ experiment: "experimento", prototype: "prototipo", opportunity: "oportunidad de negocio (LIFE OS)", project: "proyecto" }[to]}`); list.reload(); }).catch((e: Error) => setMsg(e.message));
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Idea Generator</h2><p className="muted small">Las ideas generadas son <b>hipótesis sin validar</b>, nunca inventos demostrados. Cada una propone un experimento barato para comprobarla.</p></div>
      <section className="dpanel"><header className="dpanel-head"><span>GENERAR IDEAS</span></header>
        <SchemaForm fields={[{ k: "source", label: "A partir de", type: "select", options: SRC, required: true }, { k: "text", label: "Describe el punto de partida", type: "textarea", required: true },
          { k: "category", label: "Categoría", type: "select", options: catOpts(meta) }, { k: "n", label: "Número de ideas (1-5)", type: "number" }]} initial={{ source: "daily", n: 3 }} submitLabel="Generar"
          onSubmit={(v) => lab.post<Row[]>("/ideas/generate", v).then((r) => { setMsg(`${r.length} ideas generadas`); list.reload(); })} /></section>
      {msg && <p className="small">{msg}</p>}
      <State loading={list.loading && !list.data} error={list.error} empty={list.data && !list.data.length ? "Aún no hay ideas." : false}>
        <div className="idea-grid">{list.data?.map((i) => (
          <article key={i.id} className={`dpanel idea s-${i.status}`}>
            <header className="dpanel-head"><span>{i.name.toUpperCase()}</span><Tag kind={i.origin === "generated" ? "speculative" : "prototype"}>{i.origin === "generated" ? "IA · sin validar" : "tuya"}</Tag></header>
            <p className="small">{i.concept}</p>
            <div className="idea-meta"><span>Dificultad: <b>{i.difficulty ?? "—"}</b></span><span>Coste: <b>{i.cost ?? "—"}</b></span><span>Estado: <b>{i.status}</b></span></div>
            {open === i.id && <dl className="opp-dl">{[["problem", "Problema"], ["solution", "Solución"], ["tech", "Tecnología necesaria"], ["feasibility", "Viabilidad preliminar"], ["applications", "Aplicaciones"],
              ["risks", "Riesgos"], ["customers", "Posibles clientes"], ["next_experiment", "Próximo experimento"]].filter(([k]) => i[k]).map(([k, l]) => <div key={k}><dt>{l}</dt><dd>{i[k]}</dd></div>)}</dl>}
            <div className="row-actions wrap">
              <button type="button" className="mini-btn ghost" onClick={() => setOpen(open === i.id ? null : i.id)}>{open === i.id ? "Menos" : "Detalle"}</button>
              {!i.experiment_id && <button type="button" className="mini-btn" onClick={() => convert(i.id, "experiment")}>→ Experimento</button>}
              {!i.prototype_id && <button type="button" className="mini-btn ghost" onClick={() => convert(i.id, "prototype")}>→ Prototipo</button>}
              {!i.opportunity_id && <button type="button" className="mini-btn ghost" onClick={() => convert(i.id, "opportunity")}>→ Negocio</button>}
              {!i.project_id && <button type="button" className="mini-btn ghost" onClick={() => convert(i.id, "project")}>→ Proyecto</button>}
              <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar la idea?")) void lab.del(`/ideas/${i.id}`).then(list.reload); }}>✕</button>
            </div>
          </article>
        ))}</div>
      </State>
    </div>
  );
}

/* ───────── Future Technology Simulator ───────── */
export function Future() {
  const list = useLoad<Row[]>("/scenarios", [], lab);
  const researches = useLoad<Row[]>("/research", [], lab);
  const [sel, setSel] = useState<Row | null>(null);
  const done = (researches.data ?? []).filter((r) => r.research.status === "done");
  const r = sel?.result;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Future Technology Simulator</h2><p className="muted small">Diferencia <b>hechos</b> (solo si apoyas el escenario en una investigación con fuentes), <b>hipótesis</b> y <b>predicciones</b>. Ningún escenario es una certeza.</p></div>
      <section className="dpanel"><SchemaForm fields={[{ k: "question", label: "Escenario a estudiar", type: "textarea", required: true, placeholder: "¿Qué oportunidades aparecerán con la robótica humanoide?" },
        { k: "horizon", label: "Horizonte", type: "select", options: ["1 año", "3 años", "5 años", "10 años", "20 años"].map((x) => [x, x] as [string, string]), required: true },
        { k: "research_id", label: "Apoyar en una investigación terminada (recomendado)", type: "select", options: done.map((x) => [String(x.research_id), x.research.question.slice(0, 80)] as [string, string]) }]}
        initial={{ horizon: "5 años" }} submitLabel="Simular escenario"
        onSubmit={(v) => lab.post("/scenarios", { ...v, research_id: v.research_id ? Number(v.research_id) : null }).then((x) => { setSel(x); list.reload(); })} /></section>
      <div className="mod-cols">
        <section className="dpanel"><header className="dpanel-head"><span>ESCENARIOS</span></header>
          <ul className="life-list compact">{list.data?.map((s) => <li key={s.id}><div className="life-item"><button type="button" className={`link-btn plain ${sel?.id === s.id ? "on" : ""}`} onClick={() => setSel(s)}>{s.question.slice(0, 100)}</button> <small>{s.horizon} · {s.research_id ? "con fuentes" : "sin investigación de apoyo"}</small></div>
            <button type="button" className="mini-btn ghost" onClick={() => lab.del(`/scenarios/${s.id}`).then(list.reload)}>✕</button></li>)}</ul></section>
        {r && (
          <section className="dpanel grow scenario-view">
            <header className="dpanel-head"><span>{sel!.horizon.toUpperCase()} · {sel!.model}</span></header>
            <div className="sc-block facts"><h4>Hechos demostrados</h4>{(r.hechos ?? []).length ? <ul>{r.hechos.map((h: Row, i: number) => <li key={i}>{h.texto} <small>{h.fuente}</small></li>)}</ul> : <p className="mini-note">Sin hechos: el escenario no se apoyó en una investigación con fuentes.</p>}</div>
            <div className="sc-block hyp"><h4>Hipótesis</h4><ul>{(r.hipotesis ?? []).map((x: string) => <li key={x}>{x}</li>)}</ul></div>
            <div className="sc-block pred"><h4>Predicciones (no son certezas)</h4><ul>{(r.predicciones ?? []).map((x: string) => <li key={x}>{x}</li>)}</ul></div>
            {!!r.escenarios?.length && <div className="sc-grid">{r.escenarios.map((e: Row) => <div key={e.nombre} className="sc-card"><b>{e.nombre}</b><small>probabilidad cualitativa: {e.probabilidad_cualitativa}</small><p className="small">{e.descripcion}</p>
              {!!e.senales_tempranas?.length && <p className="mini-note">Señales: {e.senales_tempranas.join("; ")}</p>}</div>)}</div>}
            {[["variables", "Variables"], ["factores", "Factores de influencia"], ["oportunidades", "Oportunidades"], ["riesgos", "Riesgos"], ["incertidumbres", "Incertidumbres"], ["fuentes", "Fuentes utilizadas"]]
              .map(([k, l]) => (r[k] ?? []).length ? <div key={k} className="sc-block"><h4>{l}</h4><ul>{r[k].map((x: string) => <li key={x}>{x}</li>)}</ul></div> : null)}
          </section>
        )}
      </div>
    </div>
  );
}

/* ───────── Patent & Invention Tracker ───────── */
export function Patents() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<Row | null>(null);
  const [key, setKey] = useState(0);
  const [k, setK] = useState({ key: "", secret: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const save = (p: Row) => lab.post("/patents", { kind: "external", title: p.title, number: p.number, office: p.office, applicants: p.applicants, abstract: p.abstract, url: p.url, published_on: p.published ?? null, technology: q })
    .then(() => { setMsg("Patente guardada"); setKey(key + 1); }).catch((e: Error) => setMsg(e.message));
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Patent & Invention Tracker</h2><p className="callout small">VISTAN no puede afirmar que una idea sea patentable ni que esté libre de derechos: eso requiere un análisis jurídico profesional (agente de la propiedad industrial).</p></div>
      <section className="dpanel"><div className="filters">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar patentes (p. ej. smart glasses translation)" aria-label="Buscar patentes" />
        <button type="button" className="btn" disabled={!q.trim()} onClick={() => lab.get(`/patents/search?q=${encodeURIComponent(q)}`).then(setRes)}>Buscar</button></div>
        {res && <>
          {res.error && <p className="warn-line l-warn">{res.error}</p>}
          <p className="small">Búsquedas oficiales: <a href={res.links.google_patents} target="_blank" rel="noreferrer noopener">Google Patents ↗</a> · <a href={res.links.espacenet} target="_blank" rel="noreferrer noopener">Espacenet ↗</a> · <a href={res.links.oepm} target="_blank" rel="noreferrer noopener">OEPM (España) ↗</a></p>
          <ul className="disc-list">{res.items.map((p: Row) => <li key={p.number}><b><a href={p.url} target="_blank" rel="noreferrer noopener">{p.title}</a></b><small>{p.number} · {p.applicants.join(", ")} · {p.published ?? "s/f"} · {p.source}</small><p className="small">{p.abstract?.slice(0, 300)}</p>
            <button type="button" className="mini-btn ghost" onClick={() => save(p)}>Guardar referencia</button></li>)}</ul></>}
      </section>
      {msg && <p className="small">{msg}</p>}
      <Crud key={key} api={lab} title="Patentes guardadas e inventos propios" path="/patents"
        fields={[{ k: "kind", label: "Tipo", type: "select", options: [["external", "Patente externa"], ["own", "Invento / idea propia"]], required: true }, { k: "title", label: "Título", required: true },
          { k: "number", label: "Número" }, { k: "office", label: "Oficina" }, { k: "applicants", label: "Solicitantes", type: "tags" }, { k: "url", label: "URL" }, { k: "published_on", label: "Publicación", type: "date" },
          { k: "technology", label: "Tecnología relacionada" }, { k: "status", label: "Estado (propias)", type: "select", options: [["idea", "Idea"], ["drafting", "Redactando"], ["consulted", "Consultado con un profesional"], ["filed", "Solicitada"]] },
          { k: "abstract", label: "Resumen", type: "textarea" }, { k: "notes", label: "Notas y comparación", type: "textarea" }]} newDefaults={{ kind: "own", status: "idea" }}
        render={(p) => <><Tag kind={p.kind === "own" ? "prototype" : "academic"}>{p.kind === "own" ? "propia" : "externa"}</Tag> <b>{p.url ? <a href={p.url} target="_blank" rel="noreferrer noopener">{p.title}</a> : p.title}</b><small> {p.number ?? ""} {p.technology ? `· ${p.technology}` : ""} {p.status ? `· ${p.status}` : ""}</small></>} />
      <section className="dpanel"><header className="dpanel-head"><span>CONECTAR ESPACENET (EPO OPS)</span></header>
        <p className="small">Gratis: regístrate en developers.epo.org, crea una app y copia el <b>consumer key</b> y el <b>secret</b>. Se guardan en el llavero de tu Mac.</p>
        <div className="filters"><input type="password" value={k.key} onChange={(e) => setK({ ...k, key: e.target.value })} placeholder="Consumer key" aria-label="Consumer key" />
          <input type="password" value={k.secret} onChange={(e) => setK({ ...k, secret: e.target.value })} placeholder="Consumer secret" aria-label="Consumer secret" />
          <button type="button" className="btn" disabled={!k.key || !k.secret} onClick={() => lab.put("/sources/epo", k).then(() => { setMsg("Credenciales guardadas"); setK({ key: "", secret: "" }); })}>Guardar</button></div></section>
    </div>
  );
}

/* ───────── Innovation Project Manager ───────── */
export function LabProjects() {
  const { data, error, loading, reload } = useLoad<Row[]>("/projects", [], lab);
  const [edit, setEdit] = useState<number | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Innovation Project Manager</h2><p className="muted small">Proyectos creados desde investigaciones, experimentos, prototipos o ideas. Las tareas viven en <Link to="/tasks">Tareas</Link> y los proyectos en <Link to="/projects">Proyectos</Link> (Planning Agent incluido).</p></div>
      <State loading={loading && !data} error={error} empty={data && !data.length ? "Aún no hay proyectos de innovación: conviértelos desde un experimento, prototipo, investigación o idea." : false}>
        {data?.map((p) => (
          <section key={p.project_id} className="dpanel">
            <header className="dpanel-head"><span>{p.name.toUpperCase()} · {p.status}</span><span>{p.tasks_done}/{p.tasks} tareas · origen: {p.origin_type}</span></header>
            <div className="progress-bar"><i style={{ width: `${p.tasks ? Math.round((p.tasks_done / p.tasks) * 100) : 0}%` }} /></div>
            {edit === p.project_id ? <SchemaForm fields={[{ k: "owner", label: "Responsable" }, { k: "budget", label: "Presupuesto (€)", type: "number" }, { k: "spent", label: "Gastado (€)", type: "number" },
              { k: "agents", label: "Agentes", type: "tags" }, { k: "resources", label: "Recursos", type: "textarea" }, { k: "results", label: "Resultados", type: "textarea" }, { k: "next_steps", label: "Próximos pasos", type: "textarea" }]}
              initial={p} onCancel={() => setEdit(null)} onSubmit={(v) => lab.patch(`/projects/${p.project_id}`, v).then(() => { setEdit(null); reload(); })} /> : (
              <div className="dec-body">
                <p className="small">Responsable: {p.owner ?? "—"} · Presupuesto: {p.budget != null ? `${p.budget} €` : "—"} · Gastado: {p.spent} € · Agentes: {(p.agents ?? []).join(", ") || "—"}</p>
                {p.next.length > 0 && <p className="small">Siguiente: {p.next.join(" · ")}</p>}
                {p.results && <p className="small">Resultados: {p.results}</p>}
                <div className="row-actions"><button type="button" className="mini-btn ghost" onClick={() => setEdit(p.project_id)}>Editar</button><Link className="mini-btn ghost" to="/projects">Abrir en Proyectos</Link></div>
              </div>
            )}
          </section>
        ))}
      </State>
    </div>
  );
}

/* ───────── Automatizaciones y fuentes ───────── */
export function LabWorkflows({ meta }: { meta: Meta }) {
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Automation & Lab Workflows</h2><p className="muted small">Usan el motor de Automatizaciones de VISTAN: permisos por paso (lectura / ejecución), historial, aprobaciones y botón de parar. Se instalan <b>desactivadas</b>: las activas tú. Ninguna compra, paga ni publica nada.</p></div>
      <div className="idea-grid">{Object.entries(meta.workflows).map(([k, w]) => (
        <article key={k} className="dpanel"><header className="dpanel-head"><span>{w.name.toUpperCase()}</span></header>
          <p className="small">Programación: {w.schedule} · Pasos: {w.steps.map((s: Row) => s.type).join(" → ")}</p>
          <div className="row-actions"><button type="button" className="mini-btn" onClick={() => lab.post(`/workflows/${k}`).then(() => setMsg(`«${w.name}» creada (desactivada). Actívala en Automatizaciones.`)).catch((e: Error) => setMsg(e.message))}>Instalar</button>
            <Link className="mini-btn ghost" to="/workflows">Gestionar</Link></div></article>
      ))}</div>
      {msg && <p className="small">{msg}</p>}
      <section className="dpanel"><header className="dpanel-head"><span>FUENTES EXTERNAS</span></header>
        <table className="dtable compact"><thead><tr><th>Fuente</th><th>Cubre</th><th>Clave</th><th>Estado</th></tr></thead>
          <tbody>{meta.sources.map((s) => <tr key={s.id}><td>{s.name}</td><td className="small">{s.covers}</td><td>{s.needs_key ? (s.configured ? "configurada" : "falta") : "no necesita"}</td>
            <td className="small">{s.last_error ? `error: ${s.last_error}` : s.ok ? `OK (${s.last_ms} ms)` : "sin usar"}{s.how && !s.configured ? ` · ${s.how}` : ""}</td></tr>)}</tbody></table></section>
    </div>
  );
}

/* ───────── Innovation Agent ───────── */
export function Agent() {
  const [msgs, setMsgs] = useState<{ role: "user" | "assistant"; content: string; meta?: string }[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [msgs]);
  const ask = (text: string) => {
    if (!text.trim() || busy) return;
    const history = msgs.map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: text }]); setQ(""); setBusy(true);
    lab.post<{ answer: string; model: string; used: string[] }>("/agent", { question: text, history })
      .then((r) => setMsgs((m) => [...m, { role: "assistant", content: r.answer, meta: `${r.model} · datos: ${r.used.join(", ")}` }]))
      .catch((e: Error) => setMsgs((m) => [...m, { role: "assistant", content: `⚠ ${e.message}` }])).finally(() => setBusy(false));
  };
  const quick = ["¿Qué experimento debería hacer ahora y con qué criterio de éxito?", "Analiza mis ideas y dime cuál tiene más evidencia a favor",
    "¿Qué tecnologías del radar tienen más actividad y por qué importa?", "Compara los resultados de mis experimentos y recomienda el siguiente"];
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Innovation Agent</h2><p className="muted small">Trabaja con VISTAN CORE y tus datos del laboratorio. Justifica sus conclusiones, distingue hechos de hipótesis y te dice cuándo no tiene información suficiente. En el chat general de VISTAN colabora con Research, Coding, Business, Planning y Memory.</p></div>
      <section className="tutor agent-full">
        <div className="tutor-log">
          {!msgs.length && <div className="quick">{quick.map((x) => <button type="button" key={x} className="chip" onClick={() => ask(x)}>{x}</button>)}</div>}
          {msgs.map((m, i) => <div key={i} className={`tmsg ${m.role}`}><div className="tbody">{m.content.split("\n").map((l, j) => <p key={j}>{l}</p>)}</div>{m.meta && <small>{m.meta}</small>}</div>)}
          {busy && <div className="tmsg assistant"><div className="tbody"><p className="muted">Analizando el laboratorio…</p></div></div>}
          <div ref={end} />
        </div>
        <form className="tutor-in" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Pregunta al Innovation Agent…" aria-label="Pregunta al Innovation Agent" maxLength={2000} />
          <button type="submit" className="btn" disabled={busy || !q.trim()}>Preguntar</button>
        </form>
      </section>
    </div>
  );
}
