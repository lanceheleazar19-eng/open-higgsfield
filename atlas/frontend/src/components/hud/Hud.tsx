import { useEffect, useRef, useState, type ReactNode } from "react";
import { telemetry, type TelemetryData } from "../../api/telemetry";

/* ---------- Sondeo de telemetría con historial real (muestras tomadas, nunca interpoladas) ---------- */
export function useTelemetry(ms = 4000) {
  const [data, setData] = useState<TelemetryData | null>(null);
  const [error, setError] = useState(false);
  const [hist, setHist] = useState<{ cpu: number[]; ram: number[] }>({ cpu: [], ram: [] });
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const t = await telemetry();
        if (!alive) return;
        setData(t); setError(false);
        setHist((h) => ({
          cpu: t.system.cpu_percent !== undefined ? [...h.cpu, t.system.cpu_percent].slice(-40) : h.cpu,
          ram: t.system.ram_percent !== undefined ? [...h.ram, t.system.ram_percent].slice(-40) : h.ram,
        }));
      } catch { if (alive) setError(true); }
    };
    void tick();
    const id = setInterval(() => { if (document.visibilityState !== "hidden") void tick(); }, ms);
    return () => { alive = false; clearInterval(id); };
  }, [ms]);
  return { data, error, hist };
}

/* ---------- Utilidades de formato (N/D cuando no hay dato) ---------- */
export const ND = "N/D";
export const pct = (v?: number | null) => (v === undefined || v === null ? ND : `${Math.round(v)}%`);
export const ms = (v?: number | null) => (v === undefined || v === null ? ND : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${v} ms`);
export function bytes(v?: number | null): string {
  if (v === undefined || v === null) return ND;
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0, x = v;
  while (x >= 1024 && i < u.length - 1) { x /= 1024; i++; }
  return `${x.toFixed(x >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
}
export function uptime(s?: number): string {
  if (s === undefined) return ND;
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m ${s % 60}s`;
}
export const hhmmss = (iso: string) => new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`)
  .toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

/* ---------- Gráfica mínima de una serie real ---------- */
export function Spark({ values, max, label, height = 34 }: { values: number[]; max?: number; label: string; height?: number }) {
  const W = 200, H = height;
  if (values.length < 2) return <div className="spark spark-empty" style={{ height }} aria-label={`${label}: recopilando muestras`}>recopilando…</div>;
  const top = max ?? Math.max(...values, 1);
  const pts = values.map((v, i) => `${(i * W) / (values.length - 1)},${H - (Math.min(v, top) / top) * (H - 4) - 2}`).join(" ");
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ height }} role="img" aria-label={label}>
      <polygon points={`0,${H} ${pts} ${W},${H}`} className="spark-area" />
      <polyline points={pts} className="spark-line" />
      <circle cx={W} cy={pts.split(" ").pop()!.split(",")[1]} r="2.6" className="spark-dot" />
    </svg>
  );
}

export function Meter({ value, warn = 75, danger = 90 }: { value?: number | null; warn?: number; danger?: number }) {
  if (value === undefined || value === null) return <span className="meter meter-nd" />;
  return <span className={`meter ${value >= danger ? "is-danger" : value >= warn ? "is-warn" : ""}`}><i style={{ width: `${Math.min(100, value)}%` }} /></span>;
}

export const Led = ({ state }: { state: "ok" | "off" | "key" | "error" | "busy" }) => <i className={`led led-${state}`} aria-hidden="true" />;

/* ---------- Widgets que se pueden ocultar y reordenar (preferencia guardada en este navegador) ---------- */
export interface WidgetDef { id: string; title: string; render: () => ReactNode; wide?: boolean }

function load(key: string, ids: string[]): { order: string[]; hidden: string[] } {
  try {
    const v = JSON.parse(localStorage.getItem(key) ?? "null") as { order: string[]; hidden: string[] } | null;
    if (v) return { order: [...v.order.filter((x) => ids.includes(x)), ...ids.filter((x) => !v.order.includes(x))], hidden: v.hidden.filter((x) => ids.includes(x)) };
  } catch { /* sin almacenamiento */ }
  return { order: ids, hidden: [] };
}

