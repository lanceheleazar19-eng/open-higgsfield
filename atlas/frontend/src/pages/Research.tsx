import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { v4, type ResearchItem } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { Empty, Panel } from "../components/Panel";
import { relativeTime } from "../lib/format";

const STATUS: Record<string, string> = { queued: "En cola", running: "Investigando", done: "Terminada", error: "Error", interrupted: "Interrumpida" };

export function Research() {
  const [params, setParams] = useSearchParams();
  const list = useAsync(v4.research, 4000);
  const projects = useAsync(v4.projects);
  const [q, setQ] = useState("");
  const [pid, setPid] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const sel = Number(params.get("id")) || null;

  async function start(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const r = await v4.startResearch(q.trim(), pid ? Number(pid) : null);
      setQ(""); setParams({ id: String(r.id) }); await list.reload();
    } catch (x) { setErr((x as Error).message); }
  }

  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Research Engine</p>
        <h1><Icon name="research" size={26} /> Investigación</h1>
        <p className="lead">VISTAN divide la pregunta, busca en varias fuentes públicas, las lee, compara lo que dicen y te entrega un informe con fuentes, fecha de consulta y nivel de confianza. También desde el chat: «investiga…».</p>
      </header>
      <div className="grid grid-tasks">
        <div className="stack">
          <Panel title="Nueva investigación">
            <form className="form" onSubmit={start}>
              <label><span>¿Qué quieres saber?</span><textarea rows={3} value={q} maxLength={1000} onChange={(e) => setQ(e.target.value)}
                placeholder="Ej.: ¿Qué dice la evidencia sobre la creatina en adolescentes?" /></label>
              <label><span>Proyecto (opcional)</span>
                <select value={pid} onChange={(e) => setPid(e.target.value)}>
                  <option value="">Ninguno</option>{(projects.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
              <div className="form-actions"><button className="btn" disabled={q.trim().length < 4}>Investigar</button>{err && <span className="neg small">{err}</span>}</div>
              <p className="muted small">Sale a internet: consulta DuckDuckGo y Wikipedia y lee las páginas públicas encontradas. Tus datos personales no se envían.</p>
            </form>
          </Panel>
          <Panel title="Historial">
            {!list.data?.length ? <Empty>Aún no hay investigaciones.</Empty> : (
              <ul className="r-list">
                {list.data.map((r) => (
                  <li key={r.id} className={sel === r.id ? "on" : ""}>
                    <button type="button" onClick={() => setParams({ id: String(r.id) })}>
                      <span className="r-q">{r.question}</span>
                      <span className="muted small">{STATUS[r.status] ?? r.status}{r.status === "running" && r.step_label ? ` · ${r.step_label} (${r.progress} %)` : ""}
                        {r.confidence ? ` · confianza ${r.confidence}` : ""} · {relativeTime(r.created_at)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
        {sel ? <Report id={sel} onChange={() => void list.reload()} onDelete={() => { setParams({}); void list.reload(); }} /> : <Panel title="Informe"><Empty>Elige o inicia una investigación.</Empty></Panel>}
      </div>
    </div>
  );
}

function Report({ id, onChange, onDelete }: { id: number; onChange: () => void; onDelete: () => void }) {
  const r = useAsync(() => v4.researchOne(id));
  const [saved, setSaved] = useState<string | null>(null);
  const d: ResearchItem | null = r.data && r.data.id === id ? r.data : null;
  useEffect(() => { void r.reload(); setSaved(null); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!d || !["running", "queued"].includes(d.status)) return;
    const t = setInterval(() => void r.reload(), 2500);
    return () => clearInterval(t);
  }, [d?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!d) return <Panel title="Informe"><Empty>Cargando…</Empty></Panel>;
  const rep = d.report;
  const src = (ids: number[]) => ids.map((i) => <a key={i} href={`#src-${i}`} className="cite">[{i}]</a>);
  return (
    <div className="stack">
      <Panel title={d.question}>
        <p className="small">
          <span className="badge">{STATUS[d.status] ?? d.status}</span>{" "}
          {d.confidence && <span className={`badge conf-${d.confidence}`}>Confianza {d.confidence}</span>}{" "}
          {d.model && <span className="muted">· modelo {d.model}</span>}
        </p>
        {["running", "queued"].includes(d.status) && (
          <div className="goal-bar" role="progressbar" aria-label="Progreso" aria-valuenow={d.progress} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${d.progress}%` }} /></div>
        )}
        {d.step_label && d.status === "running" && <p className="muted small">{d.step_label}…</p>}
        {d.error && <p className="neg small">{d.error}</p>}
        {(d.subquestions?.length ?? 0) > 0 && <p className="small muted">Subpreguntas: {d.subquestions!.join(" · ")}</p>}
        {rep && (
          <>
            <p>{rep.summary}</p>
            {rep.conclusions.length > 0 && <><h3 className="h-sm">Conclusiones</h3>
              <ul className="steps">{rep.conclusions.map((c, i) => <li key={i}>{c.text} {src(c.sources)} <span className="muted small">({c.confidence})</span></li>)}</ul></>}
            {rep.contradictions.length > 0 && <><h3 className="h-sm">Contradicciones entre fuentes</h3>
              <ul className="steps">{rep.contradictions.map((c, i) => <li key={i}>{c.text} {src(c.sources)}</li>)}</ul></>}
            {rep.unconfirmed.length > 0 && <><h3 className="h-sm">Sin confirmar</h3><ul className="steps">{rep.unconfirmed.map((u, i) => <li key={i}>{u}</li>)}</ul></>}
          </>
        )}
        <div className="form-actions">
          {["error", "interrupted"].includes(d.status) && <button className="btn" onClick={async () => { await v4.resumeResearch(id); await r.reload(); onChange(); }}>Reanudar</button>}
          {d.status === "done" && <button className="btn" onClick={async () => { const x = await v4.saveResearch(id); setSaved(x.created ? "Guardada en tu memoria." : "Ya estaba en tu memoria."); }}>Guardar en memoria</button>}
          <button className="mini-btn danger" onClick={async () => { if (confirm("¿Borrar esta investigación?")) { await v4.deleteResearch(id); onDelete(); } }}>Borrar</button>
          {saved && <span className="pos small">{saved}</span>}
        </div>
      </Panel>
      {(d.sources?.length ?? 0) > 0 && (
        <Panel title={`Fuentes (${d.sources!.length})`}>
          {d.search_errors && d.search_errors.length > 0 && <p className="t-warn small">Buscadores con problemas: {d.search_errors.join("; ")}</p>}
          <ol className="sources">
            {d.sources!.map((s) => (
              <li key={s.id} id={`src-${s.id}`}>
                <a href={s.url} target="_blank" rel="noreferrer noopener">[{s.id}] {s.title}</a>
                <span className="muted small"> · {s.domain} · fiabilidad {s.reliability} · {s.engine}{s.accessed_at ? ` · consultada ${s.accessed_at.replace("T", " ")}` : ""}
                  {s.published ? ` · publicada ${s.published}` : ""}{s.read === false ? " · no se pudo leer" : ""}{s.flagged ? " · contenía instrucciones ocultas (ignoradas)" : ""}</span>
                {s.claims && s.claims.length > 0 && <ul className="claims">{s.claims.map((c, i) => <li key={i}>{c}</li>)}</ul>}
                {(!s.claims || s.claims.length === 0) && s.snippet && <p className="small muted">{s.snippet}</p>}
              </li>
            ))}
          </ol>
        </Panel>
      )}
    </div>
  );
}
