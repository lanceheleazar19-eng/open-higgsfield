import { useState } from "react";
import { v4 } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { formatBytes } from "../lib/bytes";
import { relativeTime } from "../lib/format";
import { Panel } from "./Panel";

export function SecuritySettings() {
  const s = useAsync(v4.security);
  const act = useAsync(v4.activity);
  const [msg, setMsg] = useState<string | null>(null);
  const d = s.data;
  if (!d) return <Panel title="Seguridad y permisos"><p className="muted">Cargando…</p></Panel>;
  return (
    <Panel title="Seguridad y permisos">
      <div className="form">
        <div className="table-scroll"><table className="data-table">
          <thead><tr><th>Nivel</th><th>Qué permite</th><th>Política</th></tr></thead>
          <tbody>{(Object.keys(d.levels) as (keyof typeof d.levels)[]).map((l) => (
            <tr key={l}><td className="mono">{l}</td><td className="small">{d.levels[l]}</td><td>
              {l === "WRITE" || l === "EXECUTE" ? (
                <select aria-label={`Política ${l}`} value={d.policy[l]} onChange={async (e) => {
                  const p = { ...d.policy, [l]: e.target.value };
                  await v4.savePolicy(p.WRITE, p.EXECUTE); await s.reload();
                }}><option value="auto">Automático</option><option value="confirm">Pedir confirmación</option></select>
              ) : <span className="small">{l === "READ" ? "Automático" : "Siempre confirmar"}</span>}
            </td></tr>
          ))}</tbody>
        </table></div>
        <h3 className="h-sm">VISTAN nunca</h3>
        <ul className="steps">{d.never.map((n) => <li key={n}>{n}</li>)}</ul>
        <h3 className="h-sm">Copias de seguridad</h3>
        <p className="muted small">Automáticas cada día y antes de cada actualización de la base de datos. Se guardan en {d.backups_dir}.</p>
        <div className="form-actions">
          <button className="btn" onClick={async () => { const b = await v4.backup(); setMsg(`Copia creada: ${b.name}`); await s.reload(); }}>Copia ahora</button>
          <a className="mini-btn" href="/api/security/export" download>Exportar todos mis datos (JSON)</a>
          {msg && <span className="pos small">{msg}</span>}
        </div>
        <ul className="r-list">{d.backups.slice(0, 5).map((b) => (
          <li key={b.name} className="small"><a href={`/api/security/backups/${b.name}`} download>{b.name}</a> <span className="muted">· {formatBytes(b.size)} · {relativeTime(b.created_at)}</span></li>
        ))}</ul>
        <details className="help"><summary>Registro de actividad</summary>
          <ul className="r-list">{(act.data ?? []).slice(0, 40).map((a) => (
            <li key={a.id} className="small"><span className="badge">{a.module}</span> {a.summary} <span className="muted">· {relativeTime(a.created_at)}</span></li>
          ))}</ul>
        </details>
      </div>
    </Panel>
  );
}
