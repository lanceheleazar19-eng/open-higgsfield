import { useEffect, useState } from "react";
import { lab, type Row } from "../../api/life";
import { Stat } from "../desk/ui";
import { fmtDate, SchemaForm, State, useLoad } from "../life/kit";
import { EXP_FIELDS, type Meta } from "./LabA";

const VERD: Record<string, string> = { supported: "Hipótesis respaldada", refuted: "Hipótesis refutada", inconclusive: "No concluyente" };

/* ───────── Experimentation Engine ───────── */
export function Experiments({ meta }: { meta: Meta }) {
  const [st, setSt] = useState("");
  const list = useLoad<Row[]>(`/experiments${st ? `?status=${st}` : ""}`, [st], lab);
  const [sel, setSel] = useState<number | null>(null);
  const [mode, setMode] = useState<"view" | "edit" | "new">("view");
  const tr = useLoad<Row>(sel ? `/experiments/${sel}/trials` : null, [sel], lab);
  const [ai, setAi] = useState<Row | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [trial, setTrial] = useState({ version: "", params: "", metrics: "", observed: "", evidence: "", outcome: "inconclusive" });
  const e = tr.data?.experiment;
  const kv = (s: string) => Object.fromEntries(s.split(",").map((x) => x.split("=").map((y) => y.trim())).filter((x) => x.length === 2 && x[0])
    .map(([k, v]) => [k, isNaN(Number(v.replace(",", "."))) ? v : Number(v.replace(",", "."))]));
  const run = (k: string, fn: () => Promise<unknown>) => { setBusy(k); setErr(null); fn().catch((x: Error) => setErr(x.message)).finally(() => setBusy(null)); };
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Experimentation Engine</h2><p className="muted small">Hipótesis, metodología, resultados esperados frente a observados y registro de pruebas por versión. Un experimento no se marca como exitoso sin resultados y evidencias.</p></div>
      <div className="filters">
        <select value={st} onChange={(x) => setSt(x.target.value)} aria-label="Estado"><option value="">Todos los estados</option>{meta.states.map((s) => <option key={s}>{s}</option>)}</select>
        <button type="button" className="btn" onClick={() => { setMode("new"); setSel(null); }}>+ Experimento</button>
      </div>
      {mode === "new" && <section className="dpanel"><SchemaForm fields={EXP_FIELDS(meta)} initial={{ status: "IDEA" }} submitLabel="Crear" onCancel={() => setMode("view")}
        onSubmit={(v) => lab.post("/experiments", v).then((x) => { setSel(x.id); setMode("view"); list.reload(); })} /></section>}
      <div className="mod-cols">
        <section className="dpanel">
          <State loading={list.loading && !list.data} error={list.error} empty={list.data && !list.data.length ? "Aún no hay experimentos." : false}>
            <ul className="exp-list">{list.data?.map((x) => (
              <li key={x.id}><button type="button" className={sel === x.id ? "on" : ""} onClick={() => { setSel(x.id); setMode("view"); setAi(null); }}>
                <span className={`exp-state s-${x.status}`}>{x.status}</span><b>{x.name}</b>
                <small>{x.verdict ? VERD[x.verdict] : x.hypothesis?.slice(0, 80) ?? ""}</small></button></li>
            ))}</ul>
          </State>
        </section>
        {e && (
          <section className="dpanel grow">
            <header className="dpanel-head"><span>{e.name.toUpperCase()} · {e.status}</span>
              <span className="row-actions">
                <button type="button" className="mini-btn ghost" onClick={() => setMode(mode === "edit" ? "view" : "edit")}>{mode === "edit" ? "Cerrar" : "Editar"}</button>
                <button type="button" className="mini-btn ghost" disabled={!!busy} onClick={() => run("d", () => lab.post(`/experiments/${e.id}/design`).then(setAi))}>{busy === "d" ? "…" : "Diseñar metodología (IA)"}</button>
                <button type="button" className="mini-btn ghost" disabled={!!busy} onClick={() => run("v", () => lab.post(`/experiments/${e.id}/evaluate`).then(setAi))}>{busy === "v" ? "…" : "Evaluar resultados (IA)"}</button>
                <button type="button" className="mini-btn ghost" onClick={() => run("p", () => lab.post("/projects", { kind: "experiment", id: e.id }).then(() => setErr("Proyecto creado en Proyectos")))}>→ Proyecto</button>
                <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar el experimento y sus pruebas?")) void lab.del(`/experiments/${e.id}`).then(() => { setSel(null); list.reload(); }); }}>Eliminar</button>
              </span></header>
            {mode === "edit" ? <SchemaForm key={e.updated_at} fields={EXP_FIELDS(meta)} initial={e} onCancel={() => setMode("view")}
              onSubmit={(v) => lab.patch(`/experiments/${e.id}`, v).then(() => { setMode("view"); tr.reload(); list.reload(); })} /> : (
              <>
                <div className="exp-compare">
                  <div><small>HIPÓTESIS</small><p>{e.hypothesis ?? "—"}</p></div>
                  <div><small>RESULTADO ESPERADO</small><p>{e.expected ?? "—"}</p></div>
                  <div><small>RESULTADO OBSERVADO</small><p>{e.observed ?? "sin resultados todavía"}</p></div>
                  <div><small>VEREDICTO</small><p className={e.verdict === "supported" ? "up" : e.verdict === "refuted" ? "down" : ""}>{e.verdict ? VERD[e.verdict] : "Sin veredicto"}</p></div>
                </div>
                <dl className="opp-dl">{[["objective", "Objetivo"], ["methodology", "Metodología"], ["variables", "Variables"], ["resources", "Recursos"], ["evidence", "Evidencias"], ["conclusion", "Conclusión"]]
                  .filter(([k]) => e[k]).map(([k, l]) => <div key={k}><dt>{l}</dt><dd>{e[k]}</dd></div>)}</dl>
                <p className="mini-note">Inicio {fmtDate(e.started_on)} · Fin {fmtDate(e.finished_on)} · {e.hours} h · {e.cost} €</p>
              </>
            )}
            {err && <p className="small">{err}</p>}
            {ai && <div className="ai-text"><p className="callout small">{ai.note} · {ai.model}</p>
              {ai.metodologia && <p><b>Metodología:</b> {ai.metodologia}</p>}
              {ai.variables && <p className="small"><b>Variables:</b> independientes {(ai.variables.independientes ?? []).join(", ")} · dependientes {(ai.variables.dependientes ?? []).join(", ")} · controladas {(ai.variables.controladas ?? []).join(", ")}</p>}
              {ai.criterio_exito && <p className="small"><b>Éxito si:</b> {ai.criterio_exito} · <b>Fracaso si:</b> {ai.criterio_fracaso}</p>}
              {ai.comparacion && <p>{ai.comparacion}</p>}
              {ai.veredicto_sugerido && <p className="small"><b>Veredicto sugerido:</b> {VERD[ai.veredicto_sugerido] ?? ai.veredicto_sugerido} — {ai.por_que}</p>}
              {!!ai.evidencia_que_falta?.length && <p className="small"><b>Falta evidencia:</b> {ai.evidencia_que_falta.join("; ")}</p>}
              {ai.siguiente_experimento && <p className="small"><b>Siguiente experimento:</b> {ai.siguiente_experimento}</p>}</div>}
            <header className="dpanel-head"><span>REGISTRO DE PRUEBAS · COMPARACIÓN DE VERSIONES</span></header>
            {!!tr.data?.trials.length && (
              <div className="table-scroll"><table className="dtable compact">
                <thead><tr><th>Versión</th><th>Parámetros</th>{tr.data.metric_keys.map((k: string) => <th key={k}>{k}</th>)}<th>Resultado</th><th>Fecha</th><th /></tr></thead>
                <tbody>{tr.data.trials.map((t: Row) => (
                  <tr key={t.id}><td>{t.version}</td><td className="small">{Object.entries(t.params).map(([k, v]) => `${k}=${v}`).join(", ") || "—"}</td>
                    {tr.data!.metric_keys.map((k: string) => <td key={k} className="mono">{t.metrics?.[k] ?? "—"}</td>)}
                    <td><span className={`st st-${t.outcome === "pass" ? "filled" : t.outcome === "fail" ? "rejected" : "pending"}`}>{t.outcome}</span></td>
                    <td className="mono">{fmtDate(t.ran_at)}</td>
                    <td className="row-actions"><button type="button" className="mini-btn ghost" title="Repetir con los mismos parámetros" onClick={() => lab.post(`/experiments/${e.id}/trials/${t.id}/repeat`).then(tr.reload)}>Repetir</button>
                      <button type="button" className="mini-btn ghost" onClick={() => lab.del(`/experiments/${e.id}/trials/${t.id}`).then(tr.reload)}>✕</button></td></tr>
                ))}</tbody></table></div>
            )}
            <form className="life-form" onSubmit={(x) => { x.preventDefault(); setErr(null);
              lab.post(`/experiments/${e.id}/trials`, { version: trial.version, params: kv(trial.params), metrics: kv(trial.metrics), observed: trial.observed || null, evidence: trial.evidence || null, outcome: trial.outcome })
                .then(() => { setTrial({ version: "", params: "", metrics: "", observed: "", evidence: "", outcome: "inconclusive" }); tr.reload(); }).catch((y: Error) => setErr(y.message)); }}>
              <label><span>Versión *</span><input value={trial.version} onChange={(x) => setTrial({ ...trial, version: x.target.value })} required aria-label="Versión de la prueba" /></label>
              <label><span>Parámetros (k=v, …)</span><input value={trial.params} onChange={(x) => setTrial({ ...trial, params: x.target.value })} aria-label="Parámetros" placeholder="modelo=qwen, k=4" /></label>
              <label><span>Métricas medidas (k=v, …)</span><input value={trial.metrics} onChange={(x) => setTrial({ ...trial, metrics: x.target.value })} aria-label="Métricas" placeholder="precision=0.78, latencia_ms=420" /></label>
              <label><span>Resultado</span><select value={trial.outcome} onChange={(x) => setTrial({ ...trial, outcome: x.target.value })} aria-label="Resultado de la prueba"><option value="inconclusive">No concluyente</option><option value="pass">Pasa</option><option value="fail">Falla</option></select></label>
              <label className="wide"><span>Observaciones</span><textarea rows={2} value={trial.observed} onChange={(x) => setTrial({ ...trial, observed: x.target.value })} aria-label="Observaciones" /></label>
              <label className="wide"><span>Evidencia (enlace, archivo, dato)</span><input value={trial.evidence} onChange={(x) => setTrial({ ...trial, evidence: x.target.value })} aria-label="Evidencia" /></label>
              <div className="row-btns wide"><button type="submit" className="btn">Registrar prueba</button></div>
            </form>
          </section>
        )}
      </div>
    </div>
  );
}

