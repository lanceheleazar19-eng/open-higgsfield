import { useEffect, useRef, useState } from "react";

/** Gráfico de líneas SVG ligero (sin dependencias). Cada punto tiene tooltip nativo.
 *  El viewBox se ajusta al ancho real del contenedor para que el texto no se deforme. */
export interface Series { label: string; color: string; values: (number | null)[] }

export function LineChart({ labels, series, height = 200, unit = "", ariaLabel }: {
  labels: string[]; series: Series[]; height?: number; unit?: string; ariaLabel: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(640);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setW(Math.max(260, Math.round(el.getBoundingClientRect().width) || 640));
    update();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const H = height, P = { l: 44, r: 12, t: 12, b: 26 };
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  if (labels.length === 0 || all.length === 0) return <div ref={ref} />;
  let min = Math.min(...all), max = Math.max(...all);
  if (min === max) { min -= 1; max += 1; }
  const pad = (max - min) * 0.1;
  min -= pad; max += pad;
  const x = (i: number) => P.l + (labels.length === 1 ? (W - P.l - P.r) / 2 : (i * (W - P.l - P.r)) / (labels.length - 1));
  const y = (v: number) => P.t + (1 - (v - min) / (max - min)) * (H - P.t - P.b);
  const ticks = [0, 0.5, 1].map((f) => min + f * (max - min));
  const fmt = (v: number) => new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(v);
  const every = Math.max(1, Math.ceil(labels.length / Math.max(2, Math.floor(W / 110))));
  return (
    <div ref={ref} className="line-chart-wrap">
    <svg className="line-chart" width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel}>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} className="lc-grid" />
          <text x={P.l - 6} y={y(t) + 4} className="lc-axis" textAnchor="end">{fmt(t)}</text>
        </g>
      ))}
      {labels.map((l, i) => (i % every === 0 || i === labels.length - 1) && (
        <text key={l + i} x={x(i)} y={H - 6} className="lc-axis" textAnchor="middle">{l}</text>
      ))}
      {series.map((s) => {
        const pts = s.values.map((v, i) => (v === null ? null : [x(i), y(v)] as const)).filter(Boolean) as (readonly [number, number])[];
        return (
          <g key={s.label}>
            <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke={s.color} strokeWidth={2} />
            {s.values.map((v, i) => v === null ? null : (
              <circle key={i} cx={x(i)} cy={y(v)} r={3.5} fill={s.color} className="lc-dot">
                <title>{`${labels[i]} · ${s.label}: ${fmt(v)}${unit}`}</title>
              </circle>
            ))}
          </g>
        );
      })}
    </svg>
    </div>
  );
}
