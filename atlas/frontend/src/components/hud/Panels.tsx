import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { Dashboard } from "../../api/types";
import type { TelemetryData } from "../../api/telemetry";
import { useAsync } from "../../api/useAsync";
import { v4, type CommandCenter } from "../../api/v4";
import { formatMoney, relativeTime } from "../../lib/format";
import { PACE_LABEL, formatDue } from "../../lib/tasks";
import type { NodeInfo } from "../core/AtlasCore";
import type { CoreState } from "../core/scene";
import { NODE_DEFS } from "../core/nodes";
import { Icon } from "../Icon";
import { EventConsole, Led, Meter, ND, Spark, WidgetColumn, bytes, ms, pct, uptime, type WidgetDef } from "./Hud";

const STATE_ES: Record<CoreState, string> = { idle: "EN ESPERA", listening: "ESCUCHANDO", thinking: "RAZONANDO", researching: "INVESTIGANDO",
  executing: "EJECUTANDO", speaking: "HABLANDO", responding: "RESPONDIENDO", error: "ERROR" };
const PRIVACY: Record<string, string> = { local_only: "solo local", local_first: "local primero", best_quality: "mejor calidad" };

const Row = ({ k, v, tone }: { k: string; v: ReactNode; tone?: string }) => <div className="kvr"><dt>{k}</dt><dd className={tone}>{v}</dd></div>;
const MODULE_ROUTE: Record<string, string> = { tasks: "/tasks", calendar: "/calendar", finance: "/finance", gym: "/gym", goals: "/tasks",
  nutrition: "/nutrition", projects: "/projects", research: "/research" };
const Empty = ({ children }: { children: ReactNode }) => <p className="hud-empty">{children}</p>;

/* ===================== PANEL IZQUIERDO · SYSTEM TELEMETRY ===================== */
export function HudLeft({ t, hist, error, state }: { t: TelemetryData | null; hist: { cpu: number[]; ram: number[] }; error: boolean; state: CoreState }) {
  const s = t?.system ?? {};
  const widgets: WidgetDef[] = [
    { id: "core", title: "Núcleo", render: () => (
      <dl className="kv-dense">
        <Row k="Estado" v={<><Led state={error ? "error" : state === "error" ? "error" : "ok"} /> {error ? "SIN CONEXIÓN" : STATE_ES[state]}</>} />
        <Row k="Modelo activo" v={t ? (t.core.model ?? "modo local") : ND} />
        <Row k="Proveedor" v={t?.core.provider ?? ND} />
        <Row k="Privacidad" v={t ? PRIVACY[t.core.privacy] : ND} />
        <Row k="Uptime servidor" v={uptime(s.uptime_s)} />
      </dl>) },
    { id: "latency", title: "Latencia IA", render: () => (
      <>
        <div className="big-num"><span>{ms(t?.latency.last_ms)}</span><small>última respuesta</small></div>
        <Spark values={t?.latency.series ?? []} label="Latencia de las últimas llamadas" />
        <dl className="kv-dense">
          <Row k="Media 24 h" v={ms(t?.latency.avg_24h)} />
          <Row k="Máx. 24 h" v={ms(t?.latency.max_24h)} />
          <Row k="Llamadas / errores" v={t ? `${t.latency.calls_24h} / ${t.latency.errors_24h}` : ND} tone={t?.latency.errors_24h ? "t-warn" : ""} />
          <Row k="Ollama ping" v={ms(t?.ollama.ping_ms)} />
          <Row k="Modelos cargados" v={t?.ollama.loaded ? (t.ollama.loaded.map((m) => m.name).join(", ") || "ninguno en memoria") : ND} />
        </dl>
      </>) },
    { id: "system", title: "Sistema", render: () => (
      <>
        <div className="sys-row"><span>CPU</span><Meter value={s.cpu_percent} /><b>{pct(s.cpu_percent)}</b></div>
        <Spark values={hist.cpu} max={100} label="Uso de CPU" height={26} />
        <div className="sys-row"><span>RAM</span><Meter value={s.ram_percent} /><b>{pct(s.ram_percent)}</b></div>
        <Spark values={hist.ram} max={100} label="Uso de RAM" height={26} />
        <dl className="kv-dense">
          <Row k="RAM usada" v={`${bytes(s.ram_used)} / ${bytes(s.ram_total)}`} />
          <Row k="Swap" v={pct(s.swap_percent)} />
          <Row k="Carga (1/5/15 min)" v={s.load ? s.load.join(" · ") : ND} />
          <Row k="Proceso VISTAN" v={`${bytes(s.process_rss)} · ${s.process_threads ?? ND} hilos`} />
          <Row k="Base de datos" v={bytes(s.db_bytes)} />
          <Row k="Disco libre" v={bytes(s.disk_free)} />
        </dl>
      </>) },
    { id: "memory", title: "Actividad de memoria", render: () => (
      <dl className="kv-dense">
        <Row k="Recuerdos" v={t?.memory.memories ?? ND} />
        <Row k="Usados por la IA · 24 h" v={t?.memory.recalled_24h ?? ND} />
        <Row k="Documentos / fragmentos" v={t ? `${t.memory.documents} / ${t.memory.chunks}` : ND} />
        <Row k="Entidades / relaciones" v={t ? `${t.memory.entities} / ${t.memory.relations}` : ND} />
      </dl>) },
    { id: "agents", title: "Agentes y procesos", render: () => (
      <>
        <dl className="kv-dense">
          <Row k="Ejecuciones · 24 h" v={t?.agents.runs_24h ?? ND} />
          <Row k="Agentes activos hoy" v={t ? (t.agents.active.join(", ") || "ninguno") : ND} />
          {t?.agents.last && <Row k="Última" v={`${t.agents.last.agents.join("+") || "general"} · ${ms(t.agents.last.ms)}`} />}
        </dl>
        {!t?.processes.length ? <Empty>Ningún proceso en ejecución.</Empty> : (
          <ul className="proc-list">{t.processes.map((p, i) => <li key={i}><Led state="busy" /> <span className="mono">{p.kind}</span> {p.label} <em>{p.state}</em></li>)}</ul>
        )}
      </>) },
    { id: "connections", title: "Conexiones", render: () => (
      !t ? <Empty>{ND}</Empty> : <ul className="conn-list">{t.connections.map((c) => (
        <li key={c.name}><Led state={c.state} /><span>{c.name}</span><em>{c.detail}</em></li>
      ))}</ul>) },
    { id: "events", title: "Registro de eventos", wide: true, render: () => <EventConsole events={t?.events ?? []} /> },
  ];
  return <WidgetColumn panel="left" title="System telemetry" widgets={widgets} className="hud-left" />;
}

