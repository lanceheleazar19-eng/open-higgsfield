import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api } from "../api/client";
import type { GoalItem, Priority, TaskItem } from "../api/types";
import { useAsync } from "../api/useAsync";
import { useAtlas } from "../components/AtlasContext";
import { Icon } from "../components/Icon";
import { Empty, Panel } from "../components/Panel";
import { PRIORITY_LABEL } from "../lib/format";
import { PACE_LABEL, PRIORITIES, bucketTasks, fmtNum, formatDayLabel, formatDue, todayIn } from "../lib/tasks";

type Tab = "tasks" | "week" | "goals";

export function Tasks() {
  const [tab, setTab] = useState<Tab>(() => (new URLSearchParams(window.location.search).get("tab") as Tab) || "tasks");
  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Fase 4 · activo</p>
        <h1><Icon name="tasks" size={26} /> Tareas y objetivos</h1>
        <p className="lead">Escribe como hablas: «llamar al gestor el viernes a las 10, urgente». ATLAS entiende la fecha, la hora y la prioridad.</p>
      </header>
      <div className="tabs" role="tablist" aria-label="Secciones">
        {([["tasks", "Tareas"], ["week", "Semana"], ["goals", "Objetivos"]] as const).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>
      {tab === "tasks" && <TasksTab />}
      {tab === "week" && <WeekTab />}
      {tab === "goals" && <GoalsTab />}
    </div>
  );
}

/* ------------------------------------------------------------------ Tareas */

function TasksTab() {
  const { prefs, reloadHealth } = useAtlas();
  const tz = prefs?.timezone;
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [showDone, setShowDone] = useState(false);
  const open = useAsync(() => api.tasks({ status: "open", q, category }));
  const done = useAsync(() => (showDone ? api.tasks({ status: "done", q, category }) : Promise.resolve(null)));
  const goals = useAsync(() => api.goals("active"));
  const summary = useAsync(() => api.taskSummary("day"));
  const [editing, setEditing] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ tone: "pos" | "neg"; text: string } | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { void open.reload(); void done.reload(); }, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [q, category, showDone]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = async (text?: string) => {
    if (text) setMsg({ tone: "pos", text });
    await Promise.all([open.reload(), done.reload(), summary.reload()]);
    void reloadHealth();
  };
  const fail = (e: unknown) => setMsg({ tone: "neg", text: (e as Error).message });

  async function toggle(t: TaskItem) {
    try {
      if (t.status === "done") await api.reopenTask(t.id);
      else await api.completeTask(t.id);
      await refresh(t.status === "done" ? `Reabierta: «${t.title}»` : `Hecha: «${t.title}» ✓`);
    } catch (e) { fail(e); }
  }

  async function remove(t: TaskItem) {
    if (!window.confirm(`¿Eliminar la tarea «${t.title}»?`)) return;
    try { await api.deleteTask(t.id); await refresh("Tarea eliminada."); } catch (e) { fail(e); }
  }

  const today = todayIn(tz);
  const b = bucketTasks(open.data?.items ?? [], today);
  const s = summary.data;
  const row = (t: TaskItem) => editing === t.id ? (
    <li key={t.id}><TaskEditor task={t} goals={goals.data?.items ?? []} onDone={(m) => { setEditing(null); if (m) void refresh(m); }} /></li>
  ) : (
    <TaskRow key={t.id} t={t} tz={tz} onToggle={toggle} onEdit={() => setEditing(t.id)} onDelete={remove} />
  );

  return (
    <div className="grid grid-tasks">
      <div className="stack">
        <Panel title="Nueva tarea">
          <QuickAdd onCreated={(t) => void refresh(`Creada: «${t.title}» · ${formatDue(t, tz)}`)} />
        </Panel>
        <Panel title="Hoy">
          {!s ? <p className="muted">—</p> : (
            <dl className="kv">
              <div><dt>Completadas hoy</dt><dd className="mono pos">{s.completed}</dd></div>
              <div><dt>Pendientes para hoy</dt><dd className="mono">{s.due_open}</dd></div>
              <div><dt>Atrasadas</dt><dd className={`mono ${s.overdue ? "neg" : ""}`}>{s.overdue}</dd></div>
              <div><dt>Cumplimiento de hoy</dt><dd className="mono">{s.completion_rate === null ? "—" : `${Math.round(s.completion_rate * 100)} %`}</dd></div>
            </dl>
          )}
        </Panel>
      </div>
      <Panel title={`Pendientes${open.data ? ` (${open.data.items.length})` : ""}`} className="task-list">
        <div className="filters">
          <input type="search" placeholder="Buscar tareas…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar tareas" />
          <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Filtrar por categoría">
            <option value="">Todas las categorías</option>
            {(open.data?.categories ?? []).map((c) => <option key={c} value={c}>#{c}</option>)}
          </select>
          <label className="check"><input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} /> Ver completadas</label>
        </div>
        {msg && <p role="status" className={`small ${msg.tone}`}>{msg.text}</p>}
        {open.error && <p className="neg small">{open.error.message}</p>}
        {open.data && open.data.items.length === 0 ? (
          <Empty>{q || category ? "No hay tareas que coincidan." : "No tienes tareas pendientes. Añade una arriba o díselo a ATLAS: «apúntame…»."}</Empty>
        ) : (
          <>
            <TaskGroup title="Atrasadas" tone="neg" items={b.overdue} row={row} />
            <TaskGroup title="Hoy" items={b.today} row={row} />
            <TaskGroup title="Próximas" items={b.upcoming} row={row} />
            <TaskGroup title="Sin fecha" items={b.undated} row={row} />
          </>
        )}
        {showDone && done.data && (
          <TaskGroup title={`Completadas (${done.data.items.length})`} items={done.data.items} row={row} />
        )}
      </Panel>
    </div>
  );
}

