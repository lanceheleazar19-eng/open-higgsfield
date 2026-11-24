import { Link } from "react-router-dom";
import { v4 } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { Empty, Panel } from "../components/Panel";
import { relativeTime } from "../lib/format";
import { Trace } from "./Agents";

const PRIVACY: Record<string, string> = { local_only: "Solo local", local_first: "Local primero", best_quality: "Mejor calidad" };

export function CommandCenter() {
  const cc = useAsync(v4.commandCenter, 10000);
  const d = cc.data;
  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Estado en tiempo real</p>
        <h1><Icon name="command" size={26} /> Command Center</h1>
        <p className="lead">Todo lo que ves aquí sale del backend en este momento: núcleo, modelos, agentes, procesos, memoria y actividad.</p>
      </header>
      {!d ? <Empty>Cargando…</Empty> : (
        <>
          <div className="cc-kpis">
            <div className="kpi"><span className="kpi-l">Núcleo</span><span className={`kpi-v ${d.core.ai_reachable ? "pos" : "t-warn"}`}>{d.core.ai_reachable ? "IA conectada" : "Modo local"}</span><span className="kpi-s">{d.core.model ?? d.core.note ?? "—"}</span></div>
            <div className="kpi"><span className="kpi-l">Privacidad</span><span className="kpi-v">{PRIVACY[d.core.privacy]}</span><span className="kpi-s"><Link to="/settings#modelos">Model Router</Link></span></div>
            <div className="kpi"><span className="kpi-l">Llamadas a modelos · 24 h</span><span className="kpi-v mono">{d.model_calls_24h.count}</span><span className="kpi-s">{d.model_calls_24h.avg_ms} ms de media · {d.model_calls_24h.errors} errores</span></div>
            <div className="kpi"><span className="kpi-l">Agentes activos · 24 h</span><span className="kpi-v mono">{d.agents_active_24h.length}</span><span className="kpi-s">{d.agents_active_24h.join(", ") || "ninguno"}</span></div>
            <div className="kpi"><span className="kpi-l">Memoria</span><span className="kpi-v mono">{Object.entries(d.memory).filter(([k]) => k !== "messages").reduce((a, [, v]) => a + (typeof v === "number" ? v : 0), 0)}</span><span className="kpi-s">{d.memory.documents ?? 0} documentos</span></div>
            <div className="kpi"><span className="kpi-l">Pendiente de ti</span><span className="kpi-v mono">{d.approvals_pending}</span><span className="kpi-s"><Link to="/agents?tab=approvals">aprobaciones</Link> · {d.pending_tasks} tareas</span></div>
          </div>
          <div className="grid grid-2">
            <Panel title="Procesos en ejecución">
              {!d.processes.length ? <Empty>No hay nada ejecutándose ahora.</Empty> : (
                <ul className="r-list">{d.processes.map((p) => (
                  <li key={`${p.kind}${p.id}`}><span className="badge live">{p.kind === "research" ? "Investigación" : "Workflow"}</span> {p.label} <span className="muted small">· {p.step ?? p.status}</span></li>
                ))}</ul>
              )}
              <h3 className="h-sm">Programados</h3>
              {!d.workflows_scheduled.length ? <p className="muted small">Ninguno.</p> : <ul className="r-list">{d.workflows_scheduled.map((w) => <li key={w.id} className="small">{w.name} · <span className="mono">{w.schedule}</span></li>)}</ul>}
            </Panel>
            <Panel title="Inteligencia proactiva">
              {!d.insights.length ? <Empty>Nada que señalar con tus datos actuales.</Empty> : (
                <ul className="insights">{d.insights.map((i) => (
                  <li key={i.id} className={`ins-${i.level}`}>
                    <Link to={i.link}><strong>{i.title}</strong></Link>
                    <p className="small">{i.what} <span className="muted">{i.why}</span></p>
                    <p className="small">→ {i.recommendation}</p>
                    <button className="mini-btn ghost" onClick={async () => { await v4.dismissInsight(i.id); await cc.reload(); }}>Descartar</button>
                  </li>
                ))}</ul>
              )}
            </Panel>
            <Panel title="Últimas ejecuciones de agentes">
              {!d.recent_agent_runs.length ? <Empty>Sin ejecuciones todavía.</Empty> : d.recent_agent_runs.map((r) => (
                <details key={r.id} className="cc-run"><summary className="small">{r.request.slice(0, 80)} <span className="muted">· {r.agent_names.join(", ") || "general"} · {relativeTime(r.created_at)}</span></summary><Trace run={r} /></details>
              ))}
            </Panel>
            <Panel title="Actividad reciente">
              <ul className="r-list">{d.activity.map((a, i) => <li key={i} className="small"><span className="badge">{a.module}</span> {a.summary} <span className="muted">· {relativeTime(a.created_at)}</span></li>)}</ul>
              <h3 className="h-sm">Conversaciones</h3>
              <ul className="r-list">{d.recent_conversations.map((c) => <li key={c.id} className="small"><Link to="/ai">{c.title}</Link> <span className="muted">· {relativeTime(c.updated_at)}</span></li>)}</ul>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
