import { api } from "../api/client";
import { useReminders } from "../hooks/useReminders";

/** Avisos de recordatorios en pantalla, con acciones reales. */
export function Reminders() {
  const { items, dismiss } = useReminders();
  if (!items.length) return null;
  return (
    <div className="toasts" role="region" aria-label="Recordatorios" aria-live="assertive">
      {items.map((t) => (
        <div key={t.id} className="toast">
          <span className="toast-title">🔔 Recordatorio</span>
          <span>{t.title}</span>
          <span className="row-actions">
            <button className="mini-btn" onClick={async () => { await api.completeTask(t.id); dismiss(t.id); }}>Hecha</button>
            <button className="mini-btn ghost" onClick={() => dismiss(t.id)}>Cerrar</button>
          </span>
        </div>
      ))}
    </div>
  );
}
