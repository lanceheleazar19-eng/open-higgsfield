import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Dashboard } from "../api/types";
import { useAsync } from "../api/useAsync";
import { useAtlas } from "../components/AtlasContext";
import { CommandBar } from "../components/control/CommandBar";
import { IntelPanel } from "../components/control/IntelPanel";
import { SystemPanel } from "../components/control/SystemPanel";
import { Transcript, type Exchange } from "../components/control/Transcript";
import { AtlasCore, type NodeInfo } from "../components/core/AtlasCore";
import type { CoreState } from "../components/core/scene";
import { Telemetry } from "../components/Telemetry";
import { useVoice } from "../hooks/useVoice";
import { formatMoney, greetingFor } from "../lib/format";

const MIN_THINK_MS = 450; // deja ver la transición de estado del núcleo

/** Métricas reales de cada nodo; los módulos no construidos muestran su fase. */
function nodeInfo(d: Dashboard | null, phases: Map<string, number>, records: number | undefined, aiConnected: boolean): Record<string, NodeInfo> {
  const phase = (id: string) => ({ metric: `Fase ${phases.get(id) ?? "—"}`, planned: true });
  const n = (v: number, one: string, many: string) => `${v} ${v === 1 ? one : many}`;
  if (!d) return {};
  return {
    ai: aiConnected ? { metric: "Conectado", planned: false } : { metric: "Modo local", planned: true },
    memory: records !== undefined ? { metric: n(records, "registro", "registros"), planned: true } : phase("memory"),
    agents: { metric: "0 activos", planned: true },
    tasks: { metric: n(d.tasks.pending, "pendiente", "pendientes"), planned: true, alert: d.tasks.overdue > 0 },
    calendar: { metric: n(d.events.items.length, "próximo", "próximos"), planned: true },
    projects: { metric: n(d.projects.active, "activo", "activos"), planned: true },
    research: phase("research"),
    gym: { metric: `${n(d.fitness.sessions_7d, "sesión", "sesiones")} · 7d`, planned: true },
    finance: d.finance.has_data
      ? { metric: `${formatMoney(d.finance.net_cents, d.finance.currency)} mes`, planned: true, alert: d.finance.net_cents < 0 }
      : { metric: "Sin datos", planned: true },
    trading: phase("trading"),
  };
}

export function ControlCenter() {
  const dash = useAsync(api.dashboard, 60_000);
  const { health, healthError, modules } = useAtlas();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [responding, setResponding] = useState(false);
  const [ripple, setRipple] = useState(0);
  const [log, setLog] = useState<Exchange[]>([]);
  const [revealId, setRevealId] = useState<number | null>(null);
  const [speakReplies, setSpeakReplies] = useState(() => {
    try { return localStorage.getItem("atlas.speak") === "1"; } catch { return false; }
  });
  const seq = useRef(0);
  const speakRef = useRef(speakReplies);
  speakRef.current = speakReplies;

  const run = useCallback(async (question: string, fetcher: () => Promise<{ reply: string }>) => {
    const id = ++seq.current;
    setLog((l) => [...l, { id, question, reply: null }]);
    setBusy(true);
    setRipple((r) => r + 1);
    const t0 = performance.now();
    let reply: string;
    let error = false;
    try {
      reply = (await fetcher()).reply;
    } catch (e) {
      reply = (e as Error).message;
      error = true;
    }
    const wait = MIN_THINK_MS - (performance.now() - t0);
    if (wait > 0) await new Promise((r) => setTimeout(r, wait));
    setLog((l) => l.map((x) => (x.id === id ? { ...x, reply, error } : x)));
    setBusy(false);
    setResponding(true);
    setRevealId(id);
    if (speakRef.current && !error) voiceRef.current?.speak(reply);
    void dash.reload();
  }, [dash.reload]); // eslint-disable-line react-hooks/exhaustive-deps

  const ask = useCallback((q: string) => run(q, () => api.ask(q)), [run]);
  const voice = useVoice(ask);
  const voiceRef = useRef(voice);
  voiceRef.current = voice;

  useEffect(() => {
    try { localStorage.setItem("atlas.speak", speakReplies ? "1" : "0"); } catch { /* sin almacenamiento */ }
  }, [speakReplies]);

  const coreState: CoreState = voice.listening ? "listening" : busy ? "thinking" : responding || voice.speaking ? "responding" : "idle";
  const offline = !!healthError || (!!dash.error && !dash.data);
  const phases = useMemo(() => new Map(modules.map((m) => [m.id, m.phase])), [modules]);
  const info = useMemo(
    () => nodeInfo(dash.data, phases, health?.storage?.records, !!health?.ai.configured),
    [dash.data, phases, health],
  );
  const d = dash.data;

  return (
    <div className="control-page">
      <div className={`control ${offline ? "is-offline" : ""}`}>
        <SystemPanel health={health} offline={offline} voice={voice} speakReplies={speakReplies} />

        <div className="stage">
          <header className="stage-head">
            <p className="eyebrow">Personal Intelligence System</p>
            {d && (
              <h1 className="greet">
                {greetingFor(d.greeting.part_of_day)}{d.greeting.name ? <>, <span className="accent">{d.greeting.name}</span></> : null}
              </h1>
            )}
            {d && !d.greeting.name && <p className="hint"><Link to="/settings">Dime cómo te llamas</Link> para personalizar el saludo.</p>}
          </header>

          <AtlasCore info={info} state={offline ? "idle" : coreState} rippleKey={ripple} onOpen={navigate} />

          {offline && (
            <div className="offline-banner" role="alert">
              <strong>Núcleo de ATLAS sin conexión.</strong>{" "}
              {(dash.error ?? healthError)?.message}. Comprueba que el backend está en marcha (scripts/start).
              <button className="btn" onClick={() => void dash.reload()}>Reintentar</button>
            </div>
          )}

          <div className="dock">
            <Transcript items={log} revealId={revealId} onRevealed={() => { setRevealId(null); setResponding(false); }} onClear={() => setLog([])} />
            <CommandBar
              busy={busy || offline}
              voice={voice}
              speakReplies={speakReplies}
              onToggleSpeak={() => setSpeakReplies((v) => !v)}
              onAsk={ask}
              onBriefing={() => run("Resumen ejecutivo", api.briefing)}
            />
          </div>
        </div>

        <IntelPanel data={d} />
      </div>

      {d && (
        <section className="telemetry" aria-labelledby="telemetry-title">
          <header className="section-head">
            <p className="eyebrow">Datos registrados</p>
            <h2 id="telemetry-title">Telemetría detallada</h2>
          </header>
          <Telemetry data={d} />
        </section>
      )}
    </div>
  );
}
