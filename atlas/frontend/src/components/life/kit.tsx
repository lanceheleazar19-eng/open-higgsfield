/** Piezas reutilizables de LIFE OS: formularios por esquema, lista con estados de carga/error/vacío y chat de agente. */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { life, LockedError, type Client, type Row } from "../../api/life";

export type Field = {
  k: string; label: string; type?: "text" | "textarea" | "number" | "date" | "select" | "checkbox" | "tags" | "time" | "lines";
  options?: [string, string][]; required?: boolean; placeholder?: string; wide?: boolean; min?: number; max?: number; step?: number;
};

export function useLoad<T>(path: string | null, deps: unknown[] = [], api: Client = life): { data: T | null; error: string | null; loading: boolean; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    if (!path) return;
    setLoading(true);
    api.get<T>(path).then((d) => { setData(d); setError(null); }).catch((e: Error) => { if (!(e instanceof LockedError)) setError(e.message); }).finally(() => setLoading(false));
  }, [path]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(reload, [reload, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, loading, reload };
}

export function State({ loading, error, empty, children }: { loading: boolean; error: string | null; empty?: string | false; children?: ReactNode }) {
  if (loading) return <p className="desk-empty" role="status">Cargando…</p>;
  if (error) return <p className="error-line" role="alert">{error}</p>;
  if (empty) return <p className="desk-empty">{empty}</p>;
  return <>{children}</>;
}

function toForm(fields: Field[], v: Row): Row {
  const o: Row = {};
  for (const f of fields) {
    const x = v[f.k];
    o[f.k] = f.type === "checkbox" ? !!x : f.type === "tags" ? (x ?? []).join(", ") : f.type === "lines" ? (x ?? []).join("\n") : x ?? "";
  }
  return o;
}

function fromForm(fields: Field[], v: Row): Row {
  const o: Row = {};
  for (const f of fields) {
    const x = v[f.k];
    if (f.type === "checkbox") o[f.k] = !!x;
    else if (f.type === "number") o[f.k] = x === "" || x === null ? null : Number(String(x).replace(",", "."));
    else if (f.type === "tags") o[f.k] = String(x || "").split(",").map((s) => s.trim()).filter(Boolean);
    else if (f.type === "lines") o[f.k] = String(x || "").split("\n").map((s) => s.trim()).filter(Boolean);
    else o[f.k] = x === "" ? null : x;
  }
  return o;
}

/** Formulario con validación del servidor (los errores 422 se muestran tal cual). */
export function SchemaForm({ fields, initial, onSubmit, submitLabel = "Guardar", onCancel, extra }: {
  fields: Field[]; initial?: Row; onSubmit: (v: Row) => Promise<unknown>; submitLabel?: string; onCancel?: () => void; extra?: ReactNode;
}) {
  const [v, setV] = useState<Row>(() => toForm(fields, initial ?? {}));
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <form className="life-form" onSubmit={(e) => {
      e.preventDefault(); setBusy(true); setErr(null);
      onSubmit(fromForm(fields, v)).catch((x: Error) => setErr(x.message)).finally(() => setBusy(false));
    }}>
      {fields.map((f) => (
        <label key={f.k} className={f.wide || f.type === "textarea" || f.type === "lines" ? "wide" : f.type === "checkbox" ? "check" : ""}>
          {f.type !== "checkbox" && <span>{f.label}{f.required ? " *" : ""}</span>}
          {f.type === "textarea" || f.type === "lines" ? (
            <textarea value={v[f.k]} onChange={(e) => setV({ ...v, [f.k]: e.target.value })} rows={f.type === "lines" ? 3 : 3} placeholder={f.placeholder} required={f.required} aria-label={f.label} />
          ) : f.type === "select" ? (
            <select value={v[f.k]} onChange={(e) => setV({ ...v, [f.k]: e.target.value })} aria-label={f.label} required={f.required}>
              {!f.required && <option value="">—</option>}
              {f.options!.map(([val, l]) => <option key={val} value={val}>{l}</option>)}
            </select>
          ) : f.type === "checkbox" ? (
            <><input type="checkbox" checked={!!v[f.k]} onChange={(e) => setV({ ...v, [f.k]: e.target.checked })} aria-label={f.label} /> {f.label}</>
          ) : (
            <input type={f.type === "number" ? "text" : f.type === "date" ? "date" : f.type === "time" ? "time" : "text"} inputMode={f.type === "number" ? "decimal" : undefined}
              value={v[f.k]} onChange={(e) => setV({ ...v, [f.k]: e.target.value })} placeholder={f.placeholder} required={f.required} aria-label={f.label} />
          )}
        </label>
      ))}
      {extra}
      <div className="row-btns wide">
        {onCancel && <button type="button" className="btn ghost" onClick={onCancel}>Cancelar</button>}
        <button type="submit" className="btn" disabled={busy}>{busy ? "Guardando…" : submitLabel}</button>
      </div>
      {err && <p className="error-line wide" role="alert">{err}</p>}
    </form>
  );
}

