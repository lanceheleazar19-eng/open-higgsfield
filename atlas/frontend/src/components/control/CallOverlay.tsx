import { useEffect } from "react";
import type { Voice } from "../../hooks/useVoice";
import { Icon } from "../Icon";

/** Llamada con VISTAN: pantalla completa, conversación de voz continua. Estado real del micrófono y la voz. */
export function CallOverlay({ voice, busy, reply, onHangUp }: {
  voice: Voice;
  busy: boolean;
  reply: string;
  onHangUp: () => void;
}) {
  const state = voice.muted ? "muted" : voice.listening ? "listening" : busy ? "thinking" : voice.speaking ? "speaking" : "idle";
  const label = { muted: "Micrófono silenciado", listening: "Te escucho…", thinking: "Pensando…", speaking: "VISTAN habla · empieza a hablar para interrumpir", idle: "Conectando el micrófono…" }[state];
  const caption = voice.listening ? voice.interim : reply.length > 260 ? "…" + reply.slice(-260) : reply;

  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onHangUp(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onHangUp]);

  return (
    <div className={`call-overlay is-${state}`} role="dialog" aria-modal="true" aria-label="Llamada con VISTAN">
      <div className="call-top">
        <span className="call-led" aria-hidden="true" /> LLAMADA · VISTAN
      </div>
      <div className="call-orb" aria-hidden="true">
        <i /><i /><i />
        <span className="call-core" />
      </div>
      <p className="call-state" aria-live="polite">{label}</p>
      <p className="call-caption">{caption || (state === "listening" ? "" : " ")}</p>
      {voice.error && <p className="call-error">{voice.error}</p>}
      <div className="call-actions">
        <button type="button" className={`call-btn ${voice.muted ? "on" : ""}`} onClick={() => voice.setMuted(!voice.muted)}
          aria-pressed={voice.muted} aria-label={voice.muted ? "Activar micrófono" : "Silenciar micrófono"}>
          <Icon name={voice.muted ? "mute" : "mic"} size={24} />
        </button>
        {voice.speaking && (
          <button type="button" className="call-btn" onClick={voice.stopSpeaking} aria-label="Interrumpir a VISTAN">
            <Icon name="stop" size={22} />
          </button>
        )}
        <button type="button" className="call-btn hangup" onClick={onHangUp} aria-label="Colgar">
          <Icon name="close" size={26} />
        </button>
      </div>
      <p className="call-hint">Di «eso es todo» o pulsa Esc para colgar · con auriculares funciona mejor (no se oye a sí mismo)</p>
    </div>
  );
}
