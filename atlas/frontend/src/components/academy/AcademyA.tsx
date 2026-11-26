import { useEffect, useRef, useState } from "react";
import { academy, type Row } from "../../api/life";
import { speakText, useVoice } from "../../hooks/useVoice";
import { Stat } from "../desk/ui";
import { fmtDate, Md, State, useLoad } from "../life/kit";

export type AMeta = { categories: Record<string, string>; teachers: Row[]; coordinator: string; question_types: string[]; actions: Record<string, string>;
  settings: Row; criteria_note: string; states: Record<string, string> };
export type Go = (s: string, extra?: Record<string, string>) => void;
export const nd = (v: unknown, suf = "") => (v === null || v === undefined ? "N/D" : `${v}${suf}`);
/** Tiempo medido: en minutos mientras sea menos de una hora (sin redondear a 0 h). */
export const studyTime = (st: { hours: number; minutes_total?: number }) => ((st.minutes_total ?? st.hours * 60) < 60 ? `${Math.round((st.minutes_total ?? 0) * 10) / 10} min` : `${st.hours} h`);

/** Mide el tiempo REAL de estudio mientras la pestaña está visible y lo envía al salir (mín. 30 s). */
export function useStudyTimer(kind: string, ids: { subject_id?: number | null; course_id?: number | null; ref_id?: number | null }, active = true) {
  const acc = useRef(0);
  const last = useRef(Date.now());
  useEffect(() => {
    if (!active) return;
    last.current = Date.now();
    const tick = () => { if (document.visibilityState === "visible") acc.current += Date.now() - last.current; last.current = Date.now(); };
    const t = window.setInterval(tick, 15000);
    const vis = () => { tick(); };
    document.addEventListener("visibilitychange", vis);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", vis); tick(); flush(); };
  }, [active, ids.ref_id, ids.subject_id]); // eslint-disable-line react-hooks/exhaustive-deps
  const take = () => { if (document.visibilityState === "visible") acc.current += Date.now() - last.current; last.current = Date.now(); const m = acc.current / 60000; acc.current = 0; return Math.round(m * 10) / 10; };
  const flush = () => { const m = take(); if (m >= 0.5) void academy.post("/sessions", { kind, minutes: Math.min(240, m), ...ids }).catch(() => undefined); };
  return { take, flush };
}

