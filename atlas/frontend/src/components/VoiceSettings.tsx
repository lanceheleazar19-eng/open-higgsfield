import { useState } from "react";
import { speakText, useSystemVoices } from "../hooks/useVoice";
import { loadVoicePrefs, pickVoice, qualityLabel, saveVoicePrefs, spanishVoices } from "../lib/speech";
import { loadHandsFree, saveHandsFree } from "../lib/wake";
import { WELCOME_KEY, welcomeEnabled } from "./BootScreen";
import { Panel } from "./Panel";
import { VoiceStudioSettings } from "./VoiceStudioSettings";

const SAMPLE = "Hola, soy VISTAN. Así sonará mi voz cuando te responda. ¿Te gusta cómo suena?";

/** Elección de voz y velocidad (se guardan en este navegador: las voces dependen de cada dispositivo). */
export function VoiceSettings() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const voices = useSystemVoices();
  const [prefs, setPrefs] = useState(loadVoicePrefs);
  const [welcome, setWelcome] = useState(welcomeEnabled);
  const [hf, setHf] = useState(loadHandsFree);
  const canListen = typeof window !== "undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  const browser = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "este navegador";
  const es = spanishVoices(voices);
  const active = pickVoice(voices, prefs.voiceURI);

  const update = (p: { voiceURI?: string | null; rate?: number }) => {
    saveVoicePrefs(p);
    setPrefs(loadVoicePrefs());
  };

  return (
    <Panel title="Voz de VISTAN">
      <div className="form"><VoiceStudioSettings /></div>
      {!supported ? (
        <p className="muted">Este navegador no puede hablar. Usa Chrome, Safari o Edge.</p>
      ) : (
        <div className="form">
          <label>
            <span>Voz</span>
            <select value={prefs.voiceURI ?? ""} onChange={(e) => update({ voiceURI: e.target.value || null })}>
              <option value="">Automática (la mejor disponible{active && !prefs.voiceURI ? `: ${active.name}` : ""})</option>
              {es.map((v) => (
                <option key={v.voiceURI} value={v.voiceURI}>
                  {v.name} · {v.lang} · {qualityLabel(v)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Velocidad: <strong className="mono">{prefs.rate.toFixed(2)}×</strong></span>
            <input type="range" min={0.7} max={1.6} step={0.05} value={prefs.rate}
              onChange={(e) => update({ rate: Number(e.target.value) })} aria-label="Velocidad de la voz" />
          </label>
          <label className="check">
            <input type="checkbox" checked={welcome} onChange={(e) => {
              setWelcome(e.target.checked);
              try { localStorage.setItem(WELCOME_KEY, e.target.checked ? "1" : "0"); } catch { /* sin almacenamiento */ }
            }} />
            Pantalla de inicio con bienvenida hablada al abrir VISTAN
          </label>
          <div className="form-actions">
            <button type="button" className="btn" onClick={() => speakText(SAMPLE)} disabled={!voices.length}>Probar voz</button>
            <button type="button" className="mini-btn ghost" onClick={() => window.speechSynthesis.cancel()}>Parar</button>
          </div>
          {voices.length > 0 && es.length === 0 && (
            <p className="callout">No hay voces en español instaladas en este dispositivo.</p>
          )}
          <fieldset className="field">
            <legend>Manos libres</legend>
            {!canListen && <p className="callout">Este navegador no puede escuchar. Usa Chrome, Edge o Safari.</p>}
            <label className="check">
              <input type="checkbox" disabled={!canListen} checked={hf.wake} onChange={(e) => setHf(saveHandsFree({ wake: e.target.checked }))} />
              «Hola VISTAN»: escuchar la palabra de activación mientras VISTAN está abierto
            </label>
            <label className="check">
              <input type="checkbox" disabled={!canListen} checked={hf.continuous} onChange={(e) => setHf(saveHandsFree({ continuous: e.target.checked }))} />
              Conversación continua: tras responderte, sigo escuchando sin pulsar nada (si te callas, lo dejo)
            </label>
            <label className="check">
              <input type="checkbox" disabled={!canListen} checked={hf.clap} onChange={(e) => setHf(saveHandsFree({ clap: e.target.checked }))} />
              Dos palmadas: VISTAN empieza a escucharte (experimental; se detecta en tu ordenador, sin grabar audio)
            </label>
            <p className={hf.wake ? "callout" : "muted small"}>
              <strong>Privacidad:</strong> el reconocimiento de voz lo hace el navegador, no VISTAN.
              {browser === "Chrome" || browser === "Edge"
                ? ` En ${browser}, el audio se envía a los servidores de ${browser === "Chrome" ? "Google" : "Microsoft"} para pasarlo a texto.`
                : browser === "Safari" ? " En Safari lo procesa Apple (dictado de Siri), en el dispositivo o en sus servidores según tu Mac." : ""}
              {" "}Con «Oye VISTAN» activo, el micrófono escucha de forma continua mientras la pestaña está abierta y en primer plano. Lo que se dice antes de «VISTAN» se descarta y no se guarda.
            </p>
            <details className="help">
              <summary>Órdenes de voz</summary>
              <ul className="steps">
                <li><strong>«Hola VISTAN, …»</strong>, <strong>«Oye VISTAN, …»</strong> o <strong>«VISTAN, …»</strong> seguido de tu pregunta. Si solo dices «VISTAN», suena un pitido y te escucho.</li>
                <li><strong>«Para» / «Calla»</strong> o <strong>«VISTAN, …»</strong> mientras hablo: me interrumpes.</li>
                <li><strong>«Repite»</strong>, <strong>«Más despacio»</strong>, <strong>«Más rápido»</strong>.</li>
                <li><strong>«Eso es todo»</strong> o <strong>«Gracias»</strong>: termino la conversación y vuelvo a esperar.</li>
                <li>Tecla <strong>Esc</strong>: corta la voz y la escucha.</li>
              </ul>
            </details>
          </fieldset>
          <details className="help">
            <summary>¿Suena robótica? Instala voces mejores (Mac)</summary>
            <ol className="steps">
              <li>Abre <strong>Ajustes del Sistema → Accesibilidad → Contenido leído</strong>.</li>
              <li>En <strong>Voz del sistema</strong>, pulsa el botón <strong>(i)</strong> o <strong>Gestionar voces…</strong>.</li>
              <li>Busca <strong>Español</strong> y descarga una voz <strong>Mejorada</strong> o <strong>Premium</strong> (p. ej. Mónica o Jorge).</li>
              <li>Cierra y vuelve a abrir el navegador: aparecerá en esta lista.</li>
            </ol>
            <p className="muted small">En Chrome también suele estar «Google español», que suena muy natural (necesita Internet). En Windows, Edge incluye voces «Natural» de alta calidad.</p>
          </details>
        </div>
      )}
    </Panel>
  );
}
