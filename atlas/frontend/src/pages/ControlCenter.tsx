import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Dashboard, StoredMessage } from "../api/types";
import { useAsync } from "../api/useAsync";
import { useAtlas } from "../components/AtlasContext";
import { CommandBar } from "../components/control/CommandBar";
import { IntelPanel } from "../components/control/IntelPanel";
import { Transcript, type Exchange } from "../components/control/Transcript";
import { AtlasCore, type NodeInfo } from "../components/core/AtlasCore";
import type { CoreState } from "../components/core/scene";
import { BootScreen, alreadyBooted, welcomeEnabled } from "../components/BootScreen";
import { Telemetry } from "../components/Telemetry";
import { useVoice } from "../hooks/useVoice";
import { formatMoney, greetingFor } from "../lib/format";

const MIN_THINK_MS = 450; // deja ver la transición de estado del núcleo

/** Métricas reales de cada nodo; los módulos no construidos muestran su fase. */
function nodeInfo(d: Dashboard | null, phases: Map<string, number>, memories: number | undefined, aiModel: string | null): Record<string, NodeInfo> {
  const phase = (id: string) => ({ metric: `Fase ${phases.get(id) ?? "—"}`, planned: true });
  const n = (v: number, one: string, many: string) => `${v} ${v === 1 ? one : many}`;
  if (!d) return {};
  return {
    ai: aiModel ? { metric: aiModel, planned: false } : { metric: "Modo local", planned: false, alert: false },
    memory: memories !== undefined ? { metric: n(memories, "recuerdo", "recuerdos"), planned: false } : phase("memory"),
    agents: { metric: "0 activos", planned: true },
    tasks: { metric: n(d.tasks.pending, "pendiente", "pendientes"), planned: false, alert: d.tasks.overdue > 0 },
    calendar: { metric: n(d.events.items.length, "próximo", "próximos"), planned: true },
    projects: { metric: n(d.projects.active, "activo", "activos"), planned: true },
    research: phase("research"),
    gym: { metric: d.fitness.today_routine ? `Hoy: ${d.fitness.today_routine}` : `${n(d.fitness.sessions_7d, "sesión", "sesiones")} · 7d`, planned: false },
    finance: d.finance.has_data
      ? { metric: `${formatMoney(d.finance.net_cents, d.finance.currency)} mes`, planned: false, alert: d.finance.net_cents < 0 || d.finance.budgets?.some((b) => b.status === "over") }
      : { metric: "Sin datos", planned: false },
    trading: d.trading && (d.trading.open || d.trading.closed)
      ? { metric: `Simulado ${d.trading.pnl >= 0 ? "+" : ""}${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 }).format(d.trading.pnl)}`, planned: false }
      : { metric: "Sin operaciones", planned: false },
  };
}

