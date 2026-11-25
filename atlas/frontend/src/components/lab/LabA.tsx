import { useEffect, useRef, useState } from "react";
import { lab, type Row } from "../../api/life";
import { Stat } from "../desk/ui";
import { Crud, fmtDate, Md, SchemaForm, State, useLoad, type Field } from "../life/kit";

export type Meta = { categories: Record<string, string>; maturity: Record<string, string>; states: string[]; sources: Row[]; workflows: Record<string, Row> };
export const catOpts = (m: Meta): [string, string][] => Object.entries(m.categories);
const REL = { alta: "Fiabilidad alta", media: "Fiabilidad media", baja: "Fiabilidad baja" } as Record<string, string>;

export function Tag({ kind, children }: { kind: string; children: React.ReactNode }) {
  return <span className={`lab-tag t-${kind}`}>{children}</span>;
}

/* ───────── Innovation Command Center ───────── */
export function Command({ meta, go }: { meta: Meta; go: (s: string) => void }) {
  const { data, error, loading, reload } = useLoad<Row>("/command", [], lab);
  useEffect(() => { const t = setInterval(reload, 5000); return () => clearInterval(t); }, [reload]); // actividad en tiempo real
  return (
    <State loading={loading && !data} error={error}>
      {data && (
        <div className="desk-module">
          <section className={`lab-hero s-${data.status.label === "activo" ? "on" : "idle"}`}>
            <div className="lab-core" aria-hidden="true"><i /><i /><i /><b /></div>
            <div>
              <small>ESTADO DEL LABORATORIO</small>
              <h2>{data.status.label === "activo" ? "Procesos en marcha" : "En espera"}</h2>
              <p className="muted small">{data.status.active_research} investigaciones · {data.status.running_experiments} experimentos en curso · {data.status.arena_running} pruebas de modelos</p>
            </div>
          </section>
          <div className="stat-row">
            <Stat label="Experimentos" value={String(data.counts.experiments)} /><Stat label="En curso" value={String(data.counts.running)} />
            <Stat label="Prototipos" value={String(data.counts.prototypes)} /><Stat label="Ideas pendientes" value={String(data.counts.ideas_pending)} />
            <Stat label="Descubrimientos (7 d)" value={String(data.counts.discoveries_7d)} /><Stat label="Tecnologías" value={String(data.counts.technologies)} />
            <Stat label="Biblioteca" value={String(data.counts.library)} />
          </div>
          <div className="mod-cols">
            <section className="dpanel grow">
              <header className="dpanel-head"><span>ACTIVIDAD EN TIEMPO REAL</span><span className="live-dot">{data.live.length ? "en vivo" : "sin procesos"}</span></header>
              {!data.live.length ? <p className="desk-empty">No hay procesos reales en ejecución ahora mismo.</p> : (
                <ul className="live-list">{data.live.map((x: Row) => (
                  <li key={`${x.type}${x.id}`}><b>{x.type === "research" ? "Investigación" : "Arena"}</b> {x.label}<small>{x.step ?? ""}</small>
                    {x.progress != null && <span className="progress-bar"><i style={{ width: `${x.progress}%` }} /></span>}</li>
                ))}</ul>
              )}
              <header className="dpanel-head"><span>DESCUBRIMIENTOS RECIENTES</span><button type="button" className="link-btn" onClick={() => go("radar")}>radar</button></header>
              {!data.recent_discoveries.length ? <p className="desk-empty">Aún no hay descubrimientos registrados.</p> : (
                <ul className="life-list compact">{data.recent_discoveries.map((d: Row) => (
                  <li key={d.id}><div className="life-item"><Tag kind={d.maturity}>{meta.maturity[d.maturity]}</Tag> {d.title} <small>{d.source} · {fmtDate(d.date)} · {REL[d.reliability]}</small></div></li>
                ))}</ul>
              )}
            </section>
            <section className="dpanel">
              <header className="dpanel-head"><span>TECNOLOGÍAS EMERGENTES</span></header>
              {!data.emerging.length ? <p className="desk-empty">Añade tecnologías al radar para seguirlas.</p> : (
                <ul className="bars">{data.emerging.map((t: Row) => <li key={t.id}><span>{t.name}</span><i style={{ width: `${Math.min(100, t.discoveries * 10)}%` }} /><b className="mono">{t.discoveries}</b></li>)}</ul>
              )}
              <header className="dpanel-head"><span>RESULTADOS RECIENTES</span></header>
              {!data.recent_results.length ? <p className="desk-empty">Sin experimentos cerrados.</p> : data.recent_results.map((e: Row) => (
                <p key={e.id} className="small">{e.name}: <b>{e.status}</b> {e.verdict ? `· ${{ supported: "hipótesis respaldada", refuted: "refutada", inconclusive: "no concluyente" }[e.verdict as string]}` : ""}</p>))}
              <header className="dpanel-head"><span>RECURSOS (7 DÍAS)</span></header>
              <div className="stat-row">
                <Stat label="Llamadas a modelos" value={String(data.resources_7d.model_calls)} />
                <Stat label="Latencia media" value={data.resources_7d.avg_latency_ms != null ? `${data.resources_7d.avg_latency_ms} ms` : "N/D"} />
                <Stat label="Coste" value={data.resources_7d.cost_usd != null ? `${data.resources_7d.cost_usd} $` : "N/D"} />
                <Stat label="Ejecuciones sandbox" value={String(data.resources_7d.sandbox_runs)} />
              </div>
              <header className="dpanel-head"><span>ACTIVIDAD DEL INNOVATION AGENT</span></header>
              {!data.agents.length ? <p className="desk-empty">Sin consultas esta semana.</p> : data.agents.map((a: Row, i: number) => <p key={i} className="small">{fmtDate(a.at)} · {a.request} <small>({a.agents.join(", ")})</small></p>)}
            </section>
          </div>
        </div>
      )}
    </State>
  );
}