/* ===================== PANEL DERECHO · INTELLIGENCE DATA ===================== */
export function HudRight({ d, t, cc, module, onOpen, onClose, onChanged }: {
  d: Dashboard | null; t: TelemetryData | null; cc: CommandCenter | null;
  module?: { id: string; info?: NodeInfo } | null; onOpen: (r: string) => void; onClose: () => void; onChanged: () => void;
}) {
  const notes = useAsync(v4.notifications, 30000);
  const mail = useAsync(api.importantMail, 300000);
  const research = useAsync(v4.research, 20000);
  const [done, setDone] = useState<Set<number>>(new Set());
  const def = module ? NODE_DEFS.find((n) => n.id === module.id) : null;
  const ok = t?.connections.filter((c) => c.state === "ok").length ?? 0;
  const lastR = research.data?.[0];

  const mails = mail.data?.connected ? mail.data.items : [];
  const widgets: WidgetDef[] = [
    // Alertas y correos solo aparecen cuando hay algo (nada de tarjetas vacías)
    ...(d?.alerts.length ? [{ id: "alerts", title: `Alertas · ${d.alerts.length}`, render: () => (
      <ul className="hud-list">{d.alerts.slice(0, 4).map((a, i) => <li key={i} className={`al-${a.level}`}><Link to={MODULE_ROUTE[a.module] ?? "/"}>{a.text}</Link></li>)}</ul>) }] : []),
    ...(mails.length ? [{ id: "mail", title: `Correos importantes (${mails.length})`, render: () => (
      <ul className="hud-list">{mails.slice(0, 4).map((m) => <li key={m.id}><span><b>{m.subject}</b><br /><span className="small muted">{m.sender.replace(/<.*>/, "").trim()}{m.reason ? ` · ${m.reason}` : ""}</span></span></li>)}</ul>) }] : []),
    { id: "finance", title: "Finanzas · dinero real", render: () => (
      !d?.finance.has_data ? <Empty>Aún no hay movimientos de dinero real.</Empty> : <>
        <dl className="kv-dense">
          <Row k="Ingresos del mes" v={formatMoney(d.finance.income_cents, d.finance.currency)} />
          <Row k="Gastos del mes" v={formatMoney(d.finance.expense_cents, d.finance.currency)} />
          <Row k="Neto" v={formatMoney(d.finance.net_cents, d.finance.currency)} tone={d.finance.net_cents < 0 ? "t-warn" : ""} />
        </dl>
        {d.finance.top_expense_categories.length > 0 && <ul className="hud-list">{d.finance.top_expense_categories.slice(0, 3).map((c) => (
          <li key={c.category}>{c.category}<em>{formatMoney(c.amount_cents, d.finance.currency)}</em></li>))}</ul>}
      </>) },
    { id: "services", title: "Servicios", render: () => (
      !t ? <Empty>{ND}</Empty> : <>
        <p className="small"><b className="mono">{ok}</b> de {t.connections.length} conectados</p>
        <div className="svc-grid">{t.connections.map((c) => <span key={c.name} title={c.detail ?? ""}><Led state={c.state} />{c.name.replace(" (IA local)", "")}</span>)}</div>
      </>) },
    { id: "agents", title: "Actividad de agentes", render: () => (
      !cc?.recent_agent_runs.length ? <Empty>Sin ejecuciones todavía.</Empty> :
        <ul className="hud-list">{cc.recent_agent_runs.slice(0, 4).map((r) => (
          <li key={r.id}><span className="mono small">{r.agent_names.map((n) => n.replace(" Agent", "")).join("+") || "general"}</span> {r.request.slice(0, 60)}<em>{relativeTime(r.created_at)}</em></li>
        ))}</ul>) },
    { id: "research", title: "Investigación", render: () => (
      !lastR ? <Empty>Sin investigaciones. Di «investiga…».</Empty> : <Link to={`/research?id=${lastR.id}`} className="hud-link">
        <b>{lastR.question.slice(0, 80)}</b>
        <span className="small muted">{lastR.status === "running" ? `${lastR.step_label} · ${lastR.progress} %` : lastR.status}{lastR.confidence ? ` · confianza ${lastR.confidence}` : ""}</span>
        {lastR.status === "running" && <span className="meter"><i style={{ width: `${lastR.progress}%` }} /></span>}
      </Link>) },
    { id: "tasks", title: `Tareas pendientes${d ? ` · ${d.tasks.pending}` : ""}`, render: () => (
      !d?.tasks.items.length ? <Empty>No hay tareas registradas.</Empty> :
        <ul className="hud-list">{d.tasks.items.filter((x) => !done.has(x.id)).slice(0, 5).map((x) => (
          <li key={x.id} className={x.overdue ? "al-warning" : ""}>
            <button type="button" className="tick" aria-label={`Completar ${x.title}`} onClick={async () => { setDone((s) => new Set(s).add(x.id)); try { await api.completeTask(x.id); onChanged(); } catch { /* */ } }} />
            {x.title}<em>{x.overdue ? "Atrasada · " : ""}{formatDue({ ...x, due_date: null, all_day: x.all_day ?? false }, d.greeting.timezone)}</em></li>
        ))}</ul>) },
    { id: "events", title: "Próximos eventos", render: () => (
      !d?.events.items.length ? <Empty>Sin eventos próximos.</Empty> :
        <ul className="hud-list">{d.events.items.slice(0, 4).map((e) => (
          <li key={e.id}>{e.in_progress && <Led state="busy" />}{e.title}<em>{new Date(e.start_at).toLocaleString("es-ES", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: d.greeting.timezone })}</em></li>
        ))}</ul>) },
    { id: "recall", title: "Memoria recuperada", render: () => (
      !t?.memory.recalled.length ? <Empty>La IA aún no ha usado recuerdos.</Empty> :
        <ul className="hud-list">{t.memory.recalled.map((m, i) => <li key={i}>{m.text}<em>{relativeTime(m.at + "Z")}</em></li>)}</ul>) },
    { id: "stats", title: "Estadísticas", render: () => (
      !d ? <Empty>{ND}</Empty> : <div className="stat-grid">
        <div><b>{d.tasks.pending}</b><span>tareas</span></div>
        <div><b>{d.fitness.sessions_7d}</b><span>entrenos 7d</span></div>
        <div><b>{d.projects.active}</b><span>proyectos</span></div>
        <div><b>{cc?.research_total ?? ND}</b><span>informes</span></div>
        <div className="span2"><b>{cc ? cc.memory.memories ?? 0 : ND}</b><span>recuerdos en memoria</span></div>
      </div>) },
    { id: "notifications", title: `Notificaciones${notes.data?.unread ? ` · ${notes.data.unread}` : ""}`, render: () => (
      !notes.data?.items.length ? <Empty>Sin notificaciones.</Empty> :
        <ul className="hud-list">{notes.data.items.slice(0, 4).map((n) => <li key={n.id} className={n.read ? "" : "is-unread"}>{n.link ? <Link to={n.link}>{n.title}</Link> : n.title}<em>{relativeTime(n.created_at)}</em></li>)}</ul>) },
    { id: "activity", title: "Actividad reciente", render: () => (
      !d?.activity.items.length ? <Empty>Sin actividad todavía.</Empty> :
        <ul className="hud-list">{d.activity.items.slice(0, 5).map((a) => <li key={a.id}>{a.summary}<em>{relativeTime(a.created_at)}</em></li>)}</ul>) },
  ];
  return (
    <div className="hud-right-wrap">
      {def && (
        <section className="hud-w module-ctx" aria-label={`Contexto de ${def.label}`}>
          <header className="hud-w-head"><span className="hud-w-title"><Icon name={def.icon} size={13} /> {def.label}</span>
            {module?.info?.active && <span className="badge live">activo</span>}
            <button type="button" className="link-btn" onClick={onClose} aria-label="Cerrar contexto">×</button></header>
          <div className="hud-w-body">
            <p className="small muted">{def.description}</p>
            <p className="core-card-metric">{module?.info?.metric ?? ND}</p>
            {module?.info?.details?.length ? <ul className="hud-list">{module.info.details.map((x, i) => <li key={i}>{x}</li>)}</ul> : null}
            <button type="button" className="btn" onClick={() => onOpen(def.route)}>Abrir {def.label}</button>
          </div>
        </section>
      )}
      <WidgetColumn panel="right" title="Intelligence data" widgets={widgets} className="hud-right" />
    </div>
  );
}

