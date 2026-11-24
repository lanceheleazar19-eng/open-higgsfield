import { useEffect, useRef, useState } from "react";
import { Icon } from "../Icon";
import { LINKS, NODE_DEFS } from "./nodes";
import { DEFAULT_PITCH, cameraDistance, pitchFor, project, rotateView, separate, sub, type Vec3 } from "./orbits";
import type { AtlasScene, CoreState } from "./scene";

export interface NodeInfo {
  metric: string; // dato real del módulo
  planned: boolean;
  alert?: boolean;
  active?: boolean; // actividad real ahora (proceso en marcha, alerta, datos de hoy…)
  details?: string[]; // información contextual real para la tarjeta del planeta
}

const STATE_LABEL: Record<CoreState, string> = {
  idle: "En espera", listening: "Escuchando", thinking: "Razonando", researching: "Investigando",
  executing: "Ejecutando", speaking: "Hablando", responding: "Respondiendo", error: "Error",
};

function webglAvailable(): boolean {
  if (typeof window === "undefined" || typeof window.WebGLRenderingContext === "undefined") return false;
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

const IDX = new Map(NODE_DEFS.map((n, i) => [n.id, i]));
const LINK_IDX = LINKS.map(([a, b]) => [IDX.get(a)!, IDX.get(b)!] as [number, number]);

/** VISTAN CORE y su sistema solar de módulos. Escena WebGL (núcleo neuronal, órbitas, enlaces y partículas) +
 *  planetas HTML nítidos y accesibles proyectados con la misma cámara. Rueda: zoom · arrastrar: girar la vista ·
 *  clic en un planeta: la cámara se acerca y aparece su información. */
export function AtlasCore({ info, state, rippleKey, onOpen, selected, onSelect }: {
  info: Record<string, NodeInfo>;
  state: CoreState;
  rippleKey: number;
  onOpen: (route: string) => void;
  selected?: string | null;
  onSelect?: (id: string | null) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodeRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const sceneRef = useRef<AtlasScene | null>(null);
  const hoverRef = useRef(-1);
  const stateRef = useRef(state);
  const selRef = useRef(-1);
  const camRef = useRef({ rx: DEFAULT_PITCH, ry: 0, trx: DEFAULT_PITCH, try: 0, zoom: 1, tzoom: 1, target: [0, 0, 0] as Vec3 });
  const [mode, setMode] = useState<"webgl" | "fallback" | "pending">("pending");
  const [internalSel, setInternalSel] = useState<string | null>(null);
  const sel = selected !== undefined ? selected : internalSel;
  const select = (id: string | null) => { if (onSelect) onSelect(id); else setInternalSel(id); };
  const selectRef = useRef(select);
  selectRef.current = select;

  stateRef.current = state;
  selRef.current = sel ? IDX.get(sel) ?? -1 : -1;
  useEffect(() => { sceneRef.current?.setState(state); }, [state]);
  useEffect(() => { if (rippleKey) sceneRef.current?.ripple(); }, [rippleKey]);
  useEffect(() => { // al seleccionar, la cámara se acerca; al deseleccionar, vuelve a la vista general
    const c = camRef.current;
    c.tzoom = sel ? 0.58 : 1;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && sel) selectRef.current(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sel]);

  useEffect(() => {
    const wrap = wrapRef.current!;
    const canvas = canvasRef.current!;
    let disposed = false;
    let raf = 0;
    const reduced = prefersReducedMotion();
    const lite = window.innerWidth < 760;
    const cam = camRef.current;
    let w = 1, h = 1, baseZ = 12, lastPitch = -1;
    let orbitTime = 0;
    let last = performance.now();

    const resize = () => {
      const r = wrap.getBoundingClientRect();
      w = Math.max(1, r.width);
      h = Math.max(1, r.height);
      const pitch = pitchFor(w);
      if (pitch !== lastPitch) { cam.trx = cam.rx = pitch; lastPitch = pitch; }
      baseZ = cameraDistance(w / h, w < 640, pitch);
      sceneRef.current?.resize(w, h, baseZ * cam.zoom);
    };
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    ro?.observe(wrap);
    resize();

    // Arrastrar para girar la vista · rueda para hacer zoom
    let drag: { x: number; y: number; moved: boolean } | null = null;
    const down = (e: PointerEvent) => {
      if ((e.target as HTMLElement).closest(".planet, .core-card, .core-ctrl")) return;
      drag = { x: e.clientX, y: e.clientY, moved: false };
      wrap.setPointerCapture?.(e.pointerId);
    };
    const move = (e: PointerEvent) => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      cam.try += dx * 0.006;
      cam.trx = Math.max(0.12, Math.min(1.15, cam.trx + dy * 0.004));
      drag.x = e.clientX; drag.y = e.clientY;
    };
    const up = () => { if (drag && !drag.moved && selRef.current >= 0) selectRef.current(null); drag = null; };
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      cam.tzoom = Math.max(0.42, Math.min(1.6, cam.tzoom * (e.deltaY > 0 ? 1.1 : 0.9)));
    };
    wrap.addEventListener("pointerdown", down);
    wrap.addEventListener("pointermove", move);
    wrap.addEventListener("pointerup", up);
    wrap.addEventListener("pointercancel", up);
    wrap.addEventListener("wheel", wheel, { passive: false });
    const onCtrl = (e: Event) => {
      const a = (e as CustomEvent<string>).detail;
      if (a === "in") cam.tzoom = Math.max(0.42, cam.tzoom * 0.85);
      if (a === "out") cam.tzoom = Math.min(1.6, cam.tzoom * 1.15);
      if (a === "reset") { cam.tzoom = 1; cam.trx = pitchFor(w); cam.try = 0; selectRef.current(null); }
    };
    wrap.addEventListener("vistan-camera", onCtrl);

    let local: Vec3[] = NODE_DEFS.map(() => [0, 0, 0]);
    const offsets = NODE_DEFS.map(() => 0); // retrasos acumulados para que los planetas nunca se pisen
    let visible = true;
    const io = typeof IntersectionObserver !== "undefined" ? new IntersectionObserver(([e]) => { visible = e.isIntersecting; }) : null;
    io?.observe(wrap);
    const rects: { x0: number; y0: number; x1: number; y1: number }[] = [];

    const frame = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const si = selRef.current;
      const speed = si >= 0 ? 0.12 : hoverRef.current >= 0 ? 0.25 : stateRef.current === "thinking" ? 2 : 1;
      if (!reduced) orbitTime += dt * speed;
      const k = Math.min(1, dt * 3.2);
      cam.rx += (cam.trx - cam.rx) * k;
      cam.ry += (cam.try - cam.ry) * k;
      cam.zoom += (cam.tzoom - cam.zoom) * k;
      const camZ = baseZ * cam.zoom;
      const laid = separate(NODE_DEFS, orbitTime, offsets, { pitch: cam.rx, yaw: cam.ry, camZ, w, h, target: cam.target }, w < 640 ? 16 : 10, 30);
      local = laid.local;
      const want: Vec3 = si >= 0 ? rotateView(local[si], cam.rx, cam.ry).map((v) => v * 0.82) as Vec3 : [0, 0, 0];
      cam.target = cam.target.map((v, j) => v + (want[j] - v) * k) as Vec3;
      const core = project(sub([0, 0, 0], cam.target), camZ, w, h);

      // Proyección de los planetas (de delante a atrás para resolver solapes de etiquetas)
      const proj = laid.placed.map((p, i) => ({ i, p }));
      proj.sort((a, b) => b.p.depth - a.p.depth);
      rects.length = 0;
      const bodies = proj.map(({ i, p }) => ({ i, x0: p.x - p.r - 3, y0: p.y - p.r - 3, x1: p.x + p.r + 3, y1: p.y + p.r + 3 }));
      for (const { i, p } of proj) {
        const el = nodeRefs.current[i];
        if (!el) continue;
        const size = p.r * 2;
        el.style.setProperty("--ps", `${size.toFixed(1)}px`);
        el.style.transform = `translate3d(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px, 0) translate(-50%, -50%)`;
        el.style.zIndex = String(Math.round(100 + p.depth * 10));
        const lx = 50 + Math.max(-38, Math.min(38, ((core.x - p.x) / Math.max(1, w)) * 160));
        const ly = 50 + Math.max(-38, Math.min(38, ((core.y - p.y) / Math.max(1, h)) * 160));
        el.style.setProperty("--lx", `${lx.toFixed(0)}%`);
        el.style.setProperty("--ly", `${ly.toFixed(0)}%`);
        const off = p.x < -size || p.x > w + size || p.y < -size || p.y > h + size;
        el.style.opacity = off ? "0" : String(si >= 0 && si !== i ? 0.5 : p.depth < -2 ? 0.78 : 1);
        // etiqueta: prueba derecha, izquierda, debajo y encima; si ninguna cabe sin pisar otra etiqueta, otro
        // planeta o el nombre del núcleo, se oculta (se ve al pasar el ratón o al seleccionar el planeta)
        const lw = (w < 640 ? 100 : 112), lh = 34, gap = 6;
        const cands: [string, number, number][] = [
          ["right", p.x + size / 2 + gap, p.y - lh / 2], ["left", p.x - size / 2 - gap - lw, p.y - lh / 2],
          ["below", p.x - lw / 2, p.y + size / 2 + 2], ["above", p.x - lw / 2, p.y - size / 2 - lh - 2]];
        const ctrlBox = w < 760 ? { x0: w - 52, y0: 0, x1: w, y1: 132 } : { x0: w - 52, y0: h - 132, x1: w, y1: h }; // botones de cámara
        const coreBox = { x0: core.x - (w < 640 ? 70 : 110), y0: core.y - 30, x1: core.x + (w < 640 ? 70 : 110), y1: core.y + 34 };
        let place = "right";
        let hide = true;
        let chosen = { x0: 0, y0: 0, x1: 0, y1: 0 };
        for (const [pos, x0, y0] of cands) {
          const r = { x0, y0, x1: x0 + lw, y1: y0 + lh };
          const hit = (q: { x0: number; y0: number; x1: number; y1: number }) => r.x0 < q.x1 && r.x1 > q.x0 && r.y0 < q.y1 && r.y1 > q.y0;
          if (r.x0 < 0 || r.x1 > w || r.y0 < 0 || r.y1 > h || rects.some(hit) || bodies.some((q) => q.i !== i && hit(q)) || (si < 0 && hit(coreBox)) || hit(ctrlBox)) continue;
          place = pos; hide = false; chosen = r;
          break;
        }
        if (hide && (si === i || hoverRef.current === i)) hide = false; // el seleccionado/apuntado siempre muestra su nombre
        if (!hide && chosen.x1) rects.push(chosen);
        el.dataset.label = place;
        el.classList.toggle("is-inward", place === "left");
        el.classList.toggle("label-hidden", hide);
        el.classList.toggle("is-back", p.depth < -2.5);
      }
      if (visible) sceneRef.current?.render({
        dt, time: now / 1000, rx: cam.rx, ry: cam.ry, camZ, nodePositions: local, hovered: hoverRef.current,
        selected: si, target: cam.target,
      });
      raf = requestAnimationFrame(frame);
    };

    if (webglAvailable()) {
      import("./scene")
        .then(({ createScene }) => {
          if (disposed) return;
          try {
            sceneRef.current = createScene(canvas, NODE_DEFS.map((n) => n.hue), { lite, links: LINK_IDX });
            sceneRef.current.setState(stateRef.current);
            resize();
            setMode("webgl");
          } catch {
            setMode("fallback");
          }
        })
        .catch(() => setMode("fallback"));
    } else {
      setMode("fallback");
    }
    raf = requestAnimationFrame(frame);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      ro?.disconnect();
      io?.disconnect();
      wrap.removeEventListener("pointerdown", down);
      wrap.removeEventListener("pointermove", move);
      wrap.removeEventListener("pointerup", up);
      wrap.removeEventListener("pointercancel", up);
      wrap.removeEventListener("wheel", wheel);
      wrap.removeEventListener("vistan-camera", onCtrl);
      sceneRef.current?.dispose();
      sceneRef.current = null;
    };
  }, []);

  const camCmd = (a: string) => wrapRef.current?.dispatchEvent(new CustomEvent("vistan-camera", { detail: a }));
  const sd = sel ? NODE_DEFS[IDX.get(sel)!] : null;
  const si = sel ? info[sel] : null;

  return (
    <div ref={wrapRef} className={`core core-${state} core-${mode} ${sel ? "has-selection" : ""}`}>
      <canvas ref={canvasRef} className="core-canvas" aria-hidden="true" />
      {mode !== "webgl" && <div className="core-fallback" aria-hidden="true"><span /><span /><span /></div>}

      <div className="core-id" aria-live="polite">
        <span className="core-name">VISTAN</span>
        <span className="core-sub">CORE</span>
        <span className="core-state"><i className="core-dot" />{STATE_LABEL[state]}</span>
      </div>

      <nav className="core-nodes" aria-label="Módulos de VISTAN">
        {NODE_DEFS.map((n, i) => {
          const inf = info[n.id];
          const isSel = sel === n.id;
          return (
            <button
              key={n.id}
              ref={(el) => { nodeRefs.current[i] = el; }}
              type="button"
              className={`planet node ${isSel ? "is-selected" : ""} ${inf?.alert ? "has-alert" : ""} ${inf?.active ? "is-active" : ""}`}
              style={{ ["--hue" as string]: n.hue }}
              onClick={() => (isSel ? onOpen(n.route) : select(n.id))}
              onDoubleClick={() => onOpen(n.route)}
              onPointerEnter={() => { hoverRef.current = i; }}
              onPointerLeave={() => { hoverRef.current = -1; }}
              onFocus={() => { hoverRef.current = i; }}
              onBlur={() => { hoverRef.current = -1; }}
              aria-pressed={isSel}
              aria-label={`${n.label}: ${inf?.metric ?? ""}. ${isSel ? "Pulsa para abrir" : "Pulsa para ver detalles"}`}
            >
              <span className="planet-body"><Icon name={n.icon} size={18} /></span>
              <span className="node-text planet-label">
                <span className="node-label">{n.label}</span>
                <span className="node-metric"><i className={`node-dot ${inf?.alert ? "alert" : inf?.active ? "active" : "ok"}`} />{inf?.metric ?? "—"}</span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="core-ctrl" role="group" aria-label="Cámara">
        <button type="button" onClick={() => camCmd("in")} aria-label="Acercar">+</button>
        <button type="button" onClick={() => camCmd("out")} aria-label="Alejar">−</button>
        <button type="button" onClick={() => camCmd("reset")} aria-label="Vista general" title="Vista general">⌖</button>
      </div>

      {sd && (
        <aside className="core-card" aria-label={`Módulo ${sd.label}`}>
          <header><span className="planet-mini"><Icon name={sd.icon} size={16} /></span><strong>{sd.label}</strong>
            {si?.active && <span className="badge live">activo</span>}</header>
          <p className="small muted">{sd.description}</p>
          <p className="core-card-metric">{si?.metric ?? "—"}</p>
          {si?.details && si.details.length > 0 && <ul>{si.details.map((d, i) => <li key={i}>{d}</li>)}</ul>}
          <div className="form-actions">
            <button type="button" className="btn" onClick={() => onOpen(sd.route)}>Abrir {sd.label}</button>
            <button type="button" className="mini-btn ghost" onClick={() => select(null)}>Volver al centro</button>
          </div>
        </aside>
      )}
    </div>
  );
}