/* ───────── Technology Radar ───────── */
export function Radar({ meta }: { meta: Meta }) {
  const techs = useLoad<Row[]>("/technologies", [], lab);
  const [cat, setCat] = useState("");
  const [mat, setMat] = useState("");
  const [tid, setTid] = useState<number | null>(null);
  const disc = useLoad<Row[]>(`/discoveries?${new URLSearchParams({ ...(cat ? { category: cat } : {}), ...(mat ? { maturity: mat } : {}), ...(tid ? { technology_id: String(tid) } : {}) })}`, [cat, mat, tid], lab);
  const tl = useLoad<Row>(tid ? `/technologies/${tid}/timeline` : null, [tid], lab);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [cmp, setCmp] = useState<number[]>([]);
  const [cmpRes, setCmpRes] = useState<Row | null>(null);
  const tech = techs.data?.find((t) => t.id === tid);
  const fetchPapers = () => {
    if (!q.trim()) return;
    setBusy(true); setMsg(null);
    lab.post("/discoveries/papers", { query: q, category: tech?.category ?? (cat || "ai"), technology_id: tid })
      .then((r) => { setMsg(`${r.added} publicaciones nuevas importadas de arXiv/OpenAlex${r.errors.length ? ` · ${r.errors.join("; ")}` : ""}`); disc.reload(); })
      .catch((e: Error) => setMsg(e.message)).finally(() => setBusy(false));
  };
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Technology Radar</h2><p className="muted small">Cada descubrimiento lleva fuente, fecha, descripción, madurez (investigación académica, prototipo, producto comercial o especulativa) y fiabilidad de la fuente.</p></div>
      <div className="radar-wrap">
        <RadarViz items={disc.data ?? []} meta={meta} />
        <div className="radar-side">
          <Crud api={lab} title="Tecnologías seguidas" path="/technologies" fields={[{ k: "name", label: "Tecnología", required: true }, { k: "category", label: "Categoría", type: "select", options: catOpts(meta), required: true },
            { k: "maturity", label: "Madurez", type: "select", options: Object.entries(meta.maturity), required: true }, { k: "entities", label: "Empresas y laboratorios que sigues", type: "tags" },
            { k: "watch", label: "Seguimiento automático", type: "checkbox" }, { k: "description", label: "Descripción", type: "textarea" }]} newDefaults={{ category: "ai", maturity: "academic", watch: true }}
            onChanged={techs.reload}
            render={(t) => <button type="button" className={`link-btn plain ${tid === t.id ? "on" : ""}`} onClick={() => setTid(tid === t.id ? null : t.id)}>{t.name} <small>{meta.categories[t.category]} · {meta.maturity[t.maturity]}{t.entities?.length ? ` · ${t.entities.join(", ")}` : ""}</small></button>}
            actions={(t) => <label className="check small"><input type="checkbox" checked={cmp.includes(t.id)} onChange={() => setCmp(cmp.includes(t.id) ? cmp.filter((x) => x !== t.id) : [...cmp, t.id])} /> comparar</label>} />
          {cmp.length >= 2 && <button type="button" className="btn ghost" onClick={() => lab.post("/technologies/compare", { technology_ids: cmp }).then(setCmpRes).catch((e: Error) => setMsg(e.message))}>Comparar {cmp.length} tecnologías</button>}
        </div>
      </div>
      {cmpRes && <section className="dpanel"><header className="dpanel-head"><span>COMPARATIVA (solo con descubrimientos registrados)</span></header>
        <table className="dtable compact"><thead><tr><th>Tecnología</th><th>Madurez</th><th>Evidencia</th><th>Ventajas</th><th>Limitaciones</th></tr></thead>
          <tbody>{(cmpRes.tabla ?? []).map((r: Row) => <tr key={r.tecnologia}><td>{r.tecnologia}</td><td>{r.madurez}</td><td className="small">{r.evidencia}</td><td className="small">{(r.ventajas ?? []).join("; ")}</td><td className="small">{(r.limitaciones ?? []).join("; ")}</td></tr>)}</tbody></table>
        <p className="small">{cmpRes.conclusion}</p>{!!cmpRes.datos_que_faltan?.length && <p className="mini-note">Faltan datos: {cmpRes.datos_que_faltan.join("; ")}</p>}</section>}
      {tech && tl.data && (
        <section className="dpanel"><header className="dpanel-head"><span>EVOLUCIÓN · {tech.name.toUpperCase()}</span></header>
          {!tl.data.by_year.length ? <p className="desk-empty">Sin descubrimientos para trazar su evolución.</p> : (
            <div className="evo">{tl.data.by_year.map((y: Row) => (
              <div key={y.year}><div className="evo-bar">{Object.keys(meta.maturity).map((m) => y[m] ? <i key={m} className={`t-${m}`} style={{ flex: y[m] }} title={`${meta.maturity[m]}: ${y[m]}`} /> : null)}</div><small>{y.year} · {y.total}</small></div>
            ))}</div>
          )}</section>
      )}
      <section className="dpanel">
        <header className="dpanel-head"><span>DESCUBRIMIENTOS {tech ? `· ${tech.name}` : ""}</span><button type="button" className="link-btn" onClick={() => setAdding(!adding)}>{adding ? "cerrar" : "+ registrar"}</button></header>
        <div className="filters">
          <select value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Categoría"><option value="">Todas las categorías</option>{catOpts(meta).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <select value={mat} onChange={(e) => setMat(e.target.value)} aria-label="Madurez"><option value="">Toda madurez</option>{Object.entries(meta.maturity).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar publicaciones (arXiv / OpenAlex)…" aria-label="Buscar publicaciones" />
          <button type="button" className="btn" disabled={busy || !q.trim()} onClick={fetchPapers}>{busy ? "Buscando…" : "Importar publicaciones reales"}</button>
        </div>
        {msg && <p className="small">{msg}</p>}
        {adding && <SchemaForm fields={[{ k: "title", label: "Título", required: true }, { k: "category", label: "Categoría", type: "select", options: catOpts(meta), required: true },
          { k: "maturity", label: "Estado de desarrollo", type: "select", options: Object.entries(meta.maturity), required: true },
          { k: "kind", label: "Tipo", type: "select", options: [["news", "Noticia"], ["paper", "Publicación"], ["patent", "Patente"], ["product", "Producto"], ["report", "Informe"], ["note", "Nota"]], required: true },
          { k: "source_url", label: "URL de la fuente", placeholder: "https://…" }, { k: "source_name", label: "Nombre de la fuente" }, { k: "published_on", label: "Fecha", type: "date" },
          { k: "description", label: "Descripción", type: "textarea" }]} initial={{ category: tech?.category ?? "ai", maturity: "academic", kind: "news" }}
          onSubmit={(v) => lab.post("/discoveries", { ...v, technology_id: tid }).then(() => { setAdding(false); disc.reload(); })} />}
        <State loading={disc.loading && !disc.data} error={disc.error} empty={disc.data && !disc.data.length ? "Sin descubrimientos con estos filtros." : false}>
          <ul className="disc-list">{disc.data?.map((d) => (
            <li key={d.id}>
              <div className="d-tags"><Tag kind={d.maturity}>{meta.maturity[d.maturity]}</Tag><Tag kind={`rel-${d.reliability}`}>{REL[d.reliability]}</Tag><small>{meta.categories[d.category]}</small></div>
              <b>{d.source_url ? <a href={d.source_url} target="_blank" rel="noreferrer noopener">{d.title}</a> : d.title}</b>
              <small>{d.source_name ?? ""} · {d.published_on ? fmtDate(d.published_on) : `registrado ${fmtDate(d.created_at)}`}{d.authors?.length ? ` · ${d.authors.slice(0, 3).join(", ")}` : ""} · origen: {d.origin}</small>
              {d.description && <p className="small">{d.description.slice(0, 400)}{d.description.length > 400 ? "…" : ""}</p>}
              <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar el descubrimiento?")) void lab.del(`/discoveries/${d.id}`).then(disc.reload); }}>Eliminar</button>
            </li>
          ))}</ul>
        </State>
      </section>
    </div>
  );
}

