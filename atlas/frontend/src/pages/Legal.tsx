import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { legal, life } from "../api/life";
import { Command, Contracts, type LMeta, Research } from "../components/legal/LegalA";
import { Agent, Cases, Compliance, Knowledge, Risks, Security, Studio } from "../components/legal/LegalB";
import { State, useLoad } from "../components/life/kit";

const SECTIONS: [string, string, string][] = [
  ["command", "Command Center", "Panel"], ["research", "Legal Research", "Investigar"], ["knowledge", "Knowledge Base", "Investigar"],
  ["contracts", "Contract Analyzer", "Documentos"], ["studio", "Document Studio", "Documentos"],
  ["cases", "Expedientes", "Gestión"], ["risks", "Riesgos y plazos", "Gestión"], ["compliance", "Cumplimiento", "Gestión"],
  ["agent", "Legal Agent", "Agente"], ["security", "Seguridad", "Agente"],
];

/** VISTAN LEGAL — departamento de inteligencia jurídica. Mismo PIN y sesión que LIFE OS. */
export function Legal() {
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
  const meta = useLoad<LMeta>(locked === false ? "/meta" : null, [locked], legal);
  const s = params.get("s") && SECTIONS.some((x) => x[0] === params.get("s")) ? params.get("s")! : "command";
  const go = (k: string, extra: Record<string, string> = {}) => setParams(k === "command" ? {} : { s: k, ...extra });
  const num = (k: string) => (params.get(k) ? Number(params.get(k)) : null);
  if (locked === null) return <div className="desk"><p className="desk-empty">Cargando VISTAN LEGAL…</p></div>;
  if (locked) {
    return (
      <div className="desk life-lock">
        <form className="lock-card" onSubmit={(e) => { e.preventDefault(); setErr(null); life.post("/lock/unlock", { pin }).then(() => { setLocked(false); setPin(""); }).catch((x: Error) => setErr(x.message)); }}>
          <span className="desk-logo">VISTAN</span><b>VISTAN LEGAL bloqueado</b>
          <p className="muted small">Información jurídica confidencial. Introduce tu PIN (el mismo de LIFE OS).</p>
          <input type="password" inputMode="numeric" autoFocus value={pin} onChange={(e) => setPin(e.target.value)} aria-label="PIN" placeholder="PIN" />
          <button type="submit" className="btn" disabled={pin.length < 4}>Desbloquear</button>
          {err && <p className="error-line" role="alert">{err}</p>}
        </form>
      </div>
    );
  }
  const groups = [...new Set(SECTIONS.map((x) => x[2]))];
  return (
    <div className="desk life lab legal" data-testid="vistan-legal">
      <header className="desk-top">
        <div className="desk-brand"><span className="desk-logo">VISTAN</span><span className="desk-title">LEGAL</span></div>
        <span className="life-motto">INVESTIGACIÓN RIGUROSA · DOCUMENTOS INTELIGENTES · GESTIÓN JURÍDICA</span>
      </header>
      <div className="life-body">
        <nav className="life-nav" aria-label="Secciones de VISTAN LEGAL">
          {groups.map((g) => <div key={g}><small>{g}</small>{SECTIONS.filter((x) => x[2] === g).map(([k, l]) => <button type="button" key={k} className={s === k ? "on" : ""} onClick={() => go(k)}>{l}</button>)}</div>)}
        </nav>
        <main className="desk-main">
          <State loading={meta.loading && !meta.data} error={meta.error}>
            {meta.data && <>
              {s === "command" && <Command go={go} />}
              {s === "research" && <Research initial={num("id")} />}
              {s === "knowledge" && <Knowledge />}
              {s === "contracts" && <Contracts initialDoc={num("doc")} />}
              {s === "studio" && <Studio meta={meta.data} />}
              {s === "cases" && <Cases meta={meta.data} initial={num("id")} />}
              {s === "risks" && <Risks />}
              {s === "compliance" && <Compliance meta={meta.data} />}
              {s === "agent" && <Agent initialQ={params.get("q") ?? ""} />}
              {s === "security" && <Security meta={meta.data} onChange={meta.reload} />}
            </>}
          </State>
        </main>
      </div>
      <footer className="desk-foot">VISTAN LEGAL · información jurídica, no asesoramiento profesional · fuentes oficiales verificables · plazos siempre con verificación prioritaria</footer>
    </div>
  );
}
