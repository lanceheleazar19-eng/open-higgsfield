import { useSearchParams } from "react-router-dom";
import { Console } from "../components/meta/MetaA";
import { AgentsView, Governance, MemoryIntel, RouterView } from "../components/meta/MetaB";
import { Bench, Evaluation, Execution, Multimodal } from "../components/meta/MetaC";

const SECTIONS: [string, string, string][] = [
  ["console", "Console & Council", "Pensar"], ["exec", "Autonomous Execution", "Ejecutar"],
  ["router", "Model Router", "Coordinar"], ["agents", "Multi-Agent System", "Coordinar"], ["memory", "Memory Intelligence", "Coordinar"],
  ["bench", "Benchmark Center", "Verificar"], ["eval", "Self-Evaluation", "Verificar"], ["multimodal", "Multimodal", "Verificar"],
  ["governance", "Security & Governance", "Gobierno"],
];

/** VISTAN META-BRAIN — THINK. COORDINATE. VERIFY. EXECUTE. */
export function MetaBrain() {
  const [params, setParams] = useSearchParams();
  const run = params.get("run") ? Number(params.get("run")) : null;
  const s = params.get("s") && SECTIONS.some((x) => x[0] === params.get("s")) ? params.get("s")! : "console";
  const go = (k: string) => setParams(k === "console" ? {} : { s: k });
  const groups = [...new Set(SECTIONS.map((x) => x[2]))];
  return (
    <div className="desk life lab meta" data-testid="meta-brain">
      <header className="desk-top">
        <div className="desk-brand"><span className="desk-logo">VISTAN</span><span className="desk-title">META-BRAIN</span></div>
        <span className="life-motto">THINK. COORDINATE. VERIFY. EXECUTE.</span>
      </header>
      <div className="life-body">
        <nav className="life-nav" aria-label="Secciones del META-BRAIN">
          {groups.map((g) => (
            <div key={g}><small>{g}</small>{SECTIONS.filter((x) => x[2] === g).map(([k, l]) => <button type="button" key={k} className={s === k ? "on" : ""} onClick={() => go(k)}>{l}</button>)}</div>
          ))}
        </nav>
        <main className="desk-main">
          {s === "console" && <Console initialRun={run} onRun={(id) => setParams(id ? { run: String(id) } : {})} />}
          {s === "exec" && <Execution />}
          {s === "router" && <RouterView />}
          {s === "agents" && <AgentsView />}
          {s === "memory" && <MemoryIntel />}
          {s === "bench" && <Bench />}
          {s === "eval" && <Evaluation />}
          {s === "multimodal" && <Multimodal />}
          {s === "governance" && <Governance />}
        </main>
      </div>
      <footer className="desk-foot">META-BRAIN · modelos reales y medidos · consenso ≠ verdad · las acciones sensibles siempre con tu autorización · kill switch en Gobierno</footer>
    </div>
  );
}
