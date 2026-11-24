import { Link } from "react-router-dom";
import type { MealProposal, MemoryItem, MemorySuggestion, TaskItem, TxItem } from "../../api/types";
import { formatMoney } from "../../lib/format";
import type { AgentRunItem, ResearchItem } from "../../api/v4";
import { Trace } from "../../pages/Agents";
import { KIND_LABEL } from "../../lib/memory";

export interface Exchange {
  id: number;
  question: string;
  reply: string;
  phase: "thinking" | "streaming" | "done" | "error" | "stopped";
  mode?: "ai" | "local" | "memory" | "tasks" | "gym" | "nutrition" | "finance" | "research";
  agents?: AgentRunItem;
  sources?: { n: number; document_id: number; title: string; chunk: number; url: string | null; kind: string }[];
  research?: ResearchItem;
  money?: { item: TxItem; state: "shown" | "undone" | "error" };
  photo?: { items: MealProposal[]; state: "shown" | "saving" | "saved" | "error"; meal?: string; error?: string };
  meal?: { count: number };
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
  if (x.mode === "nutrition") return <span className="src src-gym">Nutrición</span>;
  if (x.mode === "research") return <span className="src src-task">Investigación</span>;
  if (x.mode === "finance") return <span className="src src-task">Finanzas</span>;
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

function PhotoNote({ x, onSave }: { x: Exchange; onSave: (exchangeId: number) => void }) {
  const p = x.photo!;
  const ok = p.items.filter((i) => i.food && i.grams);
  if (p.state === "saved") return <p className="mem-note">🍽️ Guardado en {p.meal} · <Link to="/nutrition">Ver nutrición</Link></p>;
  if (!ok.length) return <p className="mem-note"><Link to="/nutrition">Regístralo a mano en Nutrición</Link></p>;
  return (
    <p className="mem-note">
      <button type="button" className="mini-btn" disabled={p.state === "saving"} onClick={() => onSave(x.id)}>
        {p.state === "saving" ? "Guardando…" : "Guardar comida"}
      </button>{" "}
      <Link to="/nutrition">Ajustar gramos en Nutrición</Link>
      {p.state === "error" && <span className="t-warn"> {p.error ?? "No se pudo guardar."}</span>}
    </p>
  );
}

function MoneyNote({ x, onUndo }: { x: Exchange; onUndo: (exchangeId: number) => void }) {
  const m = x.money!;
  if (m.state === "undone") return <p className="mem-note">Movimiento eliminado.</p>;
  return (
    <p className="mem-note">
      💶 {m.item.kind === "expense" ? "Gasto" : "Ingreso"} de {formatMoney(m.item.amount_cents, m.item.currency)} · {m.item.category} · <Link to="/finance">Ver finanzas</Link>{" "}
      <button type="button" className="mini-btn ghost" onClick={() => onUndo(x.id)}>Deshacer</button>
      {m.state === "error" && <span className="t-warn"> No se pudo deshacer.</span>}
    </p>
  );
}

export function Transcript({ items, onNew, onForget, onSuggestion, onTask, onMoneyUndo, onPhotoSave }: {
  items: Exchange[];
  onPhotoSave: (exchangeId: number) => void;
  onMoneyUndo: (exchangeId: number) => void;
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
            {x.money && <MoneyNote x={x} onUndo={onMoneyUndo} />}
            {x.research && <p className="mem-note">🔎 Investigación #{x.research.id} en marcha · <Link to={`/research?id=${x.research.id}`}>Seguirla</Link></p>}
            {x.sources && x.sources.length > 0 && (
              <p className="mem-note">📄 De tus documentos: {x.sources.map((s) => <Link key={s.n} to="/knowledge" className="cite">[{s.n}] {s.title}</Link>)}</p>
            )}
            {x.agents && x.agents.agents.length > 0 && (
              <details className="agents-note"><summary>⚙ {x.agents.agent_names.join(" + ")} · {x.agents.steps.length} herramienta(s) · <Link to="/agents?tab=runs">ver</Link></summary><Trace run={x.agents} /></details>
            )}
            {x.photo && x.phase === "done" && <PhotoNote x={x} onSave={onPhotoSave} />}
            {x.meal && x.meal.count > 0 && <p className="mem-note">🍽️ Comida registrada · <Link to="/nutrition">Ver nutrición</Link></p>}
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
