import { useEffect, useState } from "react";

export interface Exchange {
  id: number;
  question: string;
  reply: string | null; // null = procesando
  error?: boolean;
}

/** Muestra la respuesta revelándose progresivamente (mientras el núcleo «responde»). */
function Reveal({ text, onDone }: { text: string; onDone: () => void }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    const step = Math.max(2, Math.ceil(text.length / 90));
    const id = setInterval(() => {
      setN((v) => {
        const next = Math.min(text.length, v + step);
        if (next >= text.length) { clearInterval(id); onDone(); }
        return next;
      });
    }, 22);
    return () => clearInterval(id);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps
  return <>{text.slice(0, n)}{n < text.length && <span className="caret" aria-hidden="true" />}</>;
}

export function Transcript({ items, revealId, onRevealed, onClear }: {
  items: Exchange[]; revealId: number | null; onRevealed: () => void; onClear: () => void;
}) {
  if (items.length === 0) return null;
  return (
    <section className="transcript" aria-label="Conversación con ATLAS" aria-live="polite">
      <header>
        <span>Transmisión</span>
        <button type="button" className="link-btn" onClick={onClear}>Limpiar</button>
      </header>
      <ol>
        {items.slice(-3).map((x) => (
          <li key={x.id}>
            <p className="q">{x.question}</p>
            <p className={`a ${x.error ? "t-warn" : ""}`}>
              {x.reply === null ? <span className="thinking-dots" aria-label="Procesando"><i /><i /><i /></span>
                : x.id === revealId ? <Reveal text={x.reply} onDone={onRevealed} /> : x.reply}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
