import { useEffect, useRef } from "react";
import {
  AreaSeries, CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, LineSeries, LineStyle, createChart,
  type IChartApi, type ISeriesApi, type LogicalRange, type SeriesType, type Time, type UTCTimestamp,
} from "lightweight-charts";
import type { Candle, Position } from "../../api/desk";
import { atr, bollinger, ema, macd, rsi, sma, vwap, type IndicatorId } from "../../lib/indicators";

export type ChartType = "candles" | "line" | "area";
export type DrawMode = "none" | "hline" | "trend";
export interface Drawings { hlines: number[]; trends: { t1: number; p1: number; t2: number; p2: number }[] }

const C = {
  bg: "#07080a", grid: "rgba(255,255,255,0.045)", text: "#a7a2a0", up: "#2fbf8f", down: "#e0304a", crimson: "#d8243c",
  line: "#f1e6e2", sma20: "#f0b35a", sma50: "#7aa7ff", ema20: "#c792ea", bb: "rgba(216,36,60,0.75)", vwap: "#4fd1c5",
};
const ts = (t: number) => t as UTCTimestamp;
const pts = (c: Candle[], v: (number | null)[]) => v.flatMap((x, i) => (x === null || !Number.isFinite(x) ? [] : [{ time: ts(c[i].time), value: x }]));

export function loadDrawings(symbol: string): Drawings {
  try { return { hlines: [], trends: [], ...JSON.parse(localStorage.getItem(`vistan.desk.draw.${symbol}`) || "{}") }; }
  catch { return { hlines: [], trends: [] }; }
}
export function saveDrawings(symbol: string, d: Drawings) {
  try { localStorage.setItem(`vistan.desk.draw.${symbol}`, JSON.stringify(d)); } catch { /* sin almacenamiento */ }
}

