import { useRef, useState, type FormEvent } from "react";
import { askingConsent, body, type AnalysisItem, type BodyPhotoItem, type PhysiqueResult } from "../api/body";
import { useAsync } from "../api/useAsync";
import { formatDayLabel } from "../lib/tasks";
import { Empty, Panel } from "./Panel";
import { PhotoCompare } from "./PhotoCompare";
import { VisionNote } from "./VisionNote";

const POSES: [string, string][] = [["front", "Frente"], ["back", "Espalda"], ["side", "Perfil"], ["other", "Otra"]];
const today = () => new Date().toISOString().slice(0, 10);

function Result({ a, photos }: { a: AnalysisItem<PhysiqueResult>; photos: BodyPhotoItem[] }) {
  const r = a.result;
  const dates = a.refs.map((id) => photos.find((p) => p.id === id)?.taken_on).filter(Boolean) as string[];
  const L = ({ t, xs }: { t: string; xs: string[] }) => xs?.length ? <><h3 className="h-sm">{t}</h3><ul className="steps">{xs.map((x, i) => <li key={i}>{x}</li>)}</ul></> : null;
  return (
    <div className="analysis">
      <p className="small muted">{a.kind === "compare" ? `Comparación ${dates.map(formatDayLabel).join(" → ")}` : `Análisis del ${dates.map(formatDayLabel).join("")}`}
        {" · "}{a.model}{" · "}<span className={`badge conf-${r.fiabilidad}`}>fiabilidad {r.fiabilidad}</span></p>
      {r.motivos_fiabilidad?.length > 0 && <p className="small t-warn">Ojo al comparar: {r.motivos_fiabilidad.join("; ")}</p>}
      <L t="Lo que se observa" xs={r.observaciones} />
      <L t="Cambios visibles" xs={r.cambios} />
      <L t="Más desarrollado" xs={r.mas_desarrollados} />
      <L t="Para trabajar" xs={r.a_trabajar} />
      {r.simetria && <p className="small"><strong>Simetría:</strong> {r.simetria}</p>}
      <L t="Recomendaciones de entrenamiento" xs={r.recomendaciones_entrenamiento} />
      <L t="Recuperación y hábitos" xs={r.habitos} />
      {r.relacion_con_datos && <p className="small"><strong>Con tus datos:</strong> {r.relacion_con_datos}</p>}
      <p className="muted small">{r.aviso}{r.omitidos ? ` (He descartado ${r.omitidos} comentario(s) con cifras corporales o médicas.)` : ""}</p>
    </div>
  );
}

