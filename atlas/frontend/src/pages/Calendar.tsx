import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { Empty, Panel } from "../components/Panel";
import { formatDayLabel } from "../lib/tasks";

const hm = (iso: string) => iso.slice(11, 16);

function offsetIso(local: string): string {
  const d = new Date(local);
  const m = -d.getTimezoneOffset();
  return `${local}:00${m >= 0 ? "+" : "-"}${String(Math.floor(Math.abs(m) / 60)).padStart(2, "0")}:${String(Math.abs(m) % 60).padStart(2, "0")}`;
}

export function Calendar() {
  const cal = useAsync(api.calendar);
  const [f, setF] = useState({ title: "", date: "", start: "", end: "", location: "", icloud: false });
  const [msg, setMsg] = useState<{ tone: "pos" | "neg"; text: string } | null>(null);
  const items = cal.data?.items ?? [];
  const conflictIds = new Set((cal.data?.conflicts ?? []).flat());
  const days = [...new Set(items.map((e) => e.start_at.slice(0, 10)))];

  async function add(e: FormEvent) {
    e.preventDefault();
    if (f.icloud && !window.confirm(`¿Crear «${f.title}» en tu calendario de iCloud?`)) return;
    try {
      await api.createEvent({ title: f.title, start_at: offsetIso(`${f.date}T${f.start}`), end_at: offsetIso(`${f.date}T${f.end}`),
        location: f.location || null, to_icloud: f.icloud });
      setMsg({ tone: "pos", text: `Evento creado${f.icloud ? " en iCloud" : ""}.` });
      setF({ ...f, title: "", location: "" });
      await cal.reload();
    } catch (err) { setMsg({ tone: "neg", text: (err as Error).message }); }
  }

  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Fase 8 · activo</p>
        <h1><Icon name="calendar" size={26} /> Calendario</h1>
        <p className="lead">Tus eventos de iCloud y los que crees en ATLAS, con avisos de choques de horario.</p>
      </header>
      {cal.data && !cal.data.connected && <p className="callout">Conecta tu calendario de iCloud en <Link to="/settings#integraciones">Configuración › Integraciones</Link>.</p>}
      <div className="grid grid-tasks">
        <Panel title="Nuevo evento">
          <form className="form" onSubmit={add}>
            <label><span>Título</span><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} maxLength={300} /></label>
            <div className="form-row">
              <label><span>Día</span><input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></label>
              <label><span>Inicio</span><input type="time" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} /></label>
              <label><span>Fin</span><input type="time" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} /></label>
            </div>
            <label><span>Lugar (opcional)</span><input value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} maxLength={300} /></label>
            {cal.data?.connected && <label className="check"><input type="checkbox" checked={f.icloud} onChange={(e) => setF({ ...f, icloud: e.target.checked })} /> Crear también en iCloud</label>}
            <div className="form-actions">
              <button className="btn" type="submit" disabled={!f.title.trim() || !f.date || !f.start || !f.end}>Crear evento</button>
              {msg && <span role="status" className={`small ${msg.tone}`}>{msg.text}</span>}
            </div>
          </form>
        </Panel>
        <Panel title="Próximos 30 días">
          {!cal.data ? <p className="muted">Cargando…</p> : !items.length ? <Empty>No hay eventos próximos.</Empty> : days.map((d) => (
            <section key={d} className="task-group">
              <h3>{formatDayLabel(d)}</h3>
              <ul className="task-items">
                {items.filter((e) => e.start_at.startsWith(d)).map((e) => (
                  <li key={e.id} className={`task ${conflictIds.has(e.id) ? "is-overdue" : ""}`}>
                    <span className="task-main"><span className="task-title">{e.title}</span>
                      <span className="mem-meta">{hm(e.start_at)}{e.end_at ? `–${hm(e.end_at)}` : ""}{e.location ? ` · ${e.location}` : ""} · {e.source === "icloud" ? "iCloud" : "ATLAS"}{conflictIds.has(e.id) ? " · ⚠ se solapa con otro evento" : ""}</span></span>
                    {e.source === "local" && <button className="mini-btn danger" aria-label={`Borrar ${e.title}`} onClick={async () => { await api.deleteEvent(e.id); await cal.reload(); }}>Borrar</button>}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </Panel>
      </div>
    </div>
  );
}
