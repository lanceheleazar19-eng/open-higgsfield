import { useEffect, useRef, useState } from "react";
import { desk, type DeskAccount } from "../../api/desk";

const QUICK = [
  "¿Qué está pasando en este mercado?",
  "¿Cómo interpreto este gráfico?",
  "¿Qué significan el RSI y el MACD ahora mismo?",
  "¿Qué riesgos tiene mi posición abierta?",
  "¿Estoy respetando mi gestión del riesgo?",
  "¿Qué errores estoy cometiendo?",
  "¿Qué puedo aprender de mis últimas operaciones?",
  "Explícame cómo funciona una estrategia de cruce de medias",
];

interface Msg { role: "user" | "assistant"; content: string; meta?: string }

/** VISTAN Trading Agent: tutor educativo con tus datos reales. Nunca ejecuta operaciones. */
export function Tutor({ account, symbol, tf, open, onClose, preset }: {
  account: DeskAccount; symbol: string; tf: string; open: boolean; onClose: () => void; preset: { q: string; n: number } | null;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [msgs, busy]);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    const history = msgs.map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: question }]);
    setQ("");
    setBusy(true);
    try {
      const r = await desk.tutor({ question, account_id: account.id, symbol, timeframe: tf, history });
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, meta: `${r.model} · datos: ${r.used.join(", ")}` }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", content: `⚠ ${(e as Error).message}` }]);
    } finally { setBusy(false); }
  };
  useEffect(() => { if (preset && open) void ask(preset.q); }, [preset?.n]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null;
  return (
    <aside className="tutor" aria-label="VISTAN Trading Agent">
      <header className="dpanel-head">
        <span>VISTAN TRADING AGENT · tutor</span>
        <button type="button" className="mini-btn ghost" onClick={onClose} aria-label="Cerrar tutor">✕</button>
      </header>
      <p className="mini-note">Contexto: <strong>{account.name}</strong> · {symbol} · {tf}. Usa tus datos reales; explica, no predice con certeza y <strong>nunca opera por ti</strong>.</p>
      <div className="tutor-log">
        {!msgs.length && (
          <div className="quick">{QUICK.map((x) => <button type="button" key={x} className="chip" onClick={() => void ask(x)}>{x}</button>)}</div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`tmsg ${m.role}`}>
            <div className="tbody">{m.content.split("\n").map((l, j) => <p key={j}>{l}</p>)}</div>
            {m.meta && <small>{m.meta}</small>}
          </div>
        ))}
        {busy && <div className="tmsg assistant"><div className="tbody"><p className="muted">Analizando tus datos…</p></div></div>}
        <div ref={end} />
      </div>
      <form className="tutor-in" onSubmit={(e) => { e.preventDefault(); void ask(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Pregunta al tutor…" aria-label="Pregunta al tutor" maxLength={2000} />
        <button type="submit" className="btn" disabled={busy || !q.trim()}>Preguntar</button>
      </form>
    </aside>
  );
}
