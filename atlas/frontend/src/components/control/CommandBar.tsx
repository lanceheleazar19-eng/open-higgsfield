import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Voice } from "../../hooks/useVoice";
import { Icon } from "../Icon";

export const QUICK_COMMANDS = [
  "¿Qué tengo pendiente hoy?",
  "¿Qué tareas son prioritarias?",
  "Próximos eventos",
  "¿Cuánto he gastado este mes?",
  "¿Cómo voy en el gimnasio?",
  "Proyectos activos",
];

export function CommandBar({ busy, voice, speakReplies, onToggleSpeak, onAsk, onBriefing }: {
  busy: boolean;
  voice: Voice;
  speakReplies: boolean;
  onToggleSpeak: () => void;
  onAsk: (text: string) => void;
  onBriefing: () => void;
}) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // «/» enfoca la barra; Esc interrumpe voz y escucha
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement;
      if (e.key === "/" && !typing) { e.preventDefault(); inputRef.current?.focus(); }
      if (e.key === "Escape") { voice.stopSpeaking(); voice.stopListening(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [voice]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = text.trim();
    if (!q || busy) return;
    onAsk(q);
    setText("");
  }

  const micLabel = !voice.canListen ? "Micrófono no disponible en este navegador" : voice.listening ? "Dejar de escuchar" : "Hablar con ATLAS";

  return (
    <div className="command">
      <div className="quick" role="group" aria-label="Comandos rápidos">
        {QUICK_COMMANDS.map((c) => (
          <button key={c} type="button" className="chip" disabled={busy} onClick={() => onAsk(c)}>{c}</button>
        ))}
      </div>
      <form className={`bar ${voice.listening ? "is-listening" : ""}`} onSubmit={submit}>
        <button type="button" className={`bar-btn mic ${voice.listening ? "on" : ""}`} onClick={voice.listening ? voice.stopListening : voice.listen}
          disabled={!voice.canListen} aria-label={micLabel} title={micLabel} aria-pressed={voice.listening}>
          <Icon name="mic" size={19} />
          {voice.listening && <span className="mic-waves" aria-hidden="true"><i /><i /><i /><i /></span>}
        </button>
        <input
          ref={inputRef}
          value={voice.listening ? voice.interim : text}
          onChange={(e) => setText(e.target.value)}
          placeholder={voice.listening ? "Escuchando…" : "Habla o escribe a ATLAS…  ( / )"}
          aria-label="Mensaje para ATLAS"
          maxLength={2000}
          readOnly={voice.listening}
        />
        {voice.speaking ? (
          <button type="button" className="bar-btn" onClick={voice.stopSpeaking} aria-label="Interrumpir respuesta" title="Interrumpir respuesta (Esc)">
            <Icon name="stop" size={18} />
          </button>
        ) : (
          <button type="button" className={`bar-btn ${speakReplies ? "on" : ""}`} onClick={onToggleSpeak} disabled={!voice.canSpeak}
            aria-pressed={speakReplies} aria-label={speakReplies ? "Desactivar respuesta hablada" : "Activar respuesta hablada"}
            title={voice.canSpeak ? (speakReplies ? "Respuesta hablada activada" : "Respuesta hablada desactivada") : "Síntesis de voz no disponible"}>
            <Icon name={speakReplies ? "volume" : "mute"} size={18} />
          </button>
        )}
        <button type="button" className="bar-btn brief" onClick={onBriefing} disabled={busy} title="Resumen ejecutivo">
          <Icon name="spark" size={18} /><span>Resumen</span>
        </button>
        <button type="submit" className="bar-btn send" disabled={busy || !text.trim() || voice.listening} aria-label="Enviar">
          <Icon name="send" size={18} />
        </button>
      </form>
    </div>
  );
}