/** Lista CRUD: crear, editar, borrar (con confirmación). */
export function Crud({ title, path, listKey, fields, render, newDefaults, onChanged, actions, editPath, api = life }: {
  title: string; path: string; listKey?: string; fields: Field[]; render: (r: Row) => ReactNode; newDefaults?: Row;
  onChanged?: () => void; actions?: (r: Row, reload: () => void) => ReactNode; editPath?: (r: Row) => string; api?: Client;
}) {
  const { data, error, loading, reload } = useLoad<Row>(path, [], api);
  const [editing, setEditing] = useState<Row | "new" | null>(null);
  const items: Row[] = (listKey ? data?.[listKey] : data) ?? [];
  const done = () => { setEditing(null); reload(); onChanged?.(); };
  return (
    <section className="dpanel">
      <header className="dpanel-head"><span>{title.toUpperCase()} · {items.length}</span>
        <button type="button" className="link-btn" onClick={() => setEditing(editing === "new" ? null : "new")}>{editing === "new" ? "cerrar" : "+ nuevo"}</button></header>
      {editing === "new" && <SchemaForm fields={fields} initial={newDefaults} onCancel={() => setEditing(null)} submitLabel="Crear"
        onSubmit={(v) => api.post(path.split("?")[0], v).then(done)} />}
      <State loading={loading && !data} error={error} empty={!items.length && editing !== "new" ? "Aún no hay registros." : false}>
        <ul className="life-list">{items.map((r) => (
          <li key={r.id}>
            {editing && editing !== "new" && editing.id === r.id ? (
              <SchemaForm fields={fields} initial={r} onCancel={() => setEditing(null)}
                onSubmit={(v) => api.patch(editPath ? editPath(r) : `${path.split("?")[0]}/${r.id}`, v).then(done)} />
            ) : (
              <>
                <div className="life-item">{render(r)}</div>
                <div className="row-actions">
                  {actions?.(r, reload)}
                  <button type="button" className="mini-btn ghost" onClick={() => setEditing(r)}>Editar</button>
                  <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar este registro? No se puede deshacer.")) void api.del(`${path.split("?")[0]}/${r.id}`).then(done); }}>Eliminar</button>
                </div>
              </>
            )}
          </li>
        ))}</ul>
      </State>
    </section>
  );
}

/** Chat con un agente especializado (usa tus datos reales vía /coach). */
export function AgentChat({ area, title, quick }: { area: string; title: string; quick: string[] }) {
  const [msgs, setMsgs] = useState<{ role: "user" | "assistant"; content: string; meta?: string }[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [msgs]);
  const ask = (text: string) => {
    if (!text.trim() || busy) return;
    const history = msgs.map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: text }]); setQ(""); setBusy(true);
    life.post<{ answer: string; model: string; used: string[] }>("/coach", { area, question: text, history })
      .then((r) => setMsgs((m) => [...m, { role: "assistant", content: r.answer, meta: `${r.model} · datos: ${r.used.join(", ")}` }]))
      .catch((e: Error) => setMsgs((m) => [...m, { role: "assistant", content: `⚠ ${e.message}` }])).finally(() => setBusy(false));
  };
  return (
    <section className="dpanel life-agent">
      <header className="dpanel-head"><span>{title.toUpperCase()}</span></header>
      <div className="tutor-log">
        {!msgs.length && <div className="quick">{quick.map((x) => <button type="button" key={x} className="chip" onClick={() => ask(x)}>{x}</button>)}</div>}
        {msgs.map((m, i) => <div key={i} className={`tmsg ${m.role}`}><div className="tbody">{m.content.split("\n").map((l, j) => <p key={j}>{l}</p>)}</div>{m.meta && <small>{m.meta}</small>}</div>)}
        {busy && <div className="tmsg assistant"><div className="tbody"><p className="muted">Analizando tus datos…</p></div></div>}
        <div ref={end} />
      </div>
      <form className="tutor-in" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Pregunta al agente…" aria-label={`Pregunta a ${title}`} maxLength={2000} />
        <button type="submit" className="btn" disabled={busy || !q.trim()}>Preguntar</button>
      </form>
    </section>
  );
}

export function Md({ text }: { text: string | null | undefined }) {
  if (!text) return null;
  return <div className="md">{text.split("\n").map((l, i) => (l.startsWith("#") ? <h4 key={i}>{l.replace(/^#+\s*/, "")}</h4> : l.trim() ? <p key={i}>{l}</p> : null))}</div>;
}

export const fmtDate = (s: string | null | undefined) => (s ? new Date(s.length === 10 ? s + "T12:00:00" : s).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" }) : "—");
export const eur = (v: number | null | undefined) => (v === null || v === undefined ? "N/D" : new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(v));
