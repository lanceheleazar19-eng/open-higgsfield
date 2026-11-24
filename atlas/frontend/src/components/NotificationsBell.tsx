import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { v4 } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { relativeTime } from "../lib/format";
import { Icon } from "./Icon";

/** Notificaciones reales de ATLAS (workflows, investigaciones, aprobaciones). Si diste permiso, también
 *  aparecen como notificación del sistema. */
export function NotificationsBell() {
  const n = useAsync(v4.notifications, 30000);
  const [open, setOpen] = useState(false);
  const seen = useRef<number>(0);
  const unread = n.data?.unread ?? 0;
  useEffect(() => {
    const top = n.data?.items[0];
    if (!top) return;
    if (seen.current && top.id > seen.current && !top.read && typeof Notification !== "undefined" && Notification.permission === "granted") {
      try { new Notification(top.title, { body: top.body.slice(0, 180) }); } catch { /* sin notificaciones */ }
    }
    seen.current = Math.max(seen.current, top.id);
  }, [n.data]);
  return (
    <div className="bell">
      <button type="button" className="icon-btn" aria-label={`Notificaciones${unread ? ` (${unread} sin leer)` : ""}`} aria-expanded={open}
        onClick={async () => { setOpen(!open); if (!open && unread) { await v4.readNotifications(); void n.reload(); } }}>
        <Icon name="bell" />{unread > 0 && <span className="bell-n">{unread > 9 ? "9+" : unread}</span>}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label="Notificaciones">
          {!n.data?.items.length ? <p className="muted small">Sin notificaciones.</p> : (
            <ul>{n.data.items.slice(0, 12).map((x) => (
              <li key={x.id} className={x.read ? "" : "unread"}>
                {x.link ? <Link to={x.link} onClick={() => setOpen(false)}><strong>{x.title}</strong></Link> : <strong>{x.title}</strong>}
                {x.body && <p className="small">{x.body.slice(0, 220)}{x.body.length > 220 ? "…" : ""}</p>}
                <span className="muted small">{relativeTime(x.created_at)}</span>
              </li>
            ))}</ul>
          )}
        </div>
      )}
    </div>
  );
}
