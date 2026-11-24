import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { FoodItem, Macros, MealProposal, NutritionProfile, NutritionTargets } from "../api/types";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { Empty, Panel } from "../components/Panel";
import { formatDayLabel } from "../lib/tasks";
import { MealPhotos } from "../components/MealPhotos";

const MEALS = ["desayuno", "comida", "merienda", "cena", "snack"] as const;
const n0 = (v: number) => new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 }).format(v);
type Tab = "today" | "photos" | "week" | "profile" | "foods";

export function Nutrition() {
  const [tab, setTab] = useState<Tab>("today");
  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Fase 5 · activo</p>
        <h1><Icon name="nutrition" size={26} /> Nutrición</h1>
        <p className="lead">Escribe lo que comes («2 huevos y una tostada») o haz una foto del plato. Las calorías salen de la base de alimentos; la foto se analiza en tu ordenador y no se guarda.</p>
      </header>
      <div className="tabs" role="tablist" aria-label="Secciones de nutrición">
        {([["today", "Hoy"], ["photos", "Fotos y asesor"], ["week", "Semana"], ["profile", "Perfil y objetivos"], ["foods", "Alimentos"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "today" && <Today />}
      {tab === "photos" && <MealPhotos />}
      {tab === "week" && <Week />}
      {tab === "profile" && <ProfileTab />}
      {tab === "foods" && <Foods />}
    </div>
  );
}

function MacroBar({ label, value, target, unit }: { label: string; value: number; target?: number; unit: string }) {
  const pct = target ? Math.min(100, (value / target) * 100) : 0;
  return (
    <div className="macro">
      <div className="macro-head"><span>{label}</span><span className="mono">{n0(value)}{target ? ` / ${n0(target)}` : ""} {unit}</span></div>
      <div className="goal-bar" role="progressbar" aria-label={label} aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

function Proposal({ items, foods, onChange }: { items: MealProposal[]; foods: FoodItem[]; onChange: (i: MealProposal[]) => void }) {
  return (
    <ul className="proposal">
      {items.map((it, idx) => (
        <li key={idx}>
          <select value={it.food?.id ?? ""} aria-label={`Alimento para «${it.text}»`} onChange={(e) => {
            const f = foods.find((x) => x.id === Number(e.target.value)) ?? null;
            onChange(items.map((x, i) => (i === idx ? { ...x, food: f, grams: x.grams ?? f?.unit_grams ?? null } : x)));
          }}>
            <option value="">{it.food ? "" : `¿«${it.text}»? Elige alimento…`}</option>
            {foods.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
          <input inputMode="decimal" value={it.grams ?? ""} aria-label={`Gramos de ${it.food?.name ?? it.text}`}
            onChange={(e) => onChange(items.map((x, i) => (i === idx ? { ...x, grams: Number(e.target.value.replace(",", ".")) || null } : x)))} />
          <span className="muted small">g</span>
          {it.food && it.grams ? <span className="mono small">{n0(it.food.kcal * it.grams / 100)} kcal · {n0(it.food.protein * it.grams / 100)} g prot.</span> : <span className="t-warn small">sin datos</span>}
          <button type="button" className="mini-btn danger" aria-label={`Quitar ${it.text}`} onClick={() => onChange(items.filter((_, i) => i !== idx))}>×</button>
        </li>
      ))}
    </ul>
  );
}

function Today() {
  const day = useAsync(api.nutritionDay);
  const foods = useAsync(() => api.foods());
  const [meal, setMeal] = useState<string>("");
  const [text, setText] = useState("");
  const [items, setItems] = useState<MealProposal[]>([]);
  const [source, setSource] = useState<"text" | "photo">("text");
  const [msg, setMsg] = useState<{ tone: "pos" | "neg"; text: string } | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const d = day.data;
  const currentMeal = meal || d?.suggested_meal || "comida";

  useEffect(() => {
    if (source !== "text") return;
    if (text.trim().length < 2) { setItems([]); return; }
    const t = setTimeout(() => { api.parseMeal(text).then((r) => setItems(r.items)).catch(() => setItems([])); }, 350);
    return () => clearTimeout(t);
  }, [text, source]);

  async function photo(f: File | undefined) {
    if (!f) return;
    setAnalyzing(true); setMsg(null); setSource("photo"); setText("");
    try {
      const r = await api.analyzePhoto(f);
      setItems(r.items);
      setMsg({ tone: "pos", text: r.items.length ? `${r.note} (modelo ${r.model})` : "No he detectado comida en la foto." });
    } catch (e) { setMsg({ tone: "neg", text: (e as Error).message }); setSource("text"); }
    finally { setAnalyzing(false); }
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    const ok = items.filter((i) => i.food && i.grams);
    if (!ok.length) return;
    try {
      await api.addMeal(currentMeal, ok.map((i) => ({ food_id: i.food!.id, grams: i.grams! })), source);
      setMsg({ tone: "pos", text: `Guardado en ${currentMeal}.` });
      setItems([]); setText(""); setSource("text");
      await day.reload();
    } catch (err) { setMsg({ tone: "neg", text: (err as Error).message }); }
  }

  const t = d?.targets;
  const tot: Macros = d?.totals ?? { kcal: 0, protein: 0, carbs: 0, fat: 0 };
  return (
    <div className="grid grid-tasks">
      <div className="stack">
        <Panel title="Hoy">
          {!t && <p className="callout">Completa la pestaña «Perfil y objetivos» para calcular tus calorías y macros.</p>}
          <MacroBar label="Calorías" value={tot.kcal} target={t?.kcal} unit="kcal" />
          <MacroBar label="Proteína" value={tot.protein} target={t?.protein} unit="g" />
          <MacroBar label="Hidratos" value={tot.carbs} target={t?.carbs} unit="g" />
          <MacroBar label="Grasas" value={tot.fat} target={t?.fat} unit="g" />
          {d && d.tips.length > 0 && <ul className="goal-insights">{d.tips.map((x) => <li key={x}>{x}</li>)}</ul>}
        </Panel>
        <Panel title="Registrar comida">
          <form className="form" onSubmit={save}>
            <label className="field"><span>Comida</span>
              <select value={currentMeal} onChange={(e) => setMeal(e.target.value)} aria-label="Tipo de comida">{MEALS.map((m) => <option key={m} value={m}>{m}</option>)}</select>
            </label>
            <label><span>¿Qué has comido?</span>
              <input value={text} onChange={(e) => { setSource("text"); setText(e.target.value); }} maxLength={1000}
                placeholder="Ej.: 200 g de arroz, pechuga de pollo y una manzana" aria-label="Comida en texto" /></label>
            <div className="row-actions">
              <button type="button" className="mini-btn" onClick={() => fileRef.current?.click()} disabled={analyzing}>
                <Icon name="camera" size={14} /> {analyzing ? "Analizando foto…" : "Foto del plato"}
              </button>
              <input ref={fileRef} type="file" accept="image/*" hidden aria-label="Foto del plato"
                onChange={(e) => { void photo(e.target.files?.[0]); e.target.value = ""; }} />
            </div>
            {items.length > 0 && <Proposal items={items} foods={foods.data?.items ?? []} onChange={setItems} />}
            <div className="form-actions">
              <button className="btn" type="submit" disabled={!items.some((i) => i.food && i.grams)}>Guardar</button>
              {msg && <span role="status" className={`small ${msg.tone}`}>{msg.text}</span>}
            </div>
          </form>
        </Panel>
      </div>
      <Panel title="Comidas de hoy">
        {!d ? <p className="muted">Cargando…</p> : d.entries.length === 0 ? <Empty>Aún no has registrado nada hoy.</Empty> : MEALS.map((m) => {
          const es = d.entries.filter((e) => e.meal === m);
          if (!es.length) return null;
          return (
            <section key={m} className="task-group">
              <h3>{m} <span className="count">{n0(es.reduce((a, e) => a + e.kcal, 0))} kcal</span></h3>
              <ul className="task-items">
                {es.map((e) => (
                  <li key={e.id} className="task">
                    <span className="task-main"><span className="task-title">{e.name}</span>
                      <span className="mem-meta">{n0(e.grams)} g · {n0(e.kcal)} kcal · P {n0(e.protein)} · H {n0(e.carbs)} · G {n0(e.fat)}{e.source === "photo" ? " · 📷" : ""}</span></span>
                    <button className="mini-btn danger" aria-label={`Borrar ${e.name}`} onClick={async () => { await api.deleteMealEntry(e.id); await day.reload(); }}>Borrar</button>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </Panel>
    </div>
  );
}

function Week() {
  const w = useAsync(api.nutritionWeek);
  const p = useAsync(api.nutritionProfile);
  if (!w.data) return <p className="muted">Cargando…</p>;
  const t = p.data?.targets;
  const max = Math.max(t?.kcal ?? 0, ...w.data.days.map((d) => d.kcal), 1);
  const logged = w.data.days.filter((d) => d.kcal > 0);
  const avg = (k: "kcal" | "protein") => (logged.length ? logged.reduce((a, d) => a + d[k], 0) / logged.length : 0);
  return (
    <Panel title="Últimos 7 días" aside={<span className="badge">media: {n0(avg("kcal"))} kcal · {n0(avg("protein"))} g prot.</span>}>
      <div className="kcal-week">
        {w.data.days.map((d) => (
          <div key={d.date} className="kcal-col" title={`${formatDayLabel(d.date)}: ${n0(d.kcal)} kcal, ${n0(d.protein)} g proteína`}>
            <span className="kcal-bar"><span style={{ height: `${(d.kcal / max) * 100}%` }} />
              {t && <i style={{ bottom: `${(t.kcal / max) * 100}%` }} />}</span>
            <span className="week-day">{formatDayLabel(d.date).split(",")[0]}</span>
            <span className="mono small">{n0(d.kcal)}</span>
          </div>
        ))}
      </div>
      <p className="muted small">{t ? `Línea: tu objetivo de ${n0(t.kcal)} kcal. ` : ""}La media cuenta solo los días con comidas registradas ({logged.length}).</p>
    </Panel>
  );
}

const ACTIVITY: [number, string][] = [[1.2, "Sedentario"], [1.375, "Ligero (1-3 entrenos)"], [1.55, "Moderado (3-5 entrenos)"], [1.725, "Alto (6-7 entrenos)"], [1.9, "Muy alto"]];

function ProfileTab() {
  const p = useAsync(api.nutritionProfile);
  const [f, setF] = useState<NutritionProfile>({ sex: "male", age: 0, height_cm: 0, weight_kg: null, activity: 1.55, goal: "maintain", target_weight_kg: null, protein_per_kg: 1.8 });
  const [targets, setTargets] = useState<NutritionTargets | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (p.data?.profile) setF(p.data.profile); setTargets(p.data?.targets ?? null); }, [p.data]);
  const num = (s: string) => Number(s.replace(",", ".")) || 0;

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      const r = await api.saveNutritionProfile(f);
      setTargets(r.targets);
      setMsg("Perfil guardado. Objetivos recalculados.");
    } catch (err) { setMsg((err as Error).message); }
  }

  return (
    <div className="grid grid-2">
      <Panel title="Tus datos">
        <form className="form" onSubmit={save}>
          <div className="form-row">
            <label><span>Sexo</span><select value={f.sex} onChange={(e) => setF({ ...f, sex: e.target.value as "male" | "female" })}><option value="male">Hombre</option><option value="female">Mujer</option></select></label>
            <label><span>Edad</span><input inputMode="numeric" value={f.age || ""} onChange={(e) => setF({ ...f, age: num(e.target.value) })} /></label>
            <label><span>Altura (cm)</span><input inputMode="decimal" value={f.height_cm || ""} onChange={(e) => setF({ ...f, height_cm: num(e.target.value) })} /></label>
          </div>
          <div className="form-row">
            <label><span>Peso (kg)</span><input inputMode="decimal" value={f.weight_kg ?? ""} placeholder={p.data?.latest_weight ? `${p.data.latest_weight} (de Gimnasio › Cuerpo)` : ""} onChange={(e) => setF({ ...f, weight_kg: e.target.value ? num(e.target.value) : null })} /></label>
            <label><span>Peso objetivo (kg)</span><input inputMode="decimal" value={f.target_weight_kg ?? ""} onChange={(e) => setF({ ...f, target_weight_kg: e.target.value ? num(e.target.value) : null })} /></label>
          </div>
          <label className="field"><span>Actividad</span><select value={f.activity} onChange={(e) => setF({ ...f, activity: Number(e.target.value) })}>{ACTIVITY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label className="field"><span>Objetivo</span><select value={f.goal} onChange={(e) => setF({ ...f, goal: e.target.value as NutritionProfile["goal"] })}>
            <option value="bulk">Ganar músculo / volumen (+300 kcal)</option><option value="maintain">Mantener</option><option value="cut">Perder grasa (−400 kcal)</option></select></label>
          <div className="form-actions"><button className="btn" type="submit" disabled={!f.age || !f.height_cm}>Guardar y calcular</button>{msg && <span role="status" className="small pos">{msg}</span>}</div>
          <p className="muted small">Si registras tu peso en Gimnasio › Cuerpo, VISTAN usa el último automáticamente.</p>
        </form>
      </Panel>
      <Panel title="Tus objetivos diarios">
        {!targets ? <Empty>Rellena tus datos para calcularlos.</Empty> : (
          <dl className="kv">
            <div><dt>Metabolismo basal</dt><dd className="mono">{n0(targets.bmr)} kcal</dd></div>
            <div><dt>Gasto diario estimado</dt><dd className="mono">{n0(targets.tdee)} kcal</dd></div>
            <div><dt>Objetivo de calorías</dt><dd className="mono">{n0(targets.kcal)} kcal</dd></div>
            <div><dt>Proteína</dt><dd className="mono">{n0(targets.protein)} g</dd></div>
            <div><dt>Hidratos</dt><dd className="mono">{n0(targets.carbs)} g</dd></div>
            <div><dt>Grasas</dt><dd className="mono">{n0(targets.fat)} g</dd></div>
            <div><dt>Peso usado</dt><dd className="mono">{targets.weight_used} kg</dd></div>
          </dl>
        )}
        <p className="muted small">Fórmula Mifflin-St Jeor. Son estimaciones: ajusta según tu evolución de peso cada 2-3 semanas. Si eres menor de edad, evita dietas extremas y consulta con un profesional si tienes dudas.</p>
      </Panel>
    </div>
  );
}

function Foods() {
  const [q, setQ] = useState("");
  const list = useAsync(() => api.foods(q));
  useEffect(() => { const t = setTimeout(() => void list.reload(), 250); return () => clearTimeout(t); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const [f, setF] = useState({ name: "", kcal: "", protein: "", carbs: "", fat: "", unit_name: "ración", unit_grams: "100" });
  const [msg, setMsg] = useState<string | null>(null);
  const num = (s: string) => Number(s.replace(",", ".")) || 0;
  async function add(e: FormEvent) {
    e.preventDefault();
    try {
      await api.addFood({ name: f.name, kcal: num(f.kcal), protein: num(f.protein), carbs: num(f.carbs), fat: num(f.fat), unit_name: f.unit_name, unit_grams: num(f.unit_grams) });
      setMsg(`Añadido: ${f.name}`); setF({ ...f, name: "", kcal: "", protein: "", carbs: "", fat: "" }); await list.reload();
    } catch (err) { setMsg((err as Error).message); }
  }
  return (
    <div className="grid grid-tasks">
      <Panel title="Añadir alimento propio">
        <form className="form" onSubmit={add}>
          <label><span>Nombre</span><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} maxLength={120} /></label>
          <p className="muted small">Valores por 100 g (míralos en la etiqueta).</p>
          <div className="form-row">
            {(["kcal", "protein", "carbs", "fat"] as const).map((k) => (
              <label key={k}><span>{{ kcal: "Kcal", protein: "Proteína", carbs: "Hidratos", fat: "Grasas" }[k]}</span><input inputMode="decimal" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></label>
            ))}
          </div>
          <div className="form-row">
            <label><span>Ración</span><input value={f.unit_name} onChange={(e) => setF({ ...f, unit_name: e.target.value })} maxLength={32} /></label>
            <label><span>Gramos por ración</span><input inputMode="decimal" value={f.unit_grams} onChange={(e) => setF({ ...f, unit_grams: e.target.value })} /></label>
          </div>
          <div className="form-actions"><button className="btn" type="submit" disabled={f.name.trim().length < 2 || !f.kcal}>Añadir</button>{msg && <span role="status" className="small">{msg}</span>}</div>
        </form>
      </Panel>
      <Panel title="Base de alimentos">
        <input type="search" className="full" placeholder="Buscar alimento…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar alimento" />
        <table className="data-table">
          <thead><tr><th>Alimento</th><th>Kcal</th><th>Prot.</th><th>Hidr.</th><th>Grasa</th><th>Ración</th></tr></thead>
          <tbody>{(list.data?.items ?? []).map((x) => (
            <tr key={x.id}><td>{x.name}{x.custom ? " ★" : ""}</td><td>{n0(x.kcal)}</td><td>{x.protein}</td><td>{x.carbs}</td><td>{x.fat}</td><td>{x.unit_name} ({n0(x.unit_grams)} g)</td></tr>
          ))}</tbody>
        </table>
        <p className="muted small">Valores medios aproximados por 100 g. ★ = añadido por ti.</p>
      </Panel>
    </div>
  );
}
