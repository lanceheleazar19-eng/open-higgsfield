import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { MemoryAccess, MemoryItem, MemoryKind, StoredMessage } from "../api/types";
import { useAsync } from "../api/useAsync";
import { useAtlas } from "../components/AtlasContext";
import { Icon } from "../components/Icon";
import { Empty, Panel } from "../components/Panel";
import { formatDateTime } from "../lib/format";
import { ACCESS_LABEL, KIND_LABEL } from "../lib/memory";

const KINDS = Object.keys(KIND_LABEL) as MemoryKind[];

/** Convierte "YYYY-MM-DD" (fin del día local) a ISO con zona horaria. */
function endOfDayIso(day: string): string {
  const d = new Date(`${day}T23:59:00`);
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  const hh = String(Math.floor(Math.abs(off) / 60)).padStart(2, "0");
  const mm = String(Math.abs(off) % 60).padStart(2, "0");
  return `${day}T23:59:00${sign}${hh}:${mm}`;
}

export function Memory() {
  const [tab, setTab] = useState<"memories" | "conversations">("memories");
  return (
    <div className="page">
      <header className="page-head">
        <p className="eyebrow">Fase 3 · activo</p>
        <h1><Icon name="memory" size={26} /> Memoria</h1>
        <p className="lead">Lo que VISTAN sabe de ti. Está guardado solo en tu ordenador: puedes consultarlo, corregirlo o borrarlo cuando quieras.</p>
      </header>
      <div className="tabs" role="tablist" aria-label="Secciones de memoria">
        <button role="tab" aria-selected={tab === "memories"} className={tab === "memories" ? "on" : ""} onClick={() => setTab("memories")}>Recuerdos</button>
        <button role="tab" aria-selected={tab === "conversations"} className={tab === "conversations" ? "on" : ""} onClick={() => setTab("conversations")}>Conversaciones</button>
      </div>
      {tab === "memories" ? <Memories /> : <Conversations />}
    </div>
  );
}