/** Radar circular: anillos = madurez, sectores = categorías. Solo dibuja descubrimientos registrados. */
function RadarViz({ items, meta }: { items: Row[]; meta: Meta }) {
  const cats = Object.keys(meta.categories);
  const rings = ["commercial", "prototype", "academic", "speculative"];
  const R = 150;
  const counts: Record<string, number> = {};
  const pts = items.slice(0, 160).map((d, i) => {
    const ci = Math.max(0, cats.indexOf(d.category));
    const ri = Math.max(0, rings.indexOf(d.maturity));
    const key = `${ci}-${ri}`;
    const k = (counts[key] = (counts[key] ?? 0) + 1);
    const a = ((ci + 0.15 + ((k * 0.17) % 0.7)) / cats.length) * Math.PI * 2 - Math.PI / 2;
    const r = ((ri + 0.25 + ((k * 0.13) % 0.5)) / rings.length) * R;
    return { x: R + Math.cos(a) * r, y: R + Math.sin(a) * r, d, i };
  });
  return (
    <figure className="radar-viz" aria-label="Radar de tecnologías: anillos por madurez y sectores por categoría">
      <svg viewBox={`0 0 ${R * 2} ${R * 2}`} role="img">
        {rings.map((m, i) => <circle key={m} cx={R} cy={R} r={((i + 1) / rings.length) * R} className="ring" />)}
        {cats.map((c, i) => { const a = (i / cats.length) * Math.PI * 2 - Math.PI / 2; return <line key={c} x1={R} y1={R} x2={R + Math.cos(a) * R} y2={R + Math.sin(a) * R} className="spoke" />; })}
        <g className="sweep"><path d={`M${R},${R} L${R},0 A${R},${R} 0 0,1 ${R + R * Math.sin(0.6)},${R - R * Math.cos(0.6)} Z`} /></g>
        {pts.map((p) => <circle key={p.d.id} cx={p.x} cy={p.y} r={3.2} className={`blip t-${p.d.maturity}`}><title>{p.d.title} · {meta.categories[p.d.category]} · {meta.maturity[p.d.maturity]}</title></circle>)}
      </svg>
      <figcaption>{rings.map((m) => <span key={m}><i className={`t-${m}`} /> {meta.maturity[m]}</span>)} · {items.length} descubrimientos</figcaption>
    </figure>
  );
}

