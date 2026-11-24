import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Voice } from "../../hooks/useVoice";
import { Icon } from "../Icon";

export const QUICK_COMMANDS = [
  "¿Qué tengo pendiente hoy?",
  "Analiza mi progreso en el gimnasio y en mis objetivos",
  "Organízame la semana",
  "¿Cómo voy con mis objetivos?",
  "¿Qué me toca hoy en el gimnasio?",
  "¿Qué tareas son prioritarias?",
  "Próximos eventos",
  "¿Cuánto he gastado este mes?",
  "¿Cómo voy en el gimnasio?",
  "Proyectos activos",
];

export function CommandBar({ busy, offline, onStop, voice, speakReplies, onToggleSpeak, onAsk, onBriefing, onPhoto }: {
  onPhoto: (file: File) => void;
  busy: boolean;
  offline: boolean;
  onStop: () => void;
  voice: Voice;
  speakReplies: boolean;
  onToggleSpeak: () => void;
  onAsk: (text: string) => void;
  onBriefing: () => void;
}) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const photoRef = useRef<HTMLInputElement>(null);

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
    if (!q || busy || offline) return;
    voice.endConversation(); // escrito → sin conversación por voz
    onAsk(q);
    setText("");
  }

  const micLabel = !voice.canListen ? "Micrófono no disponible en este navegador" : voice.listening ? "Dejar de escuchar" : "Hablar con ATLAS";

  return (
    <div className={`command ${voice.listening ? "is-listening" : ""}`}>
      <form className="bar" onSubmit={submit}>
        <button type="button" className={`mic ${voice.listening ? "on" : ""}`} onClick={voice.listening ? voice.stopListening : voice.listen}
          disabled={!voice.canListen || offline} aria-label={micLabel} title={micLabel} aria-pressed={voice.listening}>
          <Icon name="mic" size={22} />
          {voice.listening && <span className="mic-waves" aria-hidden="true"><i /><i /><i /></span>}
        </button>
        <button type="button" className="bar-btn" onClick={() => photoRef.current?.click()} disabled={busy || offline}
          aria-label="Foto de comida" title="Foto de tu comida: ATLAS calcula calorías y proteína">
          <Icon name="camera" size={18} />
        </button>
        <input ref={photoRef} type="file" accept="image/*" hidden aria-label="Elegir foto de comida"
          onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) { voice.endConversation(); onPhoto(f); } }} />
        <span className={`wave ${voice.listening || voice.speaking || busy ? "on" : ""}`} aria-hidden="true">
          {Array.from({ length: 14 }, (_, i) => <i key={i} style={{ animationDelay: `${(i % 7) * 0.09}s` }} />)}
        </span>
        <input
          ref={inputRef}
          value={voice.listening ? voice.interim : text}
          onChange={(e) => setText(e.target.value)}
          placeholder={voice.listening ? "Escuchando…" : "Pregunta a ATLAS…"}
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
        {busy ? (
          <button type="button" className="bar-btn send" onClick={onStop} aria-label="Detener respuesta" title="Detener respuesta">
            <Icon name="stop" size={18} />
          </button>
        ) : (
          <button type="submit" className="bar-btn send" disabled={offline || !text.trim() || voice.listening} aria-label="Enviar">
            <Icon name="send" size={18} />
          </button>
        )}
      </form>
      <div className="console-foot">
        <span className="listen-state"><i className={voice.listening ? "on" : ""} aria-hidden="true" />
          {voice.listening ? "Escuchando…" : busy ? "Procesando…" : voice.speaking ? (voice.conversing ? "Hablando… (di «para» o «ATLAS» para interrumpir)" : "Hablando…") : voice.wakeActive ? "Di «ATLAS»…" : "En espera"}</span>
        {voice.canListen && (
          <button type="button" className={`chip ${voice.handsFree.wake ? "on" : ""}`} aria-pressed={voice.handsFree.wake} disabled={offline}
            title="Escucha la palabra «ATLAS» mientras esta pestaña está abierta"
            onClick={() => voice.setHandsFree({ wake: !voice.handsFree.wake })}>
            <Icon name="mic" size={14} /> Hola ATLAS: {voice.handsFree.wake ? "activo" : "apagado"}
          </button>
        )}
        <div className="quick" role="group" aria-label="Comandos rápidos">
          <button type="button" className="chip" onClick={() => { voice.endConversation(); onBriefing(); }} disabled={busy || offline}><Icon name="reports" size={14} /> Resumen</button>
          {QUICK_COMMANDS.map((c) => (
            <button key={c} type="button" className="chip" disabled={busy || offline} onClick={() => { voice.endConversation(); onAsk(c); }}>{c}</button>
          ))}
        </div>
      </div>
    </div>
  );
}
