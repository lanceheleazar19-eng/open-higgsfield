import { useCallback, useMemo, useRef, useState, type FormEvent } from "react";
import { v4, type DocHit, type GraphNode } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { KIND_COLOR, KnowledgeGraph } from "../components/KnowledgeGraph";
import { Empty, Panel } from "../components/Panel";
import { formatBytes } from "../lib/bytes";

type Tab = "docs" | "graph" | "search";
const KIND_ES: Record<string, string> = { pdf: "PDF", docx: "Word", txt: "Texto", md: "Markdown", csv: "CSV", xlsx: "Excel", image: "Imagen", url: "Web", note: "Nota" };

export function Knowledge() {
  const [tab, setTab] = useState<Tab>("docs");
  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Second Brain</p>
        <h1><Icon name="knowledge" size={26} /> Conocimiento</h1>
        <p className="lead">Tus documentos, notas y enlaces, indexados en tu ordenador para que VISTAN los consulte y cite. Lo que viene de tus documentos se distingue siempre de la información externa.</p>
      </header>
      <div className="tabs" role="tablist" aria-label="Secciones de conocimiento">
        {([["docs", "Documentos"], ["graph", "Grafo"], ["search", "Buscar"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "docs" && <Docs />}
      {tab === "graph" && <Graph />}
      {tab === "search" && <Search />}
    </div>
  );
}

function Docs() {
  const docs = useAsync(() => v4.documents());
  const projects = useAsync(v4.projects);
  const [project, setProject] = useState("");
  const [msg, setMsg] = useState<{ tone: "pos" | "neg"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState("");
  const [note, setNote] = useState({ title: "", text: "" });
  const [open, setOpen] = useState<number | null>(null);
  const preview = useAsync(() => (open ? v4.document(open) : Promise.resolve(null)));
  const fileRef = useRef<HTMLInputElement>(null);
  const mdRef = useRef<HTMLInputElement>(null);
  const pid = project ? Number(project) : null;

  const run = async (fn: () => Promise<string>) => {
    setBusy(true); setMsg(null);
    try { setMsg({ tone: "pos", text: await fn() }); await docs.reload(); }
    catch (e) { setMsg({ tone: "neg", text: (e as Error).message }); }
    finally { setBusy(false); }
  };
  const upload = (files: FileList | null) => files?.length && run(async () => {
    const r = await v4.uploadDocs(Array.from(files), pid);
    const bad = r.filter((d) => d.status === "error");
    return `${r.length - bad.length} importado(s).` + (bad.length ? ` Con error: ${bad.map((d) => `${d.title} (${d.error})`).join("; ")}` : "");
  });

  return (
    <div className="grid grid-tasks">
      <div className="stack">
        <Panel title="Importar">
          <div className="form">
            <label><span>Proyecto (opcional)</span>
              <select value={project} onChange={(e) => setProject(e.target.value)}>
                <option value="">Sin proyecto (global)</option>
                {(projects.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <div className="dropzone" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); void upload(e.dataTransfer.files); }}>
              <Icon name="upload" size={22} />
              <p>Arrastra archivos aquí o</p>
              <button type="button" className="btn" disabled={busy} onClick={() => fileRef.current?.click()}>{busy ? "Procesando…" : "Elegir archivos"}</button>
              <p className="muted small">PDF, Word, TXT, Markdown, CSV, Excel e imágenes (las imágenes necesitan un modelo de visión local).</p>
              <input ref={fileRef} type="file" multiple hidden aria-label="Archivos para importar"
                accept=".pdf,.docx,.txt,.md,.markdown,.csv,.xlsx,.xlsm,.png,.jpg,.jpeg,.webp,.heic"
                onChange={(e) => { void upload(e.target.files); e.target.value = ""; }} />
            </div>
          </div>
          <form className="form" onSubmit={(e: FormEvent) => { e.preventDefault(); void run(async () => { const d = await v4.addUrl(url, pid); setUrl(""); return `Web importada: ${d.title}`; }); }}>
            <label><span>Enlace web</span><input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" inputMode="url" /></label>
            <div className="form-actions"><button className="btn" disabled={busy || url.length < 8}>Importar web</button></div>
          </form>
          <form className="form" onSubmit={(e: FormEvent) => { e.preventDefault(); void run(async () => { await v4.addNote(note.title, note.text, pid); setNote({ title: "", text: "" }); return "Nota guardada."; }); }}>
            <label><span>Título de la nota</span><input value={note.title} maxLength={300} onChange={(e) => setNote({ ...note, title: e.target.value })} /></label>
            <label><span>Nota</span><textarea rows={4} value={note.text} onChange={(e) => setNote({ ...note, text: e.target.value })} /></label>
            <div className="form-actions"><button className="btn" disabled={busy || !note.title.trim() || !note.text.trim()}>Guardar nota</button></div>
          </form>
          {msg && <p role="status" className={`small ${msg.tone}`}>{msg.text}</p>}
        </Panel>
        <Panel title="Markdown (Obsidian)">
          <p className="muted small">Exporta todo tu segundo cerebro como notas .md con [[enlaces]], o importa notas: cada [[enlace]] crea una relación real en el grafo.</p>
          <div className="form-actions">
            <a className="btn" href="/api/knowledge/markdown/export" download>Exportar .zip</a>
            <button type="button" className="mini-btn" onClick={() => mdRef.current?.click()}>Importar .md / .zip</button>
            <input ref={mdRef} type="file" multiple hidden accept=".md,.markdown,.zip" aria-label="Notas Markdown"
              onChange={(e) => { const f = e.target.files; e.target.value = ""; if (f?.length) void run(async () => { const r = await v4.importMarkdown(Array.from(f)); return `${r.documents} notas y ${r.links} enlaces importados.`; }); }} />
          </div>
        </Panel>
      </div>
      <Panel title={`Documentos (${docs.data?.length ?? 0})`}>
        {!docs.data?.length ? <Empty>Todavía no has importado documentos.</Empty> : (
          <ul className="doc-list">
            {docs.data.map((d) => (
              <li key={d.id} className={open === d.id ? "on" : ""}>
                <button type="button" className="doc-main" onClick={() => { setOpen(open === d.id ? null : d.id); void preview.reload(); }}>
                  <span className="badge">{KIND_ES[d.kind] ?? d.kind}</span>
                  <span className="doc-title">{d.title}</span>
                  <span className="muted small mono">{d.status === "error" ? <span className="neg">error</span> : `${d.chunks} frag. · ${formatBytes(d.size_bytes)}${d.embedded ? " · semántico" : ""}`}</span>
                </button>
                <button type="button" className="mini-btn danger" aria-label={`Borrar ${d.title}`}
                  onClick={async () => { if (confirm(`¿Borrar «${d.title}» de la base de conocimiento?`)) { await v4.deleteDoc(d.id); await docs.reload(); } }}>×</button>
                {open === d.id && (
                  <div className="doc-preview">
                    {d.error && <p className="neg small">{d.error}</p>}
                    {d.url && <p className="small"><a href={d.url} target="_blank" rel="noreferrer noopener">{d.url}</a></p>}
                    <pre>{preview.data?.id === d.id ? preview.data.preview : "Cargando…"}</pre>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function Graph() {
  const projects = useAsync(v4.projects);
  const [pid, setPid] = useState<number | null>(null);
  const graph = useAsync(() => v4.graph(pid));
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [sel, setSel] = useState<GraphNode | null>(null);
  const [target, setTarget] = useState("");
  const [label, setLabel] = useState("relacionado");
  const [ent, setEnt] = useState({ name: "", kind: "person" });
  const [err, setErr] = useState<string | null>(null);
  const g = graph.data;
  const kinds = useMemo(() => [...new Set((g?.nodes ?? []).map((n) => n.kind))], [g]);
  const onSelect = useCallback((n: GraphNode | null) => setSel(n), []);
  const links = g && sel ? g.edges.filter((e) => e.source === sel.id || e.target === sel.id) : [];
  const name = (id: string) => g?.nodes.find((n) => n.id === id)?.label ?? id;
  const reload = async () => { setErr(null); await graph.reload(); };

  return (
    <div className="kg-layout">
      <div className="stack">
        <div className="filters">
          <label className="field"><span>Vista</span>
            <select value={pid ?? ""} onChange={(e) => { setPid(e.target.value ? Number(e.target.value) : null); setSel(null); setTimeout(() => void graph.reload(), 0); }}>
              <option value="">Global</option>
              {(projects.data ?? []).map((p) => <option key={p.id} value={p.id}>Proyecto: {p.name}</option>)}
            </select>
          </label>
          <label className="field"><span>Buscar nodo</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nombre…" /></label>
        </div>
        <div className="set-chips" role="group" aria-label="Filtrar por tipo">
          {kinds.map((k) => (
            <button key={k} type="button" className={`chip ${hidden.has(k) ? "" : "on"}`} aria-pressed={!hidden.has(k)}
              onClick={() => setHidden((h) => { const n = new Set(h); if (n.has(k)) n.delete(k); else n.add(k); return n; })}>
              <i className="kg-dot" style={{ background: KIND_COLOR[k] }} />{g?.types[k] ?? k}
            </button>
          ))}
        </div>
        {!g ? <Empty>Cargando…</Empty> : g.nodes.length === 0
          ? <Empty>El grafo se llena con tus recuerdos, proyectos, tareas, documentos e investigaciones. Aún no hay nada que mostrar.</Empty>
          : <KnowledgeGraph data={g} hidden={hidden} query={query} selected={sel?.id ?? null} onSelect={onSelect} />}
        <p className="muted small">{g ? `${g.nodes.length} nodos · ${g.edges.length} relaciones reales (línea discontinua: mención de una entidad en el texto).` : ""} Rueda: zoom · arrastrar: mover.</p>
      </div>
      <div className="stack">
        <Panel title={sel ? sel.label : "Nodo"}>
          {!sel ? <Empty>Selecciona un nodo para ver sus conexiones.</Empty> : (
            <>
              <p className="small"><span className="badge">{g?.types[sel.kind] ?? sel.kind}</span> {sel.degree} conexión(es)</p>
              <ul className="kg-links">
                {links.map((e, i) => {
                  const other = e.source === sel.id ? e.target : e.source;
                  return (
                    <li key={i}>
                      <button type="button" className="link-btn" onClick={() => setSel(g!.nodes.find((n) => n.id === other) ?? null)}>
                        {e.source === sel.id ? "→" : "←"} {e.label}: {name(other)}
                      </button>
                      {e.origin.startsWith("manual:") && (
                        <button type="button" className="mini-btn danger" aria-label="Quitar relación"
                          onClick={async () => { await v4.deleteRelation(Number(e.origin.split(":")[1])); await reload(); }}>×</button>
                      )}
                    </li>
                  );
                })}
              </ul>
              <form className="form" onSubmit={async (e) => {
                e.preventDefault();
                try { await v4.addRelation(sel.id, target, label); setTarget(""); await reload(); } catch (x) { setErr((x as Error).message); }
              }}>
                <label><span>Relacionar con</span>
                  <select value={target} onChange={(e) => setTarget(e.target.value)}>
                    <option value="">Elige un nodo…</option>
                    {(g?.nodes ?? []).filter((n) => n.id !== sel.id).sort((a, b) => a.label.localeCompare(b.label)).map((n) => (
                      <option key={n.id} value={n.id}>{g?.types[n.kind] ?? n.kind}: {n.label}</option>
                    ))}
                  </select>
                </label>
                <label><span>Tipo de relación</span><input value={label} maxLength={64} onChange={(e) => setLabel(e.target.value)} /></label>
                <div className="form-actions"><button className="btn" disabled={!target || !label.trim()}>Crear relación</button>
                  {sel.id.startsWith("entity:") && <button type="button" className="mini-btn danger" onClick={async () => {
                    if (confirm(`¿Borrar la entidad «${sel.label}»?`)) { await v4.deleteEntity(Number(sel.id.split(":")[1])); setSel(null); await reload(); }
                  }}>Borrar entidad</button>}
                </div>
              </form>
            </>
          )}
          {err && <p className="neg small">{err}</p>}
        </Panel>
        <Panel title="Nueva entidad">
          <form className="form" onSubmit={async (e) => { e.preventDefault(); await v4.addEntity(ent.name, ent.kind, pid); setEnt({ ...ent, name: "" }); await reload(); }}>
            <div className="form-row">
              <label><span>Nombre</span><input value={ent.name} maxLength={200} onChange={(e) => setEnt({ ...ent, name: e.target.value })} placeholder="Persona, empresa, idea…" /></label>
              <label><span>Tipo</span>
                <select value={ent.kind} onChange={(e) => setEnt({ ...ent, kind: e.target.value })}>
                  <option value="person">Persona</option><option value="org">Organización</option><option value="place">Lugar</option>
                  <option value="concept">Concepto</option><option value="idea">Idea</option>
                </select>
              </label>
            </div>
            <p className="muted small">Si su nombre aparece en tus recuerdos, tareas o documentos, VISTAN las conecta solas.</p>
            <div className="form-actions"><button className="btn" disabled={!ent.name.trim()}>Añadir</button></div>
          </form>
        </Panel>
      </div>
    </div>
  );
}

function Search() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<DocHit[] | null>(null);
  return (
    <Panel title="Buscar en tus documentos">
      <form className="form" onSubmit={async (e) => { e.preventDefault(); setHits(await v4.searchDocs(q)); }}>
        <label><span>Pregunta o palabras clave</span><input value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <div className="form-actions"><button className="btn" disabled={q.trim().length < 2}>Buscar</button></div>
      </form>
      {hits && (hits.length === 0 ? <Empty>Tus documentos no contienen nada que coincida.</Empty> : (
        <ol className="hits">
          {hits.map((h, i) => (
            <li key={i}><strong>{h.title}</strong> <span className="muted small">· fragmento {h.chunk + 1}</span>
              {h.flagged && <span className="t-warn small"> · contenía instrucciones sospechosas (omitidas)</span>}
              <p className="small">{h.text.slice(0, 500)}{h.text.length > 500 ? "…" : ""}</p></li>
          ))}
        </ol>
      ))}
    </Panel>
  );
}
