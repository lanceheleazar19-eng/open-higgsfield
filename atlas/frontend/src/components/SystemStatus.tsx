import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAtlas } from "./AtlasContext";

/** «Estado del sistema» con CPU y RAM reales del ordenador (sondeo cada 5 s). */
export function SystemStatus() {
  const { health, healthError } = useAtlas();
  const [cpu, setCpu] = useState<number[]>([]);
  const [ram, setRam] = useState<number | null>(null);
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const m = await api.metrics();
        if (!alive) return;
        setCpu((l) => [...l, m.cpu_percent].slice(-30));
        setRam(m.ram_percent);
      } catch { /* núcleo sin conexión */ }
    };
    void tick();
    const id = setInterval(() => void tick(), 5000);
    return () => { alive = false; clearInterval(id); };
  }, []);
  const online = health?.status === "online" && !healthError;
  const W = 200, H = 40;
  const pts = cpu.map((v, i) => `${cpu.length === 1 ? W : (i * W) / (cpu.length - 1)},${H - (v / 100) * (H - 4) - 2}`).join(" ");
  const last = cpu[cpu.length - 1];
  return (
    <section className="sys-status" aria-label="Estado del sistema">
      <h3>Estado del sistema</h3>
      <svg className="sys-spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={`Uso de CPU reciente${last !== undefined ? `: ${Math.round(last)} %` : ""}`}>
        {cpu.length > 1 && <>
          <polygon points={`0,${H} ${pts} ${W},${H}`} className="sys-area" />
          <polyline points={pts} className="sys-line" />
        </>}
      </svg>
      <dl>
        <div><dt>CPU</dt><dd>{last !== undefined ? `${Math.round(last)}%` : "—"}</dd></div>
        <div><dt>RAM</dt><dd>{ram !== null ? `${Math.round(ram)}%` : "—"}</dd></div>
        <div><dt>Modelo IA</dt><dd>{health ? (health.ai.configured ? `Ollama (${health.ai.model})` : "Modo local") : "—"}</dd></div>
        <div><dt>Conexión</dt><dd className={online ? "t-ok" : "t-off"}>{online ? "Online" : "Offline"} <i className={`dot ${online ? "dot-on" : "dot-off"}`} /></dd></div>
      </dl>
    </section>
  );
}
