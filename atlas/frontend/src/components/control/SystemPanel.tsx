import { Link } from "react-router-dom";
import type { Health } from "../../api/types";
import { formatBytes } from "../../lib/bytes";
import type { Voice } from "../../hooks/useVoice";

function Row({ k, v, tone }: { k: string; v: string; tone?: "ok" | "warn" | "off" | "dim" }) {
  return <div className="hud-row"><dt>{k}</dt><dd className={tone ? `t-${tone}` : ""}>{v}</dd></div>;
}

/** Lateral izquierdo: estado real del sistema. */
export function SystemPanel({ health, offline, voice, speakReplies }: {
  health: Health | null; offline: boolean; voice: Voice; speakReplies: boolean;
}) {
  const st = health?.storage;
  const usedPct = st ? 100 * (1 - st.disk_free_bytes / st.disk_total_bytes) : 0;
  return (
    <aside className="hud hud-left" aria-label="Estado del sistema">
      <section>
        <h3>Sistema</h3>
        <dl>
          <Row k="Núcleo" v={offline ? "Sin conexión" : health?.status === "online" ? "Operativo" : "Degradado"} tone={offline ? "off" : health?.status === "online" ? "ok" : "warn"} />
          <Row k="Versión" v={health ? `v${health.version}` : "—"} />
          <Row k="Base de datos" v={health ? `${health.database.engine} · ${health.database.ok ? "OK" : "error"}` : "—"} />
        </dl>
      </section>
      <section>
        <h3>Cerebro IA</h3>
        <dl>
          <Row k="Modo" v={health?.ai.configured ? "IA local (Ollama)" : "Local (sin modelo)"} tone={health?.ai.configured ? "ok" : "dim"} />
          <Row k="Modelo activo" v={health?.ai.model ?? "Ninguno"} tone={health?.ai.model ? "ok" : "dim"} />
          <Row k="Modelos instalados" v={health ? String(health.ai.models_installed) : "—"} />
        </dl>
        {health && !health.ai.configured && <p className="hud-note">{health.ai.note} <Link to="/ai">Configurar</Link></p>}
      </section>
      <section>
        <h3>Memoria</h3>
        <dl>
          <Row k="Recuerdos" v={st ? String(st.memories) : "—"} />
          <Row k="Conversaciones" v={st ? String(st.conversations) : "—"} />
          <Row k="Registros" v={st ? st.records.toLocaleString("es-ES") : "—"} />
          <Row k="Tamaño" v={st ? formatBytes(st.db_bytes) : "—"} />
          <Row k="Disco libre" v={st ? formatBytes(st.disk_free_bytes) : "—"} />
        </dl>
        {st && (
          <div className="meter" role="meter" aria-label="Uso del disco" aria-valuenow={Math.round(usedPct)} aria-valuemin={0} aria-valuemax={100}>
            <span style={{ width: `${usedPct}%` }} />
          </div>
        )}
      </section>
      <section>
        <h3>Agentes</h3>
        <dl>
          <Row k="Activos" v="0" tone="dim" />
        </dl>
        <p className="hud-note">Los agentes autónomos llegan en la Fase 10.</p>
      </section>
      <section>
        <h3>Voz</h3>
        <dl>
          <Row k="Micrófono" v={voice.listening ? "Escuchando" : voice.canListen ? "Disponible" : "No disponible"} tone={voice.listening ? "ok" : voice.canListen ? undefined : "dim"} />
          <Row k="Síntesis" v={voice.canSpeak ? "Disponible" : "No disponible"} tone={voice.canSpeak ? undefined : "dim"} />
          <Row k="Respuesta hablada" v={speakReplies ? "Activada" : "Desactivada"} tone={speakReplies ? "ok" : "dim"} />
        </dl>
        {voice.canSpeak && <p className="hud-note"><Link to="/settings">Cambiar voz y velocidad</Link></p>}
        {!voice.canListen && <p className="hud-note">Usa Chrome o Edge para hablar con ATLAS.</p>}
        {voice.error && <p className="hud-note t-warn">{voice.error}</p>}
      </section>
    </aside>
  );
}