function TaskGroup({ title, items, row, tone }: { title: string; items: TaskItem[]; row: (t: TaskItem) => ReactNode; tone?: string }) {
  if (!items.length) return null;
  return (
    <section className="task-group">
      <h3 className={tone}>{title} <span className="count">{items.length}</span></h3>
      <ul className="task-items">{items.map(row)}</ul>
    </section>
  );
}

function TaskRow({ t, tz, onToggle, onEdit, onDelete }: {
  t: TaskItem; tz?: string; onToggle: (t: TaskItem) => void; onEdit: () => void; onDelete: (t: TaskItem) => void;
}) {
  const done = t.status === "done";
  return (
    <li className={`task ${done ? "is-done" : ""} ${t.overdue ? "is-overdue" : ""}`}>
      <button className={`tick ${done ? "on" : ""}`} onClick={() => onToggle(t)}
        aria-label={done ? `Reabrir: ${t.title}` : `Marcar como hecha: ${t.title}`} aria-pressed={done}>
        {done ? "✓" : ""}
      </button>
      <span className="task-main">
        <span className="task-title">{t.title}</span>
        <span className="mem-meta">
          <span className={`prio prio-${t.priority}`}>{PRIORITY_LABEL[t.priority]}</span>
          {" "}{t.overdue ? "Atrasada · " : ""}{formatDue(t, tz)}
          {t.reminder_at && !done ? " · 🔔" : ""}
          {t.category ? ` · #${t.category}` : ""}
          {t.goal_title ? ` · 🎯 ${t.goal_title}` : ""}
        </span>
      </span>
      <span className="row-actions">
        <button className="mini-btn ghost" onClick={onEdit} aria-label={`Editar: ${t.title}`}>Editar</button>
        <button className="mini-btn danger" onClick={() => onDelete(t)} aria-label={`Eliminar: ${t.title}`}>Eliminar</button>
      </span>
    </li>
  );
}

