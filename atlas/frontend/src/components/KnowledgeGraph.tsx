import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphData, GraphNode } from "../api/v4";

/** Grafo de conocimiento (estilo Obsidian) en canvas: simulación de fuerzas propia, zoom con la rueda,
 *  arrastre del fondo para moverse, arrastre de nodos, búsqueda y filtros. Representa SOLO datos reales. */
export const KIND_COLOR: Record<string, string> = {
  project: "#e11d35", memory: "#cfcfcf", decision: "#e9a23b", idea: "#f07b88", goal: "#3ccf7a", task: "#9a9a9a",
  document: "#8fa3b8", research: "#b07cff", conversation: "#6f6f6f", person: "#ff6b7a", org: "#b51224", place: "#c9a27a", concept: "#d8d8d8",
};

interface Sim { x: number; y: number; vx: number; vy: number; fixed?: boolean }

export function KnowledgeGraph({ data, hidden, query, selected, onSelect, height = 560 }: {
  data: GraphData; hidden: Set<string>; query: string; selected: string | null; onSelect: (n: GraphNode | null) => void; height?: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const sim = useRef<Map<string, Sim>>(new Map());
  const view = useRef({ x: 0, y: 0, k: 1 });
  const heat = useRef(1);
  const fitted = useRef(false);
  const hover = useRef<string | null>(null);
  const [, force] = useState(0);
  const nodes = useMemo(() => data.nodes.filter((n) => !hidden.has(n.kind)), [data, hidden]);
  const ids = useMemo(() => new Set(nodes.map((n) => n.id)), [nodes]);
  const edges = useMemo(() => data.edges.filter((e) => ids.has(e.source) && ids.has(e.target)), [data, ids]);
  const q = query.trim().toLowerCase();

  // Posiciones iniciales estables (en círculo) para los nodos nuevos
  useEffect(() => {
    const m = sim.current;
    nodes.forEach((n, i) => {
      if (!m.has(n.id)) {
        const a = (i / Math.max(1, nodes.length)) * Math.PI * 2;
        const r = 120 + (i % 7) * 25;
        m.set(n.id, { x: Math.cos(a) * r, y: Math.sin(a) * r, vx: 0, vy: 0 });
      }
    });
    heat.current = 1;
    fitted.current = false;
  }, [nodes]);

  useEffect(() => {
    let raf = 0;
    const cv = canvas.current!;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    const idx = new Map(nodes.map((n) => [n.id, n]));
    const neighbors = new Set<string>();
    if (selected) edges.forEach((e) => { if (e.source === selected) neighbors.add(e.target); if (e.target === selected) neighbors.add(e.source); });
    const step = () => {
      const m = sim.current;
      if (heat.current > 0.02) {
        const arr = nodes.map((n) => m.get(n.id)!);
        for (let i = 0; i < arr.length; i++) {
          const a = arr[i];
          for (let j = i + 1; j < arr.length; j++) {
            const b = arr[j];
            let dx = a.x - b.x, dy = a.y - b.y;
            let d2 = dx * dx + dy * dy;
            if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
            if (d2 > 250000) continue;
            const f = 380 / d2;
            a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;
          }
          a.vx -= a.x * 0.004; a.vy -= a.y * 0.004;
        }
        for (const e of edges) {
          const a = m.get(e.source)!, b = m.get(e.target)!;
          const dx = b.x - a.x, dy = b.y - a.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 1;
          const f = (d - 70) * 0.02;
          a.vx += (dx / d) * f; a.vy += (dy / d) * f; b.vx -= (dx / d) * f; b.vy -= (dy / d) * f;
        }
        for (const p of arr) {
          if (p.fixed) { p.vx = p.vy = 0; continue; }
          p.vx *= 0.82; p.vy *= 0.82;
          p.x += p.vx * heat.current; p.y += p.vy * heat.current;
        }
        heat.current *= 0.985;
        if (heat.current < 0.25 && !fitted.current && arr.length) {  // encuadre automático una vez estabilizado
          fitted.current = true;
          const xs = arr.map((p) => p.x), ys = arr.map((p) => p.y);
          const w = Math.max(80, Math.max(...xs) - Math.min(...xs)), h = Math.max(80, Math.max(...ys) - Math.min(...ys));
          const k = Math.min(2.2, Math.max(0.25, Math.min((cv.clientWidth - 120) / w, (cv.clientHeight - 80) / h)));
          view.current = { k, x: -((Math.max(...xs) + Math.min(...xs)) / 2) * k, y: -((Math.max(...ys) + Math.min(...ys)) / 2) * k };
        }
      }
      const dpr = window.devicePixelRatio || 1;
      const W = cv.clientWidth, H = cv.clientHeight;
      if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const v = view.current;
      ctx.save();
      ctx.translate(W / 2 + v.x, H / 2 + v.y);
      ctx.scale(v.k, v.k);
      for (const e of edges) {
        const a = m.get(e.source)!, b = m.get(e.target)!;
        const lit = selected && (e.source === selected || e.target === selected);
        ctx.strokeStyle = lit ? "rgba(225,29,53,.75)" : e.origin.startsWith("manual") ? "rgba(234,234,234,.28)" : "rgba(234,234,234,.12)";
        ctx.lineWidth = (lit ? 1.6 : 0.8) / Math.max(0.6, v.k);
        if (e.origin === "mención") ctx.setLineDash([3, 3]); else ctx.setLineDash([]);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      ctx.setLineDash([]);
      for (const n of nodes) {
        const p = m.get(n.id)!;
        const r = 4 + Math.min(10, Math.sqrt(n.degree) * 2.2) + (n.type === "project" ? 3 : 0);
        const match = q && n.label.toLowerCase().includes(q);
        const dim = (selected && n.id !== selected && !neighbors.has(n.id)) || (q && !match);
        ctx.globalAlpha = dim ? 0.18 : 1;
        ctx.fillStyle = KIND_COLOR[n.kind] ?? "#bbb";
        ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill();
        if (n.id === selected || match) {
          ctx.strokeStyle = "#e11d35"; ctx.lineWidth = 2 / v.k;
          ctx.beginPath(); ctx.arc(p.x, p.y, r + 4 / v.k, 0, Math.PI * 2); ctx.stroke();
        }
        if (!dim && (nodes.length <= 40 || v.k > 1.15 || n.type === "project" || n.id === hover.current || n.id === selected || match || n.degree > 3)) {
          ctx.fillStyle = "rgba(234,234,234,.86)";
          ctx.font = `${12 / v.k}px Manrope Variable, system-ui`;
          ctx.fillText(n.label.length > 34 ? n.label.slice(0, 33) + "…" : n.label, p.x + r + 4 / v.k, p.y + 4 / v.k);
        }
        ctx.globalAlpha = 1;
      }
      ctx.restore();
      raf = requestAnimationFrame(step);
      void idx;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [nodes, edges, selected, q]);

  // Interacción
  useEffect(() => {
    const cv = canvas.current!;
    let drag: { id: string | null; sx: number; sy: number; ox: number; oy: number; moved: boolean } | null = null;
    const toWorld = (cx: number, cy: number) => {
      const r = cv.getBoundingClientRect(), v = view.current;
      return { x: (cx - r.left - r.width / 2 - v.x) / v.k, y: (cy - r.top - r.height / 2 - v.y) / v.k };
    };
    const hit = (cx: number, cy: number) => {
      const w = toWorld(cx, cy);
      let best: string | null = null, bd = 14 / view.current.k;
      for (const n of nodes) {
        const p = sim.current.get(n.id);
        if (!p) continue;
        const d = Math.hypot(p.x - w.x, p.y - w.y);
        if (d < bd) { bd = d; best = n.id; }
      }
      return best;
    };
    const down = (e: PointerEvent) => {
      const id = hit(e.clientX, e.clientY);
      drag = { id, sx: e.clientX, sy: e.clientY, ox: view.current.x, oy: view.current.y, moved: false };
      cv.setPointerCapture(e.pointerId);
    };
    const move = (e: PointerEvent) => {
      if (!drag) { const h = hit(e.clientX, e.clientY); if (h !== hover.current) { hover.current = h; cv.style.cursor = h ? "pointer" : "grab"; } return; }
      if (Math.abs(e.clientX - drag.sx) + Math.abs(e.clientY - drag.sy) > 3) drag.moved = true;
      if (drag.id) {
        const p = sim.current.get(drag.id)!, w = toWorld(e.clientX, e.clientY);
        p.x = w.x; p.y = w.y; p.fixed = true; heat.current = Math.max(heat.current, 0.3);
      } else {
        view.current.x = drag.ox + (e.clientX - drag.sx); view.current.y = drag.oy + (e.clientY - drag.sy);
      }
    };
    const up = () => {
      if (drag && !drag.moved) onSelect(drag.id ? nodes.find((n) => n.id === drag!.id) ?? null : null);
      if (drag?.id) { const p = sim.current.get(drag.id); if (p) p.fixed = false; }
      drag = null;
    };
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const v = view.current, r = cv.getBoundingClientRect();
      const k = Math.min(4, Math.max(0.2, v.k * (e.deltaY < 0 ? 1.12 : 0.89)));
      const mx = e.clientX - r.left - r.width / 2, my = e.clientY - r.top - r.height / 2;
      v.x = mx - ((mx - v.x) * k) / v.k; v.y = my - ((my - v.y) * k) / v.k; v.k = k;
      force((x) => x + 1);
    };
    cv.addEventListener("pointerdown", down);
    cv.addEventListener("pointermove", move);
    cv.addEventListener("pointerup", up);
    cv.addEventListener("wheel", wheel, { passive: false });
    return () => { cv.removeEventListener("pointerdown", down); cv.removeEventListener("pointermove", move); cv.removeEventListener("pointerup", up); cv.removeEventListener("wheel", wheel); };
  }, [nodes, onSelect]);

  const zoom = (f: number) => { view.current.k = Math.min(4, Math.max(0.2, view.current.k * f)); force((x) => x + 1); };
  return (
    <div ref={wrap} className="kg-wrap" style={{ height }}>
      <canvas ref={canvas} className="kg-canvas" role="img" aria-label={`Grafo de conocimiento: ${nodes.length} nodos y ${edges.length} relaciones`} />
      <div className="kg-zoom">
        <button type="button" className="mini-btn ghost" onClick={() => zoom(1.25)} aria-label="Acercar">+</button>
        <button type="button" className="mini-btn ghost" onClick={() => zoom(0.8)} aria-label="Alejar">−</button>
        <button type="button" className="mini-btn ghost" onClick={() => { fitted.current = false; heat.current = Math.max(heat.current, 0.3); force((x) => x + 1); }}>Encuadrar</button>
      </div>
    </div>
  );
}
