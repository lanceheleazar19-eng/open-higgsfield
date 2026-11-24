import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { v4, type ProjectDetail } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { Empty, Panel } from "../components/Panel";
import { relativeTime } from "../lib/format";

const STATUS: Record<string, string> = { active: "Activo", paused: "Pausado", done: "Terminado", archived: "Archivado" };

export function Projects() {
  const [params, setParams] = useSearchParams();
  const list = useAsync(v4.projects);
  const [f, setF] = useState({ name: "", description: "" });
  const sel = Number(params.get("id")) || null;
  async function create(e: FormEvent) {
    e.preventDefault();
    const p = await v4.saveProject({ name: f.name, description: f.description || null });
    setF({ name: "", description: "" }); await list.reload(); setParams({ id: String(p.id) });
  }
  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Workspaces</p>
        <h1><Icon name="projects" size={26} /> Proyectos</h1>
        <p className="lead">Cada proyecto tiene su propio espacio: tareas, notas, documentos, investigaciones, entidades e historial. ATLAS usa ese contexto sin mezclarlo con lo demás.</p>
      </header>
      <div className="grid grid-tasks">
        <div className="stack">
          <Panel title="Nuevo proyecto">
            <form className="form" onSubmit={create}>
              <label><span>Nombre</span><input value={f.name} maxLength={200} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Tienda online, canal, estudios…" /></label>
              <label><span>Descripción</span><textarea rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></label>
              <div className="form-actions"><button className="btn" disabled={f.name.trim().length < 2}>Crear</button></div>
            </form>
          </Panel>
          <Panel title="Proyectos">
            {!list.data?.length ? <Empty>Sin proyectos todavía.</Empty> : (
              <ul className="r-list">
                {list.data.map((p) => (
                  <li key={p.id} className={sel === p.id ? "on" : ""}>
                    <button type="button" onClick={() => setParams({ id: String(p.id) })}>
                      <span className="r-q">{p.name}</span>
                      <span className="muted small">{STATUS[p.status]} · {p.tasks_done}/{p.tasks_total} tareas{p.tasks_overdue ? ` · ${p.tasks_overdue} atrasadas` : ""} · {p.notes} notas · {p.documents} docs</span>
                      {p.progress !== null && <span className="goal-bar thin"><span style={{ width: `${p.progress}%` }} /></span>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
        {sel ? <Workspace id={sel} onChange={() => void list.reload()} onDeleted={() => { setParams({}); void list.reload(); }} />
          : <Panel title="Workspace"><Empty>Elige o crea un proyecto.</Empty></Panel>}
      </div>
    </div>
  );
}

type WTab = "tasks" | "notes" | "docs" | "research" | "report" | "history";

function Workspace({ id, onChange, onDeleted }: { id: number; onChange: () => void; onDeleted: () => void }) {
  const p = useAsync(() => v4.project(id));
  const [tab, setTab] = useState<WTab>("tasks");
  const [task, setTask] = useState("");
  const [note, setNote] = useState({ content: "", kind: "note" });
  const [report, setReport] = useState<string | null>(null);
  const [edit, setEdit] = useState<{ name: string; description: string; status: string } | null>(null);
  const d: ProjectDetail | null = p.data && p.data.id === id ? p.data : null;
  useEffect(() => { void p.reload(); setReport(null); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!d) return <Panel title="Workspace"><Empty>Cargando…</Empty></Panel>;
  const reload = async () => { await p.reload(); onChange(); };
  return (
    <div className="stack">
      <Panel title={d.name} aside={<span className="badge">{STATUS[d.status]}</span>}>
        {edit ? (
          <form className="form" onSubmit={async (e) => { e.preventDefault(); await v4.saveProject(edit, id); setEdit(null); await reload(); }}>
            <label><span>Nombre</span><input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></label>
            <label><span>Descripción</span><textarea rows={3} value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></label>
            <label><span>Estado</span><select value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>
              {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            <div className="form-actions"><button className="btn">Guardar</button><button type="button" className="mini-btn ghost" onClick={() => setEdit(null)}>Cancelar</button></div>
          </form>
        ) : (
          <>
            {d.description && <p className="small">{d.description}</p>}
            <dl className="kv">
              <div><dt>Avance</dt><dd className="mono">{d.progress === null ? "sin tareas" : `${d.progress} %`} ({d.tasks_done}/{d.tasks_total})</dd></div>
              <div><dt>Atrasadas</dt><dd className={`mono ${d.tasks_overdue ? "neg" : ""}`}>{d.tasks_overdue}</dd></div>
            </dl>
            <div className="form-actions">
              <button className="mini-btn" onClick={() => setEdit({ name: d.name, description: d.description ?? "", status: d.status })}>Editar</button>
              <Link className="mini-btn ghost" to={`/knowledge`}>Grafo y documentos</Link>
              <button className="mini-btn danger" onClick={async () => { if (confirm(`¿Borrar «${d.name}»? Sus notas se borran; las tareas y documentos se conservan sin proyecto.`)) { await v4.deleteProject(id); onDeleted(); } }}>Borrar</button>
            </div>
          </>
        )}
      </Panel>
      <div className="tabs" role="tablist" aria-label="Secciones del proyecto">
        {([["tasks", `Tareas (${d.tasks.length})`], ["notes", `Notas (${d.notes.length})`], ["docs", `Documentos (${d.documents.length})`],
          ["research", `Investigaciones (${d.research.length})`], ["report", "Informe"], ["history", "Historial"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "tasks" && (
        <Panel title="Tareas del proyecto">
          <form className="form-row" onSubmit={async (e) => { e.preventDefault(); await v4.projectTask(id, task); setTask(""); await reload(); }}>
            <label><span>Nueva tarea</span><input value={task} onChange={(e) => setTask(e.target.value)} /></label>
            <button className="btn" disabled={task.trim().length < 2}>Añadir</button>
          </form>
          {!d.tasks.length ? <Empty>Sin tareas: define el siguiente paso.</Empty> : (
            <ul className="r-list">{d.tasks.map((t) => <li key={t.id}><span className={t.status === "done" ? "muted" : ""}>{t.status === "done" ? "✓ " : "○ "}{t.title}</span></li>)}</ul>
          )}
        </Panel>
      )}
      {tab === "notes" && (
        <Panel title="Notas, ideas y decisiones">
          <form className="form" onSubmit={async (e) => { e.preventDefault(); await v4.projectNote(id, note.content, note.kind); setNote({ ...note, content: "" }); await reload(); }}>
            <div className="form-row">
              <label><span>Nota</span><input value={note.content} onChange={(e) => setNote({ ...note, content: e.target.value })} /></label>
              <label><span>Tipo</span><select value={note.kind} onChange={(e) => setNote({ ...note, kind: e.target.value })}>
                <option value="note">Nota / idea</option><option value="decision">Decisión</option><option value="goal">Objetivo</option><option value="fact">Dato</option></select></label>
            </div>
            <div className="form-actions"><button className="btn" disabled={note.content.trim().length < 2}>Guardar</button></div>
          </form>
          {!d.notes.length ? <Empty>Sin notas.</Empty> : <ul className="r-list">{d.notes.map((m) => <li key={m.id}><span>{m.content}</span> <span className="muted small">· {m.kind}</span></li>)}</ul>}
        </Panel>
      )}
      {tab === "docs" && (
        <Panel title="Documentos">
          {!d.documents.length ? <Empty>Importa documentos en Conocimiento y asígnalos a este proyecto.</Empty>
            : <ul className="r-list">{d.documents.map((x) => <li key={x.id}>{x.title} <span className="muted small">· {x.kind} · {x.chunks} fragmentos</span></li>)}</ul>}
          <Link to="/knowledge" className="mini-btn">Importar documentos</Link>
        </Panel>
      )}
      {tab === "research" && (
        <Panel title="Investigaciones">
          {!d.research.length ? <Empty>Sin investigaciones en este proyecto.</Empty>
            : <ul className="r-list">{d.research.map((r) => <li key={r.id}><Link to={`/research?id=${r.id}`}>{r.question}</Link> <span className="muted small">· {r.status}</span></li>)}</ul>}
          <Link to="/research" className="mini-btn">Nueva investigación</Link>
        </Panel>
      )}
      {tab === "report" && (
        <Panel title="Análisis del proyecto">
          <button className="btn" onClick={async () => setReport((await v4.projectAnalysis(id)).report)}>Analizar ahora</button>
          {report && <pre className="report">{report}</pre>}
        </Panel>
      )}
      {tab === "history" && (
        <Panel title="Historial">
          {!d.history.length ? <Empty>Sin actividad registrada que mencione este proyecto.</Empty>
            : <ul className="r-list">{d.history.map((h, i) => <li key={i}><span className="small">{h.summary}</span> <span className="muted small">· {relativeTime(h.created_at)}</span></li>)}</ul>}
        </Panel>
      )}
    </div>
  );
}
