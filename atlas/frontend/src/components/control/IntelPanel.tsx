import { Link } from "react-router-dom";
import type { Dashboard } from "../../api/types";
import { PRIORITY_LABEL, relativeTime } from "../../lib/format";
import { PACE_LABEL } from "../../lib/tasks";
import { Clock } from "../Clock";

const LEVEL_LABEL = { critical: "Crítico", warning: "Aviso", info: "Info" } as const;
const MODULE_ROUTE: Record<string, string> = { tasks: "/tasks", calendar: "/calendar", finance: "/finance", gym: "/gym", goals: "/tasks?tab=goals" };

/** Lateral derecho: información en tiempo real detectada en tus datos. */
export function IntelPanel({ data }: { data: Dashboard | null }) {
  return (
    <aside className="hud hud-right" aria-label="Información en tiempo real">
      <section>
        <h3>Tiempo real</h3>
        <Clock timeZone={data?.greeting.timezone} />
      </section>
      <section>
        <h3>Alertas detectadas {data && data.alerts.length > 0 && <span className="count">{data.alerts.length}</span>}</h3>
        {!data ? <p className="hud-note">—</p> : data.alerts.length === 0 ? (
          <p className="hud-note">Sin alertas. Todo en orden.</p>
        ) : (
          <ul className="alerts">
            {data.alerts.map((a, i) => (
              <li key={i} className={`alert alert-${a.level}`}>
                <span className="alert-level">{LEVEL_LABEL[a.level]}</span>
                <Link to={MODULE_ROUTE[a.module] ?? "/"}>{a.text}</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3>Objetivos {data?.goals && <span className="count">{data.goals.items.length}</span>}</h3>
        {data?.goals && data.goals.items.length > 0 ? (
          <ul className="hud-goals">
            {data.goals.items.slice(0, 4).map((g) => (
              <li key={g.id}>
                <Link to="/tasks?tab=goals" className="hud-goal-title">{g.title}</Link>
                <span className={`hud-goal-pace pace-${g.pace}`}>{g.progress === null ? "—" : `${Math.round(g.progress * 100)} %`} · {PACE_LABEL[g.pace]}</span>
                <span className="mini-bar"><span style={{ width: `${Math.round((g.progress ?? 0) * 100)}%` }} /></span>
              </li>
            ))}
          </ul>
        ) : <p className="hud-note"><Link to="/tasks?tab=goals">Define tus objetivos</Link> y ATLAS medirá si vas a llegar.</p>}
      </section>
      <section>
        <h3>Tareas pendientes {data && <span className="count">{data.tasks.pending}</span>}</h3>
        {data && data.tasks.items.length > 0 ? (
          <ul className="hud-list">
            {data.tasks.items.slice(0, 4).map((t) => (
              <li key={t.id} className={t.overdue ? "is-overdue" : ""}>
                <span className={`pdot p-${t.priority}`} title={`Prioridad ${PRIORITY_LABEL[t.priority]}`} />
                <span className="hud-list-title">{t.title}</span>
              </li>
            ))}
          </ul>
        ) : <p className="hud-note">No hay tareas registradas.</p>}
      </section>
      <section>
        <h3>Actividad reciente</h3>
        {data && data.activity.items.length > 0 ? (
          <ul className="hud-list">
            {data.activity.items.slice(0, 4).map((a) => (
              <li key={a.id}>
                <span className="pdot p-activity" />
                <span className="hud-list-title">{a.summary}</span>
                <span className="hud-time">{relativeTime(a.created_at)}</span>
              </li>
            ))}
          </ul>
        ) : <p className="hud-note">Sin actividad todavía.</p>}
      </section>
    </aside>
  );
}
