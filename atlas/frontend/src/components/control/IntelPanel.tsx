import { useState } from "react";
import { useAsync } from "../../api/useAsync";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { Dashboard } from "../../api/types";
import { formatMoney, relativeTime } from "../../lib/format";
import { PACE_LABEL, formatDue } from "../../lib/tasks";

const LEVEL_LABEL = { critical: "Crítico", warning: "Aviso", info: "Info" } as const;
const MODULE_ROUTE: Record<string, string> = { tasks: "/tasks", calendar: "/calendar", finance: "/finance", gym: "/gym", goals: "/tasks?tab=goals" };
const PRIO = { critical: "Crítica", high: "Alta", medium: "Media", low: "Baja" } as const;

function Card({ title, link, children }: { title: string; link?: { to: string; label: string }; children: React.ReactNode }) {
  return (
    <section className="icard">
      <header><h3>{title}</h3>{link && <Link to={link.to}>{link.label} →</Link>}</header>
      {children}
    </section>
  );
}

function FinanceChart({ series }: { series: { date: string; net_cents: number }[] }) {
  if (series.length < 2) return null;
  const W = 300, H = 70, vals = series.map((p) => p.net_cents);
  const min = Math.min(...vals, 0), max = Math.max(...vals, 1);
  const x = (i: number) => (i * W) / (series.length - 1);
  const y = (v: number) => H - 4 - ((v - min) / (max - min || 1)) * (H - 8);
  const line = series.map((p, i) => `${x(i)},${y(p.net_cents)}`).join(" ");
  return (
    <svg className="fin-chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="Evolución del neto del mes">
      <defs><linearGradient id="fg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ff2e42" stopOpacity=".45" /><stop offset="1" stopColor="#ff2e42" stopOpacity="0" /></linearGradient></defs>
      <polygon points={`0,${H} ${line} ${W},${H}`} fill="url(#fg)" />
      <polyline points={line} fill="none" stroke="#ff3b4f" strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Columna derecha: tareas, eventos, objetivos, finanzas y actividad (todo con datos reales). */
export function IntelPanel({ data, onChanged }: { data: Dashboard | null; onChanged: () => void }) {
  const [done, setDone] = useState<Set<number>>(new Set());
  const mail = useAsync(api.importantMail, 300_000);
  if (!data) return <aside className="intel" aria-label="Información en tiempo real" />;
  const tz = data.greeting.timezone;
  const f = data.finance;

  async function complete(id: number) {
    setDone((s) => new Set(s).add(id));
    try { await api.completeTask(id); onChanged(); } catch { setDone((s) => { const n = new Set(s); n.delete(id); return n; }); }
  }

  return (
    <aside className="intel" aria-label="Información en tiempo real">
      {data.alerts.length > 0 && (
        <Card title={`Alertas (${data.alerts.length})`}>
          <ul className="alerts">
            {data.alerts.slice(0, 3).map((a, i) => (
              <li key={i} className={`alert alert-${a.level}`}>
                <span className="alert-level">{LEVEL_LABEL[a.level]}</span>
                <Link to={MODULE_ROUTE[a.module] ?? "/"}>{a.text}</Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {mail.data && mail.data.items.length > 0 && (
        <Card title={`Correos importantes (${mail.data.items.length})`}>
          <ul className="imails">
            {mail.data.items.slice(0, 4).map((m) => (
              <li key={m.id}>
                <span><strong>{m.subject}</strong><span className="mem-meta">{m.sender.replace(/<.*>/, "").trim() || m.sender}{m.reason ? ` · ${m.reason}` : ""}</span></span>
                <button className="mini-btn ghost" aria-label={`Marcar como visto: ${m.subject}`} onClick={async () => { await api.dismissMail(m.id); await mail.reload(); }}>✓</button>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Card title="Tareas pendientes" link={{ to: "/tasks", label: "Ver todas" }}>
        {data.tasks.items.length === 0 ? <p className="hud-note">No hay tareas registradas.</p> : (
          <ul className="itasks">
            {data.tasks.items.slice(0, 4).map((t) => (
              <li key={t.id} className={done.has(t.id) ? "is-done" : ""}>
                <button className="tick" aria-label={`Marcar como hecha: ${t.title}`} onClick={() => void complete(t.id)} disabled={done.has(t.id)}>
                  {done.has(t.id) ? "✓" : ""}
                </button>
                <span className="itask-title">{t.title}</span>
                <span className={`itask-meta p-${t.priority}`}>
                  {t.overdue ? "Atrasada" : t.due_at ? formatDue({ due_at: t.due_at, due_date: t.due_at.slice(0, 10), all_day: !!t.all_day }, tz) : "Sin fecha"} · {PRIO[t.priority]}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Próximos eventos" link={{ to: "/calendar", label: "Ver calendario" }}>
        {data.events.items.length === 0 ? <p className="hud-note">Sin eventos próximos.</p> : (
          <ul className="ievents">
            {data.events.items.slice(0, 3).map((e) => (
              <li key={e.id}>
                <i className={e.in_progress ? "live" : ""} aria-hidden="true" />
                <span><strong>{e.title}</strong><span className="mem-meta">{e.in_progress ? "Ahora" : formatDue({ due_at: e.start_at, due_date: null, all_day: false }, tz)}{e.location ? ` · ${e.location}` : ""}</span></span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {data.goals && data.goals.items.length > 0 && (
        <Card title="Objetivos" link={{ to: "/tasks?tab=goals", label: "Ver" }}>
          <ul className="hud-goals">
            {data.goals.items.slice(0, 3).map((g) => (
              <li key={g.id}>
                <span className="hud-goal-title">{g.title}</span>
                <span className={`hud-goal-pace pace-${g.pace}`}>{g.progress === null ? "—" : `${Math.round(g.progress * 100)} %`} · {PACE_LABEL[g.pace]}</span>
                <span className="mini-bar"><span style={{ width: `${Math.round((g.progress ?? 0) * 100)}%` }} /></span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Card title="Resumen financiero" link={{ to: "/finance", label: "Este mes" }}>
        {!f.has_data ? <p className="hud-note">Aún no hay movimientos registrados.</p> : (
          <>
            <p className={`ifin-net mono ${f.net_cents < 0 ? "neg" : ""}`}>{f.net_cents >= 0 ? "+" : ""}{formatMoney(f.net_cents, f.currency)}</p>
            <FinanceChart series={f.series ?? []} />
            <div className="ifin-row">
              <span><i className="dot dot-on" /> Ingresos <strong className="mono">{formatMoney(f.income_cents, f.currency)}</strong></span>
              <span><i className="dot dot-off" /> Gastos <strong className="mono">{formatMoney(f.expense_cents, f.currency)}</strong></span>
            </div>
          </>
        )}
      </Card>
      <Card title="Actividad reciente" link={{ to: "/#telemetria", label: "Ver más" }}>
        {data.activity.items.length === 0 ? <p className="hud-note">Sin actividad todavía.</p> : (
          <ul className="hud-list">
            {data.activity.items.slice(0, 4).map((a) => (
              <li key={a.id}><span className="pdot p-activity" /><span className="hud-list-title">{a.summary}</span><span className="hud-time">{relativeTime(a.created_at)}</span></li>
            ))}
          </ul>
        )}
      </Card>
    </aside>
  );
}
