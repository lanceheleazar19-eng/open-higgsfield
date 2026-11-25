import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { life } from "../api/life";
import { Entrepreneur, Goals, Overview, Radar, Wealth } from "../components/life/SectionsA";
import { Academy, Crm, Decisions, Discipline, Failures, Reviews, Security, Simulator, Vision } from "../components/life/SectionsB";

const SECTIONS: [string, string, string][] = [
  ["overview", "Growth Analytics", "Panel"], ["entrepreneur", "Entrepreneur", "Negocio"], ["radar", "Opportunity Radar", "Negocio"],
  ["wealth", "Wealth", "Negocio"], ["academy", "Knowledge Academy", "Crecimiento"], ["leadership", "Leadership", "Crecimiento"],
  ["communication", "Communication", "Crecimiento"], ["discipline", "Discipline", "Crecimiento"], ["goals", "Goal Engine", "Dirección"],
  ["decisions", "Decision Journal", "Dirección"], ["failures", "Failure Analysis", "Dirección"], ["crm", "Personal CRM", "Dirección"],
  ["vision", "Legacy", "Dirección"], ["reviews", "Briefing & Review", "Dirección"], ["security", "Privacidad", "Sistema"],
];

/** VISTAN LIFE OS — sistema de desarrollo personal y empresarial. */
export function Life() {
  const [params, setParams] = useSearchParams();
  const s = params.get("s") && SECTIONS.some((x) => x[0] === params.get("s")) ? params.get("s")! : "overview";
  const go = (k: string) => setParams(k === "overview" ? {} : { s: k });
  const [locked, setLocked] = useState<boolean | null>(null);
  const [pin, setPin] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    life.get<{ enabled: boolean; unlocked: boolean }>("/lock").then((r) => setLocked(!r.unlocked)).catch(() => setLocked(false));
    const on = () => setLocked(true);
    window.addEventListener("vistan-life-locked", on);
    return () => window.removeEventListener("vistan-life-locked", on);
  }, []);
  if (locked === null) return <div className="desk"><p className="desk-empty">Cargando LIFE OS…</p></div>;
  if (locked) {
    return (
      <div className="desk life-lock">
        <form className="lock-card" onSubmit={(e) => { e.preventDefault(); setErr(null); life.post("/lock/unlock", { pin }).then(() => { setLocked(false); setPin(""); }).catch((x: Error) => setErr(x.message)); }}>
          <span className="desk-logo">VISTAN</span><b>LIFE OS bloqueado</b>
          <p className="muted small">Introduce tu PIN para ver tus datos personales.</p>
          <input type="password" inputMode="numeric" autoFocus value={pin} onChange={(e) => setPin(e.target.value)} aria-label="PIN" placeholder="PIN" />
          <button type="submit" className="btn" disabled={pin.length < 4}>Desbloquear</button>
          {err && <p className="error-line" role="alert">{err}</p>}
        </form>
      </div>
    );
  }
  const groups = [...new Set(SECTIONS.map((x) => x[2]))];
  return (
    <div className="desk life" data-testid="life-os">
      <header className="desk-top">
        <div className="desk-brand"><span className="desk-logo">VISTAN</span><span className="desk-title">LIFE OS</span></div>
        <span className="life-motto">BUILD YOURSELF. BUILD YOUR FUTURE.</span>
      </header>
      <div className="life-body">
        <nav className="life-nav" aria-label="Secciones de LIFE OS">
          {groups.map((g) => (
            <div key={g}><small>{g}</small>{SECTIONS.filter((x) => x[2] === g).map(([k, l]) => (
              <button type="button" key={k} className={s === k ? "on" : ""} onClick={() => go(k)}>{l}</button>
            ))}</div>
          ))}
        </nav>
        <main className="desk-main">
          {s === "overview" && <Overview go={go} />}
          {s === "entrepreneur" && <Entrepreneur />}
          {s === "radar" && <Radar />}
          {s === "wealth" && <Wealth />}
          {s === "academy" && <Academy />}
          {s === "leadership" && <Simulator area="leadership" />}
          {s === "communication" && <Simulator area="communication" />}
          {s === "discipline" && <Discipline />}
          {s === "goals" && <Goals />}
          {s === "decisions" && <Decisions />}
          {s === "failures" && <Failures />}
          {s === "crm" && <Crm />}
          {s === "vision" && <Vision />}
          {s === "reviews" && <Reviews />}
          {s === "security" && <Security onLocked={() => setLocked(true)} />}
        </main>
      </div>
      <footer className="desk-foot">LIFE OS · tus datos se quedan en tu Mac · VISTAN te ayuda a pensar, no decide por ti</footer>
    </div>
  );
}
