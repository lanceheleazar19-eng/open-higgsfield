import { useEffect, useState } from "react";
import { academy, makeClient, type Row } from "../../api/life";
import { Stat } from "../desk/ui";
import { fmtDate, Md, State, useLoad } from "../life/kit";
import { type AMeta, nd, SubjectPick, Tutor, useStudyTimer } from "./AcademyA";

const core = makeClient("/api");
const SECTIONS: [string, string][] = [["introduccion", "Introducción"], ["teoria", "Explicación"], ["conceptos", "Conceptos"], ["ejemplos", "Ejemplos"],
  ["aplicaciones", "Aplicaciones reales"], ["errores_frecuentes", "Errores frecuentes"], ["resumen", "Resumen"], ["preguntas_comprension", "Comprensión"],
  ["ejercicios", "Ejercicios"], ["evaluacion", "Evaluación"]];

/* ───────── Course Builder ───────── */
export function Courses({ meta, initial, initialSubject }: { meta: AMeta; initial: number | null; initialSubject: number | null }) {
  const list = useLoad<Row[]>("/courses", [], academy);
  const projects = useLoad<Row[]>("/projects", [], core);
  const [sel, setSel] = useState<number | null>(initial);
  const [req, setReq] = useState("");
  const [sid, setSid] = useState<number | null>(initialSubject);
  const [pid, setPid] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Course Builder</h2><p className="muted small">Describe lo que quieres aprender: se crea un curso con objetivos, módulos, lecciones, duración, exámenes,
        proyecto final y criterios de evaluación. Puedes vincularlo a un proyecto real de VISTAN para que los ejemplos sean sobre él.</p></div>
      <section className="dpanel"><form className="life-form" onSubmit={(e) => { e.preventDefault(); setBusy(true); setMsg(null);
        academy.post("/courses", { request: req, subject_id: sid, project_id: pid ? Number(pid) : null }).then((c) => { setSel(c.id); setReq(""); list.reload(); })
          .catch((x: Error) => setMsg(x.message)).finally(() => setBusy(false)); }}>
        <label className="wide"><span>¿Qué quieres aprender? *</span><textarea rows={2} value={req} onChange={(e) => setReq(e.target.value)} required minLength={6}
          placeholder="Quiero aprender economía desde cero hasta tener conocimientos avanzados" aria-label="Qué quieres aprender" /></label>
        <label><span>Materia (opcional)</span><SubjectPick value={sid} onChange={setSid} /></label>
        <label><span>Proyecto real (opcional)</span><select value={pid} onChange={(e) => setPid(e.target.value)} aria-label="Proyecto vinculado"><option value="">Ninguno</option>
          {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <div className="wide row-btns"><button type="submit" className="btn" disabled={busy}>{busy ? "Diseñando el curso…" : "Crear curso"}</button></div>
      </form>{msg && <p className="error-line" role="alert">{msg}</p>}</section>
      <div className="mod-cols">
        <section className="dpanel meta-runs"><State loading={list.loading && !list.data} error={list.error} empty={list.data && !list.data.length ? "Aún no hay cursos." : false}>
          <ul className="exp-list">{list.data?.map((c) => <li key={c.id}><button type="button" className={sel === c.id ? "on" : ""} onClick={() => setSel(c.id)}>
            <span className={`exp-state s-${c.status === "active" ? "RUNNING" : c.status === "completed" ? "COMPLETED" : "PAUSED"}`}>{c.status}</span><b>{c.title}</b>
            <small>{c.progress.done}/{c.progress.total} lecciones · {c.progress.pct}%</small></button></li>)}</ul></State></section>
        {sel ? <CourseView key={sel} id={sel} meta={meta} onChange={list.reload} onDeleted={() => { setSel(null); list.reload(); }} /> : <section className="dpanel grow"><p className="desk-empty">Crea o elige un curso.</p></section>}
      </div>
    </div>
  );
}