function Memories() {
  const { reloadHealth, prefs } = useAtlas();
  const tz = prefs?.timezone;
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [showExpired, setShowExpired] = useState(false);
  const list = useAsync(() => api.memories({ q, kind: kind || undefined, include_expired: showExpired }));
  const [editing, setEditing] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ tone: "pos" | "neg"; text: string } | null>(null);

  // Rebusca al cambiar filtros (con pequeña espera al escribir)
  useEffect(() => {
    const t = setTimeout(() => void list.reload(), q ? 250 : 0);
    return () => clearTimeout(t);
  }, [q, kind, showExpired]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = async (text: string, tone: "pos" | "neg" = "pos") => {
    setMsg({ tone, text });
    await list.reload();
    void reloadHealth();
  };

  async function remove(m: MemoryItem) {
    if (!window.confirm(`¿Olvidar este recuerdo?\n\n«${m.content}»`)) return;
    try {
      await api.deleteMemory(m.id);
      await refresh("Recuerdo eliminado.");
    } catch (e) {
      setMsg({ tone: "neg", text: (e as Error).message });
    }
  }

  async function purge() {
    try {
      const { deleted } = await api.purgeExpired();
      await refresh(deleted ? `${deleted} recuerdos caducados eliminados.` : "No había recuerdos caducados.");
    } catch (e) {
      setMsg({ tone: "neg", text: (e as Error).message });
    }
  }

  const items = list.data?.items ?? [];
  return (
    <div className="grid grid-mem">
      <Panel title="Añadir recuerdo">
        <AddMemory onSaved={(created, content) => void refresh(created ? "Guardado." : `Ya estaba guardado: «${content}»`)} />
        <p className="muted small">También puedes decírselo a VISTAN: «recuerda que…» o «olvida que…».</p>
      </Panel>
      <Panel title={`Recuerdos${list.data ? ` (${list.data.memories})` : ""}`} className="mem-list" aside={
        <span className="row-actions">
          <button className="mini-btn ghost" onClick={() => void purge()}>Limpiar caducados</button>
          <a className="mini-btn ghost" href={api.exportUrl} download>Exportar</a>
        </span>
      }>
        <div className="filters">
          <input type="search" placeholder="Buscar en la memoria…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar en la memoria" />
          <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Filtrar por tipo">
            <option value="">Todos los tipos</option>
            {KINDS.map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
          </select>
          <label className="check"><input type="checkbox" checked={showExpired} onChange={(e) => setShowExpired(e.target.checked)} /> Ver caducados</label>
        </div>
        {msg && <p role="status" className={`small ${msg.tone}`}>{msg.text}</p>}
        {list.error && <p className="neg small">{list.error.message}</p>}
        {items.length === 0 ? (
          <Empty>{q ? "No hay recuerdos que coincidan." : "VISTAN todavía no recuerda nada. Añade algo o díselo en el centro de control."}</Empty>
        ) : (
          <ul className="mem-items">
            {items.map((m) => editing === m.id ? (
              <li key={m.id}><EditMemory m={m} onDone={(text) => { setEditing(null); if (text) void refresh(text); }} /></li>
            ) : (
              <li key={m.id} className={m.expired ? "is-expired" : ""}>
                <span className={`kind kind-${m.kind}`}>{KIND_LABEL[m.kind]}</span>
                <span className="mem-content">
                  {m.content}
                  <span className="mem-meta">
                    {m.permanent ? "Permanente" : m.expired ? "Caducado" : `Temporal · hasta ${formatDateTime(m.expires_at!, tz)}`}
                    {" · "}{m.source === "manual" ? "añadido a mano" : m.source === "chat" ? "por conversación" : "sugerido por VISTAN"}
                    {" · "}{formatDateTime(m.updated_at, tz)}
                    {m.access && m.access !== "all" && <>{" · "}<b>{ACCESS_LABEL[m.access]}</b></>}
                    {m.superseded_by && <>{" · "}histórico (reemplazado por #{m.superseded_by})</>}
                  </span>
                </span>
                <span className="row-actions">
                  <button className="mini-btn ghost" onClick={() => setEditing(m.id)} aria-label={`Editar: ${m.content}`}>Editar</button>
                  <button className="mini-btn danger" onClick={() => void remove(m)} aria-label={`Olvidar: ${m.content}`}>Olvidar</button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function AddMemory({ onSaved }: { onSaved: (created: boolean, content: string) => void }) {
  const [content, setContent] = useState("");
  const [kind, setKind] = useState<MemoryKind>("fact");
  const [temporary, setTemporary] = useState(false);
  const [until, setUntil] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!content.trim() || (temporary && !until)) return;
    setSaving(true);
    setError(null);
    try {
      const r = await api.createMemory({ content: content.trim(), kind, expires_at: temporary ? endOfDayIso(until) : null });
      onSaved(r.created, r.memory.content);
      setContent("");
      setTemporary(false);
      setUntil("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      <label>
        <span>¿Qué debe recordar VISTAN?</span>
        <textarea rows={3} maxLength={2000} value={content} onChange={(e) => setContent(e.target.value)}
          placeholder="Ej.: Mi objetivo es ahorrar 5.000 € este año" />
      </label>
      <label>
        <span>Tipo</span>
        <select value={kind} onChange={(e) => setKind(e.target.value as MemoryKind)}>
          {KINDS.map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
        </select>
      </label>
      <label className="check"><input type="checkbox" checked={temporary} onChange={(e) => setTemporary(e.target.checked)} /> Es temporal</label>
      {temporary && (
        <label>
          <span>Válido hasta</span>
          <input type="date" value={until} onChange={(e) => setUntil(e.target.value)} required />
        </label>
      )}
      <div className="form-actions">
        <button className="btn" type="submit" disabled={saving || !content.trim() || (temporary && !until)}>{saving ? "Guardando…" : "Guardar recuerdo"}</button>
        {error && <span className="neg">{error}</span>}
      </div>
    </form>
  );
}

function EditMemory({ m, onDone }: { m: MemoryItem; onDone: (msg: string | null) => void }) {
  const [content, setContent] = useState(m.content);
  const [kind, setKind] = useState<MemoryKind>(m.kind);
  const [access, setAccess] = useState<MemoryAccess>(m.access ?? "all");
  const [error, setError] = useState<string | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api.updateMemory(m.id, {
        ...(content.trim() !== m.content ? { content: content.trim() } : {}),
        ...(kind !== m.kind ? { kind } : {}),
        ...(access !== (m.access ?? "all") ? { access } : {}),
      });
      onDone("Recuerdo actualizado.");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="form mem-edit" onSubmit={save}>
      <textarea rows={2} value={content} onChange={(e) => setContent(e.target.value)} aria-label="Contenido del recuerdo" maxLength={2000} />
      <div className="form-actions">
        <select value={kind} onChange={(e) => setKind(e.target.value as MemoryKind)} aria-label="Tipo">
          {KINDS.map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
        </select>
        <select value={access} onChange={(e) => setAccess(e.target.value as MemoryAccess)} aria-label="Acceso">
          {(Object.keys(ACCESS_LABEL) as MemoryAccess[]).map((k) => <option key={k} value={k}>{ACCESS_LABEL[k]}</option>)}
        </select>
        {!m.permanent && (
          <button type="button" className="mini-btn ghost" onClick={async () => {
            try { await api.updateMemory(m.id, { permanent: true }); onDone("Ahora es permanente."); } catch (err) { setError((err as Error).message); }
          }}>Hacer permanente</button>
        )}
        <button className="mini-btn" type="submit" disabled={!content.trim()}>Guardar</button>
        <button type="button" className="mini-btn ghost" onClick={() => onDone(null)}>Cancelar</button>
        {error && <span className="neg small">{error}</span>}
      </div>
    </form>
  );
}

function Conversations() {
  const tz = useAtlas().prefs?.timezone;
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const list = useAsync(api.conversations);
  const [hits, setHits] = useState<StoredMessage[] | null>(null);
  const detail = useAsync(() => (open ? api.conversation(open) : Promise.resolve(null)));

  useEffect(() => { void detail.reload(); }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!q.trim()) { setHits(null); return; }
    const t = setTimeout(() => { api.searchConversations(q).then((r) => setHits(r.hits)).catch(() => setHits([])); }, 250);
    return () => clearTimeout(t);
  }, [q]);

  async function remove(id: number, title: string) {
    if (!window.confirm(`¿Borrar la conversación «${title}»? No se puede deshacer.`)) return;
    await api.deleteConversation(id);
    if (open === id) setOpen(null);
    await list.reload();
  }

  return (
    <div className="grid grid-mem">
      <Panel title="Historial" className="conv-list">
        <input type="search" className="full" placeholder="Buscar en todas las conversaciones…" value={q}
          onChange={(e) => setQ(e.target.value)} aria-label="Buscar en conversaciones" />
        {hits ? (
          hits.length === 0 ? <Empty>Sin resultados.</Empty> : (
            <ul className="conv-items">
              {hits.map((h) => (
                <li key={h.id}>
                  <button className="conv-btn" onClick={() => setOpen(h.conversation_id)}>
                    <span className="mem-meta">{formatDateTime(h.created_at, tz)} · {h.role === "user" ? "Tú" : "VISTAN"}</span>
                    <span className="conv-snippet">{h.content}</span>
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : !list.data || list.data.items.length === 0 ? (
          <Empty>Aún no hay conversaciones guardadas.</Empty>
        ) : (
          <ul className="conv-items">
            {list.data.items.map((c) => (
              <li key={c.id} className={open === c.id ? "on" : ""}>
                <button className="conv-btn" onClick={() => setOpen(c.id)}>
                  <span className="conv-title">{c.title}</span>
                  <span className="mem-meta">{formatDateTime(c.updated_at, tz)} · {c.messages} mensajes</span>
                </button>
                <button className="mini-btn danger" onClick={() => void remove(c.id, c.title)} aria-label={`Borrar conversación: ${c.title}`}>Borrar</button>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel title={detail.data ? detail.data.title : "Conversación"} className="conv-detail">
        {!open ? <Empty>Elige una conversación para leerla.</Empty> : !detail.data ? <p className="muted">Cargando…</p> : (
          <ol className="conv-messages">
            {detail.data.messages.map((m) => (
              <li key={m.id} className={m.role}>
                <span className="mem-meta">{m.role === "user" ? "Tú" : `VISTAN${m.model ? ` · ${m.model}` : ""}`} · {formatDateTime(m.created_at, tz)}</span>
                <p>{m.content}</p>
              </li>
            ))}
          </ol>
        )}
      </Panel>
    </div>
  );
}
