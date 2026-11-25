import { useSearchParams } from "react-router-dom";
import { lab } from "../api/life";
import { Command, Radar, Research, type Meta } from "../components/lab/LabA";
import { AiLab, AnalyticsLab, Experiments, Prototypes } from "../components/lab/LabB";
import { Agent, Future, Ideas, LabProjects, LabWorkflows, Library, Patents } from "../components/lab/LabC";
import { State, useLoad } from "../components/life/kit";

const SECTIONS: [string, string, string][] = [
  ["command", "Command Center", "Laboratorio"], ["radar", "Technology Radar", "Explorar"], ["research", "Research Lab", "Explorar"],
  ["future", "Future Simulator", "Explorar"], ["experiments", "Experimentation", "Experimentar"], ["ai", "AI Lab · Arena", "Experimentar"],
  ["prototypes", "Prototype Studio", "Inventar"], ["ideas", "Idea Generator", "Inventar"], ["patents", "Patents", "Inventar"],
  ["library", "Knowledge Base", "Conocimiento"], ["projects", "Innovation Projects", "Gestión"], ["workflows", "Lab Workflows", "Gestión"],
  ["analytics", "Analytics", "Gestión"], ["agent", "Innovation Agent", "Agente"],
];

/** VISTAN INNOVATION LAB — EXPLORE. EXPERIMENT. INVENT. */
export function Lab() {
  const [params, setParams] = useSearchParams();
  const s = params.get("s") && SECTIONS.some((x) => x[0] === params.get("s")) ? params.get("s")! : "command";
  const go = (k: string) => setParams(k === "command" ? {} : { s: k });
  const meta = useLoad<Meta>("/meta", [], lab);
  const groups = [...new Set(SECTIONS.map((x) => x[2]))];
  return (
    <div className="desk life lab" data-testid="innovation-lab">
      <header className="desk-top">
        <div className="desk-brand"><span className="desk-logo">VISTAN</span><span className="desk-title">INNOVATION LAB</span></div>
        <span className="life-motto">EXPLORE. EXPERIMENT. INVENT.</span>
      </header>
      <div className="life-body">
        <nav className="life-nav" aria-label="Secciones del Innovation Lab">
          {groups.map((g) => (
            <div key={g}><small>{g}</small>{SECTIONS.filter((x) => x[2] === g).map(([k, l]) => <button type="button" key={k} className={s === k ? "on" : ""} onClick={() => go(k)}>{l}</button>)}</div>
          ))}
        </nav>
        <main className="desk-main">
          <State loading={meta.loading && !meta.data} error={meta.error}>
            {meta.data && (
              <>
                {s === "command" && <Command meta={meta.data} go={go} />}
                {s === "radar" && <Radar meta={meta.data} />}
                {s === "research" && <Research meta={meta.data} />}
                {s === "future" && <Future />}
                {s === "experiments" && <Experiments meta={meta.data} />}
                {s === "ai" && <AiLab />}
                {s === "prototypes" && <Prototypes />}
                {s === "ideas" && <Ideas meta={meta.data} />}
                {s === "patents" && <Patents />}
                {s === "library" && <Library meta={meta.data} />}
                {s === "projects" && <LabProjects />}
                {s === "workflows" && <LabWorkflows meta={meta.data} />}
                {s === "analytics" && <AnalyticsLab meta={meta.data} />}
                {s === "agent" && <Agent />}
              </>
            )}
          </State>
        </main>
      </div>
      <footer className="desk-foot">INNOVATION LAB · hechos con fuente, hipótesis marcadas · el código solo se ejecuta en el sandbox aislado y con tu confirmación</footer>
    </div>
  );
}