/* ───────── AI Research Lab · Model Testing Arena ───────── */
export function AiLab() {
  const models = useLoad<Row[]>("/arena/models", [], lab);
  const suites = useLoad<Row[]>("/arena/suites", [], lab);
  const [suite, setSuite] = useState<number | null>(null);
  const runs = useLoad<Row[]>(suite ? `/arena/runs?suite_id=${suite}` : null, [suite], lab);
  const [chosen, setChosen] = useState<string[]>([]);
  const [judge, setJudge] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [tests, setTests] = useState([{ prompt: "", check: "contains", expected: "", rag: false }]);
  const [name, setName] = useState("");
  useEffect(() => {
    if (!runs.data?.some((r) => ["queued", "running"].includes(r.status))) return;
    const t = setInterval(runs.reload, 3000);
    return () => clearInterval(t);
  }, [runs.data]); // eslint-disable-line react-hooks/exhaustive-deps
  const s = suites.data?.find((x) => x.id === suite);
  const latest = new Map<string, Row>();
  runs.data?.forEach((r) => { if (!latest.has(r.model)) latest.set(r.model, r); });
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>AI Research Lab · Model Testing Arena</h2><p className="muted small">Ejecuta la misma batería de pruebas en los modelos <b>realmente configurados</b> (Ollama instalado o nube con clave). Latencia medida, tokens informados por el proveedor (si no, N/D) y coste según los precios que configures en Modelos.</p></div>
      <section className="dpanel"><header className="dpanel-head"><span>MODELOS DISPONIBLES</span></header>
        <State loading={models.loading && !models.data} error={models.error} empty={models.data && !models.data.length ? "No hay modelos accesibles: abre Ollama o configura una clave en Configuración → Modelos." : false}>
          <div className="filters">{models.data?.map((m) => (
            <label key={m.id} className="check"><input type="checkbox" checked={chosen.includes(m.id)} onChange={() => setChosen(chosen.includes(m.id) ? chosen.filter((x) => x !== m.id) : [...chosen, m.id])} /> {m.id} <small>{m.local ? "local" : "nube"}</small></label>
          ))}</div>
        </State></section>
      <div className="mod-cols">
        <section className="dpanel">
          <header className="dpanel-head"><span>BATERÍAS DE PRUEBAS</span></header>
          <ul className="life-list compact">{suites.data?.map((x) => <li key={x.id}><div className="life-item"><button type="button" className={`link-btn plain ${suite === x.id ? "on" : ""}`} onClick={() => setSuite(x.id)}>{x.name}</button> <small>{x.tests.length} pruebas</small></div>
            <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar la batería y sus resultados?")) void lab.del(`/arena/suites/${x.id}`).then(suites.reload); }}>✕</button></li>)}</ul>
          <form className="life-form" onSubmit={(e) => { e.preventDefault(); setErr(null);
            lab.post("/arena/suites", { name, tests: tests.filter((t) => t.prompt.trim()) }).then((x) => { setSuite(x.id); setName(""); setTests([{ prompt: "", check: "contains", expected: "", rag: false }]); suites.reload(); }).catch((y: Error) => setErr(y.message)); }}>
            <label className="wide"><span>Nueva batería *</span><input value={name} onChange={(e) => setName(e.target.value)} required aria-label="Nombre de la batería" placeholder="Razonamiento y precisión" /></label>
            {tests.map((t, i) => (
              <div key={i} className="wide test-row">
                <textarea rows={2} value={t.prompt} onChange={(e) => setTests(tests.map((x, j) => (j === i ? { ...x, prompt: e.target.value } : x)))} aria-label={`Prompt ${i + 1}`} placeholder={`Prueba ${i + 1}: prompt`} />
                <select value={t.check} onChange={(e) => setTests(tests.map((x, j) => (j === i ? { ...x, check: e.target.value } : x)))} aria-label={`Comprobación ${i + 1}`}>
                  <option value="contains">Contiene</option><option value="exact">Exacta</option><option value="regex">Regex</option><option value="judge">Modelo juez</option><option value="none">Sin puntuar</option></select>
                <input value={t.expected} onChange={(e) => setTests(tests.map((x, j) => (j === i ? { ...x, expected: e.target.value } : x)))} aria-label={`Esperado ${i + 1}`} placeholder={t.check === "judge" ? "Criterio para el juez" : "Resultado esperado"} />
                <label className="check small"><input type="checkbox" checked={t.rag} onChange={(e) => setTests(tests.map((x, j) => (j === i ? { ...x, rag: e.target.checked } : x)))} /> RAG</label>
              </div>
            ))}
            <div className="row-btns wide"><button type="button" className="btn ghost" onClick={() => setTests([...tests, { prompt: "", check: "contains", expected: "", rag: false }])}>+ prueba</button><button type="submit" className="btn">Crear batería</button></div>
          </form>
        </section>
        {s && (
          <section className="dpanel grow">
            <header className="dpanel-head"><span>{s.name.toUpperCase()}</span></header>
            <div className="filters">
              <select value={judge} onChange={(e) => setJudge(e.target.value)} aria-label="Modelo juez"><option value="">Sin modelo juez</option>{models.data?.map((m) => <option key={m.id} value={m.id}>Juez: {m.id}</option>)}</select>
              <button type="button" className="btn" disabled={!chosen.length} onClick={() => lab.post("/arena/runs", { suite_id: s.id, models: chosen, judge: judge || null }).then(runs.reload).catch((e: Error) => setErr(e.message))}>Ejecutar en {chosen.length} modelo(s)</button>
            </div>
            {!!latest.size && (
              <div className="table-scroll"><table className="dtable">
                <thead><tr><th>Modelo</th><th>Estado</th><th>Precisión / calidad</th><th>Latencia media</th><th>Tokens</th><th>Tokens/s</th><th>Coste</th><th>Fiabilidad</th><th>Errores</th></tr></thead>
                <tbody>{[...latest.values()].map((r) => (
                  <tr key={r.id}><td><b>{r.model}</b></td><td>{r.status}{r.status === "running" ? ` (${r.results.length}/${s.tests.length})` : ""}</td>
                    <td className="mono">{r.summary.avg_score != null ? `${r.summary.avg_score}/100 (${r.summary.scored})` : "N/D"}</td>
                    <td className="mono">{r.summary.avg_latency_ms != null ? `${r.summary.avg_latency_ms} ms` : "—"}</td>
                    <td className="mono">{r.summary.tokens_out ?? "N/D"}</td><td className="mono">{r.summary.tokens_per_s ?? "N/D"}</td>
                    <td className="mono">{r.summary.cost_usd != null ? `${r.summary.cost_usd} $` : "N/D"}</td>
                    <td className="mono">{r.summary.reliability_pct != null ? `${r.summary.reliability_pct} %` : "—"}</td><td className="mono">{r.summary.errors ?? "—"}</td></tr>
                ))}</tbody></table></div>
            )}
            {s.tests.map((t: Row, i: number) => (
              <details key={i} className="arena-test"><summary>Prueba {i + 1}: {t.prompt.slice(0, 90)} <small>({t.check}{t.rag ? ", RAG" : ""})</small></summary>
                {[...latest.values()].map((r) => { const x = r.results.find((y: Row) => y.i === i); return x ? (
                  <div key={r.id} className="arena-out"><b>{r.model}</b> <small>{x.latency_ms} ms · {x.tokens_out ?? "N/D"} tokens · {x.score != null ? `${x.score}/100 (${x.scored_by})` : x.scored_by ?? ""}{x.rag ? ` · ${x.rag}` : ""}</small>
                    {x.error ? <p className="error-line">{x.error}</p> : <pre>{x.output}</pre>}</div>) : null; })}
              </details>
            ))}
          </section>
        )}
      </div>
      {err && <p className="error-line">{err}</p>}
    </div>
  );
}

/* ───────── Prototype Studio + sandbox ───────── */
const PROTO_KIND: [string, string][] = [["app", "Aplicación"], ["tool", "Herramienta digital"], ["web", "Página web"], ["automation", "Automatización"], ["agent", "Agente de IA"],
  ["saas", "Producto SaaS"], ["ui", "Interfaz"], ["analytics", "Sistema de análisis"], ["software", "Experimento de software"]];
const PROTO_STATUS: [string, string][] = [["concept", "Concepto"], ["building", "En desarrollo"], ["testing", "Probando"], ["done", "Terminado"], ["abandoned", "Abandonado"]];

export function Prototypes() {
  const list = useLoad<Row[]>("/prototypes", [], lab);
  const [sel, setSel] = useState<number | null>(null);
  const det = useLoad<Row>(sel ? `/prototypes/${sel}/detail` : null, [sel], lab);
  const [mode, setMode] = useState<"view" | "edit" | "new">("view");
  const [code, setCode] = useState("print('Hola desde el sandbox')");
  const [out, setOut] = useState<Row | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const p = det.data?.prototype;
  const fields = [{ k: "name", label: "Nombre", required: true }, { k: "kind", label: "Tipo", type: "select" as const, options: PROTO_KIND, required: true },
    { k: "status", label: "Estado", type: "select" as const, options: PROTO_STATUS, required: true }, { k: "description", label: "Descripción", type: "textarea" as const },
    { k: "problem", label: "Problema que resuelve", type: "textarea" as const }, { k: "goal", label: "Objetivo", type: "textarea" as const },
    { k: "tech", label: "Tecnologías", type: "textarea" as const }, { k: "architecture", label: "Arquitectura", type: "textarea" as const },
    { k: "tests", label: "Pruebas", type: "textarea" as const }, { k: "results", label: "Resultados", type: "textarea" as const },
    { k: "hours", label: "Horas", type: "number" as const }, { k: "cost", label: "Coste (€)", type: "number" as const }];
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Prototype Studio</h2><p className="muted small">Versiones, archivos, capturas, pruebas y resultados. El código solo se ejecuta en el <b>sandbox aislado</b> (proceso aparte, sin red, sin acceso a tus archivos ni claves, límites de CPU/memoria y 10 s) y siempre con tu confirmación.</p></div>
      <button type="button" className="btn" onClick={() => { setMode("new"); setSel(null); }}>+ Prototipo</button>
      {mode === "new" && <section className="dpanel"><SchemaForm fields={fields} initial={{ kind: "app", status: "concept" }} submitLabel="Crear" onCancel={() => setMode("view")}
        onSubmit={(v) => lab.post("/prototypes", v).then((x) => { setSel(x.id); setMode("view"); list.reload(); })} /></section>}
      <div className="mod-cols">
        <section className="dpanel">
          <State loading={list.loading && !list.data} error={list.error} empty={list.data && !list.data.length ? "Aún no hay prototipos." : false}>
            <ul className="exp-list">{list.data?.map((x) => <li key={x.id}><button type="button" className={sel === x.id ? "on" : ""} onClick={() => { setSel(x.id); setMode("view"); setOut(null); }}>
              <span className="exp-state">{PROTO_STATUS.find((s) => s[0] === x.status)?.[1]}</span><b>{x.name}</b><small>{PROTO_KIND.find((k) => k[0] === x.kind)?.[1]}</small></button></li>)}</ul>
          </State>
        </section>
        {p && (
          <section className="dpanel grow">
            <header className="dpanel-head"><span>{p.name.toUpperCase()}</span>
              <span className="row-actions">
                <button type="button" className="mini-btn ghost" onClick={() => setMode(mode === "edit" ? "view" : "edit")}>{mode === "edit" ? "Cerrar" : "Editar"}</button>
                {!p.project_id && <button type="button" className="mini-btn ghost" onClick={() => lab.post("/projects", { kind: "prototype", id: p.id }).then(() => { setMsg("Proyecto creado"); det.reload(); })}>→ Proyecto</button>}
                <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar el prototipo, sus versiones y archivos?")) void lab.del(`/prototypes/${p.id}`).then(() => { setSel(null); list.reload(); }); }}>Eliminar</button>
              </span></header>
            {mode === "edit" ? <SchemaForm key={p.updated_at} fields={fields} initial={p} onCancel={() => setMode("view")} onSubmit={(v) => lab.patch(`/prototypes/${p.id}`, v).then(() => { setMode("view"); det.reload(); list.reload(); })} />
              : <dl className="opp-dl">{fields.slice(3, 10).filter((f) => p[f.k]).map((f) => <div key={f.k}><dt>{f.label}</dt><dd>{p[f.k]}</dd></div>)}</dl>}
            {msg && <p className="small">{msg}</p>}
            <header className="dpanel-head"><span>VERSIONES</span></header>
            <SchemaForm fields={[{ k: "version", label: "Versión", required: true, placeholder: "v0.1" }, { k: "notes", label: "Cambios", type: "textarea" }]} submitLabel="Añadir versión"
              onSubmit={(v) => lab.post(`/prototypes/${p.id}/versions`, v).then(det.reload)} />
            <ul className="life-list compact">{det.data!.versions.map((v: Row) => <li key={v.id}><div className="life-item"><b>{v.version}</b> <small>{fmtDate(v.created_at)}</small> {v.notes}</div></li>)}</ul>
            <header className="dpanel-head"><span>ARCHIVOS Y CAPTURAS</span></header>
            <label className="file-btn">Subir archivo o captura
              <input type="file" hidden onChange={(e) => { const f = e.target.files?.[0]; if (!f) return; const fd = new FormData(); fd.append("file", f);
                fetch(`/api/lab/prototypes/${p.id}/files`, { method: "POST", body: fd }).then(async (r) => { if (!r.ok) throw new Error((await r.json()).detail); det.reload(); }).catch((x: Error) => setMsg(x.message)); e.target.value = ""; }} />
            </label>
            <div className="file-grid">{det.data!.files.map((f: Row) => (
              <div key={f.id} className="file-card">{f.is_image ? <img src={`/api/lab/files/${f.id}`} alt={f.name} /> : <span className="file-ico">{f.name.split(".").pop()}</span>}
                <a href={`/api/lab/files/${f.id}`}>{f.name}</a><small>{Math.round(f.size / 1024)} KB</small>
                <button type="button" className="mini-btn ghost" onClick={() => lab.del(`/files/${f.id}`).then(det.reload)}>✕</button></div>
            ))}</div>
            <p className="mini-note">Los archivos se guardan en privado y se descargan tal cual; nunca se ejecutan ni se interpretan dentro de VISTAN.</p>
            <header className="dpanel-head"><span>SANDBOX AISLADO · PYTHON</span></header>
            <textarea className="code" rows={8} value={code} onChange={(e) => setCode(e.target.value)} spellCheck={false} aria-label="Código Python" />
            <div className="row-btns">
              <button type="button" className="btn danger" onClick={() => { if (!window.confirm("¿Ejecutar este código en el sandbox aislado? (sin red, sin acceso a tus archivos, máx. 10 s)")) return;
                lab.post("/sandbox/run", { code, prototype_id: p.id, confirm: true }).then((r) => { setOut(r); det.reload(); }).catch((x: Error) => setMsg(x.message)); }}>Ejecutar en sandbox</button>
            </div>
            {out && <div className={`sandbox-out s-${out.status}`}><small>{out.status} · {out.duration_ms} ms · código de salida {out.exit_code ?? "—"}</small>{out.stdout && <pre>{out.stdout}</pre>}{out.stderr && <pre className="err">{out.stderr}</pre>}</div>}
            {!!det.data!.runs.length && <p className="mini-note">Historial: {det.data!.runs.map((r: Row) => `${fmtDate(r.created_at)} ${r.status}`).join(" · ")}</p>}
          </section>
        )}
      </div>
    </div>
  );
}

