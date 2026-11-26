import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { academy, life } from "../api/life";
import { type AMeta, Dashboard, Library, Tutor } from "../components/academy/AcademyA";
import { Courses, Exams, Reviews } from "../components/academy/AcademyB";
import { Labs, MemoryView, Paths, Progress, ResearchView } from "../components/academy/AcademyC";
import { State, useLoad } from "../components/life/kit";

const SECTIONS: [string, string, string][] = [
  ["home", "Academy Command Center", "Academia"], ["library", "Biblioteca", "Academia"], ["tutor", "Profesor IA", "Aprender"], ["courses", "Cursos", "Aprender"],
  ["exams", "Exámenes", "Evaluar"], ["reviews", "Repasos", "Evaluar"], ["progress", "Progreso", "Evaluar"],
  ["labs", "Laboratorios", "Practicar"], ["research", "Investigación", "Practicar"], ["paths", "Itinerarios", "Practicar"], ["memory", "Memoria y ajustes", "Practicar"],
];

/** VISTAN ACADEMY — universidad personal con IA (mismo PIN y sesión que LIFE OS). */
export function Academy() {
  const [params, setParams] = useSearchParams();
  const [locked, setLocked] = useState<boolean | null>(null);
  const [pin, setPin] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    life.get<{ enabled: boolean; unlocked: boolean }>("/lock").then((r) => setLocked(!r.unlocked)).catch(() => setLocked(false));
    const on = () => setLocked(true);
    window.addEventListener("vistan-life-locked", on);
    return () => window.removeEventListener("vistan-life-locked", on);
  }, []);
  const meta = useLoad<AMeta>(locked === false ? "/meta" : null, [locked], academy);
  const s = params.get("s") && SECTIONS.some((x) => x[0] === params.get("s")) ? params.get("s")! : "home";
  const go = (k: string, extra: Record<string, string> = {}) => setParams(k === "home" ? {} : { s: k, ...extra });
  const num = (k: string) => (params.get(k) ? Number(params.get(k)) : null);
  if (locked === null) return <div className="desk"><p className="desk-empty">Cargando VISTAN ACADEMY…</p></div>;
  if (locked) {
    return (
      <div className="desk life-lock">
        <form className="lock-card" onSubmit={(e) => { e.preventDefault(); setErr(null); life.post("/lock/unlock", { pin }).then(() => { setLocked(false); setPin(""); }).catch((x: Error) => setErr(x.message)); }}>
          <span className="desk-logo">VISTAN</span><b>VISTAN ACADEMY bloqueada</b>
          <p className="muted small">Introduce tu PIN (el mismo de LIFE OS).</p>
          <input type="password" inputMode="numeric" autoFocus value={pin} onChange={(e) => setPin(e.target.value)} aria-label="PIN" placeholder="PIN" />
          <button type="submit" className="btn" disabled={pin.length < 4}>Desbloquear</button>
          {err && <p className="error-line" role="alert">{err}</p>}
        </form>
      </div>
    );
  }
  const groups = [...new Set(SECTIONS.map((x) => x[2]))];
  return (
    <div className="desk life lab academy" data-testid="vistan-academy">
      <header className="desk-top">
        <div className="desk-brand"><span className="desk-logo">VISTAN</span><span className="desk-title">ACADEMY</span></div>
        <span className="life-motto">APRENDE · PRACTICA · DOMINA</span>
      </header>
      <div className="life-body">
        <nav className="life-nav" aria-label="Secciones de VISTAN ACADEMY">
          {groups.map((g) => <div key={g}><small>{g}</small>{SECTIONS.filter((x) => x[2] === g).map(([k, l]) => <button type="button" key={k} className={s === k ? "on" : ""} onClick={() => go(k)}>{l}</button>)}</div>)}
        </nav>
        <main className="desk-main">
          <State loading={meta.loading && !meta.data} error={meta.error}>
            {meta.data && <>
              {s === "home" && <Dashboard go={go} />}
              {s === "library" && <Library meta={meta.data} go={go} />}
              {s === "tutor" && <Tutor meta={meta.data} initialSubject={num("subject")} />}
              {s === "courses" && <Courses meta={meta.data} initial={num("id")} initialSubject={num("subject")} />}
              {s === "exams" && <Exams meta={meta.data} initialSubject={num("subject")} />}
              {s === "reviews" && <Reviews />}
              {s === "progress" && <Progress />}
              {s === "labs" && <Labs />}
              {s === "research" && <ResearchView />}
              {s === "paths" && <Paths go={go} />}
              {s === "memory" && <MemoryView meta={meta.data} onChange={meta.reload} />}
            </>}
          </State>
        </main>
      </div>
      <footer className="desk-foot">VISTAN ACADEMY · progreso medido con tu actividad real · contenido generado por IA: contrástalo · dinero de los laboratorios siempre virtual</footer>
    </div>
  );
}