/* ───────── Research Lab ───────── */
export function Research({ meta }: { meta: Meta }) {
  const [tag, setTag] = useState("");
  const list = useLoad<Row[]>(`/research${tag ? `?tag=${encodeURIComponent(tag)}` : ""}`, [tag], lab);
  const [sel, setSel] = useState<number | null>(null);
  const det = useLoad<Row>(sel ? `/research/${sel}` : null, [sel], lab);
  const [msg, setMsg] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  useEffect(() => {
    const running = list.data?.some((r) => ["queued", "running"].includes(r.research.status));
    if (running) { timer.current = window.setInterval(() => { list.reload(); if (sel) det.reload(); }, 4000); }
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [list.data, sel]); // eslint-disable-line react-hooks/exhaustive-deps
  const r = det.data?.research;
  const m = det.data?.meta;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Research Lab</h2><p className="muted small">El Research Engine de VISTAN divide el objetivo en preguntas, busca y lee fuentes, compara, detecta contradicciones, evalúa fiabilidad y redacta un informe con referencias. Además consulta publicaciones científicas reales (OpenAlex y arXiv). Nunca inventa artículos ni autores.</p></div>
      <section className="dpanel"><header className="dpanel-head"><span>NUEVA INVESTIGACIÓN</span></header>
        <SchemaForm fields={[{ k: "question", label: "Objetivo en lenguaje natural", type: "textarea", required: true, placeholder: "Investiga las nuevas arquitecturas de agentes autónomos…" },
          { k: "category", label: "Categoría", type: "select", options: catOpts(meta) }, { k: "tags", label: "Etiquetas", type: "tags" },
          { k: "papers", label: "Consultar publicaciones científicas (OpenAlex/arXiv)", type: "checkbox" }]} initial={{ papers: true }} submitLabel="Investigar"
          onSubmit={(v) => lab.post("/research", v).then((x) => { setSel(x.research_id); list.reload(); if (x.papers_error) setMsg(x.papers_error); })} /></section>
      {msg && <p className="small">{msg}</p>}
      <div className="mod-cols">
        <section className="dpanel">
          <header className="dpanel-head"><span>HISTORIAL</span><input className="cell-in" value={tag} onChange={(e) => setTag(e.target.value)} placeholder="etiqueta" aria-label="Filtrar por etiqueta" /></header>
          <State loading={list.loading && !list.data} error={list.error} empty={list.data && !list.data.length ? "Sin investigaciones del laboratorio." : false}>
            <ul className="life-list compact">{list.data?.map((x) => (
              <li key={x.research_id}><div className="life-item"><button type="button" className={`link-btn plain ${sel === x.research_id ? "on" : ""}`} onClick={() => setSel(x.research_id)}>{x.saved ? "★ " : ""}{x.research.question.slice(0, 110)}</button>
                <small> · {x.research.status === "done" ? `terminada · confianza ${x.research.confidence ?? "N/D"}` : x.research.status === "error" ? "error" : `${x.research.step_label ?? x.research.status} ${x.research.progress} %`} · {x.papers_count} publicaciones{x.tags.length ? ` · #${x.tags.join(" #")}` : ""}</small></div></li>
            ))}</ul>
          </State>
        </section>
        {r && (
          <section className="dpanel grow">
            <header className="dpanel-head"><span>{r.status === "done" ? "INFORME" : r.status.toUpperCase()}</span>
              <span className="row-actions">
                <button type="button" className="mini-btn ghost" onClick={() => lab.patch(`/research/${r.id}`, { saved: !m?.saved }).then(() => { det.reload(); list.reload(); })}>{m?.saved ? "★ Guardada" : "☆ Guardar"}</button>
                {["error", "interrupted"].includes(r.status) && <button type="button" className="mini-btn" onClick={() => lab.post(`/research/${r.id}/resume`).then(det.reload)}>Reanudar</button>}
                {r.status === "done" && <>
                  <button type="button" className="mini-btn ghost" onClick={() => lab.post(`/research/${r.id}/discoveries`, { category: m?.category ?? "ai" }).then((x) => setMsg(`${x.added} fuentes añadidas como descubrimientos`))}>Fuentes → radar</button>
                  <button type="button" className="mini-btn ghost" onClick={() => lab.post("/projects", { kind: "research", id: r.id }).then(() => setMsg("Proyecto de innovación creado"))}>→ Proyecto</button>
                  <button type="button" className="mini-btn ghost" onClick={() => lab.post("/remember", { text: (r.report?.summary ?? "").slice(0, 1500), ref: r.question.slice(0, 120) }).then(() => setMsg("Guardado en la memoria"))}>Recordar</button></>}
              </span></header>
            <p className="small"><b>{r.question}</b></p>
            {r.status !== "done" ? <p className="desk-empty">{r.error ?? `${r.step_label ?? "En cola"} · ${r.progress} %`}</p> : (
              <div className="ai-text">
                <Md text={r.report?.summary} />
                {!!r.subquestions?.length && <><h4>Preguntas investigadas</h4><ul>{r.subquestions.map((q: string) => <li key={q}>{q}</li>)}</ul></>}
                {!!r.report?.conclusions?.length && <><h4>Conclusiones</h4><ul>{r.report.conclusions.map((c: Row, i: number) => <li key={i}>{c.text} <small>(confianza {c.confidence}{c.sources?.length ? ` · fuentes ${c.sources.map((x: number) => `[${x}]`).join("")}` : ""})</small></li>)}</ul></>}
                {!!r.report?.contradictions?.length && <><h4>Contradicciones entre fuentes</h4><ul>{r.report.contradictions.map((c: Row, i: number) => <li key={i}>{c.text} <small>{c.sources?.map((x: number) => `[${x}]`).join("")}</small></li>)}</ul></>}
                {!!r.report?.unconfirmed?.length && <><h4>Sin confirmar / preguntas abiertas</h4><ul>{r.report.unconfirmed.map((c: string) => <li key={c}>{c}</li>)}</ul></>}
                <h4>Referencias ({r.sources.length}) · consultadas el {fmtDate(r.updated_at)}</h4>
                <ol>{r.sources.map((s: Row) => <li key={s.url} value={s.id}><a href={s.url} target="_blank" rel="noreferrer noopener">{s.title || s.url}</a> <small>{s.reliability ? `· fiabilidad ${s.reliability}` : ""}</small></li>)}</ol>
              </div>
            )}
            {!!m?.papers?.length && (
              <><header className="dpanel-head"><span>PUBLICACIONES CIENTÍFICAS CONSULTADAS</span></header>
                <ul className="disc-list">{m.papers.map((p: Row) => <li key={p.external_id}><b><a href={p.url} target="_blank" rel="noreferrer noopener">{p.title}</a></b>
                  <small>{p.source} · {p.published ?? "s/f"} · {p.authors.slice(0, 3).join(", ")}{p.citations != null ? ` · ${p.citations} citas` : ""} · {p.note}</small></li>)}</ul></>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

export const EXP_FIELDS = (meta: Meta): Field[] => [
  { k: "name", label: "Nombre", required: true }, { k: "status", label: "Estado", type: "select", options: meta.states.map((s) => [s, s] as [string, string]), required: true },
  { k: "category", label: "Categoría", type: "select", options: catOpts(meta) }, { k: "technology", label: "Tecnología utilizada" },
  { k: "objective", label: "Objetivo", type: "textarea" }, { k: "hypothesis", label: "Hipótesis", type: "textarea" }, { k: "description", label: "Descripción", type: "textarea" },
  { k: "resources", label: "Materiales o recursos", type: "textarea" }, { k: "variables", label: "Variables", type: "textarea" }, { k: "methodology", label: "Metodología", type: "textarea" },
  { k: "expected", label: "Resultados esperados", type: "textarea" }, { k: "observed", label: "Resultados observados", type: "textarea" }, { k: "evidence", label: "Evidencias", type: "textarea" },
  { k: "conclusion", label: "Conclusión", type: "textarea" },
  { k: "verdict", label: "Veredicto (exige resultados y evidencias)", type: "select", options: [["supported", "Hipótesis respaldada"], ["refuted", "Hipótesis refutada"], ["inconclusive", "No concluyente"]] },
  { k: "started_on", label: "Inicio", type: "date" }, { k: "finished_on", label: "Fin", type: "date" }, { k: "hours", label: "Horas dedicadas", type: "number" }, { k: "cost", label: "Coste (€)", type: "number" },
];