export function AnalyticsLab({ meta }: { meta: Meta }) {
  const [f, setF] = useState({ start: "", end: "", category: "" });
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]).toString();
  const { data, error, loading } = useLoad<Row>(`/analytics${qs ? `?${qs}` : ""}`, [qs], lab);
  const max = Math.max(1, ...(data?.months ?? []).map((m: Row) => (m.experiments ?? 0) + (m.ideas ?? 0) + (m.discoveries ?? 0) + (m.research ?? 0) + (m.prototypes ?? 0)));
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>Innovation Analytics</h2><p className="muted small">Todo contado en tus registros. {data?.note}</p></div>
      <div className="filters">
        <input type="date" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} aria-label="Desde" />
        <input type="date" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} aria-label="Hasta" />
        <select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} aria-label="Categoría"><option value="">Todas las categorías</option>{Object.entries(meta.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      </div>
      <State loading={loading && !data} error={error}>
        {data && (
          <>
            <div className="stat-row">
              <Stat label="Investigaciones completadas" value={`${data.research_done}/${data.research_total}`} /><Stat label="Experimentos" value={String(data.experiments)} />
              <Stat label="Hipótesis respaldadas" value={String(data.experiments_supported)} /><Stat label="Refutadas" value={String(data.experiments_refuted)} />
              <Stat label="Fallidos" value={String(data.experiments_failed)} /><Stat label="Prototipos" value={`${data.prototypes} (${data.prototypes_done} terminados)`} />
              <Stat label="Ideas" value={`${data.ideas} (${data.ideas_generated} IA)`} /><Stat label="Ideas convertidas" value={String(data.ideas_converted)} />
              <Stat label="Tiempo dedicado" value={`${data.hours} h`} /><Stat label="Costes registrados" value={`${data.costs} €`} />
              <Stat label="Tecnologías" value={String(data.technologies)} /><Stat label="Descubrimientos" value={String(data.discoveries)} />
            </div>
            <section className="dpanel"><header className="dpanel-head"><span>EVOLUCIÓN DEL LABORATORIO</span></header>
              {!data.months.length ? <p className="desk-empty">Sin actividad en el periodo.</p> : (
                <div className="stack-chart">{data.months.map((m: Row) => (
                  <div key={m.month}><div className="stack">{["research", "discoveries", "experiments", "prototypes", "ideas"].map((k) => m[k] ? <i key={k} className={`k-${k}`} style={{ height: `${(m[k] / max) * 100}%` }} title={`${k}: ${m[k]}`} /> : null)}</div><small>{m.month}</small></div>
                ))}</div>
              )}
              <div className="legend">{[["research", "Investigaciones"], ["discoveries", "Descubrimientos"], ["experiments", "Experimentos"], ["prototypes", "Prototipos"], ["ideas", "Ideas"]].map(([k, l]) => <span key={k}><i className={`dot k-${k}`} /> {l}</span>)}</div>
            </section>
            <div className="mod-cols">
              <section className="dpanel"><header className="dpanel-head"><span>POR CATEGORÍA</span></header>
                <ul className="bars">{data.by_category.map(([k, n]: [string, number]) => <li key={k}><span>{meta.categories[k] ?? k}</span><i style={{ width: `${(n / Math.max(1, data.by_category[0][1])) * 100}%` }} /><b className="mono">{n}</b></li>)}</ul></section>
              <section className="dpanel"><header className="dpanel-head"><span>POR MADUREZ</span></header>
                <ul className="bars">{data.by_maturity.map(([k, n]: [string, number]) => <li key={k}><span>{meta.maturity[k] ?? k}</span><i style={{ width: `${(n / Math.max(1, data.by_maturity[0][1])) * 100}%` }} /><b className="mono">{n}</b></li>)}</ul></section>
            </div>
          </>
        )}
      </State>
    </div>
  );
}
