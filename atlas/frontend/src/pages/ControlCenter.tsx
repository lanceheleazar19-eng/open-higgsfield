import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { ChatMessage, Dashboard } from "../api/types";
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
function nodeInfo(d: Dashboard | null, phases: Map<string, number>, records: number | undefined, aiModel: string | null): Record<string, NodeInfo> {
  const phase = (id: string) => ({ metric: `Fase ${phases.get(id) ?? "—"}`, planned: true });
  const n = (v: number, one: string, many: string) => `${v} ${v === 1 ? one : many}`;
  if (!d) return {};
  return {
    ai: aiModel ? { metric: aiModel, planned: false } : { metric: "Modo local", planned: false, alert: false },
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
  const [streaming, setStreaming] = useState(false);
  const [afterglow, setAfterglow] = useState(false);
  const [ripple, setRipple] = useState(0);
  const [log, setLog] = useState<Exchange[]>([]);
  const [speakReplies, setSpeakReplies] = useState(() => {
    try { return localStorage.getItem("atlas.speak") === "1"; } catch { return false; }
  });
  const seq = useRef(0);
  const logRef = useRef(log);
  logRef.current = log;
  const abortRef = useRef<AbortController | null>(null);
  const speakRef = useRef(speakReplies);
  speakRef.current = speakReplies;
  const voiceRef = useRef<ReturnType<typeof useVoice> | null>(null);

  const patch = (id: number, p: Partial<Exchange>) => setLog((l) => l.map((x) => (x.id === id ? { ...x, ...p } : x)));

  /** Envía una consulta al cerebro (IA si está disponible; si no, modo local) y transmite la respuesta. */
  const converse = useCallback(async (question: string, prompt = question) => {
    const id = ++seq.current;
    const history: ChatMessage[] = logRef.current
      .filter((x) => x.phase === "done" && x.reply)
      .slice(-6)
      .flatMap((x) => [{ role: "user" as const, content: x.question }, { role: "assistant" as const, content: x.reply }]);
    setLog((l) => [...l, { id, question, reply: "", phase: "thinking" }]);
    setBusy(true);
    setRipple((r) => r + 1);
    voiceRef.current?.stopSpeaking();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const t0 = performance.now();
    let text = "";
    let firstDelta = true;
    let completed = false;
    try {
      await api.chat(prompt, history, (ev) => {
        if (ev.type === "delta") {
          if (firstDelta) { firstDelta = false; setStreaming(true); }
          text += ev.text;
          patch(id, { reply: text, phase: "streaming" });
        } else if (ev.type === "done") {
          completed = true;
          patch(id, { phase: "done", mode: ev.mode, model: ev.model, note: ev.reason ?? null });
        } else if (ev.type === "error") {
          patch(id, { phase: "error", reply: text ? `${text}\n[${ev.message}]` : ev.message });
        }
      }, ctrl.signal);
      if (!text) patch(id, { phase: "error", reply: "No se recibió respuesta." });
    } catch (e) {
      if ((e as Error).name === "AbortError") patch(id, { phase: "stopped", reply: text });
      else patch(id, { phase: "error", reply: (e as Error).message });
    } finally {
      // Deja ver la transición del núcleo aunque la respuesta sea instantánea
      const wait = MIN_THINK_MS - (performance.now() - t0);
      if (wait > 0) await new Promise((r) => setTimeout(r, wait));
      abortRef.current = null;
      setBusy(false);
      setStreaming(false);
      setAfterglow(true);
      setTimeout(() => setAfterglow(false), 1200);
      if (speakRef.current && completed && text) voiceRef.current?.speak(text);
      void dash.reload();
    }
  }, [dash.reload]); // eslint-disable-line react-hooks/exhaustive-deps

  const voice = useVoice(converse);
  voiceRef.current = voice;

  useEffect(() => {
    try { localStorage.setItem("atlas.speak", speakReplies ? "1" : "0"); } catch { /* sin almacenamiento */ }
  }, [speakReplies]);

  const briefing = () => converse("Resumen ejecutivo", "Prepárame el resumen ejecutivo del día (daily briefing) con mis datos.");

  const coreState: CoreState = voice.listening ? "listening"
    : busy && !streaming ? "thinking"
      : streaming || afterglow || voice.speaking ? "responding" : "idle";
  const offline = !!healthError || (!!dash.error && !dash.data);
  const phases = useMemo(() => new Map(modules.map((m) => [m.id, m.phase])), [modules]);
  const info = useMemo(
    () => nodeInfo(dash.data, phases, health?.storage?.records, health?.ai.configured ? health.ai.model : null),
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
            <Transcript items={log} onClear={() => setLog([])} />
            <CommandBar
              busy={busy}
              offline={offline}
              onStop={() => abortRef.current?.abort()}
              voice={voice}
              speakReplies={speakReplies}
              onToggleSpeak={() => setSpeakReplies((v) => !v)}
              onAsk={converse}
              onBriefing={briefing}
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
