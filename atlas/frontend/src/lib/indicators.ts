/** Indicadores técnicos sobre velas reales. Devuelven arrays alineados con las velas (null sin datos suficientes). */
import type { Candle } from "../api/desk";

type S = (number | null)[];

export function sma(v: number[], n: number): S {
  const out: S = [];
  let s = 0;
  v.forEach((x, i) => {
    s += x;
    if (i >= n) s -= v[i - n];
    out.push(i >= n - 1 ? s / n : null);
  });
  return out;
}

export function ema(v: number[], n: number): S {
  const out: S = [];
  const k = 2 / (n + 1);
  let prev: number | null = null;
  v.forEach((x, i) => {
    if (i < n - 1) { out.push(null); return; }
    prev = prev === null ? v.slice(i - n + 1, i + 1).reduce((a, b) => a + b, 0) / n : x * k + prev * (1 - k);
    out.push(prev);
  });
  return out;
}

export function rsi(v: number[], n = 14): S {
  const out: S = v.map(() => null);
  if (v.length <= n) return out;
  let g = 0, l = 0;
  for (let i = 1; i <= n; i++) { const d = v[i] - v[i - 1]; g += Math.max(d, 0); l += Math.max(-d, 0); }
  let ag = g / n, al = l / n;
  out[n] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
  for (let i = n + 1; i < v.length; i++) {
    const d = v[i] - v[i - 1];
    ag = (ag * (n - 1) + Math.max(d, 0)) / n;
    al = (al * (n - 1) + Math.max(-d, 0)) / n;
    out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
  }
  return out;
}

export function macd(v: number[], f = 12, s = 26, sig = 9): { macd: S; signal: S; hist: S } {
  const ef = ema(v, f), es = ema(v, s);
  const line: S = ef.map((a, i) => (a !== null && es[i] !== null ? a - (es[i] as number) : null));
  const start = line.findIndex((x) => x !== null);
  const signal: S = v.map(() => null);
  if (start >= 0) ema(line.slice(start) as number[], sig).forEach((x, i) => { signal[start + i] = x; });
  return { macd: line, signal, hist: line.map((a, i) => (a !== null && signal[i] !== null ? a - (signal[i] as number) : null)) };
}

export function bollinger(v: number[], n = 20, k = 2): { middle: S; upper: S; lower: S } {
  const mid = sma(v, n);
  const upper: S = [], lower: S = [];
  mid.forEach((m, i) => {
    if (m === null) { upper.push(null); lower.push(null); return; }
    const w = v.slice(i - n + 1, i + 1);
    const sd = Math.sqrt(w.reduce((a, x) => a + (x - m) ** 2, 0) / n);
    upper.push(m + k * sd);
    lower.push(m - k * sd);
  });
  return { middle: mid, upper, lower };
}

export function atr(c: Candle[], n = 14): S {
  const out: S = c.map(() => null);
  const tr = c.map((x, i) => { const pc = i ? c[i - 1].close : x.close; return Math.max(x.high - x.low, Math.abs(x.high - pc), Math.abs(x.low - pc)); });
  if (c.length < n) return out;
  let a = tr.slice(0, n).reduce((s, x) => s + x, 0) / n;
  out[n - 1] = a;
  for (let i = n; i < c.length; i++) { a = (a * (n - 1) + tr[i]) / n; out[i] = a; }
  return out;
}

/** VWAP acumulado que se reinicia cada día (UTC). */
export function vwap(c: Candle[]): S {
  let pv = 0, vol = 0, day = -1;
  return c.map((x) => {
    const d = Math.floor(x.time / 86400);
    if (d !== day) { pv = 0; vol = 0; day = d; }
    pv += ((x.high + x.low + x.close) / 3) * (x.volume || 0);
    vol += x.volume || 0;
    return vol ? pv / vol : null;
  });
}

export const INDICATORS = {
  sma20: "SMA 20", sma50: "SMA 50", ema20: "EMA 20", bb: "Bollinger (20, 2)", vwap: "VWAP", volume: "Volumen",
  rsi: "RSI 14", macd: "MACD (12, 26, 9)", atr: "ATR 14",
} as const;
export type IndicatorId = keyof typeof INDICATORS;
export const INDICATOR_HELP: Record<IndicatorId, string> = {
  sma20: "Media simple de 20 velas: suaviza el precio para ver la tendencia a corto plazo.",
  sma50: "Media simple de 50 velas: tendencia de medio plazo. Si el precio está por encima, la tendencia suele ser alcista.",
  ema20: "Media exponencial de 20 velas: como la SMA pero da más peso a lo reciente; reacciona antes.",
  bb: "Bandas de Bollinger: media de 20 ± 2 desviaciones. Bandas estrechas = poca volatilidad; tocar una banda no es por sí solo una señal.",
  vwap: "Precio medio ponderado por volumen del día: referencia que usan muchos operadores intradía.",
  volume: "Volumen negociado en cada vela: confirma la fuerza de un movimiento.",
  rsi: "RSI: fuerza relativa de 0 a 100. Por encima de 70 se considera sobrecompra y por debajo de 30 sobreventa (no garantiza un giro).",
  macd: "MACD: diferencia entre dos EMA y su señal. Los cruces indican cambios de impulso; el histograma muestra su fuerza.",
  atr: "ATR: rango medio verdadero, mide la volatilidad. Útil para colocar el stop loss a una distancia razonable.",
};