function CourseView({ id, meta, onChange, onDeleted }: { id: number; meta: AMeta; onChange: () => void; onDeleted: () => void }) {
  const { data: c, reload } = useLoad<Row>(`/courses/${id}`, [id], academy);
  const [lesson, setLesson] = useState<number | null>(null);
  const [exam, setExam] = useState<Row | null>(null);
  const [edit, setEdit] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  if (!c) return <section className="dpanel grow"><State loading error={null} /></section>;
  const open = (mi: number, li: number) => { setBusy(`${mi}-${li}`); setMsg(null);
    academy.post(`/courses/${id}/lessons/${mi}/${li}`).then((x) => setLesson(x.id)).catch((e: Error) => setMsg(e.message)).finally(() => setBusy(null)); };
  const mkExam = (kind: string, mi?: number) => { setBusy(kind); setMsg(null);
    academy.post("/exams", { course_id: id, kind, module_idx: mi ?? null, n: 6 }).then(setExam).catch((e: Error) => setMsg(e.message)).finally(() => setBusy(null)); };
  const patch = (v: Row) => academy.patch(`/courses/${id}`, v).then(() => { reload(); onChange(); }).catch((e: Error) => setMsg(e.message));
  if (lesson) return <LessonPlayer id={lesson} meta={meta} onClose={() => { setLesson(null); reload(); onChange(); }} />;
  if (exam) return <section className="dpanel grow"><ExamTaker exam={exam} onClose={() => { setExam(null); reload(); onChange(); }} /></section>;
  const p = c.progress;
  return (
    <section className="dpanel grow" data-testid="course-view">
      <header className="dpanel-head"><span>{c.title.toUpperCase()}</span><span className="row-actions">
        {p.next && !p.next.exam && <button type="button" className="mini-btn" disabled={!!busy} onClick={() => open(p.next.module, p.next.lesson)}>Continuar</button>}
        {c.status === "active" ? <button type="button" className="mini-btn ghost" onClick={() => patch({ status: "paused" })}>Pausar</button>
          : c.status === "paused" && <button type="button" className="mini-btn ghost" onClick={() => patch({ status: "active" })}>Reanudar</button>}
        <button type="button" className="mini-btn ghost" onClick={() => setEdit(!edit)}>{edit ? "Cerrar edición" : "Editar"}</button>
        <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar el curso? Las lecciones y evaluaciones se conservan en la materia.")) void academy.del(`/courses/${id}`).then(onDeleted); }}>✕</button>
      </span></header>
      <p className="small">{c.description}</p>
      <div className="stat-row"><Stat label="Progreso" value={`${p.pct}%`} /><Stat label="Nivel inicial" value={`${c.level_start}/5`} /><Stat label="Duración estimada" value={`${c.est_hours} h`} />
        <Stat label="Examen final" value={nd(p.final_score, " %")} /></div>
      {c.disclaimer && <p className="warn-line l-warn">{c.disclaimer}</p>}
      {msg && <p className="error-line">{msg}</p>}
      {!!c.goals?.length && <div className="sc-block"><h4>Objetivos</h4><ul>{c.goals.map((g: string) => <li key={g}>{g}</li>)}</ul></div>}
      {edit ? <CourseEditor modules={c.modules} onSave={(mods) => patch({ modules: mods }).then(() => setEdit(false))} />
        : c.modules.map((m: Row, mi: number) => (
          <div key={mi} className="ac-module"><h4>Módulo {mi + 1}. {m.title}</h4><p className="mini-note">{m.objective}</p>
            <ol>{m.lessons.map((l: Row, li: number) => { const st = p.lessons[`${mi}-${li}`]; return (
              <li key={li} className={st?.done ? "done" : ""}><button type="button" className="link-btn plain" disabled={!!busy} onClick={() => open(mi, li)}>{st?.done ? "✓ " : ""}{l.title}</button>
                <small> {l.minutes} min{busy === `${mi}-${li}` ? " · generando…" : st ? "" : " · se genera al abrirla"}</small></li>); })}</ol>
            <button type="button" className="mini-btn ghost" disabled={!!busy} onClick={() => mkExam("module", mi)}>Examen del módulo{p.module_exams[mi] != null ? ` (mejor: ${p.module_exams[mi]} %)` : ""}</button>
          </div>))}
      <div className="sc-block"><h4>Proyecto final</h4><p className="small">{c.final_project || "—"}</p></div>
      <div className="sc-block"><h4>Criterios de evaluación</h4><ul>{c.criteria.map((x: string) => <li key={x}>{x}</li>)}</ul></div>
      <button type="button" className="btn" disabled={!!busy} onClick={() => mkExam("final")}>{busy === "final" ? "Preparando…" : "Evaluación final"}</button>
    </section>
  );
}