export function WidgetColumn({ panel, title, widgets, className = "" }: { panel: string; title: string; widgets: WidgetDef[]; className?: string }) {
  const key = `vistan.hud.${panel}`;
  const ids = widgets.map((w) => w.id);
  const [cfg, setCfg] = useState(() => load(key, ids));
  const [edit, setEdit] = useState(false);
  const save = (c: typeof cfg) => { setCfg(c); try { localStorage.setItem(key, JSON.stringify(c)); } catch { /* */ } };
  const byId = new Map(widgets.map((w) => [w.id, w]));
  // los widgets que aparecen después (p. ej. correos o alertas al llegar datos) se añaden al orden guardado
  const order = [...cfg.order.filter((id) => byId.has(id)), ...ids.filter((id) => !cfg.order.includes(id))];
  const move = (id: string, d: number) => {
    const o = [...order], i = o.indexOf(id), j = i + d;
    if (j < 0 || j >= o.length) return;
    [o[i], o[j]] = [o[j], o[i]];
    save({ ...cfg, order: o });
  };
  const hidden = order.filter((id) => cfg.hidden.includes(id));
  return (
    <section className={`hud-col ${className} ${edit ? "is-editing" : ""}`} aria-label={title}>
      <header className="hud-col-head">
        <span className="hud-col-title">{title}</span>
        <button type="button" className="hud-edit" aria-pressed={edit} onClick={() => setEdit(!edit)} title="Personalizar widgets">{edit ? "Listo" : "⚙"}</button>
      </header>
      <div className="hud-col-body">
        {order.filter((id) => !cfg.hidden.includes(id)).map((id) => {
          const w = byId.get(id)!;
          return (
            <article key={id} className={`hud-w ${w.wide ? "is-wide" : ""}`} aria-label={w.title}>
              <header className="hud-w-head">
                <span className="hud-w-title">{w.title}</span>
                {edit && <span className="hud-w-tools">
                  <button type="button" onClick={() => move(id, -1)} aria-label={`Subir ${w.title}`}>▲</button>
                  <button type="button" onClick={() => move(id, 1)} aria-label={`Bajar ${w.title}`}>▼</button>
                  <button type="button" onClick={() => save({ ...cfg, hidden: [...cfg.hidden, id] })} aria-label={`Ocultar ${w.title}`}>✕</button>
                </span>}
              </header>
              <div className="hud-w-body">{w.render()}</div>
            </article>
          );
        })}
        {edit && hidden.length > 0 && (
          <div className="hud-hidden">
            <span className="small muted">Ocultos:</span>
            {hidden.map((id) => <button key={id} type="button" className="chip" onClick={() => save({ ...cfg, hidden: cfg.hidden.filter((x) => x !== id) })}>+ {byId.get(id)?.title}</button>)}
            <button type="button" className="link-btn" onClick={() => save({ order: ids, hidden: [] })}>Restablecer</button>
          </div>
        )}
      </div>
    </section>
  );
}

/* ---------- Consola de eventos con autodesplazamiento ---------- */
export function EventConsole({ events }: { events: TelemetryData["events"] }) {
  const ref = useRef<HTMLOListElement>(null);
  if (!events.length) return <p className="hud-empty">Sin eventos registrados todavía.</p>;
  return (
    <ol ref={ref} className="console-log" aria-label="Registro de eventos">
      {events.map((e, i) => (
        <li key={i} className={`ev-${e.action === "error" ? "err" : e.module}`}>
          <time>{hhmmss(e.ts)}</time><span className="ev-mod">{e.module.toUpperCase().slice(0, 9)}</span><span className="ev-text">{e.text}</span>
        </li>
      ))}
    </ol>
  );
}
