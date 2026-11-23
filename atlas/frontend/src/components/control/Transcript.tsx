export interface Exchange {
  id: number;
  question: string;
  reply: string;
  phase: "thinking" | "streaming" | "done" | "error" | "stopped";
  mode?: "ai" | "local";
  model?: string | null;
  note?: string | null;
}

function Source({ x }: { x: Exchange }) {
  if (x.phase === "error") return <span className="src src-err">Error</span>;
  if (x.phase === "stopped") return <span className="src">Detenido</span>;
  if (x.mode === "ai") return <span className="src src-ai">IA · {x.model}</span>;
  if (x.mode === "local") return <span className="src" title={x.note ?? undefined}>Modo local</span>;
  return null;
}

export function Transcript({ items, onClear }: { items: Exchange[]; onClear: () => void }) {
  if (items.length === 0) return null;
  return (
    <section className="transcript" aria-label="Conversación con ATLAS" aria-live="polite">
      <header>
        <span>Transmisión</span>
        <button type="button" className="link-btn" onClick={onClear}>Limpiar</button>
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
          </li>
        ))}
      </ol>
    </section>
  );
}
