import { v4 } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { Panel } from "./Panel";

export function ProactiveSettings() {
  const d = useAsync(v4.insights);
  if (!d.data) return <Panel title="Inteligencia proactiva"><p className="muted">Cargando…</p></Panel>;
  const { config, rules } = d.data;
  const save = async (enabled: boolean, r: Record<string, boolean>) => { await v4.insightsConfig(enabled, r); await d.reload(); };
  return (
    <Panel title="Inteligencia proactiva">
      <div className="form">
        <label className="check"><input type="checkbox" checked={config.enabled} onChange={(e) => void save(e.target.checked, config.rules)} />
          ATLAS analiza tus datos y te avisa de lo importante (explicando qué, por qué y qué recomienda)</label>
        {config.enabled && Object.entries(rules).map(([k, label]) => (
          <label key={k} className="check"><input type="checkbox" checked={config.rules[k]} onChange={(e) => void save(true, { ...config.rules, [k]: e.target.checked })} /> {label}</label>
        ))}
        <p className="muted small">Ahora mismo hay {d.data.items.length} detección(es) activa(s). Las verás en el Command Center y en el panel derecho.</p>
      </div>
    </Panel>
  );
}
