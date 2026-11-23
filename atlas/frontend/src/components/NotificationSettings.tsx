import { useState } from "react";
import { Panel } from "./Panel";

/** Permiso para que los recordatorios aparezcan como notificaciones del sistema. */
export function NotificationSettings() {
  const supported = typeof Notification !== "undefined";
  const [perm, setPerm] = useState<NotificationPermission | "unsupported">(supported ? Notification.permission : "unsupported");

  async function ask() {
    const r = await Notification.requestPermission();
    setPerm(r);
    if (r === "granted") new Notification("ATLAS", { body: "Notificaciones activadas. Así te avisaré de tus recordatorios." });
  }

  return (
    <Panel title="Notificaciones">
      <p className="muted small">Los recordatorios siempre aparecen dentro de ATLAS. Con este permiso también saldrán como notificación del sistema aunque estés en otra pestaña (ATLAS debe estar abierto).</p>
      {perm === "unsupported" && <p className="muted">Este navegador no admite notificaciones.</p>}
      {perm === "granted" && <p className="pos">Activadas ✓</p>}
      {perm === "denied" && <p className="callout">Bloqueadas por el navegador. Actívalas en el candado de la barra de direcciones → Notificaciones → Permitir.</p>}
      {perm === "default" && <button className="btn" onClick={() => void ask()}>Activar notificaciones</button>}
    </Panel>
  );
}