function QuickAdd({ onCreated }: { onCreated: (t: TaskItem) => void }) {
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<{ title: string; priority: Priority; category: string | null; all_day: boolean; due_local: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (text.trim().length < 3) { setPreview(null); return; }
    const t = setTimeout(() => { api.parseTask(text).then(setPreview).catch(() => setPreview(null)); }, 300);
    return () => clearTimeout(t);
  }, [text]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (text.trim().length < 2) return;
    setSaving(true);
    setError(null);
    try {
      onCreated(await api.quickTask(text.trim()));
      setText("");
      setPreview(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const when = preview?.due_local
    ? preview.all_day ? formatDayLabel(preview.due_local) : new Intl.DateTimeFormat("es-ES", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(preview.due_local))
    : "sin fecha";

  return (
    <form className="form" onSubmit={submit}>
      <label>
        <span>¿Qué tienes que hacer?</span>
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={500}
          placeholder="Ej.: preparar la oferta el jueves importante #trabajo" aria-label="Nueva tarea en lenguaje natural" />
      </label>
      {preview && (
        <p className="parse-preview" aria-live="polite">
          <strong>{preview.title}</strong> · {when} · <span className={`prio prio-${preview.priority}`}>{PRIORITY_LABEL[preview.priority]}</span>
          {preview.category ? ` · #${preview.category}` : ""}
        </p>
      )}
      <div className="form-actions">
        <button className="btn" type="submit" disabled={saving || text.trim().length < 2}>{saving ? "Creando…" : "Añadir tarea"}</button>
        {error && <span className="neg small">{error}</span>}
      </div>
      <p className="muted small">Entiende: hoy, mañana, pasado mañana, el viernes, el 5 de diciembre, 1/12, en 3 días, la semana que viene, a las 10, por la tarde, urgente, importante, sin prisa, #categoría.</p>
    </form>
  );
}

function TaskEditor({ task, goals, onDone }: { task: TaskItem; goals: GoalItem[]; onDone: (msg: string | null) => void }) {
  const [title, setTitle] = useState(task.title);
  const [priority, setPriority] = useState<Priority>(task.priority);
  const [category, setCategory] = useState(task.category ?? "");
  const [date, setDate] = useState(task.due_date ?? "");
  const [time, setTime] = useState(task.all_day || !task.due_at ? "" : task.due_at.slice(11, 16));
  const [reminder, setReminder] = useState(!!task.reminder_at);
  const [goalId, setGoalId] = useState(task.goal_id ? String(task.goal_id) : "");
  const [error, setError] = useState<string | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    const off = (() => {
      if (!date) return "";
      const d = new Date(`${date}T${time || "12:00"}:00`);
      const m = -d.getTimezoneOffset();
      return `${m >= 0 ? "+" : "-"}${String(Math.floor(Math.abs(m) / 60)).padStart(2, "0")}:${String(Math.abs(m) % 60).padStart(2, "0")}`;
    })();
    const dueAt = date && time ? `${date}T${time}:00${off}` : null;
    try {
      await api.updateTask(task.id, {
        title: title.trim(), priority, category: category.trim() || null,
        ...(date ? (time ? { due_at: dueAt } : { due_date: date }) : { due_at: null }),
        reminder_at: reminder && dueAt ? dueAt : reminder && date ? `${date}T09:00:00${off}` : null,
        goal_id: goalId ? Number(goalId) : null,
      });
      onDone("Tarea actualizada.");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="form task-editor" onSubmit={save}>
      <input value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Título" maxLength={300} />
      <div className="form-row">
        <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)} aria-label="Prioridad">
          {PRIORITIES.map((p) => <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>)}
        </select>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Fecha" />
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)} aria-label="Hora (opcional)" disabled={!date} />
        <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Categoría" aria-label="Categoría" maxLength={64} />
        <select value={goalId} onChange={(e) => setGoalId(e.target.value)} aria-label="Objetivo">
          <option value="">Sin objetivo</option>
          {goals.map((g) => <option key={g.id} value={g.id}>🎯 {g.title}</option>)}
        </select>
      </div>
      <div className="form-actions">
        <label className="check"><input type="checkbox" checked={reminder} disabled={!date} onChange={(e) => setReminder(e.target.checked)} /> Avisarme</label>
        <button className="mini-btn" type="submit" disabled={!title.trim()}>Guardar</button>
        <button className="mini-btn ghost" type="button" onClick={() => onDone(null)}>Cancelar</button>
        {error && <span className="neg small">{error}</span>}
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------ Semana */

