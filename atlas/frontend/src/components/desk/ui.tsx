import { useEffect, useRef } from "react";
import { AreaSeries, ColorType, LineSeries, createChart, type UTCTimestamp } from "lightweight-charts";
import type { DataKind } from "../../api/desk";

export const ND = "N/D";
const nf = (d: number) => new Intl.NumberFormat("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });

export function price(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return ND;
  const a = Math.abs(v);
  return nf(a >= 1000 ? 2 : a >= 1 ? (a >= 100 ? 2 : 4) : 6).format(v);
}
export function money(v: number | null | undefined, ccy = "EUR", sign = false): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return ND;
  const s = new Intl.NumberFormat("es-ES", { style: "currency", currency: ccy, maximumFractionDigits: 2 }).format(v);
  return sign && v > 0 ? `+${s}` : s;
}
export function pct(v: number | null | undefined, sign = true, d = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return ND;
  return `${sign && v > 0 ? "+" : ""}${nf(d).format(v)} %`;
}
export function num(v: number | null | undefined, d = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return ND;
  return nf(d).format(v);
}
export function compact(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return ND;
  return new Intl.NumberFormat("es-ES", { notation: "compact", maximumFractionDigits: 1 }).format(v);
}
export const tone = (v: number | null | undefined) => (v === null || v === undefined || v === 0 ? "" : v > 0 ? "up" : "down");
export function ago(ts: number | null | undefined): string {
  if (!ts) return ND;
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${Math.round(s / 60)} min`;
  if (s < 172800) return `${Math.round(s / 3600)} h`;
  return `${Math.round(s / 86400)} d`;
}
export function dt(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleString("es-ES", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
}
export function held(iso: string): string {
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
  const h = (Date.now() - d.getTime()) / 3_600_000;
  return h < 1 ? `${Math.max(1, Math.round(h * 60))} min` : h < 48 ? `${Math.round(h)} h` : `${Math.round(h / 24)} d`;
}

const KIND: Record<DataKind, [string, string]> = {
  realtime: ["TR", "Tiempo real"], delayed: ["RET", "Con retraso"], plan: ["TR/RET", "Tiempo real o retraso según tu plan"],
  historical: ["HIST", "Histórico"], none: ["N/D", "Sin datos"],
};
export function KindTag({ kind, source }: { kind: DataKind | null | undefined; source?: string | null }) {
  const k = (kind || "none") as DataKind;
  return <span className={`kind-tag k-${k}`} title={`${KIND[k][1]}${source ? ` · fuente: ${source}` : ""}`}>{KIND[k][0]}</span>;
}

export function SimBadge() {
  return <span className="sim-badge" title="Todas las operaciones son simuladas con dinero virtual">PAPER · SIMULACIÓN</span>;
}

/** Curva (equity, resultados…) con Lightweight Charts. */
export function MiniChart({ data, height = 220, color = "#d8243c", area = true, baseline }: {
  data: { time: number; value: number }[]; height?: number; color?: string; area?: boolean; baseline?: number;
}) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!box.current || data.length < 2) return;
    const ch = createChart(box.current, {
      autoSize: true, layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#a7a2a0", fontSize: 10 },
      grid: { vertLines: { visible: false }, horzLines: { color: "rgba(255,255,255,0.05)" } },
      rightPriceScale: { borderVisible: false }, timeScale: { borderVisible: false, timeVisible: true }, handleScroll: false, handleScale: false,
    });
    const uniq = [...new Map(data.map((d) => [Math.floor(d.time), d.value])).entries()].sort((a, b) => a[0] - b[0]);
    const pts = uniq.map(([t, v]) => ({ time: t as UTCTimestamp, value: v }));
    const s = area
      ? ch.addSeries(AreaSeries, { lineColor: color, topColor: `${color}55`, bottomColor: `${color}05`, lineWidth: 2, priceLineVisible: false })
      : ch.addSeries(LineSeries, { color, lineWidth: 2, priceLineVisible: false });
    s.setData(pts);
    if (baseline !== undefined) s.createPriceLine({ price: baseline, color: "rgba(255,255,255,0.3)", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "inicio" });
    ch.timeScale().fitContent();
    return () => ch.remove();
  }, [data, height, color, area, baseline]);
  if (data.length < 2) return <p className="muted small desk-empty">Sin datos suficientes para dibujar la curva (se necesitan al menos 2 puntos registrados).</p>;
  return <div ref={box} style={{ height }} className="mini-chart" />;
}

export function Stat({ label, value, cls = "", hint }: { label: string; value: string; cls?: string; hint?: string }) {
  return (
    <div className="dstat" title={hint}>
      <span>{label}</span>
      <strong className={`mono ${cls}`}>{value}</strong>
    </div>
  );
}

export const toNum = (s: string): number | null => {
  const t = s.trim().replace(/\s/g, "");
  if (!t) return null;
  const n = Number(t.includes(",") && !t.includes(".") ? t.replace(",", ".") : t.replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
};
