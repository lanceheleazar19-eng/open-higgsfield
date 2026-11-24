import { useRef, useState } from "react";
import { askingConsent, body, type MealItemEst, type MealPhotoItem } from "../api/body";
import { useAsync } from "../api/useAsync";
import { Empty, Panel } from "./Panel";
import { VisionNote } from "./VisionNote";

const MEALS = ["desayuno", "comida", "merienda", "cena", "snack"] as const;
const n0 = (v: number) => new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 }).format(v);
const localNow = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };

function scale(it: MealItemEst, grams: number): MealItemEst {
  const k = grams / Math.max(1, it.grams);
  return { ...it, grams, kcal: it.kcal * k, protein: it.protein * k, carbs: it.carbs * k, fat: it.fat * k };
}

function MealCard({ m, onChange }: { m: MealPhotoItem; onChange: () => Promise<void> }) {
  const [items, setItems] = useState<MealItemEst[]>(m.analysis?.items ?? []);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(m.error);
  const [edit, setEdit] = useState(false);
  const [meta, setMeta] = useState({ meal: m.meal, eaten_at: m.eaten_at.slice(0, 16), description: m.description ?? "" });
  const tot = items.reduce((a, i) => ({ kcal: a.kcal + i.kcal, protein: a.protein + i.protein, carbs: a.carbs + i.carbs, fat: a.fat + i.fat }), { kcal: 0, protein: 0, carbs: 0, fat: 0 });
  const a = m.analysis;

  async function reanalyze() {
    setBusy(true); setErr(null);
    try {
      const desc = [m.description, answer].filter(Boolean).join(". ");
      const r = await askingConsent((c) => body.analyzeMeal(m.id, desc || null, c));
      if (r) { setItems(r.analysis?.items ?? []); setAnswer(""); await onChange(); } else setErr("No has autorizado enviar la foto: no se ha analizado.");
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <li className="meal-card">
      <img src={m.thumb} alt={`Foto de ${m.meal}`} loading="lazy" />
      <div className="meal-body">
        <p className="small"><strong className="cap">{m.meal}</strong> · {new Date(m.eaten_at).toLocaleString("es-ES", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
          {" · "}<span className={`badge ${m.status === "logged" ? "live" : ""}`}>{{ pending: "sin analizar", analyzed: "por confirmar", logged: "registrada", error: "sin análisis" }[m.status] ?? m.status}</span></p>
        {m.description && <p className="small muted">«{m.description}»</p>}
        {err && <p className="small t-warn">{err}</p>}
        {a && !a.is_food && <p className="small t-warn">No he reconocido comida en la foto.</p>}
        {items.length > 0 && (
          <div className="table-scroll"><table className="data-table">
            <thead><tr><th>Alimento</th><th>g</th><th>kcal</th><th>Prot.</th><th>HC</th><th>Grasa</th><th>Origen</th><th /></tr></thead>
            <tbody>{items.map((it, i) => (
              <tr key={i}>
                <td>{it.name}{it.preparation ? <span className="muted small"> · {it.preparation}</span> : null}{it.confidence === "baja" && <span className="t-warn small"> · dudoso</span>}</td>
                <td><input className="grams" inputMode="decimal" aria-label={`Gramos de ${it.name}`} value={Math.round(it.grams)}
                  onChange={(e) => { const g = Number(e.target.value.replace(",", ".")); if (g > 0) setItems(items.map((x, j) => j === i ? scale(x, g) : x)); }} /></td>
                <td className="mono">{n0(it.kcal)}</td><td className="mono">{n0(it.protein)}</td><td className="mono">{n0(it.carbs)}</td><td className="mono">{n0(it.fat)}</td>
                <td className="small muted">{it.source === "base de alimentos" ? "tabla" : "estimado"}</td>
                <td><button type="button" className="mini-btn danger" aria-label={`Quitar ${it.name}`} onClick={() => setItems(items.filter((_, j) => j !== i))}>×</button></td>
              </tr>
            ))}</tbody>
            <tfoot><tr><td><strong>Total</strong></td><td /><td className="mono"><strong>{n0(tot.kcal)}</strong></td><td className="mono"><strong>{n0(tot.protein)}</strong></td><td className="mono">{n0(tot.carbs)}</td><td className="mono">{n0(tot.fat)}</td><td colSpan={2} /></tr></tfoot>
          </table></div>
        )}
        {a?.quality && <p className="small"><strong>Calidad:</strong> {a.quality}{a.quality_note ? ` — ${a.quality_note}` : ""}</p>}
        {a?.disclaimer && <p className="muted small">{a.disclaimer}</p>}
        {a && a.questions.length > 0 && (
          <div className="meal-q">
            <p className="small"><strong>VISTAN pregunta:</strong> {a.questions.join(" ")}</p>
            <div className="form-row"><label><span>Tu respuesta</span><input value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Ej.: sí, una cucharada de aceite" /></label>
              <button type="button" className="mini-btn" disabled={busy || !answer.trim()} onClick={() => void reanalyze()}>Reanalizar</button></div>
          </div>
        )}
        <div className="form-actions">
          {items.length > 0 && <button className="btn" disabled={busy} onClick={async () => { setBusy(true); try { await body.logMeal(m.id, items.map((i) => ({ name: i.name, grams: Math.round(i.grams), food_id: i.food_id, kcal: i.kcal, protein: i.protein, carbs: i.carbs, fat: i.fat }))); await onChange(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } }}>
            {m.status === "logged" ? "Actualizar registro" : "Guardar en mi registro"}</button>}
          {(m.status === "pending" || m.status === "error") && <button className="mini-btn" disabled={busy} onClick={() => void reanalyze()}>{busy ? "Analizando…" : "Analizar"}</button>}
          <button className="mini-btn ghost" onClick={() => setEdit(!edit)}>Editar</button>
          <button className="mini-btn danger" onClick={async () => { if (confirm("¿Borrar esta comida? Se borran la foto y sus registros de macros.")) { await body.deleteMeal(m.id); await onChange(); } }}>Borrar</button>
        </div>
        {edit && (
          <form className="form" onSubmit={async (e) => { e.preventDefault(); await body.patchMeal(m.id, { meal: meta.meal, eaten_at: meta.eaten_at, description: meta.description || null }); setEdit(false); await onChange(); }}>
            <div className="form-row">
              <label><span>Comida</span><select value={meta.meal} onChange={(e) => setMeta({ ...meta, meal: e.target.value })}>{MEALS.map((x) => <option key={x}>{x}</option>)}</select></label>
              <label><span>Fecha y hora</span><input type="datetime-local" value={meta.eaten_at} onChange={(e) => setMeta({ ...meta, eaten_at: e.target.value })} /></label>
            </div>
            <label><span>Descripción</span><input value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} /></label>
            <div className="form-actions"><button className="btn">Guardar</button></div>
          </form>
        )}
      </div>
    </li>
  );
}

/** Comidas con foto: subir, analizar (local por defecto), revisar las estimaciones y confirmar. */
export function MealPhotos() {
  const [filter, setFilter] = useState("");
  const list = useAsync(() => body.meals(filter || undefined));
  const [f, setF] = useState({ meal: "", eaten_at: localNow(), description: "" });
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  async function save() {
    if (!file) return;
    setBusy(true); setMsg(null);
    try {
      let r = await body.uploadMeal(file, { meal: f.meal || undefined, eaten_at: f.eaten_at, description: f.description || undefined });
      if (r.needs_consent && confirm(`${r.needs_consent.message}\n\n¿Autorizas enviar ESTA foto?`)) r = await body.analyzeMeal(r.id, f.description || null, true);
      setMsg(r.status === "analyzed" ? "Analizada: revisa los gramos y guárdala en tu registro." : r.error ?? "Foto guardada sin analizar.");
      setFile(null); setPreview(null); setF({ ...f, description: "", eaten_at: localNow() });
      await list.reload();
    } catch (e) { setMsg((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="grid grid-tasks">
      <div className="stack">
        <Panel title="Foto de una comida">
          <div className="form">
            <div className="dropzone" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); const x = e.dataTransfer.files[0]; if (x) { setFile(x); setPreview(URL.createObjectURL(x)); } }}>
              {preview ? <img src={preview} alt="Vista previa del plato" className="photo-preview" /> : <p>Arrastra la foto del plato</p>}
              <button type="button" className="mini-btn" onClick={() => input.current?.click()}>{preview ? "Cambiar" : "Elegir foto"}</button>
              <input ref={input} type="file" accept="image/jpeg,image/png,image/webp,.heic" hidden aria-label="Foto de comida" onChange={(e) => { const x = e.target.files?.[0]; e.target.value = ""; if (x) { setFile(x); setPreview(URL.createObjectURL(x)); } }} />
            </div>
            <div className="form-row">
              <label><span>Comida</span><select value={f.meal} onChange={(e) => setF({ ...f, meal: e.target.value })}><option value="">Según la hora</option>{MEALS.map((x) => <option key={x}>{x}</option>)}</select></label>
              <label><span>Fecha y hora</span><input type="datetime-local" value={f.eaten_at} onChange={(e) => setF({ ...f, eaten_at: e.target.value })} /></label>
            </div>
            <label><span>Descripción (mejora la estimación)</span><input value={f.description} maxLength={1000} placeholder="Ej.: pasta con atún, una cucharada de aceite" onChange={(e) => setF({ ...f, description: e.target.value })} /></label>
            <VisionNote />
            <div className="form-actions"><button type="button" className="btn" disabled={!file || busy} onClick={() => void save()}>{busy ? "Analizando…" : "Guardar y analizar"}</button>
              {msg && <span role="status" className="small">{msg}</span>}</div>
          </div>
        </Panel>
        <NutritionAdvisor />
      </div>
      <Panel title="Historial de comidas con foto">
        <div className="tabs" role="tablist" aria-label="Filtrar por comida">
          {[["", "Todas"], ...MEALS.map((x) => [x, x])].map(([k, l]) => (
            <button key={k} role="tab" aria-selected={filter === k} className={filter === k ? "on" : ""} onClick={() => { setFilter(k); setTimeout(() => void list.reload(), 0); }}>{l}</button>
          ))}
        </div>
        {!list.data?.length ? <Empty>No hay comidas con foto{filter ? ` de ${filter}` : ""} en los últimos 60 días.</Empty> : (
          <ul className="meal-list">{list.data.map((m) => <MealCard key={`${m.id}-${m.status}-${m.analysis?.items.length ?? 0}`} m={m} onChange={list.reload} />)}</ul>
        )}
      </Panel>
    </div>
  );
}

export function NutritionAdvisor() {
  const [r, setR] = useState<Record<string, unknown> | null>(null);
  const [meta, setMeta] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const L = (t: string, k: string) => Array.isArray(r?.[k]) && (r![k] as string[]).length ? <><h3 className="h-sm">{t}</h3><ul className="steps">{(r![k] as string[]).map((x, i) => <li key={i}>{x}</li>)}</ul></> : null;
  return (
    <Panel title="Asesor nutricional">
      <p className="small muted">Analiza tus últimos 14 días registrados frente a tus objetivos y tu entrenamiento. Distingue lo registrado de lo estimado por foto.</p>
      <button className="btn" disabled={busy} onClick={async () => { setBusy(true); try { const a = await body.nutritionAdvice(); setR(a.result.advice); setMeta(a.result.mode === "ai" ? `Con ${a.model}` : "Sin IA: análisis directo de tus datos"); } finally { setBusy(false); } }}>
        {busy ? "Analizando…" : "Analizar mi alimentación"}</button>
      {r && <div className="analysis">
        <p className="small muted">{meta}</p>
        {typeof r.resumen === "string" && <p>{r.resumen}</p>}
        {typeof r.cumplimiento === "string" && <p className="small">{r.cumplimiento}</p>}
        {L("Lo que haces bien", "puntos_fuertes")}{L("Para mejorar", "mejorar")}{L("Alternativas", "alternativas")}{L("Necesito saber", "preguntas")}
      </div>}
    </Panel>
  );
}
