import { useState } from "react";
import { speakText, useSystemVoices } from "../hooks/useVoice";
import { loadVoicePrefs, pickVoice, qualityLabel, saveVoicePrefs, spanishVoices } from "../lib/speech";
import { Panel } from "./Panel";

const SAMPLE = "Hola, soy ATLAS. Así sonará mi voz cuando te responda. ¿Te gusta cómo suena?";

/** Elección de voz y velocidad (se guardan en este navegador: las voces dependen de cada dispositivo). */
export function VoiceSettings() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const voices = useSystemVoices();
  const [prefs, setPrefs] = useState(loadVoicePrefs);
  const es = spanishVoices(voices);
  const active = pickVoice(voices, prefs.voiceURI);

  const update = (p: { voiceURI?: string | null; rate?: number }) => {
    saveVoicePrefs(p);
    setPrefs(loadVoicePrefs());
  };

  return (
    <Panel title="Voz de ATLAS">
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
          <div className="form-actions">
            <button type="button" className="btn" onClick={() => speakText(SAMPLE)} disabled={!voices.length}>Probar voz</button>
            <button type="button" className="mini-btn ghost" onClick={() => window.speechSynthesis.cancel()}>Parar</button>
          </div>
          {voices.length > 0 && es.length === 0 && (
            <p className="callout">No hay voces en español instaladas en este dispositivo.</p>
          )}
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