export function ControlCenter() {
  const dash = useAsync(api.dashboard, 60_000);
  const { health, healthError, modules, reloadHealth } = useAtlas();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [afterglow, setAfterglow] = useState(false);
  const [ripple, setRipple] = useState(0);
  const [log, setLog] = useState<Exchange[]>([]);
  const [speakReplies, setSpeakReplies] = useState(() => {
    try { return localStorage.getItem("atlas.speak") === "1"; } catch { return false; }
  });
  const [conversationId, setConversationId] = useState<number | null>(() => {
    try { const v = Number(localStorage.getItem("atlas.conversation")); return v > 0 ? v : null; } catch { return null; }
  });
  const convRef = useRef(conversationId);
  convRef.current = conversationId;
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
    setLog((l) => [...l, { id, question, reply: "", phase: "thinking" }]);
    setBusy(true);
    setRipple((r) => r + 1);
    voiceRef.current?.stopSpeaking();
    voiceRef.current?.beginReply();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const t0 = performance.now();
    let text = "";
    let firstDelta = true;
    let completed = false;
    let mode: string | null = null;
    let cid = convRef.current;
    let spoken = 0; // parte del texto ya enviada a la voz
    const speakNew = (final: boolean) => {
      // Si me hablaste por voz, respondo en voz aunque el altavoz de la barra esté apagado
      if (!speakRef.current && !voiceRef.current?.conversing) return;
      const pendingText = text.slice(spoken);
      // habla hasta el último final de frase disponible (o todo, al terminar)
      const m = final ? pendingText.length : Math.max(pendingText.lastIndexOf(". "), pendingText.lastIndexOf("? "),
        pendingText.lastIndexOf("! "), pendingText.lastIndexOf(".\n")) + 1;
      if (m > 0) {
        voiceRef.current?.enqueue(pendingText.slice(0, m));
        spoken += m;
      }
    };
    try {
      await api.chat(prompt, convRef.current, (ev) => {
        if (ev.type === "meta") {
          cid = ev.conversation_id;
          setConversationId(ev.conversation_id);
        } else if (ev.type === "meal") {
          patch(id, { meal: { count: ev.entries.length } });
        } else if (ev.type === "finance") {
          patch(id, { money: { item: ev.transaction, state: "shown" } });
        } else if (ev.type === "gym") {
          patch(id, { gym: { sets: ev.session.working_sets, tonnage: ev.session.tonnage } });
        } else if (ev.type === "task") {
          patch(id, { task: { action: ev.action, item: ev.task, state: "shown" } });
        } else if (ev.type === "memory") {
          patch(id, { memory: { action: ev.action, item: ev.memory, state: "shown" } });
        } else if (ev.type === "delta") {
          if (firstDelta) { firstDelta = false; setStreaming(true); }
          text += ev.text;
          patch(id, { reply: text, phase: "streaming" });
          speakNew(false);
        } else if (ev.type === "done") {
          completed = true;
          mode = ev.mode;
          speakNew(true);
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
      void dash.reload();
      void reloadHealth();
      // La IA propone recuerdos del intercambio; nunca se guardan sin tu aprobación
      if (completed && mode === "ai" && cid && question.length >= 15) {
        api.suggestMemories(cid)
          .then(({ suggestions }) => {
            if (suggestions.length) patch(id, { suggestions: suggestions.map((sg) => ({ ...sg, state: "pending" as const })) });
          })
          .catch(() => { /* sugerencias opcionales */ });
      }
    }
  }, [dash.reload]); // eslint-disable-line react-hooks/exhaustive-deps

  // Retoma la última conversación al volver a abrir ATLAS
  useEffect(() => {
    try {
      if (conversationId) localStorage.setItem("atlas.conversation", String(conversationId));
      else localStorage.removeItem("atlas.conversation");
    } catch { /* sin almacenamiento */ }
  }, [conversationId]);
  useEffect(() => {
    const cid = convRef.current;
    if (!cid) return;
    api.conversation(cid)
      .then((c) => setLog((l) => (l.length ? l : toExchanges(c.messages, seq))))
      .catch(() => setConversationId(null)); // borrada o inexistente → empezar de cero
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const newConversation = () => {
    abortRef.current?.abort();
    setConversationId(null);
    setLog([]);
  };

  const confirmForget = async (exId: number) => {
    const x = logRef.current.find((e) => e.id === exId);
    if (!x?.memory) return;
    try {
      await api.deleteMemory(x.memory.item.id);
      patch(exId, { memory: { ...x.memory, state: "done" } });
      void reloadHealth();
    } catch (e) {
      patch(exId, { memory: { ...x.memory, state: "error", error: (e as Error).message } });
    }
  };

  const taskAction = async (exId: number, action: "undo" | "complete") => {
    const x = logRef.current.find((e) => e.id === exId);
    if (!x?.task?.item) return;
    try {
      if (action === "undo") await api.deleteTask(x.task.item.id);
      else await api.completeTask(x.task.item.id);
      patch(exId, { task: { ...x.task, state: action === "undo" ? "undone" : "done" } });
      void dash.reload();
    } catch {
      patch(exId, { task: { ...x.task, state: "error" } });
    }
  };

  const moneyUndo = async (exId: number) => {
    const x = logRef.current.find((e) => e.id === exId);
    if (!x?.money) return;
    try {
      await api.deleteTransaction(x.money.item.id);
      patch(exId, { money: { ...x.money, state: "undone" } });
      void dash.reload();
    } catch {
      patch(exId, { money: { ...x.money, state: "error" } });
    }
  };

  const decideSuggestion = async (exId: number, idx: number, save: boolean) => {
    const x = logRef.current.find((e) => e.id === exId);
    const sg = x?.suggestions?.[idx];
    if (!x || !sg) return;
    const set = (state: "saved" | "dismissed" | "error") =>
      setLog((l) => l.map((e) => (e.id === exId
        ? { ...e, suggestions: e.suggestions!.map((s2, i) => (i === idx ? { ...s2, state } : s2)) } : e)));
    if (!save) return set("dismissed");
    try {
      await api.createMemory({ content: sg.content, kind: sg.kind, source: "suggested" });
      set("saved");
      void reloadHealth();
    } catch {
      set("error");
    }
  };

  const voice = useVoice(converse, busy);
  voiceRef.current = voice;

  // Pantalla de arranque con bienvenida hablada (una vez por sesión del navegador)
  const [booting, setBooting] = useState(() => welcomeEnabled() && !alreadyBooted());
  const startAtlas = async (withVoice: boolean) => {
    setBooting(false);
    setRipple((r) => r + 1);
    if (!withVoice) return;
    try {
      const { reply } = await api.welcome();
      const id = ++seq.current;
      setLog((l) => [...l, { id, question: "Inicio de sesión", reply, phase: "done", mode: "local" }]);
      voiceRef.current?.speak(reply);
    } catch { /* núcleo sin conexión: el banner ya lo indica */ }
  };

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
    () => nodeInfo(dash.data, phases, health?.storage?.memories, health?.ai.configured ? health.ai.model : null),
    [dash.data, phases, health],
  );
  const d = dash.data;

  return (
    <div className="control-page">
      {booting && <BootScreen health={health} onStart={(v) => void startAtlas(v)} />}
      <div className={`control ${offline ? "is-offline" : ""}`}>
        <div className="stage">
          <header className="stage-head">
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
            <Transcript items={log} onNew={newConversation} onForget={confirmForget} onSuggestion={decideSuggestion} onTask={taskAction} onMoneyUndo={moneyUndo} />
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

        <IntelPanel data={d} onChanged={() => void dash.reload()} />
      </div>

      {d && (
        <section className="telemetry" id="telemetria" aria-labelledby="telemetry-title">
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

/** Reconstruye el historial guardado en pares pregunta/respuesta para mostrarlo. */
function toExchanges(messages: StoredMessage[], seq: { current: number }): Exchange[] {
  const out: Exchange[] = [];
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    if (m.role !== "user") continue;
    const next = messages[i + 1]?.role === "assistant" ? messages[i + 1] : null;
    out.push({
      id: ++seq.current, question: m.content, reply: next?.content ?? "",
      phase: next ? "done" : "error", mode: next?.mode ?? undefined, model: next?.model ?? null,
    });
  }
  return out.slice(-4);
}
