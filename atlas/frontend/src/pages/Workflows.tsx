import { useState } from "react";
import { v4, type WfStep, type WorkflowItem } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { Empty, Panel } from "../components/Panel";
import { relativeTime } from "../lib/format";
import { LEVEL_CLASS } from "./Agents";

const DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
const RUN_STATUS: Record<string, string> = { running: "En curso", done: "Completado", error: "Error", awaiting_approval: "Esperando tu autorización" };

function scheduleLabel(s: string | null): string {
  if (!s) return "Manual";
  const p = s.split(" ");
  return p[0] === "daily" ? `Cada día a las ${p[1]}` : `Cada ${DAYS[Number(p[1])]} a las ${p[2]}`;
}

export function Workflows() {
  const data = useAsync(v4.workflows);
  const runs = useAsync(v4.wfRuns, 8000);
  const projects = useAsync(v4.projects);
  const [editing, setEditing] = useState<WorkflowItem | null>(null);
  const [params, setParams] = useState<Record<number, Record<string, string>>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const types = data.data?.step_types ?? {};

  async function run(w: WorkflowItem) {
    setMsg(null);
    try {
      const r = await v4.runWorkflow(w.id, params[w.id] ?? {});
      setMsg(`${w.name}: ${RUN_STATUS[r.status] ?? r.status}`); await runs.reload(); await data.reload();
    } catch (e) { setMsg((e as Error).message); }
  }
  const blank: WorkflowItem = { id: 0, key: null, name: "", description: "", steps: [{ type: "agent", params: { prompt: "" } }], schedule: null, enabled: true, builtin: false, last_run_at: null, needs: [] };

  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Workflow Engine</p>
        <h1><Icon name="workflows" size={26} /> Automatizaciones</h1>
        <p className="lead">Secuencias que ATLAS ejecuta solo o cuando las lanzas. Los pasos de nivel EXECUTE (internet, copias) te piden autorización. Funcionan mientras ATLAS está encendido.</p>
      </header>
      {msg && <p role="status" className="callout">{msg}</p>}
      <div className="grid grid-tasks">
        <div className="stack">
          {(data.data?.workflows ?? []).map((w) => (
            <Panel key={w.id} title={w.name} aside={<span className={`badge ${w.enabled ? "live" : ""}`}>{w.enabled ? scheduleLabel(w.schedule) : "Desactivado"}</span>}>
              <p className="small">{w.description}</p>
              <ol className="wf-steps">{w.steps.map((s, i) => (
                <li key={i}><span className={`lvl ${LEVEL_CLASS[types[s.type]?.level ?? "READ"]}`}>{types[s.type]?.level}</span> {types[s.type]?.label ?? s.type}
                  {s.params && Object.values(s.params).some(Boolean) && <span className="muted small"> · {Object.values(s.params).filter(Boolean).join(", ").slice(0, 60)}</span>}</li>
              ))}</ol>
              {w.needs.includes("project_id") && (
                <label className="field"><span>Proyecto</span>
                  <select value={params[w.id]?.project_id ?? ""} onChange={(e) => setParams({ ...params, [w.id]: { ...params[w.id], project_id: e.target.value } })}>
                    <option value="">Elige…</option>{(projects.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select></label>
              )}
              {w.needs.includes("question") && (
                <label className="field"><span>Pregunta</span>
                  <input value={params[w.id]?.question ?? ""} onChange={(e) => setParams({ ...params, [w.id]: { ...params[w.id], question: e.target.value } })} /></label>
              )}
              <div className="form-actions">
                <button className="btn" onClick={() => void run(w)} disabled={w.needs.some((n) => !params[w.id]?.[n])}>Ejecutar ahora</button>
                <button className="mini-btn ghost" onClick={() => setEditing(w)}>{w.builtin ? "Horario" : "Editar"}</button>
                {w.last_run_at && <span className="muted small">Última: {relativeTime(w.last_run_at)}</span>}
              </div>
            </Panel>
          ))}
          <button className="btn" onClick={() => setEditing(blank)}><Icon name="plus" size={14} /> Nuevo workflow</button>
        </div>
        <div className="stack">
          {editing && <Editor w={editing} types={types} onClose={() => setEditing(null)} onSaved={async () => { setEditing(null); await data.reload(); }} />}
          <Panel title="Ejecuciones">
            {!runs.data?.length ? <Empty>Aún no se ha ejecutado ningún workflow.</Empty> : (
              <ul className="run-list">
                {runs.data.map((r) => (
                  <li key={r.id}>
                    <details>
                      <summary><strong>{r.workflow}</strong> <span className="muted small">· {RUN_STATUS[r.status] ?? r.status} · {r.trigger === "schedule" ? "programado" : "manual"} · {relativeTime(r.started_at)}</span></summary>
                      <ol className="trace">{r.log.map((l, i) => (
                        <li key={i} className={l.ok === false ? "neg" : ""}><span className={`lvl ${LEVEL_CLASS[l.level]}`}>{l.level}</span> <span className="mono small">{l.type}</span>
                          <span className="small pre">{l.output}</span></li>
                      ))}</ol>
                    </details>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Editor({ w, types, onClose, onSaved }: { w: WorkflowItem; types: Record<string, { level: string; label: string; params: string[] }>; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(w.name);
  const [desc, setDesc] = useState(w.description ?? "");
  const [steps, setSteps] = useState<WfStep[]>(w.steps);
  const [kind, setKind] = useState(w.schedule ? w.schedule.split(" ")[0] : "manual");
  const [day, setDay] = useState(w.schedule?.startsWith("weekly") ? w.schedule.split(" ")[1] : "6");
  const [time, setTime] = useState(w.schedule ? w.schedule.split(" ").slice(-1)[0] : "08:00");
  const [enabled, setEnabled] = useState(w.enabled);
  const [err, setErr] = useState<string | null>(null);
  const schedule = kind === "manual" ? null : kind === "daily" ? `daily ${time}` : `weekly ${day} ${time}`;
  const move = (i: number, d: number) => { const s = [...steps]; const [x] = s.splice(i, 1); s.splice(i + d, 0, x); setSteps(s); };
  const PARAM_ES: Record<string, string> = { prompt: "Instrucción", agents: "Agentes (opcional, separados por coma)", question: "Pregunta", title: "Título", content: "Contenido (vacío = resultado anterior)", project_id: "ID de proyecto (o al ejecutar)" };
  async function save() {
    setErr(null);
    try { await v4.saveWorkflow({ name, description: desc, steps, schedule, enabled }, w.id || undefined); onSaved(); }
    catch (e) { setErr((e as Error).message); }
  }
  return (
    <Panel title={w.id ? `Editar: ${w.name}` : "Nuevo workflow"}>
      <div className="form">
        {!w.builtin && <>
          <label><span>Nombre</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label><span>Descripción</span><input value={desc} onChange={(e) => setDesc(e.target.value)} /></label>
          <ol className="wf-editor">
            {steps.map((s, i) => (
              <li key={i}>
                <div className="form-row">
                  <label><span>Paso {i + 1}</span>
                    <select value={s.type} onChange={(e) => setSteps(steps.map((x, j) => j === i ? { type: e.target.value, params: {} } : x))}>
                      {Object.entries(types).map(([k, t]) => <option key={k} value={k}>{t.label} ({t.level})</option>)}
                    </select></label>
                  {(types[s.type]?.params ?? []).map((p) => (
                    <label key={p}><span>{PARAM_ES[p] ?? p}</span>
                      <input value={String(s.params?.[p] ?? "")} onChange={(e) => setSteps(steps.map((x, j) => j === i ? { ...x, params: { ...x.params, [p]: e.target.value } } : x))} /></label>
                  ))}
                </div>
                <div className="row-actions">
                  <button type="button" className="mini-btn ghost" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Subir paso">↑</button>
                  <button type="button" className="mini-btn ghost" disabled={i === steps.length - 1} onClick={() => move(i, 1)} aria-label="Bajar paso">↓</button>
                  <button type="button" className="mini-btn danger" disabled={steps.length === 1} onClick={() => setSteps(steps.filter((_, j) => j !== i))} aria-label="Quitar paso">×</button>
                </div>
              </li>
            ))}
          </ol>
          <button type="button" className="mini-btn" onClick={() => setSteps([...steps, { type: "notify", params: { title: name || "ATLAS" } }])}>+ Añadir paso</button>
        </>}
        <div className="form-row">
          <label><span>Cuándo</span><select value={kind} onChange={(e) => setKind(e.target.value)}><option value="manual">Solo manual</option><option value="daily">Cada día</option><option value="weekly">Cada semana</option></select></label>
          {kind === "weekly" && <label><span>Día</span><select value={day} onChange={(e) => setDay(e.target.value)}>{DAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}</select></label>}
          {kind !== "manual" && <label><span>Hora</span><input type="time" value={time} onChange={(e) => setTime(e.target.value)} /></label>}
        </div>
        <label className="check"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Activado</label>
        <div className="form-actions"><button className="btn" onClick={() => void save()} disabled={!name.trim() || !steps.length}>Guardar</button>
          <button className="mini-btn ghost" onClick={onClose}>Cancelar</button>
          {w.id > 0 && !w.builtin && <button className="mini-btn danger" onClick={async () => { if (confirm("¿Borrar este workflow?")) { await v4.deleteWorkflow(w.id); onSaved(); } }}>Borrar</button>}
          {err && <span className="neg small">{err}</span>}</div>
      </div>
    </Panel>
  );
}
