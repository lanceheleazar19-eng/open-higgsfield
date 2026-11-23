import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, type RoutineInput } from "../api/client";
import type { GymExercise, GymSession, ParsedLog, RoutineData, RoutineItem } from "../api/types";
import { useAsync } from "../api/useAsync";
import { useAtlas } from "../components/AtlasContext";
import { Icon } from "../components/Icon";
import { LineChart } from "../components/LineChart";
import { Empty, Panel } from "../components/Panel";
import { formatDayLabel } from "../lib/tasks";

type Tab = "today" | "history" | "progress" | "routines" | "body";
const DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
const kg = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 }).format(v)} kg`);
const num = (s: string) => Number(s.replace(",", "."));

export function Gym() {
  const [tab, setTab] = useState<Tab>("today");
  const tabs: [Tab, string][] = [["today", "Hoy"], ["history", "Historial"], ["progress", "Progreso"], ["routines", "Rutinas"], ["body", "Cuerpo"]];
  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Fase 5 · activo</p>
        <h1><Icon name="gym" size={26} /> Gimnasio</h1>
        <p className="lead">Registra como lo apuntas: «inclinado 2x8 40kg rir 2». ATLAS calcula tu progresión, tu volumen por músculo y te avisa si te estancas.</p>
      </header>
      <div className="tabs" role="tablist" aria-label="Secciones del gimnasio">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>
      {tab === "today" && <TodayTab />}
      {tab === "history" && <HistoryTab />}
      {tab === "progress" && <ProgressTab />}
      {tab === "routines" && <RoutinesTab />}
      {tab === "body" && <BodyTab />}
    </div>
  );
}

/* ------------------------------------------------------------------ Hoy */

function TodayTab() {
  const { reloadHealth } = useAtlas();
  const today = useAsync(api.gymToday);
  const routines = useAsync(api.gymRoutines);
  const [override, setOverride] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ tone: "pos" | "neg"; text: string } | null>(null);
  const t = today.data;

  const routine: RoutineData | null = override
    ? routines.data?.items.find((r) => r.id === override) ?? null
    : t?.routine ?? null;

  const refresh = async (text: string, tone: "pos" | "neg" = "pos") => {
    setMsg({ tone, text });
    await today.reload();
    void reloadHealth();
  };

  if (!t) return <p className="muted">{today.error ? today.error.message : "Cargando…"}</p>;
  const noRoutines = routines.data && routines.data.items.length === 0;

  return (
    <div className="grid grid-tasks">
      <div className="stack">
        <Panel title={t.rest_day && !override ? `Hoy (${t.weekday_name}): descanso` : `Hoy: ${routine?.name ?? "entreno libre"}`}>
          {t.rest_day && !override && (
            <p className="muted small">
              {t.next ? <>Próximo entreno: <strong>{t.next.name}</strong> el {t.next.weekday_name}.</> : "No tienes rutinas con día asignado."}
            </p>
          )}
          {routines.data && routines.data.items.length > 0 && (
            <label className="field">
              <span>Entrenar otra rutina hoy</span>
              <select value={override ?? ""} onChange={(e) => setOverride(e.target.value ? Number(e.target.value) : null)} aria-label="Rutina para hoy">
                <option value="">{t.routine ? `La de hoy (${t.routine.name})` : "—"}</option>
                {routines.data.items.map((r) => <option key={r.id} value={r.id}>{r.name}{r.weekday_name ? ` (${r.weekday_name})` : ""}</option>)}
              </select>
            </label>
          )}
          {noRoutines && <p className="callout">Aún no tienes rutinas. Ve a la pestaña <strong>Rutinas</strong> e importa la tuya en un clic.</p>}
        </Panel>
        <Panel title="Registro rápido">
          <TextLogger routineId={override} onLogged={(n) => void refresh(`Registrado: ${n}`)} />
        </Panel>
        {t.session && <SessionCard s={t.session} onChange={(m) => void refresh(m)} />}
      </div>
      <Panel title={routine ? "Ejercicios" : "Entreno"} className="task-list">
        {msg && <p role="status" className={`small ${msg.tone}`}>{msg.text}</p>}
        {!routine ? (
          <Empty>{noRoutines ? "Importa tu rutina para ver aquí los ejercicios del día." : "Día de descanso. Recuperar también es entrenar. Si entrenas igualmente, elige una rutina arriba o usa el registro rápido."}</Empty>
        ) : (
          <ul className="gym-list">
            {routine.exercises.map((it) => (
              <ExerciseLogger key={it.id} item={it} routineId={override}
                done={!!t.session?.exercises.some((e) => e.exercise_id === it.exercise_id)}
                onLogged={(text) => void refresh(`Registrado: ${text}`)} onError={(text) => setMsg({ tone: "neg", text })} />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function target(it: RoutineItem): string {
  const reps = it.reps_max && it.reps_max !== it.reps_min ? `${it.reps_min}-${it.reps_max}` : `${it.reps_min}`;
  const w = it.weight ? ` · ${kg(it.weight)}${it.per_side ? " por lado" : ""}` : "";
  const warm = it.warmup_sets ? `${it.warmup_sets} calent. + ` : "";
  return `${warm}${it.sets}×${reps}${w}`;
}

function ExerciseLogger({ item, routineId, done, onLogged, onError }: {
  item: RoutineItem; routineId: number | null; done: boolean; onLogged: (t: string) => void; onError: (t: string) => void;
}) {
  const [reps, setReps] = useState(String(item.reps_min));
  const [weight, setWeight] = useState(item.weight !== null ? String(item.weight) : "");
  const [rir, setRir] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.addSet({ exercise_id: item.exercise_id, reps: num(reps), weight: weight ? num(weight) : 0,
        rir: rir === "" ? null : Number(rir), routine_id: routineId });
      onLogged(`${item.name}: ${reps} reps${weight ? ` × ${weight} kg` : ""}${rir !== "" ? ` · RIR ${rir}` : ""}`);
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className={`gym-ex ${done ? "is-done" : ""}`}>
      <div className="gym-ex-head">
        <span className="task-title">{done ? "✓ " : ""}{item.name}</span>
        <span className="mem-meta">Objetivo: {target(item)}{item.notes ? ` · ${item.notes}` : ""}</span>
        {item.last && (
          <span className="mem-meta">Última vez ({formatDayLabel(item.last.date)}): {item.last.sets.map((s) => `${s.reps}×${s.weight}`).join(", ")}</span>
        )}
      </div>
      <form className="set-form" onSubmit={save}>
        <input inputMode="numeric" value={reps} onChange={(e) => setReps(e.target.value)} aria-label={`Repeticiones de ${item.name}`} />
        <span>reps</span>
        <input inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} aria-label={`Peso de ${item.name}`} />
        <span>kg{item.per_side ? "/lado" : ""}</span>
        <select value={rir} onChange={(e) => setRir(e.target.value)} aria-label={`RIR de ${item.name}`}>
          <option value="">RIR</option>
          {[0, 1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <button className="mini-btn" type="submit" disabled={busy || !reps}>+ Serie</button>
      </form>
    </li>
  );
}

function TextLogger({ routineId, onLogged }: { routineId: number | null; onLogged: (names: string) => void }) {
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<ParsedLog[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (text.trim().length < 4) { setPreview(null); return; }
    const t = setTimeout(() => { api.logWorkoutText(text, true).then((r) => setPreview(r.parsed)).catch(() => setPreview(null)); }, 350);
    return () => clearTimeout(t);
  }, [text]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const r = await api.logWorkoutText(text, false, routineId);
      if (!r.parsed.length) { setError("No he reconocido ningún ejercicio con series."); return; }
      onLogged(r.parsed.map((p) => p.name).join(", "));
      setText("");
      setPreview(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      <label>
        <span>Pega o escribe tu entreno (una línea por ejercicio)</span>
        <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} maxLength={4000}
          placeholder={"Inclinado 2x8 40kg rir 2\nAperturas hacia el medio 3x10 15kg por lado\nDominadas 6, 5 y 5"} aria-label="Entreno en texto" />
      </label>
      {preview && preview.length > 0 && (
        <ul className="parse-list" aria-live="polite">
          {preview.map((p, i) => (
            <li key={i}><strong>{p.name}</strong>: {p.reps.length}×({p.reps.join("/")}){p.weight ? ` · ${kg(p.weight)}${p.per_side ? "/lado" : ""}` : ""}{p.rir !== null ? ` · RIR ${p.rir}` : ""}{p.warmup_sets ? ` · ${p.warmup_sets} calent.` : ""}</li>
          ))}
        </ul>
      )}
      {preview && preview.length === 0 && <p className="muted small">Aún no reconozco un ejercicio con series en el texto.</p>}
      <div className="form-actions">
        <button className="btn" type="submit" disabled={!preview?.length}>Registrar</button>
        {error && <span className="neg small">{error}</span>}
      </div>
    </form>
  );
}

function SessionCard({ s, onChange }: { s: GymSession; onChange: (msg: string) => void }) {
  async function delSet(id: number) {
    await api.deleteSet(id);
    onChange("Serie eliminada.");
  }
  return (
    <Panel title={`Sesión de hoy · ${s.working_sets} series`} aside={<span className="badge">{kg(s.tonnage)} totales</span>}>
      {s.notes && <p className="muted small">{s.notes}</p>}
      <ul className="session-ex">
        {s.exercises.map((e) => (
          <li key={e.exercise_id}>
            <strong>{e.name}</strong>
            <span className="set-chips">
              {e.sets.map((x) => (
                <button key={x.id} className="set-chip" onClick={() => void delSet(x.id)} title="Pulsa para borrar esta serie"
                  aria-label={`Borrar serie ${x.set_number} de ${e.name}`}>
                  {x.reps}×{x.weight}{x.rir !== null ? ` @${x.rir}` : ""}
                </button>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/* ------------------------------------------------------------------ Historial */

function HistoryTab() {
  const list = useAsync(api.gymSessions);
  async function remove(s: GymSession) {
    if (!window.confirm(`¿Borrar la sesión del ${formatDayLabel(s.date)} (${s.routine_name ?? "entreno"})?`)) return;
    await api.deleteGymSession(s.id);
    await list.reload();
  }
  if (!list.data) return <p className="muted">Cargando…</p>;
  if (!list.data.items.length) return <Empty>Aún no hay entrenamientos registrados.</Empty>;
  return (
    <div className="stack">
      {list.data.items.map((s) => (
        <Panel key={s.id} title={`${formatDayLabel(s.date)} · ${s.routine_name ?? "Entreno"}`} aside={
          <span className="row-actions"><span className="badge">{s.working_sets} series · {kg(s.tonnage)}</span>
            <button className="mini-btn danger" onClick={() => void remove(s)} aria-label={`Borrar sesión del ${s.date}`}>Borrar</button></span>
        }>
          <ul className="session-ex">
            {s.exercises.map((e) => (
              <li key={e.exercise_id}>
                <strong>{e.name}</strong>
                <span className="set-chips">{e.sets.map((x) => <span key={x.id} className="set-chip static">{x.reps}×{x.weight}{x.rir !== null ? ` @${x.rir}` : ""}</span>)}</span>
              </li>
            ))}
          </ul>
          {s.notes && <p className="muted small">{s.notes}</p>}
        </Panel>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Progreso */

function ProgressTab() {
  const exercises = useAsync(api.gymExercises);
  const sessions = useAsync(api.gymSessions);
  const insights = useAsync(api.gymInsights);
  const volume = useAsync(() => api.gymVolume(7));
  const trained = useMemo(() => {
    const ids = new Set(sessions.data?.items.flatMap((s) => s.exercises.map((e) => e.exercise_id)) ?? []);
    return (exercises.data?.items ?? []).filter((e) => ids.has(e.id));
  }, [exercises.data, sessions.data]);
  const [exId, setExId] = useState<number | null>(null);
  const current = exId ?? trained[0]?.id ?? null;
  const prog = useAsync(() => (current ? api.gymProgress(current) : Promise.resolve(null)));
  useEffect(() => { void prog.reload(); }, [current]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="stack">
      <Panel title="Progresión por ejercicio" aside={trained.length > 0 && (
        <select value={current ?? ""} onChange={(e) => setExId(Number(e.target.value))} aria-label="Ejercicio">
          {trained.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      )}>
        {!trained.length ? <Empty>Registra entrenamientos para ver tu progresión.</Empty> : !prog.data ? <p className="muted">Cargando…</p> : (
          <>
            <div className="goal-stats">
              {prog.data.best && <span>Mejor 1RM estimado: <strong className="mono">{kg(prog.data.best.e1rm)}</strong></span>}
              {prog.data.change_pct !== undefined && prog.data.change_pct !== null && (
                <span className={prog.data.change_pct >= 0 ? "pos" : "neg"}>
                  {prog.data.change_pct >= 0 ? "▲" : "▼"} {Math.abs(prog.data.change_pct)} % desde {formatDayLabel(prog.data.since!)}
                </span>
              )}
              {prog.data.stagnant && <span className="pace-tag pace-behind">Estancado</span>}
              {prog.data.exercise.per_side && <span className="muted small">Peso por lado</span>}
            </div>
            <LineChart ariaLabel={`Progresión de ${prog.data.exercise.name}`} unit=" kg"
              labels={prog.data.points.map((p) => formatDayLabel(p.date))}
              series={[
                { label: "1RM estimado", color: "#22d3ee", values: prog.data.points.map((p) => p.e1rm) },
                { label: "Peso máximo", color: "#4d7dff", values: prog.data.points.map((p) => p.top_weight) },
              ]} />
            <p className="muted small">1RM estimado con la fórmula de Epley a partir de tu mejor serie de cada día. Línea azul: peso máximo usado.</p>
          </>
        )}
      </Panel>
      <div className="grid grid-2">
        <Panel title="Volumen semanal por músculo" aside={<span className="badge">últimos 7 días</span>}>
          {!volume.data ? <p className="muted">Cargando…</p> : (
            <>
              <ul className="vol-list">
                {volume.data.muscles.map((m) => (
                  <li key={m.muscle} className={`vol-${m.status.replace(" ", "-")}`}>
                    <span>{m.label}</span>
                    <span className="vol-track" title={`${m.sets} series · ${m.status}`}>
                      <i className="vol-band" style={{ left: `${(volume.data!.reference.min / 25) * 100}%`, width: `${((volume.data!.reference.max - volume.data!.reference.min) / 25) * 100}%` }} />
                      <span style={{ width: `${Math.min(100, (m.sets / 25) * 100)}%` }} />
                    </span>
                    <span className="mono">{new Intl.NumberFormat("es-ES").format(m.sets)}</span>
                  </li>
                ))}
              </ul>
              <p className="muted small">Series efectivas (el músculo secundario cuenta como media serie). Zona marcada: 10-20 series, una referencia general para hipertrofia, no una regla.</p>
            </>
          )}
        </Panel>
        <Panel title="Lo que ATLAS detecta">
          {!insights.data ? <p className="muted">Cargando…</p> : (
            <ul className="goal-insights">
              {insights.data.stagnations.length > 0 && (
                <li>
                  Sin mejorar en sus últimas 3 sesiones: <strong>{insights.data.stagnations.slice(0, 5).map((s) => s.name).join(", ")}</strong>
                  {insights.data.stagnations.length > 5 ? ` y ${insights.data.stagnations.length - 5} más` : ""}.
                  {" "}Para romper el estancamiento: sube 1-2 repeticiones antes de subir peso, ajusta el descanso o haz una semana de descarga.
                </li>
              )}
              {insights.data.undertrained.filter((m) => ["pecho", "espalda", "hombros", "biceps", "triceps", "cuadriceps", "isquios", "gluteos"].includes(m.muscle)).length > 0 && (
                <li>Por debajo de 10 series esta semana: {insights.data.undertrained.filter((m) => ["pecho", "espalda", "hombros", "biceps", "triceps", "cuadriceps", "isquios", "gluteos"].includes(m.muscle)).map((m) => m.label).join(", ")}.</li>
              )}
              {insights.data.compare && (() => {
                const changed = insights.data!.compare!.exercises.filter((e) => e.delta_e1rm !== 0);
                return (
                  <li>Última sesión ({formatDayLabel(insights.data!.compare!.current)}) frente a la anterior:{" "}
                    {changed.length
                      ? changed.map((e) => `${e.name} ${e.delta_e1rm > 0 ? "+" : ""}${new Intl.NumberFormat("es-ES").format(e.delta_e1rm)} kg de 1RM`).join(", ")
                      : "mismos pesos y repeticiones"}.</li>
                );
              })()}
              {!insights.data.stagnations.length && !insights.data.compare && <li className="muted">Necesito más sesiones registradas para detectar patrones.</li>}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Rutinas */

function RoutinesTab() {
  const data = useAsync(api.gymRoutines);
  const exercises = useAsync(api.gymExercises);
  const [editing, setEditing] = useState<RoutineData | "new" | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function importTpl(id: string) {
    await api.importRoutineTemplate(id);
    setMsg("Rutina importada. Ya puedes registrar tus entrenos.");
    await data.reload();
  }
  async function remove(r: RoutineData) {
    if (!window.confirm(`¿Eliminar la rutina «${r.name}»? Tus entrenos registrados se conservan.`)) return;
    await api.deleteRoutine(r.id);
    await data.reload();
  }

  if (!data.data) return <p className="muted">Cargando…</p>;
  if (editing) {
    return <RoutineEditor routine={editing === "new" ? null : editing} exercises={exercises.data?.items ?? []}
      onDone={async (m) => { setEditing(null); if (m) { setMsg(m); await data.reload(); } }} />;
  }
  return (
    <div className="stack">
      {msg && <p role="status" className="small pos">{msg}</p>}
      {data.data.items.length === 0 && data.data.templates.map((t) => (
        <Panel key={t.id} title="Importar rutina">
          <p><strong>{t.name}</strong></p>
          {t.description && <p className="muted small">{t.description}</p>}
          <p className="small">{t.days.map((d) => `${d.weekday !== null ? DAYS[d.weekday] : "sin día"}: ${d.name}`).join(" · ")}</p>
          <button className="btn" onClick={() => void importTpl(t.id)}>Importar esta rutina</button>
        </Panel>
      ))}
      <div className="row-actions"><button className="mini-btn" onClick={() => setEditing("new")}>+ Nueva rutina</button></div>
      <div className="grid grid-2">
        {data.data.items.map((r) => (
          <Panel key={r.id} title={r.name} aside={
            <span className="row-actions"><span className="badge">{r.weekday_name ?? "sin día"}</span>
              <button className="mini-btn ghost" onClick={() => setEditing(r)}>Editar</button>
              <button className="mini-btn danger" onClick={() => void remove(r)} aria-label={`Eliminar rutina ${r.name}`}>Eliminar</button></span>
          }>
            <ul className="routine-items">
              {r.exercises.map((it) => (
                <li key={it.id}><span>{it.name}</span><span className="mono muted small">{target(it)}</span></li>
              ))}
            </ul>
          </Panel>
        ))}
      </div>
    </div>
  );
}

type EditItem = RoutineInput["exercises"][number] & { key: number };

function RoutineEditor({ routine, exercises, onDone }: { routine: RoutineData | null; exercises: GymExercise[]; onDone: (msg: string | null) => void }) {
  const [name, setName] = useState(routine?.name ?? "");
  const [weekday, setWeekday] = useState<string>(routine?.weekday !== null && routine?.weekday !== undefined ? String(routine.weekday) : "");
  const [items, setItems] = useState<EditItem[]>(() => (routine?.exercises ?? []).map((e, i) => ({
    key: i, exercise_id: e.exercise_id, warmup_sets: e.warmup_sets, sets: e.sets, reps_min: e.reps_min,
    reps_max: e.reps_max, weight: e.weight, notes: e.notes,
  })));
  const [add, setAdd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const byId = new Map(exercises.map((e) => [e.id, e]));
  const upd = (key: number, p: Partial<EditItem>) => setItems((l) => l.map((x) => (x.key === key ? { ...x, ...p } : x)));

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api.saveRoutine({ name: name.trim(), weekday: weekday === "" ? null : Number(weekday),
        exercises: items.map(({ key: _k, ...rest }) => rest) }, routine?.id);
      onDone("Rutina guardada.");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Panel title={routine ? `Editar: ${routine.name}` : "Nueva rutina"}>
      <form className="form" onSubmit={save}>
        <div className="form-row">
          <label><span>Nombre</span><input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></label>
          <label><span>Día</span>
            <select value={weekday} onChange={(e) => setWeekday(e.target.value)}>
              <option value="">Sin día fijo</option>
              {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
          </label>
        </div>
        <ul className="routine-edit">
          {items.map((it, idx) => (
            <li key={it.key}>
              <strong>{byId.get(it.exercise_id)?.name}</strong>
              <span className="form-row">
                <label><span>Calent.</span><input inputMode="numeric" value={it.warmup_sets} onChange={(e) => upd(it.key, { warmup_sets: Number(e.target.value) || 0 })} /></label>
                <label><span>Series</span><input inputMode="numeric" value={it.sets} onChange={(e) => upd(it.key, { sets: Number(e.target.value) || 1 })} /></label>
                <label><span>Reps</span><input inputMode="numeric" value={it.reps_min} onChange={(e) => upd(it.key, { reps_min: Number(e.target.value) || 1 })} /></label>
                <label><span>Hasta</span><input inputMode="numeric" value={it.reps_max ?? ""} onChange={(e) => upd(it.key, { reps_max: e.target.value ? Number(e.target.value) : null })} /></label>
                <label><span>Kg</span><input inputMode="decimal" value={it.weight ?? ""} onChange={(e) => upd(it.key, { weight: e.target.value ? num(e.target.value) : null })} /></label>
              </span>
              <span className="row-actions">
                <button type="button" className="mini-btn ghost" disabled={idx === 0} onClick={() => setItems((l) => { const c = [...l]; [c[idx - 1], c[idx]] = [c[idx], c[idx - 1]]; return c; })} aria-label="Subir">↑</button>
                <button type="button" className="mini-btn danger" onClick={() => setItems((l) => l.filter((x) => x.key !== it.key))} aria-label={`Quitar ${byId.get(it.exercise_id)?.name}`}>Quitar</button>
              </span>
            </li>
          ))}
        </ul>
        <div className="form-row">
          <select value={add} onChange={(e) => setAdd(e.target.value)} aria-label="Añadir ejercicio">
            <option value="">Añadir ejercicio…</option>
            {exercises.map((e) => <option key={e.id} value={e.id}>{e.name} · {e.muscle_label}</option>)}
          </select>
          <button type="button" className="mini-btn" disabled={!add} onClick={() => {
            setItems((l) => [...l, { key: Date.now(), exercise_id: Number(add), warmup_sets: 0, sets: 3, reps_min: 8, reps_max: null, weight: null, notes: null }]);
            setAdd("");
          }}>Añadir</button>
        </div>
        <div className="form-actions">
          <button className="btn" type="submit" disabled={name.trim().length < 2}>Guardar rutina</button>
          <button className="mini-btn ghost" type="button" onClick={() => void onDone(null)}>Cancelar</button>
          {error && <span className="neg small">{error}</span>}
        </div>
      </form>
    </Panel>
  );
}

/* ------------------------------------------------------------------ Cuerpo */

function BodyTab() {
  const list = useAsync(api.bodyMetrics);
  const [f, setF] = useState({ weight_kg: "", waist_cm: "", chest_cm: "", arm_cm: "", thigh_cm: "", body_fat_pct: "" });
  const [error, setError] = useState<string | null>(null);
  const items = list.data?.items ?? [];
  const weights = items.filter((b) => b.weight_kg !== null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const payload = Object.fromEntries(Object.entries(f).filter(([, v]) => v.trim()).map(([k, v]) => [k, num(v)]));
    try {
      await api.addBodyMetric(payload);
      setF({ weight_kg: "", waist_cm: "", chest_cm: "", arm_cm: "", thigh_cm: "", body_fat_pct: "" });
      await list.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const fields: [keyof typeof f, string][] = [["weight_kg", "Peso (kg)"], ["body_fat_pct", "Grasa (%)"], ["waist_cm", "Cintura (cm)"],
    ["chest_cm", "Pecho (cm)"], ["arm_cm", "Brazo (cm)"], ["thigh_cm", "Muslo (cm)"]];
  return (
    <div className="grid grid-tasks">
      <Panel title="Registrar medidas">
        <form className="form" onSubmit={save}>
          <div className="form-row">
            {fields.map(([k, label]) => (
              <label key={k}><span>{label}</span><input inputMode="decimal" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></label>
            ))}
          </div>
          <div className="form-actions">
            <button className="btn" type="submit" disabled={!Object.values(f).some((v) => v.trim())}>Guardar</button>
            {error && <span className="neg small">{error}</span>}
          </div>
        </form>
      </Panel>
      <Panel title="Evolución">
        {!items.length ? <Empty>Registra tu peso y medidas para ver la evolución.</Empty> : (
          <>
            {weights.length > 0 && (
              <LineChart ariaLabel="Evolución del peso" unit=" kg" labels={weights.map((b) => formatDayLabel(b.measured_on))}
                series={[{ label: "Peso", color: "#34d399", values: weights.map((b) => b.weight_kg) }]} height={170} />
            )}
            <table className="data-table">
              <thead><tr><th>Fecha</th><th>Peso</th><th>Grasa</th><th>Cintura</th><th>Pecho</th><th>Brazo</th><th>Muslo</th><th /></tr></thead>
              <tbody>
                {[...items].reverse().map((b) => (
                  <tr key={b.id}>
                    <td>{formatDayLabel(b.measured_on)}</td><td>{b.weight_kg ?? "—"}</td><td>{b.body_fat_pct ?? "—"}</td><td>{b.waist_cm ?? "—"}</td>
                    <td>{b.chest_cm ?? "—"}</td><td>{b.arm_cm ?? "—"}</td><td>{b.thigh_cm ?? "—"}</td>
                    <td><button className="mini-btn danger" onClick={async () => { await api.deleteBodyMetric(b.id); await list.reload(); }} aria-label={`Borrar medidas del ${b.measured_on}`}>×</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Panel>
    </div>
  );
}
