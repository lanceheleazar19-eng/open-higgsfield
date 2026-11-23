import type { Dashboard as D } from "../api/types";
import { Icon } from "./Icon";
import { Empty, Panel } from "./Panel";
import {
  PRIORITY_LABEL, formatDateTime, formatDay, formatMoney, relativeTime, weekdayInitial,
} from "../lib/format";
import { formatDue } from "../lib/tasks";

/** Telemetría detallada: los paneles de datos del dashboard original. */
export function Telemetry({ data }: { data: D }) {
  const tz = data.greeting.timezone;
  return (
    <div className="grid">
      <TasksPanel t={data.tasks} tz={tz} />
      <EventsPanel e={data.events} tz={tz} />
      <FinancePanel f={data.finance} />
      <FitnessPanel f={data.fitness} />
      <ProjectsPanel p={data.projects} />
      <ActivityPanel a={data.activity} />
    </div>
  );
}

function TasksPanel({ t, tz }: { t: D["tasks"]; tz: string }) {
  return (
    <Panel title="Tareas pendientes" icon={<Icon name="tasks" />} aside={<span className="badge">{t.due_today} hoy</span>}>
      {t.items.length === 0 ? (
        <Empty>No hay tareas registradas. Añádelas en Tareas o dile a ATLAS «apúntame…».</Empty>
      ) : (
        <ul className="list">
          {t.items.map((i) => (
            <li key={i.id} className={i.overdue ? "is-overdue" : ""}>
              <span className={`prio prio-${i.priority}`}>{PRIORITY_LABEL[i.priority]}</span>
              <span className="list-main">
                <span className="list-title">{i.title}</span>
                <span className="list-meta mono">{i.due_at ? (i.overdue ? "Atrasada · " : "") + (i.all_day ? formatDue({ due_at: i.due_at, due_date: i.due_at.slice(0, 10), all_day: true }) : formatDateTime(i.due_at, tz)) : "Sin fecha"}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function EventsPanel({ e, tz }: { e: D["events"]; tz: string }) {
  return (
    <Panel title="Próximos eventos" icon={<Icon name="calendar" />}>
      {e.items.length === 0 ? (
        <Empty>Sin eventos próximos. El calendario se activa en la Fase 8.</Empty>
      ) : (
        <ul className="list">
          {e.items.map((i) => (
            <li key={i.id}>
              {i.in_progress ? <span className="badge live">Ahora</span> : null}
              <span className="list-main">
                <span className="list-title">{i.title}{i.location ? <span className="muted"> · {i.location}</span> : null}</span>
                <span className="list-meta mono">{formatDateTime(i.start_at, tz)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function FinancePanel({ f }: { f: D["finance"] }) {
  const max = Math.max(f.income_cents, f.expense_cents, 1);
  const catMax = Math.max(...f.top_expense_categories.map((c) => c.amount_cents), 1);
  return (
    <Panel title="Resumen financiero" icon={<Icon name="finance" />} aside={<span className="badge">{f.month}</span>}>
      {!f.has_data ? (
        <Empty>Aún no hay movimientos de dinero real registrados. Finanzas llega en la Fase 6.</Empty>
      ) : (
        <>
          <div className="fin-balance">
            <span className="muted">Saldo registrado</span>
            <span className={`mono big ${f.balance_cents < 0 ? "neg" : ""}`}>{formatMoney(f.balance_cents, f.currency)}</span>
          </div>
          <div className="bars" role="list">
            {[
              { k: "Ingresos", v: f.income_cents, c: "bar-in" },
              { k: "Gastos", v: f.expense_cents, c: "bar-out" },
            ].map((b) => (
              <div key={b.k} className="bar-row" role="listitem" title={`${b.k}: ${formatMoney(b.v, f.currency)}`}>
                <span className="bar-label">{b.k}</span>
                <span className="bar-track"><span className={`bar-fill ${b.c}`} style={{ width: `${(b.v / max) * 100}%` }} /></span>
                <span className="mono">{formatMoney(b.v, f.currency)}</span>
              </div>
            ))}
          </div>
          <p className="fin-net">Neto del mes: <strong className={`mono ${f.net_cents < 0 ? "neg" : "pos"}`}>{formatMoney(f.net_cents, f.currency)}</strong></p>
          {f.top_expense_categories.length > 0 && (
            <ul className="cats">
              {f.top_expense_categories.map((c) => (
                <li key={c.category} title={formatMoney(c.amount_cents, f.currency)}>
                  <span>{c.category}</span>
                  <span className="cat-track"><span style={{ width: `${(c.amount_cents / catMax) * 100}%` }} /></span>
                  <span className="mono muted">{formatMoney(c.amount_cents, f.currency)}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Panel>
  );
}

function FitnessPanel({ f }: { f: D["fitness"] }) {
  const max = Math.max(...f.days.map((d) => d.sessions), 1);
  return (
    <Panel title="Actividad física" icon={<Icon name="gym" />} aside={<span className="badge">{f.minutes_7d} min / 7d</span>}>
      <div className="week" aria-label="Sesiones de los últimos 7 días">
        {f.days.map((d) => (
          <div key={d.date} className="week-col" title={`${formatDay(d.date)}: ${d.sessions} ${d.sessions === 1 ? "sesión" : "sesiones"}`}>
            <span className="week-bar"><span style={{ height: `${(d.sessions / max) * 100}%` }} className={d.sessions ? "on" : ""} /></span>
            <span className="week-day">{weekdayInitial(d.date)}</span>
          </div>
        ))}
      </div>
      {f.last_session ? (
        <p className="muted small">Último entreno: <strong>{f.last_session.routine ?? "Sesión"}</strong> · {formatDay(f.last_session.date)}{f.last_session.duration_min ? ` · ${f.last_session.duration_min} min` : ""}</p>
      ) : (
        <Empty>Sin entrenamientos registrados. El módulo de gimnasio llega en la Fase 5.</Empty>
      )}
    </Panel>
  );
}

function ProjectsPanel({ p }: { p: D["projects"] }) {
  return (
    <Panel title="Proyectos activos" icon={<Icon name="projects" />}>
      {p.items.length === 0 ? (
        <Empty>No hay proyectos activos. Proyectos y negocios llega en la Fase 7.</Empty>
      ) : (
        <ul className="list">
          {p.items.map((i) => (
            <li key={i.id}>
              <span className="list-main">
                <span className="list-title">{i.name}{i.description ? <span className="muted"> · {i.description}</span> : null}</span>
                <span className="list-meta mono">{i.open_tasks} {i.open_tasks === 1 ? "tarea" : "tareas"}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function ActivityPanel({ a }: { a: D["activity"] }) {
  return (
    <Panel title="Actividad reciente" icon={<Icon name="reports" />}>
      {a.items.length === 0 ? (
        <Empty>Todavía no hay actividad. Todo lo que hagas en ATLAS quedará registrado aquí.</Empty>
      ) : (
        <ol className="timeline">
          {a.items.map((i) => (
            <li key={i.id}>
              <span className="tl-dot" aria-hidden="true" />
              <span className="list-title">{i.summary}</span>
              <span className="list-meta">{relativeTime(i.created_at)}</span>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
