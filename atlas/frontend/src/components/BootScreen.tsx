import { useEffect, useState } from "react";
import type { Health } from "../api/types";

export const WELCOME_KEY = "atlas.welcome";
const BOOTED_KEY = "atlas.booted";

export function welcomeEnabled(): boolean {
  try { return localStorage.getItem(WELCOME_KEY) !== "0"; } catch { return false; }
}

export function alreadyBooted(): boolean {
  try { return sessionStorage.getItem(BOOTED_KEY) === "1"; } catch { return true; }
}

/** Pantalla de arranque. Los navegadores no permiten hablar sin que el usuario pulse algo:
 *  el botón «Iniciar» es esa interacción, y a la vez la entrada cinematográfica a ATLAS. */
export function BootScreen({ health, onStart }: { health: Health | null; onStart: (withVoice: boolean) => void }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => Math.min(s + 1, 4)), 380);
    return () => clearInterval(id);
  }, []);
  const start = (voice: boolean) => {
    try { sessionStorage.setItem(BOOTED_KEY, "1"); } catch { /* sin almacenamiento */ }
    onStart(voice);
  };
  const lines: [string, string, boolean][] = [
    ["Núcleo", health ? (health.status === "online" ? "operativo" : "degradado") : "conectando…", !!health],
    ["Memoria", health?.storage ? `${health.storage.memories} recuerdos` : "—", !!health?.storage],
    ["Cerebro IA", health ? (health.ai.configured ? health.ai.model ?? "conectado" : "modo local") : "—", !!health],
    ["Voz", typeof window !== "undefined" && "speechSynthesis" in window ? "lista" : "no disponible", true],
  ];
  return (
    <div className="boot" role="dialog" aria-modal="true" aria-label="Inicio de ATLAS">
      <div className="boot-inner">
        <div className="boot-ring" aria-hidden="true"><span /><span /><span /></div>
        <p className="eyebrow">Personal Intelligence System</p>
        <h1 className="boot-title">ATLAS</h1>
        <ul className="boot-lines">
          {lines.map(([k, v, ok], i) => (
            <li key={k} className={i < step ? "on" : ""}>
              <span>{k}</span><span className={ok ? "t-ok" : "t-dim"}>{i < step ? v : "…"}</span>
            </li>
          ))}
        </ul>
        <button className="btn boot-btn" onClick={() => start(true)} autoFocus>Iniciar ATLAS</button>
        <button className="link-btn" onClick={() => start(false)}>Entrar en silencio</button>
      </div>
    </div>
  );
}