function CourseEditor({ modules, onSave }: { modules: Row[]; onSave: (m: Row[]) => void }) {
  const [mods, setMods] = useState<Row[]>(JSON.parse(JSON.stringify(modules)));
  const mv = (mi: number, li: number, d: number) => { const m = [...mods]; const ls = [...m[mi].lessons]; const j = li + d; if (j < 0 || j >= ls.length) return; [ls[li], ls[j]] = [ls[j], ls[li]]; m[mi] = { ...m[mi], lessons: ls }; setMods(m); };
  return (
    <div className="ac-editor">{mods.map((m, mi) => <div key={mi} className="ac-module">
      <input value={m.title} onChange={(e) => setMods(mods.map((x, i) => (i === mi ? { ...x, title: e.target.value } : x)))} aria-label={`Módulo ${mi + 1}`} />
      {m.lessons.map((l: Row, li: number) => <div key={li} className="filters">
        <input value={l.title} onChange={(e) => setMods(mods.map((x, i) => (i === mi ? { ...x, lessons: x.lessons.map((y: Row, j: number) => (j === li ? { ...y, title: e.target.value } : y)) } : x)))} aria-label="Lección" />
        <button type="button" className="mini-btn ghost" onClick={() => mv(mi, li, -1)} aria-label="Subir">↑</button><button type="button" className="mini-btn ghost" onClick={() => mv(mi, li, 1)} aria-label="Bajar">↓</button>
        <button type="button" className="mini-btn ghost" onClick={() => setMods(mods.map((x, i) => (i === mi ? { ...x, lessons: x.lessons.filter((_: Row, j: number) => j !== li) } : x)))} aria-label="Quitar lección">✕</button></div>)}
      <button type="button" className="link-btn" onClick={() => setMods(mods.map((x, i) => (i === mi ? { ...x, lessons: [...x.lessons, { title: "Nueva lección", objective: "", minutes: 30 }] } : x)))}>+ lección</button>
    </div>)}
      <div className="row-btns"><button type="button" className="link-btn" onClick={() => setMods([...mods, { title: "Nuevo módulo", objective: "", lessons: [{ title: "Primera lección", objective: "", minutes: 30 }] }])}>+ módulo</button>
        <button type="button" className="btn" onClick={() => onSave(mods)}>Guardar estructura</button></div></div>
  );
}

