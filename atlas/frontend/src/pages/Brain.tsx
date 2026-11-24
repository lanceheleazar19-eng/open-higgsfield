import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAtlas } from "../components/AtlasContext";
import { Icon } from "../components/Icon";
import { Panel } from "../components/Panel";
import { formatBytes } from "../lib/bytes";

/** Página «Inteligencia artificial»: estado del cerebro y elección de modelo. */
export function Brain() {
  const status = useAsync(api.aiStatus);
  const { prefs, reloadPrefs } = useAtlas();
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const st = status.data;

  async function choose(model: string) {
    setSaving(true);
    setMsg(null);
    try {
      await api.updatePrefs({ ai_model: model });
      await Promise.all([reloadPrefs(), status.reload()]);
      setMsg(model ? `Modelo fijado: ${model}` : "Elección automática activada");
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <header className="page-head">
        <p className="eyebrow">Fase 2 · activo</p>
        <h1><Icon name="ai" size={26} /> Inteligencia artificial</h1>
        <p className="lead">El cerebro de VISTAN. Funciona con modelos locales de Ollama: tus datos no salen de tu ordenador.</p>
      </header>
      <div className="grid grid-2">
        <Panel title="Estado del cerebro" aside={
          <button className="icon-btn" onClick={() => void status.reload()} aria-label="Comprobar de nuevo" title="Comprobar de nuevo" disabled={status.loading}>
            <span className={status.loading ? "spin" : ""}><Icon name="refresh" /></span>
          </button>
        }>
          {!st ? <p className="muted">{status.error ? status.error.message : "Comprobando…"}</p> : (
            <>
              <dl className="kv">
                <div><dt>Proveedor</dt><dd>Ollama (local)</dd></div>
                <div><dt>Dirección</dt><dd className="mono">{st.url}</dd></div>
                <div><dt>Conexión</dt><dd className={st.reachable ? "pos" : "neg"}>{st.reachable ? "Conectado" : "No detectado"}</dd></div>
                <div><dt>Modelo activo</dt><dd className="mono">{st.model ?? "—"}</dd></div>
              </dl>
              {st.note && <p className="callout">{st.note}</p>}
              {!st.reachable && (
                <ol className="steps">
                  <li>Abre la aplicación <strong>Ollama</strong> en tu ordenador (icono de la llama junto al reloj de Windows).</li>
                  <li>Si no tienes modelos, en PowerShell ejecuta <code>ollama pull qwen2.5:7b</code> (≈4,7 GB).</li>
                  <li>Pulsa el botón de comprobar de arriba.</li>
                </ol>
              )}
            </>
          )}
        </Panel>
        <Panel title="Modelo">
          {st && st.models.length > 0 ? (
            <div className="form">
              <label>
                <span>Modelo que usa VISTAN</span>
                <select value={prefs?.ai_model ?? ""} disabled={saving} onChange={(e) => void choose(e.target.value)}>
                  <option value="">Automático{st.model && !prefs?.ai_model ? ` (${st.model})` : ""}</option>
                  {st.models.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.name}{m.parameter_size ? ` · ${m.parameter_size}` : ""} · {formatBytes(m.size_bytes)}
                    </option>
                  ))}
                </select>
              </label>
              {msg && <p role="status" className="small pos">{msg}</p>}
              <p className="muted small">
                Recomendados: <code>qwen2.5:7b</code> (buen español, 8 GB de RAM) o <code>qwen2.5:3b</code> / <code>llama3.2:3b</code> para ordenadores más modestos.
                Instala otros con <code>ollama pull nombre</code>.
              </p>
            </div>
          ) : (
            <p className="muted">{st?.reachable ? "Ollama no tiene modelos instalados todavía." : "Conecta Ollama para ver tus modelos."}</p>
          )}
        </Panel>
        <Panel title="Qué puede hacer ahora">
          <ul className="checklist">
            <li>Conversar de forma natural y responder preguntas generales.</li>
            <li>Analizar tus tareas, eventos, finanzas, entrenos y proyectos con los datos registrados (sin inventar cifras).</li>
            <li>Preparar el resumen ejecutivo del día.</li>
            <li>Recordar el hilo de la conversación actual.</li>
          </ul>
          <p className="muted small">Aún no: crear o modificar datos (llega con cada módulo), memoria entre sesiones (Fase 3), Internet y documentos (Investigación).
            Habla con VISTAN desde el <Link to="/">centro de control</Link>.</p>
        </Panel>
      </div>
    </div>
  );
}
