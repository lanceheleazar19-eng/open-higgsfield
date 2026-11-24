import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { v4, type AgentRunItem, type Level } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { Empty, Panel } from "../components/Panel";
import { relativeTime } from "../lib/format";

type Tab = "agents" | "runs" | "approvals" | "try";
export const LEVEL_CLASS: Record<Level, string> = { READ: "lvl-read", WRITE: "lvl-write", EXECUTE: "lvl-exec", ADMIN: "lvl-admin" };

export function Trace({ run }: { run: AgentRunItem }) {
  return (
    <ol className="trace">
      {run.steps.map((s, i) => (
        <li key={i} className={s.ok ? "" : "neg"}>
          <span className={`lvl ${LEVEL_CLASS[s.level]}`}>{s.level}</span>
          <span className="mono small">{s.agent} · {s.tool}</span>
          <span className="muted small">{s.shared ? "compartido" : `${s.ms} ms`} · {s.summary}</span>
        </li>
      ))}
    </ol>
  );
}

export function Agents() {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "agents";
  const cat = useAsync(v4.agents);
  const runs = useAsync(v4.agentRuns, 15000);
  const approvals = useAsync(() => v4.approvals("pending"), 10000);
  const [text, setText] = useState("");
  const [pick, setPick] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AgentRunItem | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function tryRun(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { setResult(await v4.runAgents(text, pick.length ? pick : undefined)); await runs.reload(); }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  const pend = approvals.data?.length ?? 0;

  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Sistema multiagente</p>
        <h1><Icon name="agents" size={26} /> Agentes</h1>
        <p className="lead">{cat.data?.core.role ?? "VISTAN CORE coordina agentes especializados."} Cada paso queda registrado con su nivel de permiso.</p>
      </header>
      <div className="tabs" role="tablist" aria-label="Secciones de agentes">
        {([["agents", "Agentes"], ["runs", "Ejecuciones"], ["approvals", `Aprobaciones${pend ? ` (${pend})` : ""}`], ["try", "Probar"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setParams({ tab: k })}>{l}</button>
        ))}
      </div>

      {tab === "agents" && (
        <div className="agent-grid">
          {(cat.data?.agents ?? []).map((a) => (
            <Panel key={a.id} title={a.name} aside={<span className="muted small mono">{a.runs} ejec.</span>}>
              <p className="small">{a.role}</p>
              {a.limits && <p className="muted small">Límites: {a.limits}</p>}
              <ul className="tool-list">
                {[...a.tools, ...a.actions].map((t) => (
                  <li key={t.name}><span className={`lvl ${LEVEL_CLASS[t.level]}`}>{t.level}</span> <span className="small">{t.description}</span></li>
                ))}
              </ul>
              {a.last && <p className="muted small">Última vez: {relativeTime(a.last)}</p>}
            </Panel>
          ))}
        </div>
      )}

      {tab === "runs" && (
        <Panel title="Ejecuciones recientes">
          {!runs.data?.length ? <Empty>Aún no hay ejecuciones. Pregunta algo en el chat o en «Probar».</Empty> : (
            <ul className="run-list">
              {runs.data.map((r) => (
                <li key={r.id}>
                  <details>
                    <summary><span className="r-q">{r.request}</span>
                      <span className="muted small"> · {r.agent_names.join(", ") || "conversación general"} · {r.status}{r.duration_ms ? ` · ${(r.duration_ms / 1000).toFixed(1)} s` : ""}{r.model ? ` · ${r.model}` : ""} · {relativeTime(r.created_at)}</span>
                    </summary>
                    <Trace run={r} />
                    {r.result && <p className="small run-result">{r.result}</p>}
                  </details>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}

      {tab === "approvals" && (
        <Panel title="Acciones que esperan tu autorización">
          {!approvals.data?.length ? <Empty>No hay nada pendiente. Las acciones de nivel EXECUTE y ADMIN siempre te preguntan antes.</Empty> : (
            <ul className="run-list">
              {approvals.data.map((a) => (
                <li key={a.id} className="approval">
                  <span className={`lvl ${LEVEL_CLASS[a.level]}`}>{a.level}</span> <strong>{a.summary}</strong>
                  <span className="muted small"> · {relativeTime(a.created_at)}</span>
                  <div className="form-actions">
                    <button className="btn" onClick={async () => { await v4.decide(a.id, true); await approvals.reload(); }}>Autorizar</button>
                    <button className="mini-btn danger" onClick={async () => { await v4.decide(a.id, false); await approvals.reload(); }}>Rechazar</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}

      {tab === "try" && (
        <div className="grid grid-tasks">
          <Panel title="Pregunta a los agentes">
            <form className="form" onSubmit={tryRun}>
              <label><span>Petición</span><textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Ej.: ¿Puedo permitirme suplementos este mes y me ayudarían a mi objetivo de volumen?" /></label>
              <div className="set-chips" role="group" aria-label="Forzar agentes (opcional)">
                {(cat.data?.agents ?? []).map((a) => (
                  <button key={a.id} type="button" className={`chip ${pick.includes(a.id) ? "on" : ""}`} aria-pressed={pick.includes(a.id)}
                    onClick={() => setPick((p) => p.includes(a.id) ? p.filter((x) => x !== a.id) : [...p, a.id].slice(-3))}>{a.name.replace(" Agent", "")}</button>
                ))}
              </div>
              <p className="muted small">Si no eliges ninguno, VISTAN CORE decide quién interviene (máx. 3, colaborando entre sí).</p>
              <div className="form-actions"><button className="btn" disabled={busy || text.trim().length < 2}>{busy ? "Trabajando…" : "Ejecutar"}</button>{err && <span className="neg small">{err}</span>}</div>
            </form>
          </Panel>
          <Panel title="Resultado">
            {!result ? <Empty>Aquí verás qué agentes han intervenido, qué herramientas han usado y la respuesta.</Empty> : (
              <>
                <p className="small muted">{result.agent_names.join(" + ") || "Sin agentes específicos"}{result.model ? ` · ${result.model}` : ""}</p>
                <Trace run={result} />
                <p className="run-result">{result.result}</p>
              </>
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}
