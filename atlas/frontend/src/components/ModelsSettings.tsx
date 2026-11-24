import { useState } from "react";
import { v4, type ModelsStatus, type RouterConfig } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { Panel } from "./Panel";

const KEY_HELP: Record<string, string> = {
  openai: "platform.openai.com → API keys", anthropic: "console.anthropic.com → API Keys", gemini: "aistudio.google.com → Get API key",
};

/** Multi-model: proveedores reales, API keys en el Llavero, modelo por tarea, privacidad, límites y uso. */
export function ModelsSettings() {
  const st = useAsync(v4.models);
  const usage = useAsync(v4.usage);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [tests, setTests] = useState<Record<string, { connected: boolean; error: string | null; models: string[] }>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const d: ModelsStatus | null = st.data;
  const save = async (c: Partial<RouterConfig> & { clear_limit?: boolean }) => { await v4.saveRouter(c); await st.reload(); setMsg("Guardado."); };
  if (!d) return <Panel title="Modelos de IA"><p className="muted">Cargando…</p></Panel>;
  const cfg = d.config;
  const modelsFor = (p: string) => p === "ollama" ? d.providers[0].models : tests[p]?.models ?? (cfg.providers[p]?.model ? [cfg.providers[p].model] : []);

  return (
    <Panel title="Modelos de IA (multi-modelo)">
      <div className="form">
        <label><span>Privacidad</span>
          <select value={cfg.privacy} onChange={(e) => void save({ privacy: e.target.value as RouterConfig["privacy"] })}>
            {Object.entries(d.privacy_options).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <div className="table-scroll"><table className="data-table">
          <thead><tr><th>Proveedor</th><th>Estado</th><th>Modelo</th><th /></tr></thead>
          <tbody>
            {d.providers.map((p) => (
              <tr key={p.id}>
                <td>{p.label}</td>
                <td className="small">{p.local ? (p.connected ? <span className="pos">Conectado</span> : <span className="t-warn">{p.note}</span>)
                  : tests[p.id] ? (tests[p.id].connected ? <span className="pos">Conectado ({tests[p.id].models.length} modelos)</span> : <span className="neg">{tests[p.id].error}</span>)
                  : p.configured ? <span>Key guardada · sin probar</span> : <span className="muted">Falta la API key</span>}</td>
                <td>{p.local ? <span className="mono small">{p.model ?? "—"}</span> : (
                  <select aria-label={`Modelo de ${p.label}`} value={cfg.providers[p.id]?.model ?? ""} disabled={!p.configured}
                    onChange={(e) => void save({ providers: { ...cfg.providers, [p.id]: { model: e.target.value } } })}>
                    <option value="">{tests[p.id] ? "Elige modelo…" : "Prueba la conexión para listar modelos"}</option>
                    {modelsFor(p.id).map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>)}</td>
                <td>{!p.local && (p.configured
                  ? <span className="row-actions">
                      <button type="button" className="mini-btn" onClick={async () => setTests({ ...tests, [p.id]: await v4.testProvider(p.id) })}>Probar</button>
                      <button type="button" className="mini-btn danger" onClick={async () => { if (confirm(`¿Borrar la API key de ${p.label}?`)) { await v4.deleteKey(p.id); await st.reload(); } }}>Quitar key</button>
                    </span>
                  : <form className="row-actions" onSubmit={async (e) => { e.preventDefault(); await v4.saveKey(p.id, keys[p.id]); setKeys({ ...keys, [p.id]: "" }); await st.reload(); setTests({ ...tests, [p.id]: await v4.testProvider(p.id) }); }}>
                      <input type="password" autoComplete="off" aria-label={`API key de ${p.label}`} placeholder={KEY_HELP[p.id]} value={keys[p.id] ?? ""} onChange={(e) => setKeys({ ...keys, [p.id]: e.target.value })} />
                      <button className="mini-btn" disabled={(keys[p.id] ?? "").length < 10}>Guardar</button>
                    </form>)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
        <p className="muted small">Las API keys se guardan en el Llavero de tu Mac y nunca vuelven al navegador. Sin key, ese proveedor no se usa ni se simula.</p>
        <h3 className="h-sm">Modelo por tarea</h3>
        <div className="table-scroll"><table className="data-table">
          <thead><tr><th>Tarea</th><th>Proveedor</th><th>Modelo</th><th>Ahora usa</th></tr></thead>
          <tbody>
            {Object.entries(d.tasks).map(([t, label]) => (
              <tr key={t}>
                <td>{label}</td>
                <td><select aria-label={`Proveedor para ${label}`} value={cfg.tasks[t].provider}
                  onChange={(e) => void save({ tasks: { ...cfg.tasks, [t]: { provider: e.target.value, model: "" } } })}>
                  <option value="auto">Automático</option><option value="ollama">Ollama (local)</option>
                  {d.providers.filter((p) => !p.local && p.configured).map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select></td>
                <td>{["auto", "ollama"].includes(cfg.tasks[t].provider) ? <span className="muted small">—</span> : (
                  <select aria-label={`Modelo para ${label}`} value={cfg.tasks[t].model} onChange={(e) => void save({ tasks: { ...cfg.tasks, [t]: { ...cfg.tasks[t], model: e.target.value } } })}>
                    <option value="">El del proveedor</option>{modelsFor(cfg.tasks[t].provider).map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>)}</td>
                <td className="mono small">{d.routes[t]}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
        <form className="form-row" onSubmit={(e) => { e.preventDefault(); const v = (e.currentTarget.elements.namedItem("limit") as HTMLInputElement).value; void save(v ? { monthly_limit_usd: Number(v) } : { clear_limit: true }); }}>
          <label><span>Límite de gasto mensual en la nube (USD, vacío = sin límite)</span>
            <input name="limit" inputMode="decimal" defaultValue={cfg.monthly_limit_usd ?? ""} /></label>
          <button className="mini-btn">Guardar límite</button>
        </form>
        <p className="muted small">Gastado este mes (estimado con los precios que indiques): {d.month_cost_usd.toFixed(4)} USD. El coste solo se calcula si das el precio por millón de tokens de cada modelo.</p>
        {msg && <p className="pos small" role="status">{msg}</p>}
        <details className="help">
          <summary>Registro de uso ({usage.data?.by_model.length ?? 0} modelos)</summary>
          {!usage.data?.by_model.length ? <p className="muted small">Aún no hay llamadas registradas.</p> : (
            <div className="table-scroll"><table className="data-table">
              <thead><tr><th>Modelo</th><th>Llamadas</th><th>Media</th><th>Errores</th><th>Coste</th></tr></thead>
              <tbody>{usage.data.by_model.map((u) => (
                <tr key={u.provider + u.model}><td className="mono small">{u.provider}:{u.model}</td><td>{u.calls}</td><td>{u.avg_ms} ms</td><td>{u.errors}</td><td>{u.cost_usd === null ? "—" : `${u.cost_usd} $`}</td></tr>
              ))}</tbody>
            </table></div>
          )}
        </details>
      </div>
    </Panel>
  );
}
