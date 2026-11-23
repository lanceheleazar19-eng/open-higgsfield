import { useEffect, useRef, useState } from "react";
import { Icon } from "../Icon";
import { NODE_DEFS } from "./nodes";
import { ORBITS, cameraDistance, orbitPoint, project, rotateView, type Vec3 } from "./orbits";
import type { AtlasScene, CoreState } from "./scene";

export interface NodeInfo {
  metric: string; // dato real (o fase si el módulo aún no existe)
  planned: boolean;
  alert?: boolean;
}

const STATE_LABEL: Record<CoreState, string> = {
  idle: "En espera",
  listening: "Escuchando",
  thinking: "Procesando",
  responding: "Respondiendo",
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

/** Núcleo holográfico de ATLAS con los módulos orbitando. Los nodos son botones HTML
 *  posicionados con la misma proyección que la escena WebGL. */
export function AtlasCore({ info, state, rippleKey, onOpen }: {
  info: Record<string, NodeInfo>;
  state: CoreState;
  rippleKey: number;
  onOpen: (route: string) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodeRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const sceneRef = useRef<AtlasScene | null>(null);
  const hoverRef = useRef(-1);
  const stateRef = useRef(state);
  const [mode, setMode] = useState<"webgl" | "fallback" | "pending">("pending");

  stateRef.current = state;
  useEffect(() => { sceneRef.current?.setState(state); }, [state]);
  useEffect(() => { if (rippleKey) sceneRef.current?.ripple(); }, [rippleKey]);

  useEffect(() => {
    const wrap = wrapRef.current!;
    const canvas = canvasRef.current!;
    let disposed = false;
    let raf = 0;
    const reduced = prefersReducedMotion();
    const lite = window.innerWidth < 760;

    let w = 1, h = 1, camZ = 9;
    const view = { rx: 0.12, ry: 0, trx: 0.12, try: 0 };
    let orbitTime = 0;
    let last = performance.now();

    const resize = () => {
      const r = wrap.getBoundingClientRect();
      w = Math.max(1, r.width);
      h = Math.max(1, r.height);
      camZ = cameraDistance(w / h, w < 640);
      sceneRef.current?.resize(w, h, camZ);
    };
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    ro?.observe(wrap);
    resize();

    const onPointer = (e: PointerEvent) => {
      const r = wrap.getBoundingClientRect();
      view.try = ((e.clientX - r.left) / r.width - 0.5) * 0.35;
      view.trx = 0.12 + ((e.clientY - r.top) / r.height - 0.5) * 0.2;
    };
    wrap.addEventListener("pointermove", onPointer);

    const positions: Vec3[] = NODE_DEFS.map(() => [0, 0, 0]);

    // No dibujar WebGL cuando el núcleo no está en pantalla
    let visible = true;
    const io = typeof IntersectionObserver !== "undefined"
      ? new IntersectionObserver(([e]) => { visible = e.isIntersecting; })
      : null;
    io?.observe(wrap);

    const frame = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (!reduced && hoverRef.current < 0) orbitTime += dt * (stateRef.current === "thinking" ? 2.2 : 1);
      view.rx += (view.trx - view.rx) * Math.min(1, dt * 3);
      view.ry += (view.try - view.ry) * Math.min(1, dt * 3);

      NODE_DEFS.forEach((n, i) => {
        const o = ORBITS[n.orbit];
        const local = orbitPoint(o, n.phase + orbitTime * o.speed);
        positions[i] = local;
        const p = project(rotateView(local, view.rx, view.ry), camZ, w, h);
        const el = nodeRefs.current[i];
        if (el) {
          const s = 0.78 + 0.32 * Math.min(1.3, p.scale);
          el.style.transform = `translate3d(${p.x}px, ${p.y}px, 0) translate(-50%, -50%) scale(${s.toFixed(3)})`;
          el.style.zIndex = String(p.depth > 0 ? 3 : 1);
          el.style.opacity = String(p.depth > 0 ? 1 : 0.62 + 0.38 * (1 + p.depth / 4));
          const inward = w < 640 ? p.x > w / 2 : p.x > w * 0.72;
          if (el.classList.contains("is-inward") !== inward) el.classList.toggle("is-inward", inward);
          const back = p.depth < -0.6;
          if (el.classList.contains("is-back") !== back) el.classList.toggle("is-back", back);
        }
      });

      if (visible) sceneRef.current?.render({
        dt, time: now / 1000, rx: view.rx, ry: view.ry, camZ, nodePositions: positions, hovered: hoverRef.current,
      });
      raf = requestAnimationFrame(frame);
    };

    if (webglAvailable()) {
      import("./scene")
        .then(({ createScene }) => {
          if (disposed) return;
          try {
            sceneRef.current = createScene(canvas, NODE_DEFS.map((n) => n.color), { lite });
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
      wrap.removeEventListener("pointermove", onPointer);
      sceneRef.current?.dispose();
      sceneRef.current = null;
    };
  }, []);

  return (
    <div ref={wrapRef} className={`core core-${state} core-${mode}`}>
      <canvas ref={canvasRef} className="core-canvas" aria-hidden="true" />
      {mode !== "webgl" && <div className="core-fallback" aria-hidden="true"><span /><span /><span /></div>}

      <div className="core-id" aria-live="polite">
        <span className="core-name">ATLAS</span>
        <span className="core-state"><i className="core-dot" />{STATE_LABEL[state]}</span>
      </div>

      <nav className="core-nodes" aria-label="Módulos de ATLAS">
        {NODE_DEFS.map((n, i) => {
          const inf = info[n.id];
          return (
            <button
              key={n.id}
              ref={(el) => { nodeRefs.current[i] = el; }}
              type="button"
              className={`node ${inf?.planned ? "is-planned" : ""} ${inf?.alert ? "has-alert" : ""}`}
              style={{ ["--node" as string]: n.color }}
              onClick={() => onOpen(n.route)}
              onPointerEnter={() => { hoverRef.current = i; }}
              onPointerLeave={() => { hoverRef.current = -1; }}
              onFocus={() => { hoverRef.current = i; }}
              onBlur={() => { hoverRef.current = -1; }}
              aria-label={`Abrir ${n.label}: ${inf?.metric ?? ""}`}
            >
              <span className="node-orb"><Icon name={n.icon} size={19} /></span>
              <span className="node-text">
                <span className="node-label">{n.label}</span>
                <span className="node-metric"><i className={`node-dot ${inf?.alert ? "alert" : inf?.planned ? "planned" : "ok"}`} />{inf?.metric ?? "—"}</span>
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