function WeekTab() {
  const [perDay, setPerDay] = useState(4);
  const plan = useAsync(() => api.weekPlan(perDay));
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { void plan.reload(); }, [perDay]); // eslint-disable-line react-hooks/exhaustive-deps

  const unpinned = plan.data?.days.flatMap((d) => d.tasks.filter((t) => !t.pinned).map((t) => ({ task_id: t.id, date: d.date }))) ?? [];

  async function apply() {
    if (!window.confirm(`Se fijará fecha a ${unpinned.length} tareas que no la tenían. ¿Continuar?`)) return;
    const r = await api.applyPlan(unpinned);
    setMsg(`Plan aplicado: ${r.scheduled} tareas programadas.`);
    await plan.reload();
  }

  return (
    <div className="stack">
      <Panel title="Tu semana" aside={
        <span className="row-actions">
          <label className="check">Máx. por día
            <select value={perDay} onChange={(e) => setPerDay(Number(e.target.value))} aria-label="Máximo de tareas por día">
              {[2, 3, 4, 5, 6, 8].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <button className="mini-btn" onClick={() => void apply()} disabled={!unpinned.length}>Aplicar plan ({unpinned.length})</button>
        </span>
      }>
        <p className="muted small">ATLAS coloca primero lo atrasado y lo que tiene fecha (📌), y reparte el resto por prioridad. Las tareas sin fecha solo se programan si pulsas «Aplicar plan».</p>
        {msg && <p role="status" className="small pos">{msg}</p>}
        {!plan.data ? <p className="muted">Calculando…</p> : (
          <div className="week-grid">
            {plan.data.days.map((d, i) => (
              <section key={d.date} className={`week-day-col ${d.over_capacity ? "over" : ""}`}>
                <h3>{i === 0 ? "Hoy" : formatDayLabel(d.date)} <span className="count">{d.load}</span></h3>
                {d.tasks.length === 0 ? <p className="muted small">Libre</p> : (
                  <ul>
                    {d.tasks.map((t) => (
                      <li key={t.id} className={`plan-task prio-edge-${t.priority} ${t.overdue ? "is-overdue" : ""}`}>
                        {t.pinned && <span title="Con fecha">📌 </span>}{t.title}
                        {t.time && <span className="mem-meta"> · {t.time}</span>}
                        {t.overdue && <span className="mem-meta neg"> · atrasada</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            ))}
          </div>
        )}
        {plan.data && plan.data.if_time.length > 0 && (
          <p className="small muted"><strong>Si queda tiempo:</strong> {plan.data.if_time.map((t) => t.title).join(", ")}</p>
        )}
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------ Objetivos */

function GoalsTab() {
  const { reloadHealth } = useAtlas();
  const [showAll, setShowAll] = useState(false);
  const goals = useAsync(() => api.goals(showAll ? "all" : "active"));
  const [msg, setMsg] = useState<{ tone: "pos" | "neg"; text: string } | null>(null);
  useEffect(() => { void goals.reload(); }, [showAll]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = async (text: string, tone: "pos" | "neg" = "pos") => {
    setMsg({ tone, text });
    await goals.reload();
    void reloadHealth();
  };

  return (
    <div className="grid grid-tasks">
      <Panel title="Nuevo objetivo">
        <GoalForm onSaved={(g) => void refresh(`Objetivo creado: «${g.title}»`)} />
      </Panel>
      <Panel title="Objetivos" aside={<label className="check"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Ver todos</label>}>
        {msg && <p role="status" className={`small ${msg.tone}`}>{msg.text}</p>}
        {!goals.data ? <p className="muted">Cargando…</p> : goals.data.items.length === 0 ? (
          <Empty>Aún no tienes objetivos medibles. Crea uno y ATLAS calculará tu ritmo, lo que necesitas por semana y cuándo lo conseguirás.</Empty>
        ) : (
          <ul className="goal-items">
            {goals.data.items.map((g) => <GoalCard key={g.id} g={g} onChange={(t, tone) => void refresh(t, tone)} />)}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function GoalCard({ g, onChange }: { g: GoalItem; onChange: (msg: string, tone?: "pos" | "neg") => void }) {
  const m = g.metrics;
  const pct = m.progress === null ? null : Math.round(m.progress * 100);
  const exp = m.expected_progress !== undefined ? Math.round(m.expected_progress * 100) : null;
  const [val, setVal] = useState("");
  const [mode, setMode] = useState<"add" | "set">("add");
  const unit = g.unit ?? "";

  async function record(e: FormEvent) {
    e.preventDefault();
    const n = Number(val.replace(",", "."));
    if (!val.trim() || Number.isNaN(n)) return;
    try {
      const r = await api.goalProgress(g.id, mode === "add" ? { delta: n } : { value: n });
      setVal("");
      onChange(r.status === "achieved" ? `🎯 ¡Objetivo conseguido: «${g.title}»!` : `Progreso registrado en «${g.title}».`);
    } catch (err) {
      onChange((err as Error).message, "neg");
    }
  }

  async function setStatus(status: GoalItem["status"]) {
    await api.updateGoal(g.id, { status });
    onChange(`«${g.title}»: ${status === "active" ? "reactivado" : status === "paused" ? "en pausa" : status === "achieved" ? "conseguido" : "abandonado"}.`);
  }

  async function remove() {
    if (!window.confirm(`¿Eliminar el objetivo «${g.title}» y su historial?`)) return;
    await api.deleteGoal(g.id);
    onChange("Objetivo eliminado.");
  }

  return (
    <li className={`goal pace-${m.pace ?? "none"} ${g.status !== "active" ? "is-inactive" : ""}`}>
      <div className="goal-head">
        <span className="goal-title">🎯 {g.title}</span>
        <span className={`pace-tag pace-${m.pace}`}>{g.status === "active" ? PACE_LABEL[m.pace ?? "not_started"] : g.status === "achieved" ? "Conseguido" : g.status === "paused" ? "En pausa" : "Abandonado"}</span>
      </div>
      <div className="goal-bar" role="progressbar" aria-label={`Progreso de ${g.title}`} aria-valuenow={pct ?? 0} aria-valuemin={0} aria-valuemax={100}>
        <span style={{ width: `${pct ?? 0}%` }} />
        {exp !== null && g.status === "active" && <i style={{ left: `${exp}%` }} title={`Donde deberías estar hoy: ${exp} %`} />}
      </div>
      <div className="goal-stats">
        <span className="mono big-pct">{pct === null ? "—" : `${pct} %`}</span>
        {g.kind === "numeric"
          ? <span>{fmtNum(g.current_value, unit)} de {fmtNum(g.target_value, unit)}</span>
          : <span>{g.tasks_done} de {g.tasks_total} tareas</span>}
        {g.deadline && <span className="muted">· límite {formatDayLabel(g.deadline)}{m.days_left !== undefined && m.days_left >= 0 ? ` (${m.days_left} días)` : ""}</span>}
      </div>
      {g.status === "active" && (
        <ul className="goal-insights">
          {m.required_per_week !== undefined && m.required_per_week !== null && (
            <li>Necesitas <strong>{fmtNum(Math.abs(m.required_per_week), g.kind === "numeric" ? unit : "tareas")}</strong> por semana para llegar a tiempo.</li>
          )}
          {m.rate_per_week !== undefined && (
            <li>Tu ritmo real: <strong>{fmtNum(Math.abs(m.rate_per_week), g.kind === "numeric" ? unit : "tareas")}</strong> por semana.</li>
          )}
          {m.projected_date && <li>A este ritmo lo conseguirás el <strong>{formatDayLabel(m.projected_date)}</strong>.</li>}
          {!m.rate_per_week && m.pace !== "achieved" && <li className="muted">Registra tu progreso para que ATLAS calcule tu ritmo real.</li>}
        </ul>
      )}
      <div className="goal-actions">
        {g.status === "active" && g.kind === "numeric" && (
          <form onSubmit={record} className="progress-form">
            <select value={mode} onChange={(e) => setMode(e.target.value as "add" | "set")} aria-label="Tipo de registro">
              <option value="add">Sumar</option>
              <option value="set">Nuevo total</option>
            </select>
            <input inputMode="decimal" value={val} onChange={(e) => setVal(e.target.value)} placeholder={unit || "valor"}
              aria-label={`Registrar progreso de ${g.title}`} />
            <button className="mini-btn" type="submit" disabled={!val.trim()}>Registrar</button>
          </form>
        )}
        {g.status === "active" && g.kind === "milestones" && <span className="muted small">Vincula tareas a este objetivo al editarlas.</span>}
        <span className="row-actions">
          {g.status === "active"
            ? <button className="mini-btn ghost" onClick={() => void setStatus("paused")}>Pausar</button>
            : <button className="mini-btn ghost" onClick={() => void setStatus("active")}>Reactivar</button>}
          <button className="mini-btn danger" onClick={() => void remove()} aria-label={`Eliminar objetivo: ${g.title}`}>Eliminar</button>
        </span>
      </div>
    </li>
  );
}

function GoalForm({ onSaved }: { onSaved: (g: GoalItem) => void }) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"numeric" | "milestones">("numeric");
  const [unit, setUnit] = useState("");
  const [start, setStart] = useState("0");
  const [target, setTarget] = useState("");
  const [deadline, setDeadline] = useState("");
  const [area, setArea] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const num = (s: string) => Number(s.replace(",", "."));
    try {
      const g = await api.createGoal({
        title: title.trim(), kind, area: area || null, deadline: deadline || null,
        ...(kind === "numeric" ? { unit: unit.trim() || null, start_value: num(start || "0"), target_value: num(target) } : {}),
      });
      onSaved(g);
      setTitle(""); setTarget(""); setDeadline(""); setUnit(""); setStart("0");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      <label><span>Objetivo</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder="Ej.: Ahorrar para la entrada del piso" />
      </label>
      <label><span>Cómo se mide</span>
        <select value={kind} onChange={(e) => setKind(e.target.value as "numeric" | "milestones")}>
          <option value="numeric">Con un número (€, kg, km, clientes…)</option>
          <option value="milestones">Por tareas completadas</option>
        </select>
      </label>
      {kind === "numeric" && (
        <div className="form-row">
          <label><span>Valor actual</span><input inputMode="decimal" value={start} onChange={(e) => setStart(e.target.value)} /></label>
          <label><span>Meta</span><input inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} required /></label>
          <label><span>Unidad</span><input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="€" maxLength={16} /></label>
        </div>
      )}
      <div className="form-row">
        <label><span>Fecha límite</span><input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></label>
        <label><span>Área</span>
          <select value={area} onChange={(e) => setArea(e.target.value)}>
            <option value="">—</option>
            {["finanzas", "salud", "negocio", "carrera", "aprendizaje", "personal"].map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
      </div>
      <p className="muted small">Para bajar (p. ej. peso de 86 a 78 kg) pon el valor actual mayor que la meta.</p>
      <div className="form-actions">
        <button className="btn" type="submit" disabled={title.trim().length < 2 || (kind === "numeric" && !target.trim())}>Crear objetivo</button>
        {error && <span className="neg small">{error}</span>}
      </div>
    </form>
  );
}