/* ===================== FRANJA INFERIOR ===================== */
export function HudGoals({ d }: { d: Dashboard | null }) {
  const g = d?.goals?.items ?? [];
  return (
    <article className="hud-w strip-w" aria-label="Objetivos personales">
      <header className="hud-w-head"><span className="hud-w-title">Objetivos</span><Link to="/tasks" className="link-btn">ver</Link></header>
      <div className="hud-w-body">{!g.length ? <Empty>Sin objetivos activos.</Empty> : g.slice(0, 4).map((x) => (
        <div key={x.id} className="bar-line"><span>{x.title}</span><span className="meter"><i style={{ width: `${Math.min(100, x.progress ?? 0)}%` }} /></span>
          <em>{x.progress !== null ? `${Math.round(x.progress)}%` : ND} · {PACE_LABEL[x.pace] ?? x.pace}</em></div>
      ))}</div>
    </article>
  );
}

export function HudProjects() {
  const p = useAsync(v4.projects, 60000);
  const items = (p.data ?? []).filter((x) => x.status === "active").slice(0, 4);
  return (
    <article className="hud-w strip-w" aria-label="Progreso de proyectos">
      <header className="hud-w-head"><span className="hud-w-title">Proyectos</span><Link to="/projects" className="link-btn">ver</Link></header>
      <div className="hud-w-body">{!items.length ? <Empty>Sin proyectos activos.</Empty> : items.map((x) => (
        <div key={x.id} className="bar-line"><span>{x.name}</span><span className="meter"><i style={{ width: `${x.progress ?? 0}%` }} /></span>
          <em>{x.progress !== null ? `${x.progress}%` : "sin tareas"}{x.tasks_overdue ? ` · ${x.tasks_overdue} atrasadas` : ""}</em></div>
      ))}</div>
    </article>
  );
}

export function HudToday({ t }: { t: TelemetryData | null }) {
  const x = t?.today;
  return (
    <article className="hud-w strip-w" aria-label="Actividad del día">
      <header className="hud-w-head"><span className="hud-w-title">Actividad de hoy</span></header>
      <div className="hud-w-body">{!x ? <Empty>{ND}</Empty> : (
        <div className="stat-grid">
          <div><b>{x.events}</b><span>eventos</span></div>
          <div><b>{x.tasks_done}</b><span>tareas hechas</span></div>
          <div><b>{x.messages}</b><span>mensajes</span></div>
          <div><b>{x.model_calls}</b><span>llamadas IA</span></div>
        </div>
      )}</div>
    </article>
  );
}