/* ───────── Lesson Engine ───────── */
export function LessonPlayer({ id, meta, onClose }: { id: number; meta: AMeta; onClose: () => void }) {
  const { data: x, reload } = useLoad<Row>(`/lessons/${id}`, [id], academy);
  const [sec, setSec] = useState(0);
  const [reveal, setReveal] = useState<Record<number, boolean>>({});
  const [ans, setAns] = useState<(number | null)[]>([]);
  const [check, setCheck] = useState<Row | null>(null);
  const [ask, setAsk] = useState(false);
  const timer = useStudyTimer("lesson", { subject_id: x?.subject_id, course_id: x?.course_id, ref_id: id }, !!x);
  useEffect(() => { if (x) { setSec(Math.min(SECTIONS.length - 1, x.progress?.section ?? 0)); setAns(((x.content?.evaluacion ?? []) as Row[]).map(() => null)); } }, [x?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!x) return <section className="dpanel grow"><State loading error={null} /></section>;
  const c = x.content ?? {};
  const avail = SECTIONS.filter(([k]) => (Array.isArray(c[k]) ? c[k].length : c[k]));
  const goTo = (i: number) => { setSec(i); void academy.patch(`/lessons/${id}/progress`, { section: i, seen: avail.slice(0, i + 1).map(([k]) => k) }); };
  const [key, label] = avail[Math.min(sec, avail.length - 1)] ?? ["teoria", "Explicación"];
  const body = () => {
    const v = c[key];
    if (key === "conceptos") return <dl className="opp-dl">{v.map((t: Row) => <div key={t.termino}><dt>{t.termino}</dt><dd>{t.definicion}</dd></div>)}</dl>;
    if (key === "preguntas_comprension") return <ol>{v.map((p: Row, i: number) => <li key={i}>{p.pregunta} <button type="button" className="link-btn" onClick={() => setReveal({ ...reveal, [i]: !reveal[i] })}>{reveal[i] ? "ocultar" : "ver respuesta"}</button>{reveal[i] && <p className="small ac-ans">{p.respuesta}</p>}</li>)}</ol>;
    if (key === "evaluacion") return <div>{v.map((q: Row, i: number) => <div key={i} className="ac-q"><p><b>{i + 1}.</b> {q.q}</p>
      {q.options.map((o: string, j: number) => <label key={j} className={`check ${check ? (check.results[i].answer === j ? "ok" : ans[i] === j ? "bad" : "") : ""}`}>
        <input type="radio" name={`q${i}`} checked={ans[i] === j} disabled={!!check} onChange={() => setAns(ans.map((a, k) => (k === i ? j : a)))} /> {o}</label>)}
      {check && <p className="mini-note">{check.results[i].correct ? "✓ Correcta" : "✗ Incorrecta"} · {check.results[i].explanation}</p>}</div>)}
      {!check ? <button type="button" className="btn" disabled={ans.some((a) => a === null)} onClick={() => academy.post(`/lessons/${id}/check`, { answers: ans }).then((r) => { setCheck(r); reload(); })}>Corregir</button>
        : <p className="small">Resultado: <b>{check.score} %</b> · tu dominio de cada concepto se ha actualizado.</p>}</div>;
    if (Array.isArray(v)) return <ul>{v.map((t: string, i: number) => <li key={i}><Md text={t} /></li>)}</ul>;
    return <Md text={v} />;
  };
  return (
    <section className="dpanel grow ac-lesson" data-testid="lesson-player">
      <header className="dpanel-head"><span>{(c.titulo || x.topic).toUpperCase()}</span><span className="row-actions">
        <button type="button" className="mini-btn ghost" onClick={() => setAsk(!ask)}>{ask ? "Cerrar preguntas" : "Preguntar al profesor"}</button>
        <button type="button" className="mini-btn ghost" onClick={() => { timer.flush(); onClose(); }}>Salir (se guarda dónde te quedas)</button></span></header>
      <p className="mini-note">{x.subject} · nivel {x.level}/5 · {(c.teacher ?? []).join(" + ")} · contenido generado por IA: puede contener errores, contrástalo.</p>
      {c.disclaimer && <p className="warn-line l-warn">{c.disclaimer}</p>}
      {!!c.aprenderas?.length && sec === 0 && <div className="sc-block facts"><h4>Qué aprenderás</h4><ul>{c.aprenderas.map((a: string) => <li key={a}>{a}</li>)}</ul></div>}
      <nav className="ac-steps">{avail.map(([k, l], i) => <button type="button" key={k} className={i === sec ? "on" : i < sec ? "seen" : ""} onClick={() => goTo(i)}>{l}</button>)}</nav>
      <div className="ac-section"><h3>{label}</h3>{body()}
        {key === "teoria" && c.tabla && <Md text={c.tabla} />}
        {key === "teoria" && c.diagrama && <pre className="arena-out">{c.diagrama}</pre>}
        {key === "ejemplos" && c.codigo && <pre className="arena-out">{c.codigo}</pre>}</div>
      <div className="row-btns">
        <button type="button" className="btn ghost" disabled={sec === 0} onClick={() => goTo(sec - 1)}>Anterior</button>
        {sec < avail.length - 1 ? <button type="button" className="btn" onClick={() => goTo(sec + 1)}>Siguiente</button>
          : <button type="button" className="btn" onClick={() => academy.post(`/lessons/${id}/complete`, { minutes: timer.take() }).then(onClose)}>{x.completed_at ? "Volver" : "Completar lección"}</button>}
      </div>
      {c.video_search && <p className="mini-note">¿Prefieres vídeo? <a href={c.video_search} target="_blank" rel="noreferrer noopener">Buscar vídeos sobre este tema ↗</a> (búsqueda externa: VISTAN no recomienda vídeos concretos que no ha verificado).</p>}
      {ask && <Tutor meta={meta} initialSubject={x.subject_id} lessonId={id} />}
    </section>
  );
}

/* ───────── Examination Engine ───────── */
export function ExamTaker({ exam, onClose }: { exam: Row; onClose: () => void }) {
  const [ans, setAns] = useState<unknown[]>(exam.questions.map((q: Row) => (q.type === "code" ? (q.template ?? "") : null)));
  const [res, setRes] = useState<Row | null>(exam.score != null ? exam : null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const timer = useStudyTimer("exam", { subject_id: exam.subject_id, course_id: exam.course_id, ref_id: exam.id }, !res);
  const set = (i: number, v: unknown) => setAns(ans.map((a, k) => (k === i ? v : a)));
  const fb = res?.feedback;
  return (
    <div className="ac-exam" data-testid="exam-taker">
      <header className="dpanel-head"><span>{({ quiz: "Test", exam: "Examen", module: "Examen de módulo", final: "Evaluación final", review: "Repaso", critical: "Pensamiento crítico" } as Record<string, string>)[exam.kind] ?? exam.kind} · dificultad {exam.difficulty}/5</span>
        <button type="button" className="mini-btn ghost" onClick={onClose}>Cerrar</button></header>
      {exam.questions.map((q: Row, i: number) => { const r = fb?.results?.[i]; return (
        <div key={i} className={`ac-q ${r ? (r.correct ? "ok" : r.score > 0 ? "partial" : "bad") : ""}`}>
          <p><b>{i + 1}.</b> {q.q} <small>({q.type === "mcq" ? "test" : q.type === "tf" ? "V/F" : q.type === "numeric" ? "numérica" : q.type === "code" ? "código" : q.type === "case" ? "caso práctico" : "abierta"} · {q.topic})</small></p>
          {q.type === "mcq" && q.options.map((o: string, j: number) => <label key={j} className="check"><input type="radio" name={`e${i}`} disabled={!!res} checked={(res ? res.answers?.[i] : ans[i]) === j} onChange={() => set(i, j)} /> {o}</label>)}
          {q.type === "tf" && [true, false].map((v) => <label key={String(v)} className="check"><input type="radio" name={`e${i}`} disabled={!!res} checked={(res ? res.answers?.[i] : ans[i]) === v} onChange={() => set(i, v)} /> {v ? "Verdadero" : "Falso"}</label>)}
          {q.type === "numeric" && <input value={String((res ? res.answers?.[i] : ans[i]) ?? "")} disabled={!!res} onChange={(e) => set(i, e.target.value)} aria-label={`Respuesta ${i + 1}`} placeholder="Resultado" />}
          {(q.type === "open" || q.type === "case") && <><textarea rows={4} value={String((res ? res.answers?.[i] : ans[i]) ?? "")} disabled={!!res} onChange={(e) => set(i, e.target.value)} aria-label={`Respuesta ${i + 1}`} />
            {!res && <p className="mini-note">Criterios: {q.criteria?.map((c: Row) => `${c.criterio} (${c.puntos} p)`).join(" · ")}</p>}</>}
          {q.type === "code" && <><pre className="mini-note">{q.tests}</pre><textarea className="code" rows={8} value={String((res ? res.answers?.[i] : ans[i]) ?? "")} disabled={!!res} onChange={(e) => set(i, e.target.value)} aria-label={`Código ${i + 1}`} spellCheck={false} /></>}
          {r && <div className="ac-fb"><b>{r.score} %</b>{r.explanation && <span> · {r.explanation}</span>}{r.feedback && <span> · {r.feedback}</span>}
            {r.answer !== undefined && r.answer !== null && q.type !== "open" && q.type !== "case" && <span> · Respuesta correcta: {q.type === "mcq" ? q.options?.[r.answer] ?? r.answer : String(r.answer)}</span>}
            {r.criteria && <ul>{r.criteria.map((c: Row) => <li key={c.criterio}>{c.cumple ? "✓" : c.cumple === false ? "✗" : "?"} {c.criterio} ({c.puntos} p){c.porque ? ` — ${c.porque}` : ""}</li>)}</ul>}
            {(q.type === "open" || q.type === "case") && r.answer && <details><summary>Respuesta modelo</summary><p className="small">{r.answer}</p></details>}</div>}
        </div>); })}
      {err && <p className="error-line">{err}</p>}
      {!res ? <button type="button" className="btn" disabled={busy || ans.some((a, i) => a === null && ["mcq", "tf"].includes(exam.questions[i].type))}
        onClick={() => { setBusy(true); setErr(null); academy.post(`/exams/${exam.id}/submit`, { answers: ans.map((a) => a ?? ""), minutes: timer.take() }).then(setRes).catch((e: Error) => setErr(e.message)).finally(() => setBusy(false)); }}>
        {busy ? "Corrigiendo…" : "Entregar y corregir"}</button> : (
        <div className="stat-row">
          <Stat label="Nota" value={`${fb.grade_10}/10`} /><Stat label="Aciertos" value={`${res.score} %`} /><Stat label="Correctas" value={String(fb.correct)} /><Stat label="Incorrectas" value={String(fb.incorrect)} />
          <Stat label="Evolución" value={res.evolution == null ? (fb.previous == null ? "primera" : `${Math.round((res.score - fb.previous) * 10) / 10} pts`) : `${res.evolution > 0 ? "+" : ""}${res.evolution} pts`} />
        </div>)}
      {fb && <p className="small">Dominados: {fb.mastered_topics?.join(", ") || "—"} · Pendientes: {fb.weak_topics?.join(", ") || "—"}{fb.pending_ai ? " · alguna respuesta abierta no se pudo corregir con IA" : ""}</p>}
      {fb && <p className="mini-note">{exam.criteria?.note ?? ""} Un único examen no consolida un concepto: se programan repasos espaciados.</p>}
    </div>
  );
}

export function Exams({ meta, initialSubject }: { meta: AMeta; initialSubject: number | null }) {
  const [sid, setSid] = useState<number | null>(initialSubject);
  const list = useLoad<Row[]>(`/exams${sid ? `?subject_id=${sid}` : ""}`, [sid], academy);
  const [cfg, setCfg] = useState({ kind: "quiz", difficulty: "", n: 6, types: ["mcq", "tf", "numeric", "open"] as string[], topics: "" });
  const [exam, setExam] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (exam) return <div className="desk-module"><section className="dpanel"><ExamTaker exam={exam} onClose={() => { setExam(null); list.reload(); }} /></section></div>;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Examination Engine</h2><p className="muted small">Test, verdadero/falso, numéricas, abiertas, casos y código (corregido con tests en el sandbox). La dificultad se adapta a tu nivel.
        {" "}{meta.criteria_note}</p></div>
      <section className="dpanel"><div className="filters">
        <SubjectPick value={sid} onChange={setSid} />
        <select value={cfg.kind} onChange={(e) => setCfg({ ...cfg, kind: e.target.value })} aria-label="Tipo de evaluación"><option value="quiz">Test rápido</option><option value="exam">Examen</option></select>
        <select value={cfg.difficulty} onChange={(e) => setCfg({ ...cfg, difficulty: e.target.value })} aria-label="Dificultad"><option value="">Dificultad adaptativa</option>{[1, 2, 3, 4, 5].map((d) => <option key={d} value={d}>{d}/5</option>)}</select>
        <input value={cfg.topics} onChange={(e) => setCfg({ ...cfg, topics: e.target.value })} placeholder="Temas (separados por comas, opcional)" aria-label="Temas" />
        <input type="number" min={2} max={15} value={cfg.n} onChange={(e) => setCfg({ ...cfg, n: Number(e.target.value) })} aria-label="Número de preguntas" /></div>
        <div className="filters">{meta.question_types.map((t) => <label key={t} className="check"><input type="checkbox" checked={cfg.types.includes(t)} onChange={(e) => setCfg({ ...cfg, types: e.target.checked ? [...cfg.types, t] : cfg.types.filter((x) => x !== t) })} /> {({ mcq: "Test", tf: "V/F", numeric: "Numéricas", open: "Abiertas", case: "Casos prácticos", code: "Código" } as Record<string, string>)[t]}</label>)}</div>
        <button type="button" className="btn" disabled={!sid || busy || !cfg.types.length} onClick={() => { setBusy(true); setErr(null);
          academy.post("/exams", { subject_id: sid, kind: cfg.kind, difficulty: cfg.difficulty ? Number(cfg.difficulty) : null, n: cfg.n, types: cfg.types, topics: cfg.topics.split(",").map((x) => x.trim()).filter(Boolean) })
            .then(setExam).catch((e: Error) => setErr(e.message)).finally(() => setBusy(false)); }}>{busy ? "Preparando preguntas…" : "Empezar"}</button>
        {err && <p className="error-line">{err}</p>}</section>
      <section className="dpanel"><header className="dpanel-head"><span>HISTORIAL</span></header>
        <State loading={list.loading && !list.data} error={list.error} empty={list.data && !list.data.length ? "Sin evaluaciones." : false}>
          <table className="dtable compact"><thead><tr><th>Fecha</th><th>Materia</th><th>Tipo</th><th>Dif.</th><th>Nota</th><th /></tr></thead>
            <tbody>{list.data?.map((a) => <tr key={a.id}><td>{fmtDate(a.created_at)}</td><td>{a.subject}</td><td>{a.kind}</td><td>{a.difficulty}</td><td className="mono">{a.score != null ? `${a.score} %` : "sin entregar"}</td>
              <td><button type="button" className="mini-btn ghost" onClick={() => academy.get(`/exams/${a.id}`).then(setExam)}>{a.score != null ? "Ver" : "Continuar"}</button></td></tr>)}</tbody></table>
        </State></section>
    </div>
  );
}

/* ───────── Adaptive Learning: repasos espaciados ───────── */
export function Reviews() {
  const { data: d, error, loading, reload } = useLoad<Row>("/reviews", [], academy);
  const [exam, setExam] = useState<Row | null>(null);
  const [rem, setRem] = useState<Row | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (exam) return <div className="desk-module">{rem && <section className="dpanel"><header className="dpanel-head"><span>EXPLICACIÓN ALTERNATIVA</span></header>
    <p className="small"><b>Patrón detectado:</b> {rem.pattern}</p><Md text={rem.explanation} /><ul className="small">{rem.keys.map((k: string) => <li key={k}>{k}</li>)}</ul></section>}
    <section className="dpanel"><ExamTaker exam={exam} onClose={() => { setExam(null); setRem(null); reload(); }} /></section></div>;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Adaptive Learning · Repasos</h2><p className="muted small">Repetición espaciada: cada concepto vuelve justo cuando empiezas a olvidarlo. Un concepto solo se consolida con al menos 3 aciertos
        separados en el tiempo (≥ 7 días). Si fallas varias veces, el profesor identifica el patrón, lo explica de otra forma y te vuelve a evaluar.</p></div>
      <State loading={loading && !d} error={error}>
        {d && <>
          <section className="dpanel"><header className="dpanel-head"><span>PARA HOY ({d.due.length})</span><span className="row-actions">
            <button type="button" className="mini-btn" disabled={!d.due.length || busy} onClick={() => { setBusy(true); academy.post("/reviews/start").then(setExam).catch((e: Error) => setMsg(e.message)).finally(() => setBusy(false)); }}>{busy ? "Preparando…" : "Empezar repaso"}</button>
            <button type="button" className="mini-btn ghost" onClick={() => academy.post("/reviews/schedule").then((r) => setMsg(`${r.created} recordatorio(s) creados en Tareas`))}>Programar en Tareas</button></span></header>
            {!d.due.length ? <p className="desk-empty">Nada pendiente hoy.</p> : <ul className="life-list compact">{d.due.map((c: Row) => <li key={c.id}><div className="life-item">{c.name} <small>{c.subject} · dominio {c.mastery} · {c.state_label}</small></div></li>)}</ul>}
            {msg && <p className="small">{msg}</p>}</section>
          {!!d.patterns.length && <section className="dpanel"><header className="dpanel-head"><span>ERRORES REPETIDOS</span></header>
            <ul className="life-list compact">{d.patterns.map((c: Row) => <li key={c.id}><div className="life-item">{c.name} <small>{c.subject} · {c.lapses} fallos · último: {c.errors.at(-1)?.q ?? "—"}</small></div>
              <button type="button" className="mini-btn" onClick={() => academy.post(`/concepts/${c.id}/remediate`).then((r) => { setRem(r.remediation); setExam(r.exam); }).catch((e: Error) => setMsg(e.message))}>Reforzar</button></li>)}</ul></section>}
          <section className="dpanel"><header className="dpanel-head"><span>CALENDARIO DE REPASOS (21 DÍAS)</span></header>
            {!d.calendar.length ? <p className="desk-empty">Aún no hay conceptos evaluados.</p> : <div className="ac-cal">{d.calendar.map((day: Row) => <div key={day.day}><b>{fmtDate(day.day)}</b>
              <small>{day.items.map((x: Row) => x.name).join(" · ")}</small></div>)}</div>}</section>
        </>}
      </State>
    </div>
  );
}
