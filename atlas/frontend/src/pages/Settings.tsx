import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAtlas } from "../components/AtlasContext";
import { Panel } from "../components/Panel";
import { VoiceSettings } from "../components/VoiceSettings";
import { ProfileSettings } from "../components/ProfileSettings";
import { IntegrationsSettings } from "../components/IntegrationsSettings";
import { NotificationSettings } from "../components/NotificationSettings";
import { desktop, isDesktop } from "../lib/desktop";
import { ModelsSettings } from "../components/ModelsSettings";
import { ProactiveSettings } from "../components/ProactiveSettings";
import { SecuritySettings } from "../components/SecuritySettings";

const CURRENCIES = ["EUR", "USD", "MXN", "GBP", "COP", "ARS", "CLP"];

export function Settings() {
  const { prefs, reloadPrefs, health } = useAtlas();
  const tzs = useAsync(api.timezones);
  const [form, setForm] = useState({ user_name: "", timezone: "", currency: "EUR" });
  // ai_model se gestiona en la página de Inteligencia artificial
  const [state, setState] = useState<{ kind: "idle" | "saving" | "ok" | "error"; msg?: string }>({ kind: "idle" });

  useEffect(() => {
    if (prefs) setForm({ user_name: prefs.user_name, timezone: prefs.timezone, currency: prefs.currency });
  }, [prefs]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setState({ kind: "saving" });
    try {
      await api.updatePrefs(form);
      await reloadPrefs();
      setState({ kind: "ok", msg: "Preferencias guardadas." });
    } catch (err) {
      setState({ kind: "error", msg: (err as Error).message });
    }
  }

  const dirty = prefs && (form.user_name !== prefs.user_name || form.timezone !== prefs.timezone || form.currency !== prefs.currency);

  return (
    <div className="page">
      <header className="page-head">
        <p className="eyebrow">Sistema</p>
        <h1>Configuración</h1>
      </header>
      {isDesktop() && (
        <p className="desk-settings-link">
          <button type="button" className="btn" onClick={() => void desktop.openPreferences().catch(() => undefined)}>VISTAN Desktop · Permisos y privacidad…</button>
          <span className="muted small">Inicio automático, atajo global, notificaciones, micrófono, actualizaciones.</span>
        </p>
      )}
      <ProfileSettings />
      <div id="integraciones"><IntegrationsSettings /></div>
      <div id="modelos"><ModelsSettings /></div>
      <div className="grid grid-2">
        <div id="seguridad"><SecuritySettings /></div>
        <div id="proactividad"><ProactiveSettings /></div>
      </div>
      <div className="grid grid-2">
        <Panel title="Región">
          <form className="form" onSubmit={submit}>
            <label>
              <span>Zona horaria</span>
              <select value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} disabled={!tzs.data}>
                {(tzs.data ?? (form.timezone ? [form.timezone] : [])).map((tz) => <option key={tz} value={tz}>{tz}</option>)}
              </select>
            </label>
            <label>
              <span>Moneda principal</span>
              <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
                {[...new Set([form.currency, ...CURRENCIES])].map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <div className="form-actions">
              <button className="btn" type="submit" disabled={!dirty || state.kind === "saving"}>
                {state.kind === "saving" ? "Guardando…" : "Guardar"}
              </button>
              {state.msg && <span role="status" className={state.kind === "error" ? "neg" : "pos"}>{state.msg}</span>}
            </div>
          </form>
        </Panel>
        <VoiceSettings />
        <NotificationSettings />
        <Panel title="Estado del sistema">
          {health ? (
            <dl className="kv">
              <div><dt>Versión</dt><dd className="mono">{health.version}</dd></div>
              <div><dt>Núcleo</dt><dd>{health.status === "online" ? "Operativo" : "Degradado"}</dd></div>
              <div><dt>Base de datos</dt><dd className="mono">{health.database.engine} · {health.database.ok ? "OK" : "Error"}</dd></div>
              <div><dt>Cerebro IA</dt><dd>{health.ai.configured ? `Ollama · ${health.ai.model}` : health.ai.note}</dd></div>
              <div><dt>Python</dt><dd className="mono">{health.python}</dd></div>
            </dl>
          ) : (
            <p className="muted">Sin conexión con el núcleo.</p>
          )}
          <p className="muted small">Tus datos se guardan solo en tu ordenador (carpeta <code>atlas/data/</code>). Exportación y copias de seguridad llegan en la Fase 11.</p>
        </Panel>
      </div>
    </div>
  );
}