/** Gráfico financiero interactivo: zoom con rueda/pellizco, arrastre temporal, indicadores en paneles y dibujo. */
export function PriceChart({ candles, symbol, tf, type, indicators, compare, compareLabel, positions, drawings, drawMode, onDraw, onApi, height = 520 }: {
  candles: Candle[]; symbol: string; tf: string; type: ChartType; indicators: Set<IndicatorId>;
  compare?: Candle[] | null; compareLabel?: string; positions?: Position[]; drawings: Drawings; drawMode: DrawMode;
  onDraw: (d: Drawings) => void; onApi?: (api: { screenshot: () => string | null; fit: () => void } | null) => void; height?: number;
}) {
  const box = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const mainRef = useRef<ISeriesApi<SeriesType> | null>(null);
  const range = useRef<{ key: string; r: LogicalRange | null }>({ key: "", r: null });
  const pending = useRef<{ t: number; p: number } | null>(null);
  const modeRef = useRef(drawMode);
  modeRef.current = drawMode;
  const drawRef = useRef(drawings);
  drawRef.current = drawings;
  const onDrawRef = useRef(onDraw);
  onDrawRef.current = onDraw;
  const key = `${symbol}|${tf}`;

  useEffect(() => {
    const el = box.current;
    if (!el || !candles.length) return;
    const chart = createChart(el, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: C.bg }, textColor: C.text, fontFamily: "'JetBrains Mono Variable', ui-monospace, monospace", fontSize: 11,
        panes: { separatorColor: "rgba(216,36,60,0.35)", separatorHoverColor: "rgba(216,36,60,0.6)" } },
      grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: "rgba(216,36,60,0.6)", labelBackgroundColor: C.crimson }, horzLine: { color: "rgba(216,36,60,0.6)", labelBackgroundColor: C.crimson } },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
      leftPriceScale: { visible: !!compare?.length, borderColor: "rgba(255,255,255,0.08)" },
      timeScale: { borderColor: "rgba(255,255,255,0.08)", timeVisible: !["1d", "1w", "1M"].includes(tf), secondsVisible: false, rightOffset: 6 },
    });
    chartRef.current = chart;
    const closes = candles.map((c) => c.close);

    let main: ISeriesApi<SeriesType>;
    if (type === "candles") {
      main = chart.addSeries(CandlestickSeries, { upColor: C.up, downColor: C.down, borderUpColor: C.up, borderDownColor: C.down, wickUpColor: C.up, wickDownColor: C.down });
      main.setData(candles.map((c) => ({ time: ts(c.time), open: c.open, high: c.high, low: c.low, close: c.close })));
    } else if (type === "line") {
      main = chart.addSeries(LineSeries, { color: C.line, lineWidth: 2 });
      main.setData(candles.map((c) => ({ time: ts(c.time), value: c.close })));
    } else {
      main = chart.addSeries(AreaSeries, { lineColor: C.crimson, topColor: "rgba(216,36,60,0.35)", bottomColor: "rgba(216,36,60,0.02)", lineWidth: 2 });
      main.setData(candles.map((c) => ({ time: ts(c.time), value: c.close })));
    }
    mainRef.current = main;

    const overlay = (v: (number | null)[], color: string, width: 1 | 2 = 1, style: LineStyle = LineStyle.Solid) =>
      chart.addSeries(LineSeries, { color, lineWidth: width, lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }).setData(pts(candles, v));
    if (indicators.has("sma20")) overlay(sma(closes, 20), C.sma20);
    if (indicators.has("sma50")) overlay(sma(closes, 50), C.sma50);
    if (indicators.has("ema20")) overlay(ema(closes, 20), C.ema20);
    if (indicators.has("vwap")) overlay(vwap(candles), C.vwap, 1, LineStyle.Dashed);
    if (indicators.has("bb")) {
      const b = bollinger(closes);
      overlay(b.upper, C.bb); overlay(b.middle, "rgba(216,36,60,0.45)", 1, LineStyle.Dotted); overlay(b.lower, C.bb);
    }
    if (indicators.has("volume")) {
      const vol = chart.addSeries(HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
      vol.setData(candles.map((c) => ({ time: ts(c.time), value: c.volume, color: c.close >= c.open ? "rgba(47,191,143,0.35)" : "rgba(224,48,74,0.35)" })));
      chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    }
    let pane = 1;
    if (indicators.has("rsi")) {
      const s = chart.addSeries(LineSeries, { color: "#f1e6e2", lineWidth: 1, priceLineVisible: false }, pane);
      s.setData(pts(candles, rsi(closes)));
      s.createPriceLine({ price: 70, color: "rgba(224,48,74,0.6)", lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: false, title: "70" });
      s.createPriceLine({ price: 30, color: "rgba(47,191,143,0.6)", lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: false, title: "30" });
      pane++;
    }
    if (indicators.has("macd")) {
      const m = macd(closes);
      chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, pane)
        .setData(m.hist.flatMap((x, i) => (x === null ? [] : [{ time: ts(candles[i].time), value: x, color: x >= 0 ? "rgba(47,191,143,0.55)" : "rgba(224,48,74,0.55)" }])));
      chart.addSeries(LineSeries, { color: "#7aa7ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane).setData(pts(candles, m.macd));
      chart.addSeries(LineSeries, { color: C.sma20, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane).setData(pts(candles, m.signal));
      pane++;
    }
    if (indicators.has("atr")) {
      chart.addSeries(LineSeries, { color: C.vwap, lineWidth: 1, priceLineVisible: false }, pane).setData(pts(candles, atr(candles)));
      pane++;
    }
    for (let i = 1; i < pane; i++) chart.panes()[i]?.setHeight(110);

    if (compare?.length) {
      chart.addSeries(LineSeries, { color: "#7aa7ff", lineWidth: 1, priceScaleId: "left", title: compareLabel, priceLineVisible: false })
        .setData(compare.map((c) => ({ time: ts(c.time), value: c.close })));
    }

    // Posiciones abiertas (simuladas) de este activo: entrada, SL y TP
    for (const p of positions ?? []) {
      main.createPriceLine({ price: p.entry_price, color: "#f1e6e2", lineStyle: LineStyle.Solid, lineWidth: 1, title: `${p.side === "long" ? "LARGO" : "CORTO"} ${p.qty}` });
      if (p.sl) main.createPriceLine({ price: p.sl, color: C.down, lineStyle: LineStyle.Dashed, lineWidth: 1, title: "SL" });
      if (p.tp) main.createPriceLine({ price: p.tp, color: C.up, lineStyle: LineStyle.Dashed, lineWidth: 1, title: "TP" });
    }
    // Dibujos: soportes/resistencias y líneas de tendencia
    for (const h of drawings.hlines) main.createPriceLine({ price: h, color: C.crimson, lineStyle: LineStyle.LargeDashed, lineWidth: 1, title: "S/R" });
    for (const t of drawings.trends) {
      const a = { time: ts(Math.min(t.t1, t.t2)), value: t.t1 <= t.t2 ? t.p1 : t.p2 };
      const b = { time: ts(Math.max(t.t1, t.t2)), value: t.t1 <= t.t2 ? t.p2 : t.p1 };
      if (a.time === b.time) continue;
      chart.addSeries(LineSeries, { color: "#f0b35a", lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }).setData([a, b]);
    }

    chart.subscribeClick((param) => {
      const mode = modeRef.current;
      if (mode === "none" || !param.point || param.time === undefined) return;
      const price = main.coordinateToPrice(param.point.y);
      if (price === null) return;
      const d = drawRef.current;
      if (mode === "hline") { onDrawRef.current({ ...d, hlines: [...d.hlines, +price.toPrecision(8)] }); return; }
      const t = Number(param.time as Time);
      if (!pending.current) { pending.current = { t, p: price }; return; }
      const first = pending.current;
      pending.current = null;
      if (first.t !== t) onDrawRef.current({ ...d, trends: [...d.trends, { t1: first.t, p1: first.p, t2: t, p2: price }] });
    });

    if (range.current.key === key && range.current.r) chart.timeScale().setVisibleLogicalRange(range.current.r);
    else chart.timeScale().fitContent();
    const keep = () => { range.current = { key, r: chart.timeScale().getVisibleLogicalRange() }; };
    chart.timeScale().subscribeVisibleLogicalRangeChange(keep);

    onApi?.({
      screenshot: () => { try { return chart.takeScreenshot().toDataURL("image/png"); } catch { return null; } },
      fit: () => chart.timeScale().fitContent(),
    });
    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(keep);
      onApi?.(null);
      chart.remove();
      chartRef.current = null;
      mainRef.current = null;
    };
  }, [candles, type, indicators, compare, compareLabel, positions, drawings, key, tf, onApi]);

  useEffect(() => { pending.current = null; }, [drawMode]);

  return <div ref={box} className={`desk-chart ${drawMode !== "none" ? "is-drawing" : ""}`} style={{ height }} data-testid="price-chart" />;
}