/* ───────── Academy Command Center ───────── */
export function Dashboard({ go }: { go: Go }) {
  const { data: d, error, loading, reload } = useLoad<Row>("/dashboard", [], academy);
  const [goal, setGoal] = useState({ title: "", hours: "" });
  const maxMin = Math.max(1, ...((d?.stats.weekly ?? []) as Row[]).map((w) => w.minutes));
  return (
    <State loading={loading && !d} error={error}>
      {d && <div className="desk-module">
        <section className="dpanel ac-hero">
          <div><small>VISTAN ACADEMY</small><h2>{d.greeting ? `Hola, ${d.greeting}` : "Hola"}</h2>
            <p className="muted small">Nivel educativo medio: <b>{d.overall_level ? `${d.overall_level}/5` : "sin evaluar todavía"}</b> · racha {d.stats.streak} día(s) · {studyTime(d.stats)} de estudio medidos</p></div>
          <button type="button" className="btn ac-continue" onClick={() => d.continue ? (d.continue.kind === "reviews" ? go("reviews") : go("courses", { id: String(d.continue.course_id) })) : go("courses")}>
            CONTINUAR APRENDIZAJE<small>{d.continue?.label ?? "Crea tu primer curso"}</small></button>
        </section>
        <div className="stat-row">
          <Stat label="Cursos activos" value={String(d.stats.courses_active)} /><Stat label="Tiempo de aprendizaje" value={studyTime(d.stats)} />
          <Stat label="Lecciones completadas" value={String(d.stats.lessons_done)} /><Stat label="Racha" value={`${d.stats.streak} d`} />
          <Stat label="Nota media" value={nd(d.stats.avg_score, " %")} /><Stat label="Retención" value={nd(d.stats.retention_pct, " %")} hint={d.stats.retention_rule} />
          <Stat label="Repasos hoy" value={String(d.stats.due_reviews)} />
        </div>
        <div className="mod-cols">
          <section className="dpanel grow">
            <header className="dpanel-head"><span>PROGRESO SEMANAL</span><span>{d.stats.minutes_week} / {d.weekly_target.minutes} min · {d.lessons_week} / {d.weekly_target.lessons} lecciones</span></header>
            <div className="ac-week">{d.stats.weekly.map((w: Row) => <div key={w.day}><i style={{ height: `${(w.minutes / maxMin) * 100}%` }} title={`${w.minutes} min`} /><small>{new Date(w.day + "T12:00").toLocaleDateString("es-ES", { weekday: "short" })}</small></div>)}</div>
            <header className="dpanel-head"><span>CURSOS ACTIVOS</span><button type="button" className="link-btn" onClick={() => go("courses")}>todos</button></header>
            {!d.courses.length ? <p className="desk-empty">Aún no tienes cursos. Pide uno: «Quiero aprender economía desde cero».</p> : d.courses.map((c: Row) => (
              <div key={c.id} className="ac-course-row"><button type="button" className="link-btn plain" onClick={() => go("courses", { id: String(c.id) })}><b>{c.title}</b></button>
                <div className="progress-bar"><i style={{ width: `${c.progress.pct}%` }} /></div><small>{c.progress.done}/{c.progress.total} lecciones · siguiente: {c.progress.next?.title ?? "—"}</small></div>))}
            <header className="dpanel-head"><span>PRÓXIMOS EXÁMENES</span></header>
            {!d.upcoming_exams.length ? <p className="desk-empty">Ninguno pendiente.</p> : <ul className="life-list compact">{d.upcoming_exams.map((x: Row) => <li key={x.course_id}><div className="life-item">{x.title} <small>{x.course}</small></div></li>)}</ul>}
          </section>
          <section className="dpanel">
            <header className="dpanel-head"><span>RECOMENDACIONES</span></header>
            <ul className="life-list compact">{d.recommendations.map((r: Row, i: number) => <li key={i}><div className="life-item">{r.text}</div>
              {r.kind === "review" && <button type="button" className="mini-btn" onClick={() => go("reviews")}>Repasar</button>}
              {r.kind === "continue" && <button type="button" className="mini-btn" onClick={() => go("courses", { id: String(r.course_id) })}>Continuar</button>}
              {r.kind === "remediate" && <button type="button" className="mini-btn" onClick={() => go("reviews")}>Reforzar</button>}</li>)}</ul>
            <header className="dpanel-head"><span>OBJETIVOS EDUCATIVOS</span></header>
            {d.goals.map((g: Row) => <p key={g.id} className="small">{g.title} <small>{g.current}/{g.target ?? "—"} {g.unit ?? ""}{g.deadline ? ` · ${fmtDate(g.deadline)}` : ""}</small></p>)}
            <form className="filters" onSubmit={(e) => { e.preventDefault(); void academy.post("/goals", { title: goal.title, target_hours: goal.hours ? Number(goal.hours) : null }).then(() => { setGoal({ title: "", hours: "" }); reload(); }); }}>
              <input value={goal.title} onChange={(e) => setGoal({ ...goal, title: e.target.value })} placeholder="Nuevo objetivo" aria-label="Nuevo objetivo educativo" minLength={3} required />
              <input type="number" value={goal.hours} onChange={(e) => setGoal({ ...goal, hours: e.target.value })} placeholder="horas" aria-label="Horas objetivo" min={1} />
              <button type="submit" className="btn ghost">Añadir</button></form>
            {d.gamification && <><header className="dpanel-head"><span>NIVEL {d.gamification.level} · {d.gamification.xp} XP</span></header>
              <div className="progress-bar"><i style={{ width: `${Math.min(100, (d.gamification.xp / d.gamification.next_level_xp) * 100)}%` }} /></div>
              <p className="d-tags">{d.gamification.badges.map((b: string) => <span key={b} className="lab-tag t-commercial">{b}</span>)}</p>
              <details className="small"><summary>Cómo se calcula el XP</summary><ul>{Object.entries(d.gamification.breakdown as Record<string, number>).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul></details></>}
            <header className="dpanel-head"><span>ACTIVIDAD RECIENTE</span></header>
            {!d.recent.length ? <p className="desk-empty">Sin actividad todavía.</p> : <ul className="life-list compact">{d.recent.map((r: Row, i: number) => <li key={i}><div className="life-item"><small>{fmtDate(r.at)}</small> {r.summary}</div></li>)}</ul>}
          </section>
        </div>
      </div>}
    </State>
  );
}

/* ───────── Academy Library ───────── */
export function Library({ meta, go }: { meta: AMeta; go: Go }) {
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const list = useLoad<Row[]>(`/library?${new URLSearchParams(Object.entries({ category: cat, q }).filter(([, v]) => v) as [string, string][])}`, [cat, q], academy);
  const [sel, setSel] = useState<number | null>(null);
  const [neu, setNeu] = useState({ name: "", category: "tecnologia" });
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Academy Library</h2><p className="muted small">Disciplinas en 9 áreas (ampliable). Elige una para ver tu nivel real, sus conceptos y estudiar con su profesor.</p></div>
      <div className="filters"><select value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Área"><option value="">Todas las áreas</option>{Object.entries(meta.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar disciplina" aria-label="Buscar disciplina" /></div>
      <State loading={list.loading && !list.data} error={list.error}>
        {Object.entries(meta.categories).filter(([k]) => !cat || k === cat).map(([k, label]) => {
          const items = list.data?.filter((s) => s.category === k) ?? [];
          return items.length ? <section key={k} className="dpanel"><header className="dpanel-head"><span>{label.toUpperCase()}</span><span>{items.length}</span></header>
            <div className="ac-grid">{items.map((s) => <button type="button" key={s.id} className={`ac-subject ${sel === s.id ? "on" : ""}`} onClick={() => setSel(sel === s.id ? null : s.id)}>
              <b>{s.name}</b><small>{s.lessons_done ? `${s.lessons_done} lecciones · ` : ""}{s.concepts ? `${s.concepts} conceptos` : "sin empezar"}{s.custom ? " · propia" : ""}</small></button>)}</div>
            {items.some((s) => s.id === sel) && <SubjectPanel id={sel!} go={go} onDeleted={() => { setSel(null); list.reload(); }} />}</section> : null;
        })}
      </State>
      <section className="dpanel"><header className="dpanel-head"><span>AÑADIR DISCIPLINA</span></header>
        <form className="filters" onSubmit={(e) => { e.preventDefault(); academy.post("/library", neu).then(() => { setNeu({ ...neu, name: "" }); setMsg("Disciplina añadida"); list.reload(); }).catch((x: Error) => setMsg(x.message)); }}>
          <input value={neu.name} onChange={(e) => setNeu({ ...neu, name: e.target.value })} placeholder="Nombre de la disciplina" aria-label="Nombre de la disciplina" required minLength={2} />
          <select value={neu.category} onChange={(e) => setNeu({ ...neu, category: e.target.value })} aria-label="Área de la disciplina">{Object.entries(meta.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <button type="submit" className="btn ghost">Añadir</button></form>{msg && <p className="small">{msg}</p>}</section>
    </div>
  );
}

function SubjectPanel({ id, go, onDeleted }: { id: number; go: Go; onDeleted: () => void }) {
  const { data: d } = useLoad<Row>(`/subjects/${id}`, [id], academy);
  if (!d) return <p className="small">Cargando…</p>;
  const m = d.mastery;
  return (
    <div className="ac-subject-panel">
      <p className="small"><b>{d.subject.name}</b> · Nivel: <b>{m.label}</b>{m.avg != null ? ` (media ${m.avg} %)` : ""} · Profesor: {d.teachers.join(" + ")}</p>
      <p className="mini-note">{m.rule}</p>
      {d.disclaimer && <p className="warn-line l-warn">{d.disclaimer}</p>}
      {!!d.concepts.length && <p className="d-tags">{d.concepts.slice(0, 16).map((c: Row) => <span key={c.id} className={`lab-tag ac-st-${c.state}`} title={`${c.state_label} · ${c.mastery}`}>{c.name}</span>)}</p>}
      <div className="row-actions wrap">
        <button type="button" className="mini-btn" onClick={() => go("courses", { subject: String(id) })}>Crear curso</button>
        <button type="button" className="mini-btn ghost" onClick={() => go("tutor", { subject: String(id) })}>Hablar con el profesor</button>
        <button type="button" className="mini-btn ghost" onClick={() => go("exams", { subject: String(id) })}>Examinarme</button>
        {d.subject.custom && <button type="button" className="mini-btn ghost" onClick={() => void academy.del(`/library/${id}`).then(onDeleted)}>Eliminar</button>}
      </div>
    </div>
  );
}

export function SubjectPick({ value, onChange }: { value: number | null; onChange: (v: number) => void }) {
  const list = useLoad<Row[]>("/library", [], academy);
  return <select value={value ?? ""} onChange={(e) => onChange(Number(e.target.value))} aria-label="Materia"><option value="" disabled>Elige materia</option>
    {list.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>;
}

/* ───────── AI Teacher (texto y voz) ───────── */
export function Tutor({ meta, initialSubject, lessonId }: { meta: AMeta; initialSubject: number | null; lessonId?: number }) {
  const [sid, setSid] = useState<number | null>(initialSubject);
  const [log, setLog] = useState<{ role: string; content: string; meta?: string }[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const autoplay = !!meta.settings.voice_autoplay;
  const send = (question: string | null, action?: string) => {
    if (!sid || busy || (!question?.trim() && !action)) return;
    setBusy(true); setQ("");
    setLog((l) => [...l, { role: "user", content: action ? `${meta.actions[action]}${question ? ` (${question})` : ""}` : question! }]);
    academy.post<{ answer: string; model: string; teachers: string[] }>("/tutor", { subject_id: sid, question: question || null, action: action || null, lesson_id: lessonId ?? null })
      .then((r) => { setLog((l) => [...l, { role: "assistant", content: r.answer, meta: `${r.teachers.join(" + ")} · ${r.model}` }]); if (autoplay) speakText(r.answer); })
      .catch((e: Error) => setLog((l) => [...l, { role: "assistant", content: `⚠ ${e.message}` }])).finally(() => setBusy(false));
  };
  const voice = useVoice((t) => send(t), busy);
  useStudyTimer("tutor", { subject_id: sid }, !!sid);
  useEffect(() => { if (sid) academy.get<Row[]>(`/tutor/history?${lessonId ? `lesson_id=${lessonId}` : `subject_id=${sid}`}`).then((h) => setLog((h as unknown as Row[]).map((m) => ({ role: m.role, content: m.content, meta: m.teacher ?? undefined })))); }, [sid, lessonId]);
  return (
    <div className={lessonId ? "" : "desk-module"}>
      {!lessonId && <div className="mod-head"><h2>AI Teacher Engine</h2><p className="muted small">El {meta.coordinator} elige al profesor especializado (y un colaborador si mezclas disciplinas).
        Conoce tu nivel, tus errores frecuentes y tu ritmo. Puedes hablarle: la voz se procesa en tu navegador y no se guardan grabaciones.</p></div>}
      {!lessonId && <div className="filters"><SubjectPick value={sid} onChange={setSid} /></div>}
      <div className="quick ac-actions">{Object.keys(meta.actions).map((k) => <button type="button" key={k} className="chip" disabled={!sid || busy} onClick={() => send(q || null, k)}>{meta.actions[k].split(/[.,]/)[0]}</button>)}</div>
      <section className="tutor agent-full"><div className="tutor-log">
        {!log.length && <p className="desk-empty">{sid ? "Pregunta lo que quieras o usa un botón." : "Elige una materia para empezar."}</p>}
        {log.map((m, i) => <div key={i} className={`tmsg ${m.role}`}><div className="tbody"><Md text={m.content} /></div>
          {m.role === "assistant" && <small>{m.meta} {voice.canSpeak && <button type="button" className="link-btn" onClick={() => speakText(m.content)}>🔊 escuchar</button>}</small>}</div>)}
        {busy && <div className="tmsg assistant"><div className="tbody"><p className="muted">El profesor está preparando la respuesta…</p></div></div>}</div>
        <form className="tutor-in" onSubmit={(e) => { e.preventDefault(); send(q); }}>
          <input value={voice.listening ? voice.interim || "Escuchando…" : q} onChange={(e) => setQ(e.target.value)} placeholder="Pregunta al profesor…" aria-label="Pregunta al profesor" maxLength={4000} disabled={!sid} />
          {voice.canListen && <button type="button" className={`btn ghost ${voice.listening ? "on" : ""}`} aria-label="Hablar" disabled={!sid || busy} onClick={() => voice.listening ? voice.stopListening() : voice.listen()}>🎤</button>}
          <button type="submit" className="btn" disabled={busy || !q.trim() || !sid}>Preguntar</button></form></section>
      {!voice.canListen && !lessonId && <p className="mini-note">Este navegador no ofrece reconocimiento de voz; puedes escribir. La corrección de pronunciación no está disponible: el reconocimiento del navegador no la evalúa.</p>}
    </div>
  );
}
