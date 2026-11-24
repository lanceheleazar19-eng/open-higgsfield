import { useState } from "react";
import { Link } from "react-router-dom";
import { body, type Trend } from "../api/body";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { LineChart } from "../components/LineChart";
import { Empty, Panel } from "../components/Panel";
import { PhotoCompare } from "../components/PhotoCompare";
import { formatDayLabel } from "../lib/tasks";

const fmt = (v: number, d = 1) => new Intl.NumberFormat("es-ES", { maximumFractionDigits: d }).format(v);

function TrendBadge({ t, unit }: { t: Trend; unit: string }) {
  if (t.status === "insuficiente") return <span className="badge" title={t.reason}>datos insuficientes</span>;
  const label = { subiendo: "tendencia al alza", bajando: "tendencia a la baja", estable: "estable" }[t.status];
  return <span className={`badge trend-${t.status}`} title={`${t.points} registros en ${t.days} días · ruido ±${t.noise}`}>
    {label}{t.status !== "estable" && t.per_week !== undefined ? ` · ${t.per_week > 0 ? "+" : ""}${fmt(t.per_week, 2)} ${unit}/sem` : ""}</span>;
}

/** PROGRESS: físico, peso, entrenamiento, nutrición y objetivos juntos, con tendencias reales. */
export function Progress() {
  const d = useAsync(body.progress);
  const photos = useAsync(body.photos);
  const [sum, setSum] = useState<Awaited<ReturnType<typeof body.progressSummary>> | null>(null);
  const [busy, setBusy] = useState(false);
  const [pair, setPair] = useState<[number, number] | null>(null);
  const g = d.data;
  const ph = [...(photos.data ?? [])].sort((a, b) => a.taken_on.localeCompare(b.taken_on));
  const cmp = pair ?? (ph.length >= 2 ? [ph[0].id, ph[ph.length - 1].id] as [number, number] : null);
  const A = cmp && ph.find((p) => p.id === cmp[0]), B = cmp && ph.find((p) => p.id === cmp[1]);
  const s = sum?.result;

  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Personal</p>
        <h1><Icon name="progress" size={26} /> Progress</h1>
        <p className="lead">Tu evolución con datos reales: fotos, peso, entrenamientos, nutrición y objetivos. VISTAN solo habla de tendencia cuando hay suficientes registros; una variación de un día no lo es.</p>
      </header>
      {!g ? <Empty>Cargando…</Empty> : (
        <>
          <Panel title="Resumen de VISTAN" aside={<button className="btn" disabled={busy} onClick={async () => { setBusy(true); try { setSum(await body.progressSummary()); } finally { setBusy(false); } }}>{busy ? "Analizando…" : "Analizar mi progreso"}</button>}>
            {!s ? (
              <ul className="steps">{g.facts.map((f, i) => <li key={i}>{f}</li>)}</ul>
            ) : (
              <div className="analysis">
                <p className="small muted">{s.mode === "ai" ? `Con ${sum!.model}` : "Sin IA: resumen directo de tus datos"} · {new Date(sum!.created_at).toLocaleString("es-ES")}</p>
                <p>{s.resumen}</p>
                {[["Tendencias", s.tendencias], ["Variaciones puntuales (no son tendencia)", s.variaciones_puntuales], ["Cómo se relaciona todo", s.conexiones],
                  ["Recomendaciones", s.recomendaciones], ["Faltan datos", s.faltan_datos]].map(([t, xs]) =>
                  Array.isArray(xs) && xs.length ? <div key={t as string}><h3 className="h-sm">{t as string}</h3><ul className="steps">{(xs as string[]).map((x, i) => <li key={i}>{x}</li>)}</ul></div> : null)}
                <details className="help"><summary>Datos usados</summary><ul className="steps">{s.facts.map((f, i) => <li key={i}>{f}</li>)}</ul></details>
              </div>
            )}
          </Panel>
          <div className="grid grid-2">
            <Panel title="Físico" aside={<Link to="/gym" className="mini-btn">Subir fotos</Link>}>
              {ph.length < 2 ? <Empty>{ph.length ? "Sube otra foto para poder comparar." : "Aún no hay fotos de progreso. Súbelas en Fitness › Físico."}</Empty> : (
                <>
                  <div className="form-row">
                    {[0, 1].map((k) => (
                      <label key={k}><span>{k ? "Después" : "Antes"}</span>
                        <select value={cmp![k]} onChange={(e) => { const v = Number(e.target.value); setPair(k ? [cmp![0], v] : [v, cmp![1]]); }}>
                          {ph.map((p) => <option key={p.id} value={p.id}>{formatDayLabel(p.taken_on)} · {p.pose_es}</option>)}
                        </select></label>
                    ))}
                  </div>
                  {A && B && <PhotoCompare before={A.url} after={B.url} labelBefore={formatDayLabel(A.taken_on)} labelAfter={formatDayLabel(B.taken_on)} />}
                  {A && B && A.pose !== B.pose && <p className="small t-warn">Poses distintas: la comparación visual es poco fiable.</p>}
                </>
              )}
              {ph.length > 0 && <ul className="photo-strip">{ph.map((p) => <li key={p.id}><img src={p.thumb} alt={`Foto del ${p.taken_on}`} loading="lazy" /><span className="small">{formatDayLabel(p.taken_on)}</span></li>)}</ul>}
            </Panel>
            <Panel title="Peso" aside={<TrendBadge t={g.weight_trend} unit="kg" />}>
              {g.weights.length < 2 ? <Empty>Registra tu peso (Fitness › Cuerpo o Apple Salud) para ver su evolución.</Empty> : (
                <LineChart ariaLabel="Evolución del peso" unit=" kg" labels={g.weights.map((w) => formatDayLabel(w.date))} height={190}
                  series={[{ label: "Peso", color: "#e11d35", values: g.weights.map((w) => w.kg) }]} />
              )}
              {g.weight_trend.status === "insuficiente" && <p className="muted small">{g.weight_trend.reason}</p>}
            </Panel>
            <Panel title="Entrenamiento (12 semanas)" aside={<TrendBadge t={g.tonnage_trend} unit="kg" />}>
              {!g.weeks_trained ? <Empty>No hay entrenamientos registrados.</Empty> : <>
                <LineChart ariaLabel="Sesiones por semana" labels={g.training_weeks.map((w) => formatDayLabel(w.week))} height={150}
                  series={[{ label: "Sesiones", color: "#e11d35", values: g.training_weeks.map((w) => w.sessions) }]} />
                <LineChart ariaLabel="Tonelaje semanal" unit=" kg" labels={g.training_weeks.map((w) => formatDayLabel(w.week))} height={150}
                  series={[{ label: "Tonelaje", color: "#eaeaea", values: g.training_weeks.map((w) => w.tonnage) }]} />
              </>}
            </Panel>
            <Panel title="Nutrición (6 semanas)" aside={<TrendBadge t={g.kcal_trend} unit="kcal" />}>
              {!g.nutrition_days.length ? <Empty>No hay comidas registradas.</Empty> : <>
                <LineChart ariaLabel="Calorías por día" labels={g.nutrition_days.map((x) => formatDayLabel(x.date))} height={160}
                  series={[{ label: "kcal", color: "#e11d35", values: g.nutrition_days.map((x) => x.kcal) },
                           ...(g.targets ? [{ label: "Objetivo", color: "#777777", values: g.nutrition_days.map(() => g.targets!.kcal) }] : [])]} />
                <LineChart ariaLabel="Proteína por día" unit=" g" labels={g.nutrition_days.map((x) => formatDayLabel(x.date))} height={140}
                  series={[{ label: "Proteína", color: "#eaeaea", values: g.nutrition_days.map((x) => x.protein) },
                           ...(g.targets ? [{ label: "Objetivo", color: "#777777", values: g.nutrition_days.map(() => g.targets!.protein) }] : [])]} />
                {g.targets && <p className="small">Proteína cumplida (≥90 %) en <strong>{g.protein_days_met}</strong> de {g.nutrition_days.length} días registrados.</p>}
              </>}
            </Panel>
          </div>
          <Panel title="Objetivos">
            {!g.goals.length ? <Empty>No tienes objetivos activos. Créalos en Tareas › Objetivos.</Empty> : (
              <ul className="r-list">{g.goals.map((x) => <li key={x.id}><span>{x.title}</span> <span className="muted small">· {x.pace ?? "sin ritmo"}{x.progress_pct != null ? ` · ${x.progress_pct} %` : ""}</span></li>)}</ul>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
