import { useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { formatDayLabel } from "../lib/tasks";
import { LineChart } from "./LineChart";
import { Empty, Panel } from "./Panel";

/** Apple Salud vía Atajo del iPhone: VISTAN solo recibe lo que el Atajo envía. */
export function HealthTab() {
  const days = useAsync(() => api.healthDays(30));
  const setup = useAsync(api.healthSetup);
  const [show, setShow] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const url = `${window.location.origin}${setup.data?.path ?? "/api/health/ingest"}`;
  const d = days.data ?? [];
  const copy = async (label: string, v: string) => {
    try { await navigator.clipboard.writeText(v); setCopied(label); } catch { setCopied(null); }
  };
  const steps = d.filter((x) => x.steps !== null), sleep = d.filter((x) => x.sleep_hours !== null);
  return (
    <div className="grid grid-tasks">
      <Panel title="Conectar Apple Salud (Atajo del iPhone)">
        <p className="muted small">El iPhone envía tus datos a VISTAN por tu red privada de Tailscale. Abre VISTAN en el iPhone con la dirección de Tailscale para que esta URL sea la correcta.</p>
        <dl className="kv">
          <div><dt>URL</dt><dd className="mono small">{url} <button className="mini-btn ghost" type="button" onClick={() => copy("url", url)}>{copied === "url" ? "Copiada" : "Copiar"}</button></dd></div>
          <div><dt>Cabecera</dt><dd className="mono small">X-Vistan-Token</dd></div>
          <div><dt>Clave</dt><dd className="mono small">
            {setup.data ? (show ? setup.data.token : "•".repeat(12)) : "…"}{" "}
            <button className="mini-btn ghost" type="button" onClick={() => setShow(!show)}>{show ? "Ocultar" : "Mostrar"}</button>{" "}
            {setup.data && <button className="mini-btn ghost" type="button" onClick={() => copy("token", setup.data!.token)}>{copied === "token" ? "Copiada" : "Copiar"}</button>}{" "}
            <button className="mini-btn danger" type="button" onClick={async () => {
              if (confirm("¿Generar una clave nueva? El Atajo dejará de funcionar hasta que pongas la nueva.")) { await api.rotateHealthToken(); await setup.reload(); }
            }}>Nueva clave</button>
          </dd></div>
        </dl>
        <ol className="steps">
          <li>En el iPhone abre <strong>Atajos → Automatización → Nueva automatización → Hora del día</strong> (por ejemplo 23:30, cada día, «Ejecutar inmediatamente»).</li>
          <li>Añade <strong>Buscar muestras de salud</strong> → Tipo: <em>Pasos</em>, fecha de inicio: <em>hoy</em>. Después <strong>Calcular estadísticas → Suma</strong>. Repite para <em>Energía activa</em> y <em>Distancia a pie y en carrera</em>.</li>
          <li>Para el sueño: <strong>Buscar muestras de salud</strong> → <em>Análisis del sueño</em>, últimas 24 h, valor <em>Dormido</em> → <strong>Obtener detalles → Duración</strong> → <strong>Calcular estadísticas → Suma</strong> (en minutos).</li>
          <li>Opcional: <strong>Buscar muestras de salud</strong> → <em>Peso</em>, ordenar por fecha, límite 1. El peso también se usa en Gimnasio y Nutrición.</li>
          <li>Añade <strong>Obtener contenido de URL</strong>: la URL de arriba, método <em>POST</em>, encabezado <em>X-Vistan-Token</em> con tu clave y cuerpo <em>JSON</em> con los campos <code>steps</code>, <code>active_kcal</code>, <code>distance_km</code>, <code>sleep_minutes</code> y <code>weight_kg</code> (cada uno con su resultado).</li>
          <li>Pulsa ▶︎ para probarlo. Debe responder <code>{"{\"ok\": true}"}</code> y los datos aparecerán aquí. VISTAN tiene que estar abierto en tu Mac.</li>
        </ol>
        <p className="muted small">La clave se guarda en el Llavero de tu Mac. Puedes enviar solo los campos que quieras: los que falten no se inventan.</p>
      </Panel>
      <div className="stack">
        <Panel title="Pasos (30 días)">
          {steps.length ? <LineChart ariaLabel="Pasos por día" labels={steps.map((x) => formatDayLabel(x.day))} height={170}
            series={[{ label: "Pasos", color: "#e11d35", values: steps.map((x) => x.steps) }]} /> : <Empty>Aún no ha llegado ningún dato del Atajo.</Empty>}
        </Panel>
        <Panel title="Sueño (horas)">
          {sleep.length ? <LineChart ariaLabel="Horas de sueño" unit=" h" labels={sleep.map((x) => formatDayLabel(x.day))} height={170}
            series={[{ label: "Sueño", color: "#a78bfa", values: sleep.map((x) => x.sleep_hours) }]} /> : <Empty>Sin datos de sueño.</Empty>}
        </Panel>
        {d.length > 0 && (
          <Panel title="Registros">
            <table className="data-table">
              <thead><tr><th>Día</th><th>Pasos</th><th>Sueño</th><th>Kcal activas</th><th>Distancia</th><th>Peso</th></tr></thead>
              <tbody>{[...d].reverse().map((x) => (
                <tr key={x.day}><td>{formatDayLabel(x.day)}</td><td className="mono">{x.steps ?? "—"}</td><td className="mono">{x.sleep_hours ?? "—"}</td>
                  <td className="mono">{x.active_kcal ?? "—"}</td><td className="mono">{x.distance_km ?? "—"}</td><td className="mono">{x.weight_kg ?? "—"}</td></tr>
              ))}</tbody>
            </table>
          </Panel>
        )}
      </div>
    </div>
  );
}
