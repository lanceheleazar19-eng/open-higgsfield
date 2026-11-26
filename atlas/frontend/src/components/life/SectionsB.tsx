import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { life, type Row } from "../../api/life";
import { Stat } from "../desk/ui";
import { AgentChat, Crud, fmtDate, Md, SchemaForm, State, useLoad, type Field } from "./kit";

const todayIso = () => new Date().toLocaleDateString("sv-SE");

/* ───────── Knowledge Academy ───────── */
export function Academy() {
  const list = useLoad<Row[]>("/academy");
  const [sid, setSid] = useState<number | null>(null);
  const detail = useLoad<Row>(sid ? `/academy/${sid}` : null, [sid]);
  const [lesson, setLesson] = useState<Row | null>(null);
  const [quiz, setQuiz] = useState<Row | null>(null);
  const [answers, setAnswers] = useState<(number | string | null)[]>([]);
  const [result, setResult] = useState<Row | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [topic, setTopic] = useState("");
  const run = (k: string, fn: () => Promise<unknown>) => { setBusy(k); setErr(null); fn().catch((e: Error) => setErr(e.message)).finally(() => setBusy(null)); };
  const d = detail.data;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Knowledge Academy</h2><p className="muted small">El nivel de dominio se calcula <b>solo con evaluaciones corregidas</b>; completar lecciones no te marca como experto. El contenido lo genera la IA: contrástalo.</p>
        <p className="small">Estas asignaturas, lecciones y evaluaciones forman parte de <Link to="/academy">VISTAN ACADEMY</Link>, con cursos completos, profesores, repasos espaciados y laboratorios.</p></div>
      <State loading={list.loading && !list.data} error={list.error}>
        <div className="subject-grid">{list.data?.map((s) => (
          <button type="button" key={s.id} className={`subject ${sid === s.id ? "on" : ""}`} onClick={() => { setSid(s.id); setLesson(null); setQuiz(null); setResult(null); }}>
            <b>{s.name}</b><span className={`lvl l${s.mastery.level}`}>{s.mastery.label}</span>
            <small>{s.mastery.avg != null ? `${s.mastery.avg} % · ${s.mastery.assessments} eval.` : `${s.mastery.lessons_done} lecciones`}</small>
          </button>
        ))}</div>
      </State>
      {err && <p className="error-line" role="alert">{err}</p>}
      {sid && d && (
        <div className="mod-cols">
          <section className="dpanel">
            <header className="dpanel-head"><span>{d.subject.name.toUpperCase()} · {d.mastery.label}</span></header>
            <p className="mini-note">{d.mastery.rule}</p>
            {!!d.mastery.weak_topics?.length && <p className="warn-line l-warn">Puntos débiles: {d.mastery.weak_topics.join(", ")}</p>}
            <header className="dpanel-head"><span>TEMARIO</span>
              <button type="button" className="link-btn" disabled={!!busy} onClick={() => run("syl", () => life.post(`/academy/${sid}/syllabus`).then(detail.reload))}>{busy === "syl" ? "generando…" : d.subject.syllabus.length ? "regenerar" : "generar temario"}</button></header>
            {d.subject.syllabus.length ? (
              <ol className="syllabus">{d.subject.syllabus.map((tp: Row) => (
                <li key={tp.topic}><span>{tp.topic} <small>nivel {tp.level}</small></span>
                  <button type="button" className="mini-btn ghost" disabled={!!busy} onClick={() => run("les", () => life.post(`/academy/${sid}/lessons`, { topic: tp.topic, level: tp.level }).then((l) => { setLesson(l); detail.reload(); }))}>Lección</button>
                  <button type="button" className="mini-btn ghost" disabled={!!busy} onClick={() => run("quiz", () => life.post(`/academy/${sid}/assessments`, { kind: "quiz", topic: tp.topic }).then((q) => { setQuiz(q); setAnswers(q.questions.map(() => null)); setResult(null); }))}>Test</button>
                </li>
              ))}</ol>
            ) : <p className="desk-empty">Genera el temario o escribe un tema concreto.</p>}
            <div className="filters">
              <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Otro tema…" aria-label="Tema" />
              <button type="button" className="mini-btn" disabled={!topic.trim() || !!busy} onClick={() => run("les", () => life.post(`/academy/${sid}/lessons`, { topic, level: Math.max(1, d.mastery.level) }).then((l) => { setLesson(l); detail.reload(); }))}>Lección</button>
              <button type="button" className="btn" disabled={!!busy} onClick={() => run("quiz", () => life.post(`/academy/${sid}/assessments`, { kind: "exam" }).then((q) => { setQuiz(q); setAnswers(q.questions.map(() => null)); setResult(null); }))}>
                {busy === "quiz" ? "Generando…" : "Examen adaptativo"}</button>
            </div>
            <header className="dpanel-head"><span>HISTORIAL DE APRENDIZAJE</span></header>
            <ul className="life-list compact">
              {d.assessments.map((a: Row) => <li key={a.id}><div className="life-item">{a.kind === "exam" ? "Examen" : "Test"} · {a.topic ?? "general"} · dificultad {a.difficulty}/5 · <b className="mono">{a.score != null ? `${a.score} %` : "sin corregir"}</b> <small>{fmtDate(a.created_at)}</small></div></li>)}
              {d.lessons.map((l: Row) => <li key={`l${l.id}`}><div className="life-item">Lección: {l.topic} {l.completed_at ? "✓" : ""} <small>{fmtDate(l.created_at)}</small>
                <button type="button" className="link-btn" onClick={() => life.get(`/lessons/${l.id}`).then(setLesson)}>abrir</button></div></li>)}
            </ul>
          </section>
          <section className="dpanel grow">
            {quiz ? (
              <div className="quiz">
                <header className="dpanel-head"><span>{quiz.kind === "exam" ? "EXAMEN" : "TEST"} · DIFICULTAD {quiz.difficulty}/5</span></header>
                {quiz.questions.map((q: Row, i: number) => (
                  <fieldset key={i} className="q">
                    <legend>{i + 1}. {q.q}</legend>
                    {q.type === "mcq" ? q.options.map((o: string, j: number) => (
                      <label key={j} className={`opt ${result ? (result.feedback.results[i].answer === j ? "right" : answers[i] === j ? "wrong" : "") : ""}`}>
                        <input type="radio" name={`q${i}`} checked={answers[i] === j} disabled={!!result} onChange={() => setAnswers(answers.map((a, k) => (k === i ? j : a)))} /> {o}
                      </label>
                    )) : <textarea rows={3} value={(answers[i] as string) ?? ""} disabled={!!result} onChange={(e) => setAnswers(answers.map((a, k) => (k === i ? e.target.value : a)))} aria-label={`Respuesta ${i + 1}`} />}
                    {result && <p className="mini-note">{result.feedback.results[i].explanation ?? result.feedback.results[i].feedback} {result.feedback.results[i].model_answer ? `· Respuesta modelo: ${result.feedback.results[i].model_answer}` : ""} ({result.feedback.results[i].score} %)</p>}
                  </fieldset>
                ))}
                {!result ? <button type="button" className="btn" disabled={!!busy || answers.some((a, i) => quiz.questions[i].type === "mcq" && a === null)}
                  onClick={() => run("grade", () => life.post(`/assessments/${quiz.id}/submit`, { answers }).then((r) => { setResult(r); detail.reload(); list.reload(); }))}>{busy === "grade" ? "Corrigiendo…" : "Entregar y corregir"}</button>
                  : <div className="stat-row"><Stat label="Nota" value={`${result.score} %`} /><Stat label="Nuevo nivel" value={result.mastery.label} />
                    <Stat label="Puntos débiles" value={(result.feedback.weak_topics ?? []).join(", ") || "—"} /></div>}
              </div>
            ) : lesson ? (
              <div className="lesson">
                <header className="dpanel-head"><span>{lesson.topic.toUpperCase()} · NIVEL {lesson.level}</span><span>IA · {lesson.model}</span></header>
                <Md text={lesson.content.explicacion} />
                {!!lesson.content.ideas_clave?.length && <><h4>Ideas clave</h4><ul>{lesson.content.ideas_clave.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                {!!lesson.content.ejemplos_reales?.length && <><h4>Ejemplos</h4><ul>{lesson.content.ejemplos_reales.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                {lesson.content.caso_practico?.situacion && <><h4>Caso práctico</h4><p>{lesson.content.caso_practico.situacion}</p><ul>{(lesson.content.caso_practico.preguntas ?? []).map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                {!!lesson.content.ejercicios?.length && <><h4>Ejercicios</h4><ol>{lesson.content.ejercicios.map((x: string) => <li key={x}>{x}</li>)}</ol></>}
                {!!lesson.content.errores_comunes?.length && <><h4>Errores comunes</h4><ul>{lesson.content.errores_comunes.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                <button type="button" className="btn ghost" disabled={!!lesson.completed_at} onClick={() => life.post(`/lessons/${lesson.id}/complete`).then((l) => { setLesson({ ...lesson, completed_at: l.completed_at }); detail.reload(); })}>
                  {lesson.completed_at ? "Lección completada" : "Marcar como completada"}</button>
                <p className="mini-note">Completar la lección no sube tu nivel: haz un test para demostrarlo.</p>
              </div>
            ) : <p className="desk-empty">Elige un tema del temario para abrir una lección o hacer un test.</p>}
          </section>
        </div>
      )}
      <AgentChat area="learning" title="Learning Agent" quick={["¿Qué debería estudiar esta semana según mis resultados?", "¿Cuáles son mis puntos débiles?", "Hazme 3 preguntas rápidas de repaso"]} />
    </div>
  );
}

/* ───────── Simulador (Liderazgo y Comunicación) ───────── */
export function Simulator({ area }: { area: "leadership" | "communication" }) {
  const sc = useLoad<Record<string, Row>>("/scenarios");
  const hist = useLoad<Row[]>(`/sims?area=${area}`, [area]);
  const [sim, setSim] = useState<Row | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setSim(null); }, [area]);
  const run = (fn: () => Promise<Row>) => { setBusy(true); setErr(null); fn().then((s) => { setSim((prev) => ({ ...prev, ...s })); hist.reload(); }).catch((e: Error) => setErr(e.message)).finally(() => setBusy(false)); };
  const title = area === "leadership" ? "Leadership Intelligence" : "Communication & Social Intelligence";
  const deb = sim?.debrief;
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>{title}</h2><p className="muted small">Simulaciones con IA: tú decides y hablas; al terminar, el agente analiza tus decisiones, sus consecuencias, ventajas y errores. {area === "communication" ? "Objetivo: comunicar con claridad, seguridad y respeto — nunca manipular." : ""}</p></div>
      {!sim ? (
        <div className="scenario-grid">{Object.entries(sc.data ?? {}).filter(([, s]) => s.area === area).map(([k, s]) => (
          <button type="button" key={k} className="scenario" disabled={busy} onClick={() => run(() => life.post("/sims", { scenario: k }))}><b>{s.title}</b><span>{s.brief}</span></button>
        ))}</div>
      ) : (
        <div className="mod-cols">
          <section className="dpanel grow sim">
            <header className="dpanel-head"><span>{sim.title.toUpperCase()}</span><button type="button" className="link-btn" onClick={() => setSim(null)}>cerrar</button></header>
            <p className="mini-note">{sim.brief} · Interlocutor: {sim.role}</p>
            <div className="tutor-log">{sim.transcript.map((m: Row, i: number) => (
              <div key={i} className={`tmsg ${m.role === "user" ? "user" : "assistant"}`}><div className="tbody"><p>{m.content}</p></div></div>
            ))}{busy && <div className="tmsg assistant"><div className="tbody"><p className="muted">…</p></div></div>}</div>
            {sim.status === "active" ? (
              <>
                <form className="tutor-in" onSubmit={(e) => { e.preventDefault(); const tx = text; setText(""); run(() => life.post(`/sims/${sim.id}/say`, { text: tx })); }}>
                  <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Tu respuesta…" aria-label="Tu intervención" maxLength={3000} />
                  <button type="submit" className="btn" disabled={busy || !text.trim()}>Responder</button>
                </form>
                <button type="button" className="btn ghost" disabled={busy || !sim.transcript.some((m: Row) => m.role === "user")} onClick={() => run(() => life.post(`/sims/${sim.id}/finish`))}>Terminar y analizar</button>
              </>
            ) : null}
          </section>
          {deb && (
            <section className="dpanel">
              <header className="dpanel-head"><span>ANÁLISIS DE TU ACTUACIÓN</span></header>
              <p>{deb.resumen}</p>
              {deb.criterios && <div className="stat-row">{Object.entries(deb.criterios as Record<string, number>).map(([k, v]) => <Stat key={k} label={k} value={`${v}/5`} />)}</div>}
              <p className="mini-note">Las puntuaciones valoran esta conversación concreta, no a ti como persona.</p>
              {(deb.decisiones ?? []).map((x: Row, i: number) => <div key={i} className="decision-card"><b>{x.decision}</b><p className="small">Consecuencias: {x.consecuencias}</p><p className="small up">Ventajas: {x.ventajas}</p><p className="small down">Errores: {x.errores}</p></div>)}
              {!!deb.lo_mejor?.length && <><b>Lo mejor</b><ul>{deb.lo_mejor.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
              {!!deb.a_mejorar?.length && <><b>A mejorar</b><ul>{deb.a_mejorar.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
              {deb.frase_alternativa && <p className="small"><b>Podrías haber dicho:</b> «{deb.frase_alternativa}»</p>}
              {deb.ejercicio_siguiente && <p className="small"><b>Siguiente ejercicio:</b> {deb.ejercicio_siguiente}</p>}
            </section>
          )}
        </div>
      )}
      {err && <p className="error-line" role="alert">{err}</p>}
      <section className="dpanel"><header className="dpanel-head"><span>HISTORIAL</span></header>
        <State loading={hist.loading && !hist.data} error={hist.error} empty={hist.data && !hist.data.length ? "Aún no has hecho simulaciones." : false}>
          <ul className="life-list compact">{hist.data?.map((s) => <li key={s.id}><div className="life-item">{s.title} · {s.status === "finished" ? "terminada" : "en curso"} <small>{fmtDate(s.created_at)}</small>
            {s.debrief?.criterios && <small> · {Object.entries(s.debrief.criterios as Record<string, number>).map(([k, v]) => `${k} ${v}`).join(" · ")}</small>}
            <button type="button" className="link-btn" onClick={() => life.get(`/sims/${s.id}`).then(setSim)}>abrir</button></div></li>)}</ul>
        </State>
      </section>
      <AgentChat area={area} title={area === "leadership" ? "Leadership Agent" : "Communication Agent"}
        quick={area === "leadership" ? ["¿Qué patrón ves en mis simulaciones?", "¿Cómo negocio mejor cuando no tengo poder?"] : ["¿Cómo mejoro mi escucha activa?", "Dame un ejercicio de oratoria para hoy"]} />
    </div>
  );
}

/* ───────── Discipline Engine ───────── */
const CAT: [string, string][] = [["reading", "Lectura"], ["training", "Entrenamiento"], ["sleep", "Sueño"], ["work", "Trabajo"], ["study", "Estudio"], ["distraction", "Distracciones (límite)"], ["custom", "Otro"]];
const WD = ["L", "M", "X", "J", "V", "S", "D"];

export function Discipline() {
  const { data, error, loading, reload } = useLoad<Row>("/discipline");
  const [form, setForm] = useState<Row | null>(null);
  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6]);
  const [vals, setVals] = useState<Record<number, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const log = (h: Row, value: number) => life.put(`/habits/${h.id}/log`, { day: data!.today, value }).then(reload).catch((e: Error) => setErr(e.message));
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Discipline Engine</h2><p className="muted small">Exigente y objetivo: solo cuenta lo registrado. Sueño y entrenos se leen de Apple Salud y Gimnasio (no se duplican).</p></div>
      <State loading={loading && !data} error={error}>
        {data && (
          <>
            {!!data.findings.length && <section className="dpanel"><header className="dpanel-head"><span>PATRONES DETECTADOS</span></header>
              <ul className="findings">{data.findings.map((f: string) => <li key={f}>{f}</li>)}</ul></section>}
            <div className="stat-row">
              <Stat label="Compromisos cumplidos (90 d)" value={data.commitment_rate_90d != null ? `${data.commitment_rate_90d} %` : "N/D"} />
              <Stat label="Sueño medio 7 d" value={data.auto.sleep_avg_7d != null ? `${data.auto.sleep_avg_7d} h` : "N/D"} hint={data.auto.sources} />
              <Stat label="Entrenos 7 d" value={String(data.auto.workouts_7d)} hint={data.auto.sources} />
            </div>
            <section className="dpanel">
              <header className="dpanel-head"><span>HÁBITOS · HOY {fmtDate(data.today)}</span><button type="button" className="link-btn" onClick={() => setForm(form ? null : { category: "custom", kind: "check" })}>{form ? "cerrar" : "+ hábito"}</button></header>
              {form && (
                <SchemaForm fields={[{ k: "name", label: "Hábito", required: true }, { k: "category", label: "Categoría", type: "select", options: CAT, required: true },
                  { k: "kind", label: "Tipo", type: "select", options: [["check", "Hecho / no hecho"], ["amount", "Cantidad"]], required: true },
                  { k: "target", label: "Objetivo diario", type: "number" }, { k: "unit", label: "Unidad (min, pág…)" }, { k: "limit", label: "Es un límite (no superar)", type: "checkbox" },
                  { k: "remind_at", label: "Recordatorio (HH:MM)", type: "time" }]} initial={form}
                  extra={<div className="wide wd-pick">{WD.map((w, i) => <button type="button" key={w} className={`chip ${days.includes(i) ? "on" : ""}`} onClick={() => setDays(days.includes(i) ? days.filter((x) => x !== i) : [...days, i].sort())}>{w}</button>)}</div>}
                  onSubmit={(v) => (form.id ? life.patch(`/habits/${form.id}`, { ...v, days, active: true }) : life.post("/habits", { ...v, days })).then(() => { setForm(null); reload(); })} />
              )}
              {!data.habits.length ? <p className="desk-empty">Crea tus hábitos: lectura, entreno, estudio, sueño, trabajo profundo, límite de redes…</p> : (
                <div className="habit-list">{data.habits.map((h: Row) => {
                  const def = data.habit_defs.find((x: Row) => x.id === h.id);
                  return (
                    <div key={h.id} className={`habit ${h.done_today ? "done" : ""}`}>
                      <div className="h-main">
                        <b>{h.name}</b><small>{CAT.find((c) => c[0] === h.category)?.[1]} · racha {h.streak} (mejor {h.best_streak}) · {h.compliance_30d != null ? `${h.compliance_30d} % en 30 d` : "sin historial"}</small>
                      </div>
                      <div className="h-cal" aria-label="Últimos 28 días">{h.calendar.map((c: Row) => <i key={c.day} title={`${c.day}: ${c.value ?? "—"}`} className={!c.due ? "off" : c.met === true && (c.value != null || def?.limit) ? "ok" : c.value != null ? "bad" : ""} />)}</div>
                      <div className="h-act">
                        {h.due_today ? (def?.kind === "check" ? (
                          <button type="button" className={`mini-btn ${h.done_today ? "" : "ghost"}`} onClick={() => (h.done_today ? life.del(`/habits/${h.id}/log?day=${data.today}`).then(reload) : log(h, 1))}>{h.done_today ? "✓ Hecho" : "Marcar hecho"}</button>
                        ) : (
                          <><input className="cell-in" inputMode="decimal" value={vals[h.id] ?? (h.today_value ?? "")} onChange={(e) => setVals({ ...vals, [h.id]: e.target.value })} aria-label={`Cantidad de ${h.name}`} placeholder={def?.unit ?? ""} />
                            <button type="button" className="mini-btn" onClick={() => log(h, Number(String(vals[h.id] ?? h.today_value ?? 0).replace(",", ".")))}>Registrar</button></>
                        )) : <small>No toca hoy</small>}
                        <button type="button" className="mini-btn ghost" onClick={() => { setForm(def); setDays(def.days); }}>Editar</button>
                        <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm(`¿Eliminar el hábito «${h.name}» y su historial?`)) void life.del(`/habits/${h.id}`).then(reload); }}>✕</button>
                      </div>
                    </div>
                  );
                })}</div>
              )}
            </section>
            <section className="dpanel">
              <header className="dpanel-head"><span>COMPROMISOS SEMANALES Y MENSUALES</span></header>
              <SchemaForm fields={[{ k: "period", label: "Periodo", type: "select", options: [["week", "Semana"], ["month", "Mes"]], required: true },
                { k: "title", label: "Compromiso verificable", required: true, placeholder: "p. ej. Enviar 5 propuestas a clientes" }, { k: "due", label: "Fecha límite", type: "date", required: true }]}
                initial={{ period: "week", due: todayIso() }} submitLabel="Añadir" onSubmit={(v) => life.post("/commitments", v).then(reload)} />
              <ul className="life-list compact">{data.commitments.map((c: Row) => (
                <li key={c.id}><div className="life-item"><span className={`st st-${c.status === "done" ? "filled" : c.status === "missed" ? "rejected" : c.due < data.today ? "rejected" : "pending"}`}>
                  {{ open: c.due < data.today ? "Vencido" : "Abierto", done: "Cumplido", missed: "Incumplido", dropped: "Descartado" }[c.status as string]}</span> {c.title} <small>{c.period === "week" ? "semana" : "mes"} · {fmtDate(c.due)}</small></div>
                  <div className="row-actions">{c.status === "open" && <>
                    <button type="button" className="mini-btn" onClick={() => life.patch(`/commitments/${c.id}`, { status: "done" }).then(reload)}>Cumplido</button>
                    <button type="button" className="mini-btn ghost" onClick={() => life.patch(`/commitments/${c.id}`, { status: "missed" }).then(reload)}>Incumplido</button></>}
                    <button type="button" className="mini-btn ghost" onClick={() => life.del(`/commitments/${c.id}`).then(reload)}>✕</button></div></li>
              ))}</ul>
            </section>
          </>
        )}
      </State>
      {err && <p className="error-line">{err}</p>}
      <AgentChat area="discipline" title="Discipline Agent" quick={["Sé directo: ¿en qué estoy fallando?", "¿Qué hábito debería reforzar primero y cómo?"]} />
    </div>
  );
}

/* ───────── Personal CRM ───────── */
const CONTACT: Field[] = [
  { k: "name", label: "Nombre", required: true }, { k: "email", label: "Email" }, { k: "phone", label: "Teléfono" }, { k: "company", label: "Empresa" },
  { k: "role", label: "Profesión / cargo" }, { k: "relation", label: "Relación", placeholder: "mentor, cliente, amigo…" },
  { k: "scope", label: "Ámbito", type: "select", options: [["professional", "Profesional"], ["personal", "Personal"]], required: true },
  { k: "last_interaction", label: "Última interacción", type: "date" }, { k: "next_followup", label: "Próximo seguimiento", type: "date" },
  { k: "interests", label: "Intereses profesionales", type: "textarea" }, { k: "opportunities", label: "Oportunidades de colaboración", type: "textarea" }, { k: "notes", label: "Notas", type: "textarea" },
];

export function Crm() {
  const [open, setOpen] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Personal CRM</h2><p className="muted small">Datos privados: solo en tu Mac, protegibles con PIN y nunca enviados a nadie. Los recordatorios crean una tarea para ti; VISTAN no escribe a tus contactos.</p></div>
      {msg && <p className="ok-line">{msg}</p>}
      <Crud title="Contactos" path="/contacts" fields={CONTACT} newDefaults={{ scope: "professional" }}
        render={(c) => <><b>{c.name}</b>{c.company ? ` · ${c.company}` : ""}{c.role ? ` · ${c.role}` : ""} <small>{c.scope === "personal" ? "personal" : "profesional"}</small>
          {c.next_followup && <span className={`small ${c.next_followup <= todayIso() ? "down" : ""}`}> · seguimiento {fmtDate(c.next_followup)}</span>}
          {c.last_interaction && <small> · última {fmtDate(c.last_interaction)}</small>}
          {open === c.id && <Interactions cid={c.id} />}</>}
        actions={(c, reload) => <>
          <button type="button" className="mini-btn ghost" onClick={() => setOpen(open === c.id ? null : c.id)}>Interacciones</button>
          {c.next_followup && <button type="button" className="mini-btn ghost" onClick={() => life.post(`/contacts/${c.id}/task`).then(() => { setMsg(`Tarea de seguimiento creada para ${c.name}`); reload(); }).catch((e: Error) => setMsg(e.message))}>Recordatorio</button>}
        </>} />
      <AgentChat area="communication" title="Communication Agent" quick={["¿A quién debería hacer seguimiento esta semana?", "Ayúdame a preparar un mensaje de seguimiento respetuoso"]} />
    </div>
  );
}

function Interactions({ cid }: { cid: number }) {
  const { data, reload } = useLoad<Row[]>(`/contacts/${cid}/interactions`);
  return (
    <div className="interactions">
      <SchemaForm fields={[{ k: "day", label: "Fecha", type: "date", required: true }, { k: "channel", label: "Canal" }, { k: "summary", label: "Resumen", type: "textarea", required: true },
        { k: "next_followup", label: "Próximo seguimiento", type: "date" }]} initial={{ day: todayIso() }} submitLabel="Añadir interacción"
        onSubmit={(v) => life.post(`/contacts/${cid}/interactions`, v).then(reload)} />
      <ul>{data?.map((i) => <li key={i.id}><small>{fmtDate(i.day)} {i.channel ? `· ${i.channel}` : ""}</small> {i.summary}</li>)}</ul>
    </div>
  );
}

/* ───────── Decision Journal ───────── */
const DECISION: Field[] = [
  { k: "title", label: "Título", required: true }, { k: "day", label: "Fecha", type: "date", required: true }, { k: "area", label: "Área" },
  { k: "context", label: "Contexto", type: "textarea" }, { k: "problem", label: "Problema", type: "textarea" }, { k: "options", label: "Opciones (una por línea)", type: "lines" },
  { k: "decision", label: "Decisión tomada", type: "textarea", required: true }, { k: "reasons", label: "Motivos", type: "textarea" },
  { k: "expectations", label: "Expectativas", type: "textarea" }, { k: "risks", label: "Riesgos", type: "textarea" },
  { k: "confidence", label: "Confianza (0-100)", type: "number", required: true }, { k: "expected_result", label: "Resultado esperado", type: "textarea" },
  { k: "review_on", label: "Fecha de revisión", type: "date" }, { k: "remember", label: "Guardar en la memoria de VISTAN", type: "checkbox" },
];

export function Decisions() {
  const { data, error, loading, reload } = useLoad<Row>("/decisions");
  const [adding, setAdding] = useState(false);
  const [reviewing, setReviewing] = useState<number | null>(null);
  const [edit, setEdit] = useState<Row | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Decision Journal</h2><p className="muted small">Registra decisiones con tu nivel de confianza y revísalas después: VISTAN compara lo esperado con lo ocurrido y mide tu calibración.</p></div>
      <State loading={loading && !data} error={error}>
        {data && (
          <>
            <div className="stat-row">
              <Stat label="Decisiones" value={String(data.items.length)} /><Stat label="Revisadas" value={String(data.calibration.reviewed)} />
              <Stat label="Pendientes de revisar" value={String(data.due.length)} />
              <Stat label="Calibración (Brier)" value={data.calibration.brier != null ? String(data.calibration.brier) : "N/D"} hint="0 = tu confianza coincide con lo que pasa" />
            </div>
            {!!data.calibration.bins.length && <table className="dtable compact"><thead><tr><th>Confianza declarada</th><th>n</th><th>Media declarada</th><th>Salió como esperabas</th></tr></thead>
              <tbody>{data.calibration.bins.map((b: Row) => <tr key={b.range}><td>{b.range}</td><td className="mono">{b.n}</td><td className="mono">{b.confidence} %</td><td className="mono">{b.hit} %</td></tr>)}</tbody></table>}
            <section className="dpanel"><header className="dpanel-head"><span>NUEVA DECISIÓN</span><button type="button" className="link-btn" onClick={() => setAdding(!adding)}>{adding ? "cerrar" : "+ registrar"}</button></header>
              {adding && <SchemaForm fields={DECISION} initial={{ day: todayIso(), confidence: 60 }} submitLabel="Registrar" onSubmit={(v) => life.post("/decisions", v).then(() => { setAdding(false); reload(); })} />}</section>
            {data.items.map((d: Row) => (
              <section key={d.id} className={`dpanel ${data.due.includes(d.id) ? "due" : ""}`}>
                <header className="dpanel-head"><span>{d.title.toUpperCase()} · {fmtDate(d.day)}</span><span>confianza {d.confidence} % {d.outcome ? `· ${{ better: "mejor de lo esperado", as_expected: "como esperabas", worse: "peor" }[d.outcome as string]}` : data.due.includes(d.id) ? "· ¡toca revisarla!" : ""}</span></header>
                {edit?.id === d.id ? <SchemaForm fields={DECISION.filter((f) => f.k !== "remember")} initial={d} onCancel={() => setEdit(null)} onSubmit={(v) => life.patch(`/decisions/${d.id}`, v).then(() => { setEdit(null); reload(); })} /> : (
                  <div className="dec-body">
                    <p><b>Decisión:</b> {d.decision}</p>
                    {d.reasons && <p className="small"><b>Motivos:</b> {d.reasons}</p>}
                    {d.expected_result && <p className="small"><b>Esperado:</b> {d.expected_result}</p>}
                    {d.actual_result && <p className="small"><b>Real:</b> {d.actual_result}</p>}
                    {d.analysis && <div className="ai-text"><p>{d.analysis.comparacion}</p><p className="small"><b>Proceso:</b> {d.analysis.calidad_del_proceso}</p>
                      <p className="small"><b>Suerte vs decisión:</b> {d.analysis.suerte_vs_decision}</p>
                      {!!d.analysis.sesgos_posibles?.length && <><b>Posibles sesgos</b><ul>{d.analysis.sesgos_posibles.map((s: Row) => <li key={s.sesgo}>{s.sesgo}: {s.evidencia}</li>)}</ul></>}
                      {!!d.analysis.patrones_con_decisiones_anteriores?.length && <><b>Patrones</b><ul>{d.analysis.patrones_con_decisiones_anteriores.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
                      {!!d.analysis.lecciones?.length && <><b>Lecciones</b><ul>{d.analysis.lecciones.map((x: string) => <li key={x}>{x}</li>)}</ul></>}</div>}
                    <div className="row-actions">
                      {!d.outcome && <button type="button" className="mini-btn" onClick={() => setReviewing(reviewing === d.id ? null : d.id)}>Revisar resultado</button>}
                      <button type="button" className="mini-btn ghost" onClick={() => setEdit(d)}>Editar</button>
                      <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar esta decisión?")) void life.del(`/decisions/${d.id}`).then(reload); }}>Eliminar</button>
                    </div>
                    {reviewing === d.id && <SchemaForm fields={[{ k: "actual_result", label: "¿Qué ocurrió realmente?", type: "textarea", required: true },
                      { k: "outcome", label: "Comparado con lo esperado", type: "select", options: [["better", "Mejor"], ["as_expected", "Como esperaba"], ["worse", "Peor"]], required: true },
                      { k: "analyze", label: "Analizar con el Decision Agent (sesgos y patrones)", type: "checkbox" }]} initial={{ outcome: "as_expected", analyze: true }} submitLabel="Guardar revisión"
                      onSubmit={(v) => life.post(`/decisions/${d.id}/review`, v).then(() => { setReviewing(null); reload(); })} />}
                  </div>
                )}
              </section>
            ))}
          </>
        )}
      </State>
      <AgentChat area="decision" title="Decision Agent" quick={["¿Qué sesgos se repiten en mis decisiones?", "¿Soy demasiado confiado o prudente?"]} />
    </div>
  );
}

/* ───────── Failure Analysis ───────── */
const FAILURE: Field[] = [
  { k: "title", label: "Qué pasó", required: true }, { k: "kind", label: "Tipo", type: "select", required: true,
    options: [["project", "Proyecto fallido"], ["decision", "Decisión equivocada"], ["business", "Error empresarial"], ["goal", "Objetivo incumplido"], ["personal", "Problema personal"]] },
  { k: "day", label: "Fecha", type: "date", required: true }, { k: "description", label: "Descripción", type: "textarea" }, { k: "causes", label: "Causas", type: "textarea" },
  { k: "consequences", label: "Consecuencias", type: "textarea" }, { k: "lessons", label: "Lecciones aprendidas", type: "textarea" },
  { k: "actions", label: "Acciones correctivas", type: "textarea" }, { k: "tags", label: "Etiquetas (separadas por comas)", type: "tags", placeholder: "prisa, sin validar, exceso de confianza" },
  { k: "remember", label: "Guardar la lección en la memoria", type: "checkbox" },
];

export function Failures() {
  const [an, setAn] = useState<Row | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pat = useLoad<Row>("/failures");
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Failure Analysis</h2><p className="muted small">Sin juicios: el objetivo es encontrar patrones y no repetir fallos.</p></div>
      {!!pat.data?.patterns.repeated.length && <p className="warn-line l-warn">Etiquetas que se repiten: {pat.data.patterns.repeated.join(", ")}</p>}
      <Crud title="Errores registrados" path="/failures" listKey="items" fields={FAILURE} newDefaults={{ kind: "personal", day: todayIso() }} onChanged={pat.reload}
        render={(f) => <><b>{f.title}</b> <small>{fmtDate(f.day)} · {f.kind}</small>{f.lessons && <p className="small">Lección: {f.lessons}</p>}{!!f.tags?.length && <small> · {f.tags.join(", ")}</small>}</>} />
      <button type="button" className="btn" disabled={busy} onClick={() => { setBusy(true); setErr(null); life.post("/failures/analyze").then(setAn).catch((e: Error) => setErr(e.message)).finally(() => setBusy(false)); }}>
        {busy ? "Buscando patrones…" : "Buscar patrones entre mis errores"}</button>
      {err && <p className="error-line">{err}</p>}
      {an && <div className="ai-text">
        {(an.patrones ?? []).map((p: Row) => <div key={p.patron}><b>{p.patron}</b><p className="small">Causa raíz probable: {p.causa_raiz_probable}</p><ul>{(p.evidencia ?? []).map((x: string) => <li key={x}>{x}</li>)}</ul></div>)}
        {!!an.acciones_preventivas?.length && <><b>Acciones preventivas</b><ul>{an.acciones_preventivas.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
        {!!an.senales_de_alerta?.length && <><b>Señales de alerta</b><ul>{an.senales_de_alerta.map((x: string) => <li key={x}>{x}</li>)}</ul></>}
        <small>{an.model}</small></div>}
    </div>
  );
}

/* ───────── Legacy ───────── */
export function Vision() {
  const { data, error, loading, reload } = useLoad<Row>("/vision");
  const [edit, setEdit] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<string | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Legacy — visión de futuro</h2><p className="muted small">Tu visión la defines tú. VISTAN no decide quién debes ser: la usa para ayudarte a ser coherente con ella.</p></div>
      <State loading={loading && !data} error={error}>
        <div className="vision-grid">{data?.sections.map((s: Row) => (
          <section key={s.key} className="dpanel">
            <header className="dpanel-head"><span>{s.label.toUpperCase()}</span>{saved === s.key && <span className="ok-chip">guardado</span>}</header>
            <textarea rows={4} value={edit[s.key] ?? s.content} onChange={(e) => setEdit({ ...edit, [s.key]: e.target.value })} aria-label={s.label} />
            <div className="row-btns">
              <button type="button" className="mini-btn ghost" disabled={edit[s.key] === undefined} onClick={() => life.put(`/vision/${s.key}`, { content: edit[s.key], remember: true }).then(() => { setSaved(s.key); reload(); })}>Guardar y recordar</button>
              <button type="button" className="mini-btn" disabled={edit[s.key] === undefined} onClick={() => life.put(`/vision/${s.key}`, { content: edit[s.key] }).then(() => { setSaved(s.key); reload(); })}>Guardar</button>
            </div>
          </section>
        ))}</div>
        <Crud title="Línea temporal" path="/timeline" fields={[{ k: "year", label: "Año", type: "number", required: true }, { k: "title", label: "Hito", required: true },
          { k: "area", label: "Área" }, { k: "status", label: "Estado", type: "select", options: [["planned", "Planeado"], ["achieved", "Conseguido"], ["dropped", "Descartado"]], required: true },
          { k: "notes", label: "Notas", type: "textarea" }]} newDefaults={{ year: new Date().getFullYear() + 1, status: "planned" }}
          render={(m) => <><b className="mono">{m.year}</b> · {m.title} <small>{m.area ?? ""} · {{ planned: "planeado", achieved: "conseguido ✓", dropped: "descartado" }[m.status as string]}</small></>} />
      </State>
    </div>
  );
}

/* ───────── Daily Briefing y Weekly Review (Workflows) ───────── */
export function Reviews() {
  const { data, error, loading, reload } = useLoad<Row>("/reviews");
  const [busy, setBusy] = useState<string | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Daily Briefing y Weekly Review</h2><p className="muted small">Se generan solos (briefing diario a las 08:00 y revisión los domingos a las 20:00, ajustable en Automatizaciones) con tus datos reales, incluido LIFE OS.</p></div>
      <State loading={loading && !data} error={error}>
        {data && (["daily_briefing", "weekly_review"] as const).map((k) => (
          <section key={k} className="dpanel">
            <header className="dpanel-head"><span>{k === "daily_briefing" ? "DAILY BRIEFING" : "WEEKLY REVIEW · HISTÓRICO"}</span>
              <button type="button" className="link-btn" disabled={!!busy} onClick={() => { setBusy(k); life.post(`/reviews/${k}/now`).then(() => setTimeout(() => { reload(); setBusy(null); }, 1500)).catch(() => setBusy(null)); }}>{busy === k ? "generando…" : "generar ahora"}</button></header>
            {!data[k].runs.length ? <p className="desk-empty">Aún no se ha generado ninguno.</p> : (
              <div className="review-list">{data[k].runs.slice(0, k === "daily_briefing" ? 3 : 12).map((r: Row) => (
                <details key={r.id} open={r === data[k].runs[0]}><summary>{fmtDate(r.started_at)} · {r.status === "done" ? "completado" : r.status}</summary><pre className="review-text">{r.output ?? "—"}</pre></details>
              ))}</div>
            )}
          </section>
        ))}
      </State>
    </div>
  );
}

/* ───────── Seguridad de LIFE OS ───────── */
export function Security({ onLocked }: { onLocked: () => void }) {
  const st = useLoad<Row>("/lock");
  const [pin, setPin] = useState("");
  const [cur, setCur] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Privacidad y seguridad</h2><p className="muted small">Tus datos se quedan en tu Mac. Copias de seguridad, exportación completa, registro de actividad y permisos por acción están en Configuración → Seguridad.</p></div>
      <section className="dpanel">
        <header className="dpanel-head"><span>BLOQUEO CON PIN</span><span>{st.data?.enabled ? "activado" : "desactivado"}</span></header>
        <p className="small">Con PIN, cada navegador (Mac, iPhone…) debe desbloquear LIFE OS para ver contactos, decisiones, errores, patrimonio y visión. La sesión caduca a las 12 h. El PIN se guarda cifrado (hash) en el llavero.</p>
        <div className="filters">
          {st.data?.enabled && <input type="password" inputMode="numeric" value={cur} onChange={(e) => setCur(e.target.value)} placeholder="PIN actual" aria-label="PIN actual" />}
          <input type="password" inputMode="numeric" value={pin} onChange={(e) => setPin(e.target.value)} placeholder="Nuevo PIN (4-12 cifras)" aria-label="Nuevo PIN" />
          <button type="button" className="btn" disabled={!pin} onClick={() => life.put("/lock/pin", { pin, current: cur || null }).then(() => { setMsg("PIN guardado"); setPin(""); setCur(""); st.reload(); }).catch((e: Error) => setMsg(e.message))}>Guardar PIN</button>
          {st.data?.enabled && <>
            <button type="button" className="btn ghost" onClick={() => life.post("/lock/lock").then(onLocked)}>Bloquear ahora</button>
            <button type="button" className="btn ghost" disabled={!cur} onClick={() => life.del("/lock/pin", { pin: cur }).then(() => { setMsg("PIN eliminado"); setCur(""); st.reload(); }).catch((e: Error) => setMsg(e.message))}>Quitar PIN</button></>}
        </div>
        {msg && <p className="small">{msg}</p>}
      </section>
      <section className="dpanel"><header className="dpanel-head"><span>EXPORTAR Y COPIAS</span></header>
        <div className="filters"><a className="btn ghost" href="/api/security/export">Exportar todos mis datos (JSON)</a><a className="btn ghost" href="/memory">Ver, corregir o borrar la memoria</a><a className="btn ghost" href="/settings">Copias de seguridad y permisos</a></div></section>
    </div>
  );
}
