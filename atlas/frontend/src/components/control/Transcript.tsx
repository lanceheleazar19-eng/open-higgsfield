import { Link } from "react-router-dom";
import type { MemoryItem, MemorySuggestion, TaskItem } from "../../api/types";
import { KIND_LABEL } from "../../lib/memory";

export interface Exchange {
  id: number;
  question: string;
  reply: string;
  phase: "thinking" | "streaming" | "done" | "error" | "stopped";
  mode?: "ai" | "local" | "memory" | "tasks" | "gym";
  gym?: { sets: number; tonnage: number };
  model?: string | null;
  note?: string | null;
  memory?: { action: "saved" | "duplicate" | "forget_candidate"; item: MemoryItem; state: "shown" | "done" | "error"; error?: string };
  task?: { action: "created" | "complete_candidate" | "not_found"; item: TaskItem | null; state: "shown" | "done" | "undone" | "error" };
  suggestions?: (MemorySuggestion & { state: "pending" | "saved" | "dismissed" | "error" })[];
}

function Source({ x }: { x: Exchange }) {
  if (x.phase === "error") return <span className="src src-err">Error</span>;
  if (x.phase === "stopped") return <span className="src">Detenido</span>;
  if (x.mode === "ai") return <span className="src src-ai">IA · {x.model}</span>;
  if (x.mode === "memory") return <span className="src src-mem">Memoria</span>;
  if (x.mode === "tasks") return <span className="src src-task">Tareas</span>;
  if (x.mode === "gym") return <span className="src src-gym">Gimnasio</span>;
  if (x.mode === "local") return <span className="src" title={x.note ?? undefined}>Modo local</span>;
  return null;
}

function MemoryNote({ x, onForget }: { x: Exchange; onForget: (id: number) => void }) {
  const m = x.memory!;
  if (m.action === "forget_candidate") {
    if (m.state === "done") return <p className="mem-note">Olvidado: «{m.item.content}»</p>;
    return (
      <p className="mem-note">
        <button type="button" className="mini-btn danger" onClick={() => onForget(x.id)}>Olvidar «{m.item.content}»</button>
        {m.state === "error" && <span className="t-warn"> {m.error}</span>}
      </p>
    );
  }
  return (
    <p className="mem-note">
      🧠 {m.action === "saved" ? "Guardado en memoria" : "Ya estaba en memoria"} · {KIND_LABEL[m.item.kind]}
      {!m.item.permanent && " · temporal"} · <Link to="/memory">Ver memoria</Link>
    </p>
  );
}

function TaskNote({ x, onTask }: { x: Exchange; onTask: (exchangeId: number, action: "undo" | "complete") => void }) {
  const t = x.task!;
  if (!t.item) return null;
  if (t.action === "created") {
    if (t.state === "undone") return <p className="mem-note">Tarea eliminada.</p>;
    return (
      <p className="mem-note">
        ✅ Tarea creada · <Link to="/tasks">Ver tareas</Link>{" "}
        <button type="button" className="mini-btn ghost" onClick={() => onTask(x.id, "undo")}>Deshacer</button>
      </p>
    );
  }
  if (t.action === "complete_candidate") {
    if (t.state === "done") return <p className="mem-note">✓ Hecha: «{t.item.title}»</p>;
    return (
      <p className="mem-note">
        <button type="button" className="mini-btn" onClick={() => onTask(x.id, "complete")}>Marcar como hecha «{t.item.title}»</button>
        {t.state === "error" && <span className="t-warn"> No se pudo.</span>}
      </p>
    );
  }
  return null;
}

export function Transcript({ items, onNew, onForget, onSuggestion, onTask }: {
  items: Exchange[];
  onTask: (exchangeId: number, action: "undo" | "complete") => void;
  onNew: () => void;
  onForget: (exchangeId: number) => void;
  onSuggestion: (exchangeId: number, index: number, save: boolean) => void;
}) {
  if (items.length === 0) return null;
  return (
    <section className="transcript" aria-label="Conversación con ATLAS" aria-live="polite">
      <header>
        <span>Transmisión</span>
        <button type="button" className="link-btn" onClick={onNew} title="Empezar una conversación nueva (la actual queda guardada)">
          Nueva conversación
        </button>
      </header>
      <ol>
        {items.slice(-4).map((x) => (
          <li key={x.id}>
            <p className="q">{x.question} <Source x={x} /></p>
            <p className={`a ${x.phase === "error" ? "t-warn" : ""}`}>
              {x.phase === "thinking"
                ? <span className="thinking-dots" aria-label="Procesando"><i /><i /><i /></span>
                : <>{x.reply}{x.phase === "streaming" && <span className="caret" aria-hidden="true" />}</>}
            </p>
            {x.memory && <MemoryNote x={x} onForget={onForget} />}
            {x.task && <TaskNote x={x} onTask={onTask} />}
            {x.gym && <p className="mem-note">🏋️ Sesión de hoy: {x.gym.sets} series · <Link to="/gym">Ver entreno</Link></p>}
            {x.suggestions?.some((s) => s.state !== "dismissed") && (
              <div className="suggest" role="group" aria-label="ATLAS propone recordar">
                <span className="suggest-title">ATLAS propone recordar</span>
                {x.suggestions.map((s, i) => s.state === "dismissed" ? null : (
                  <div key={i} className="suggest-item">
                    <span>{s.content} <em>· {KIND_LABEL[s.kind]}</em></span>
                    {s.state === "pending" && (
                      <span className="suggest-actions">
                        <button type="button" className="mini-btn" onClick={() => onSuggestion(x.id, i, true)}>Guardar</button>
                        <button type="button" className="mini-btn ghost" onClick={() => onSuggestion(x.id, i, false)}>Descartar</button>
                      </span>
                    )}
                    {s.state === "saved" && <span className="pos small">Guardado</span>}
                    {s.state === "error" && <span className="t-warn small">No se pudo guardar</span>}
                  </div>
                ))}
              </div>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