/** Seguimiento físico con fotos privadas: subir, ordenar, comparar y pedir análisis. */
export function PhysiqueTab() {
  const photos = useAsync(body.photos);
  const analyses = useAsync(() => body.analyses<PhysiqueResult>("physique,compare"));
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [f, setF] = useState({ taken_on: today(), pose: "front", note: "" });
  const [sel, setSel] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "pos" | "neg"; text: string } | null>(null);
  const [edit, setEdit] = useState<BodyPhotoItem | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const list = photos.data ?? [];
  const chosen = sel.map((id) => list.find((p) => p.id === id)!).filter(Boolean).sort((a, b) => a.taken_on.localeCompare(b.taken_on));

  function pick(fl: File | undefined) {
    if (!fl) return;
    if (!/^image\/(jpeg|png|webp|heic|heif)$/.test(fl.type) && !/\.(jpe?g|png|webp|heic)$/i.test(fl.name)) { setMsg({ tone: "neg", text: "Usa JPG, PNG o WEBP." }); return; }
    setFile(fl); setPreview(URL.createObjectURL(fl)); setMsg(null);
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    try { await body.uploadPhoto(file, f.taken_on, f.pose, f.note || undefined); setFile(null); setPreview(null); setF({ ...f, note: "" }); setMsg({ tone: "pos", text: "Foto guardada en privado." }); await photos.reload(); }
    catch (err) { setMsg({ tone: "neg", text: (err as Error).message }); } finally { setBusy(false); }
  }
  async function analyze() {
    setBusy(true); setMsg(null);
    try {
      const r = await askingConsent((cloud) => body.analyzePhotos(sel, cloud));
      if (r) { await analyses.reload(); setMsg({ tone: "pos", text: "Análisis listo." }); } else setMsg({ tone: "neg", text: "No has autorizado enviar la foto: no se ha analizado." });
    } catch (err) { setMsg({ tone: "neg", text: (err as Error).message }); } finally { setBusy(false); }
  }
  const toggle = (id: number) => setSel((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2));

  return (
    <div className="grid grid-tasks">
      <div className="stack">
        <Panel title="Nueva foto de progreso">
          <form className="form" onSubmit={save}>
            <div className="dropzone" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files[0]); }}>
              {preview ? <img src={preview} alt="Vista previa" className="photo-preview" /> : <p>Arrastra una foto aquí</p>}
              <button type="button" className="mini-btn" onClick={() => input.current?.click()}>{preview ? "Cambiar foto" : "Elegir foto"}</button>
              <input ref={input} type="file" accept="image/jpeg,image/png,image/webp,.heic" hidden aria-label="Foto de físico" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
            </div>
            <div className="form-row">
              <label><span>Fecha</span><input type="date" value={f.taken_on} max={today()} onChange={(e) => setF({ ...f, taken_on: e.target.value })} /></label>
              <label><span>Pose</span><select value={f.pose} onChange={(e) => setF({ ...f, pose: e.target.value })}>{POSES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
            </div>
            <label><span>Comentario (opcional)</span><input value={f.note} maxLength={1000} placeholder="Ej.: por la mañana, en ayunas, misma luz" onChange={(e) => setF({ ...f, note: e.target.value })} /></label>
            <div className="form-actions"><button className="btn" disabled={!file || busy}>{busy ? "Guardando…" : "Guardar"}</button>
              {msg && <span role="status" className={`small ${msg.tone}`}>{msg.text}</span>}</div>
            <p className="muted small">Se guardan solo en tu ordenador, sin datos de ubicación (EXIF), en una carpeta privada. Para comparar bien: misma luz, distancia, pose y hora.</p>
          </form>
        </Panel>
        <Panel title="Analizar">
          <VisionNote />
          <p className="small">{sel.length === 0 ? "Selecciona 1 foto para analizarla o 2 para compararlas." : sel.length === 1 ? "1 foto seleccionada: análisis individual." : "2 fotos seleccionadas: comparación."}</p>
          {chosen.length === 2 && <PhotoCompare before={chosen[0].url} after={chosen[1].url} labelBefore={formatDayLabel(chosen[0].taken_on)} labelAfter={formatDayLabel(chosen[1].taken_on)} />}
          <div className="form-actions"><button className="btn" disabled={!sel.length || busy} onClick={() => void analyze()}>{busy ? "Analizando…" : sel.length === 2 ? "Comparar con IA" : "Analizar con IA"}</button></div>
          <p className="muted small">VISTAN solo describe lo visible: no calcula % de grasa ni medidas y no hace diagnósticos.</p>
        </Panel>
      </div>
      <div className="stack">
        <Panel title={`Historial visual (${list.length})`}>
          {!list.length ? <Empty>Aún no has subido fotos de progreso.</Empty> : (
            <ul className="photo-grid">
              {list.map((p) => (
                <li key={p.id} className={sel.includes(p.id) ? "on" : ""}>
                  <button type="button" className="photo-btn" onClick={() => toggle(p.id)} aria-pressed={sel.includes(p.id)} aria-label={`Seleccionar foto del ${p.taken_on}`}>
                    <img src={p.thumb} alt={`Foto de ${p.pose_es} del ${p.taken_on}`} loading="lazy" />
                  </button>
                  <span className="small">{formatDayLabel(p.taken_on)} · {p.pose_es}</span>
                  {p.note && <span className="muted small photo-note">{p.note}</span>}
                  <span className="row-actions">
                    <button type="button" className="mini-btn ghost" onClick={() => setEdit(p)}>Editar</button>
                    <button type="button" className="mini-btn danger" aria-label={`Borrar foto del ${p.taken_on}`}
                      onClick={async () => { if (confirm("¿Borrar esta foto? Se elimina el archivo de tu ordenador.")) { await body.deletePhoto(p.id); setSel((s) => s.filter((x) => x !== p.id)); await photos.reload(); } }}>×</button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {edit && (
            <form className="form" onSubmit={async (e) => { e.preventDefault(); await body.patchPhoto(edit.id, { taken_on: edit.taken_on, pose: edit.pose, note: edit.note }); setEdit(null); await photos.reload(); }}>
              <div className="form-row">
                <label><span>Fecha</span><input type="date" value={edit.taken_on} onChange={(e) => setEdit({ ...edit, taken_on: e.target.value })} /></label>
                <label><span>Pose</span><select value={edit.pose} onChange={(e) => setEdit({ ...edit, pose: e.target.value })}>{POSES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
              </div>
              <label><span>Comentario</span><input value={edit.note ?? ""} onChange={(e) => setEdit({ ...edit, note: e.target.value })} /></label>
              <div className="form-actions"><button className="btn">Guardar cambios</button><button type="button" className="mini-btn ghost" onClick={() => setEdit(null)}>Cancelar</button></div>
            </form>
          )}
        </Panel>
        <Panel title="Análisis anteriores">
          {!analyses.data?.length ? <Empty>Todavía no has pedido ningún análisis.</Empty> : analyses.data.map((a) => (
            <details key={a.id} open={a.id === analyses.data![0].id} className="analysis-item">
              <summary className="small">{new Date(a.created_at).toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" })} · {a.kind === "compare" ? "comparación" : "análisis"}
                <button type="button" className="mini-btn danger" onClick={async (e) => { e.preventDefault(); await body.deleteAnalysis(a.id); await analyses.reload(); }}>Borrar</button></summary>
              <Result a={a} photos={list} />
            </details>
          ))}
        </Panel>
      </div>
    </div>
  );
}
