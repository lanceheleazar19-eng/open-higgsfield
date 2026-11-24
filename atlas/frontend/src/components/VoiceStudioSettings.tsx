import { useCallback, useEffect, useState } from "react";
import { speakText } from "../hooks/useVoice";
import { loadEngine, saveEngine, vsStatus, vsStop, vsWarmup, VS_WAIT_MS, type VoiceEngine, type VsStatus } from "../lib/voicestudio";

const SAMPLE = "Hola, soy VISTAN. Esta es mi voz con VoiceStudio, generada en tu propio ordenador.";

/** Motor de voz: navegador o VoiceStudio (app de voz local). Estado medido, nunca supuesto. */
export function VoiceStudioSettings({ sample = SAMPLE }: { sample?: string }) {
  const [pref, setPref] = useState(loadEngine);
  const [st, setSt] = useState<VsStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [testing, setTesting] = useState(false);

  const check = useCallback(() => {
    setChecking(true);
    vsStatus().then(setSt).catch(() => setSt(null)).finally(() => setChecking(false));
  }, []);
  useEffect(check, [check]);

  const update = (p: { engine?: VoiceEngine; vsVoice?: string | null; callBrowser?: boolean }) => { saveEngine(p); setPref(loadEngine()); vsWarmup(true); };
  const on = pref.engine === "voicestudio";

  return (
    <fieldset className="field">
      <legend>Motor de voz</legend>
      <label>
        <span>VISTAN habla con</span>
        <select value={pref.engine} onChange={(e) => update({ engine: e.target.value as VoiceEngine })} aria-label="Motor de voz">
          <option value="browser">Voz del navegador / sistema</option>
          <option value="voicestudio">VoiceStudio (voz neuronal local)</option>
        </select>
      </label>
      <p className="muted small">
        Estado de VoiceStudio:{" "}
        {checking ? "comprobando…" : st?.reachable
          ? <strong>conectado · {st.ping_ms} ms · {st.voices.length} voces{st.local ? " · en este equipo" : ` · ${st.url}`}</strong>
          : <strong>no disponible</strong>}
        {!checking && st && !st.reachable && st.error ? ` (${st.error})` : ""}
        {" "}<button type="button" className="mini-btn ghost" onClick={check} disabled={checking}>Comprobar</button>
      </p>
      {on && st?.reachable && (
        <p className="muted small">
          Tiempo real por frase: {st.synthesis.avg_ms != null
            ? <strong>{(st.synthesis.avg_ms / 1000).toFixed(1)} s de media · última {((st.synthesis.last_ms ?? 0) / 1000).toFixed(1)} s</strong>
            : "N/D (aún no ha generado ninguna)"}
          {st.synthesis.errors ? ` · ${st.synthesis.errors} fallos` : ""}.
          {" "}Si una frase tarda más de {VS_WAIT_MS / 1000} s, esa respuesta sigue con la voz del navegador para no dejarte esperando.
        </p>
      )}
      {on && st?.reachable && (
        <label>
          <span>Voz de VoiceStudio</span>
          <select value={pref.vsVoice ?? ""} onChange={(e) => update({ vsVoice: e.target.value || null })} aria-label="Voz de VoiceStudio">
            <option value="">Predeterminada de VoiceStudio</option>
            {st.voices.map((v) => (
              <option key={v.id} value={v.id}>{v.name}{v.type === "profile" ? " · tu perfil" : ""}{v.language ? ` · ${v.language}` : ""}</option>
            ))}
          </select>
        </label>
      )}
      {on && (
        <label className="check">
          <input type="checkbox" checked={pref.callBrowser} onChange={(e) => update({ callBrowser: e.target.checked })} />
          En el modo llamada, usar la voz del navegador (instantánea; VoiceStudio en tu Mac tarda en generar cada frase)
        </label>
      )}
      {on && (
        <div className="form-actions">
          <button type="button" className="btn" disabled={!st?.reachable || testing}
            onClick={() => { setTesting(true); speakText(sample, undefined, () => setTesting(false)); setTimeout(() => setTesting(false), 30000); }}>
            {testing ? "Generando…" : "Probar VoiceStudio"}
          </button>
          <button type="button" className="mini-btn ghost" onClick={() => { vsStop(); setTesting(false); }}>Parar</button>
        </div>
      )}
      {on && !st?.reachable && !checking && (
        <p className="callout">VoiceStudio no responde: mientras tanto VISTAN usará la voz del navegador.</p>
      )}
      <p className="muted small">
        <strong>Privacidad:</strong> el texto va del núcleo de VISTAN a VoiceStudio en tu Mac; no sale a Internet.
        En el iPhone el audio también lo genera el Mac y te llega por Tailscale.
      </p>
      <details className="help">
        <summary>Instalar VoiceStudio en el Mac</summary>
        <ol className="steps">
          <li>En la Terminal: <code>brew tap debpalash/tap</code>, luego <code>brew trust --cask debpalash/tap/voicestudio</code> y <code>brew install --cask debpalash/tap/voicestudio</code> (o descarga el DMG de su página de GitHub).</li>
          <li>Abre <strong>VoiceStudio</strong> y en su gestor de modelos descarga el modelo de voz (la primera vez tarda).</li>
          <li>Déjalo abierto: escucha en <code>127.0.0.1:3900</code>. Pulsa <strong>Comprobar</strong> aquí y elige «VoiceStudio».</li>
        </ol>
        <p className="muted small">Ojo con la licencia: los modelos por defecto (OmniVoice) son solo para uso no comercial. Clona solo tu propia voz o voces con permiso.</p>
      </details>
    </fieldset>
  );
}
