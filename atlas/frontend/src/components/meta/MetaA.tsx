import { useEffect, useState } from "react";
import { meta, type Row } from "../../api/life";
import { Stat } from "../desk/ui";
import { fmtDate, Md, State, useLoad } from "../life/kit";

export const MODES: [string, string][] = [["auto", "Automático (según complejidad)"], ["direct", "Directo (1 modelo)"], ["agents", "Agentes (datos reales)"],
  ["council", "Consejo (especialistas + crítico + verificador)"], ["research", "Investigación (fuentes web)"]];
const PH: Record<string, string> = { understand: "Comprender", formulate: "Formular", context: "Contexto", research: "Investigar", specialists: "Especialistas",
  critic: "Crítico", integrate: "Integrar", verify: "Verificar" };
const ST: Record<string, string> = { queued: "en cola", running: "en curso", waiting: "esperando investigación", done: "terminado", error: "error", cancelled: "cancelado" };
const VS: Record<string, string> = { respaldado: "con respaldo", debil: "respaldo débil", sin_respaldo: "sin respaldo", sin_fuente: "sin fuente" };
export const nd = (v: unknown, suf = "") => (v === null || v === undefined ? "N/D" : `${v}${suf}`);
const live = (s: string) => ["queued", "running", "waiting"].includes(s);

/* ───────── Consola ───────── */
export function Console({ initialRun, onRun }: { initialRun: number | null; onRun: (id: number | null) => void }) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState("auto");
  const [plan, setPlan] = useState<Row | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<number | null>(initialRun);
  const runs = useLoad<Row[]>("/runs?limit=40", [], meta);
  useEffect(() => {
    if (!runs.data?.some((r) => live(r.status))) return;
    const t = window.setInterval(runs.reload, 2500);
    return () => clearInterval(t);
  }, [runs.data]); // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (id: number | null) => { setSel(id); onRun(id); };
  return (
    <div className="desk-module">
      <div className="mod-head"><h2>META-BRAIN Console</h2><p className="muted small">El CORE interpreta tu petición, mide su complejidad, elige modo, agentes y modelos reales, reúne
        datos y memoria autorizada, coordina especialistas, pasa un <b>crítico independiente</b> y un <b>verificador</b>, y te entrega la respuesta con hechos, hipótesis e incertidumbres.
        En el chat también funciona: «piensa a fondo: …».</p></div>
      <section className="dpanel">
        <form className="meta-ask" onSubmit={(e) => { e.preventDefault(); setErr(null);
          meta.post("/runs", { text, mode }).then((r) => { setText(""); setPlan(null); pick(r.id); runs.reload(); }).catch((x: Error) => setErr(x.message)); }}>
          <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="¿Qué necesitas resolver? (p. ej. «Analiza si me conviene montar una tienda online de suplementos: costes, riesgos y plan»)"
            aria-label="Petición para el META-BRAIN" maxLength={6000} required />
          <div className="row-btns">
            <select value={mode} onChange={(e) => setMode(e.target.value)} aria-label="Modo">{MODES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <button type="button" className="btn ghost" disabled={text.trim().length < 2} onClick={() => meta.post("/analyze", { text }).then(setPlan).catch((x: Error) => setErr(x.message))}>Analizar sin ejecutar</button>
            <button type="submit" className="btn" disabled={text.trim().length < 2}>Ejecutar</button>
          </div>
        </form>
        {err && <p className="error-line" role="alert">{err}</p>}
        {plan && (
          <div className="meta-plan">
            <p className="small"><b>Complejidad {plan.label} ({plan.score}/100)</b> · modo «{plan.mode}» · {plan.reasons.join(" · ") || "sin señales"}</p>
            <p className="small">Agentes: {plan.agent_names.join(", ") || "ninguno"} · Fases: {plan.phases.map((p: string) => PH[p] ?? p).join(" → ")}</p>
            <p className="small">Modelos: {(plan.route.agents.length ? plan.route.agents : plan.route.chat).map((c: Row) => c.id).join(" → ") || <b>ninguno accesible (abre Ollama o configura un proveedor)</b>}
              {plan.local_only && <> · <span className="lab-tag t-prototype">solo local</span> {plan.local_reason}</>}</p>
          </div>
        )}
      </section>
      <div className="mod-cols">
        <section className="dpanel meta-runs">
          <header className="dpanel-head"><span>EJECUCIONES</span><span>{runs.data?.length ?? 0}</span></header>
          <State loading={runs.loading && !runs.data} error={runs.error} empty={runs.data && !runs.data.length ? "Aún no hay ejecuciones." : false}>
            <ul className="exp-list">{runs.data?.map((r) => (
              <li key={r.id}><button type="button" className={sel === r.id ? "on" : ""} onClick={() => pick(r.id)}>
                <span className={`exp-state s-${r.status === "done" ? "COMPLETED" : r.status === "error" ? "FAILED" : live(r.status) ? "RUNNING" : "ARCHIVED"}`}>{ST[r.status]}</span>
                <b>{r.request.slice(0, 70)}</b><small>#{r.id} · {r.mode} · {r.calls} llamadas · {fmtDate(r.created_at)}</small></button></li>
            ))}</ul>
          </State>
        </section>
        {sel ? <RunView id={sel} onChange={runs.reload} onDeleted={() => { pick(null); runs.reload(); }} /> : <section className="dpanel grow"><p className="desk-empty">Elige una ejecución para ver su traza completa.</p></section>}
      </div>
    </div>
  );
}

export function RunView({ id, onChange, onDeleted }: { id: number; onChange: () => void; onDeleted: () => void }) {
  const { data: r, error, loading, reload } = useLoad<Row>(`/runs/${id}`, [id], meta);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    if (!r || !live(r.status)) return;
    const t = window.setInterval(reload, 1500);
    return () => clearInterval(t);
  }, [r?.status, r?.trace?.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const act = (p: Promise<unknown>, ok?: string) => p.then(() => { if (ok) setMsg(ok); reload(); onChange(); }).catch((e: Error) => setMsg(e.message));
  if (!r) return <section className="dpanel grow"><State loading={loading} error={error} /></section>;
  const res = r.result ?? {};
  const ver = r.verification ?? {};
  const claims: Record<string, Row> = Object.fromEntries((ver.claims ?? []).map((c: Row) => [c.claim, c]));
  return (
    <section className="dpanel grow meta-run" data-testid="meta-run">
      <header className="dpanel-head"><span>#{r.id} · {ST[r.status].toUpperCase()} · {r.mode}</span>
        <span className="row-actions">
          {live(r.status) && <button type="button" className="mini-btn" onClick={() => act(meta.post(`/runs/${r.id}/cancel`), "Cancelada")}>Cancelar</button>}
          {["error", "cancelled"].includes(r.status) && <button type="button" className="mini-btn" onClick={() => act(meta.post(`/runs/${r.id}/resume`), "Reanudada desde el último checkpoint")}>Reanudar</button>}
          {r.status === "done" && <>
            <button type="button" className={`mini-btn ghost ${r.feedback === 1 ? "on" : ""}`} aria-label="Útil" onClick={() => act(meta.post(`/runs/${r.id}/feedback`, { value: 1 }))}>👍</button>
            <button type="button" className={`mini-btn ghost ${r.feedback === -1 ? "on" : ""}`} aria-label="No útil" onClick={() => act(meta.post(`/runs/${r.id}/feedback`, { value: -1 }))}>👎</button>
            <button type="button" className="mini-btn ghost" onClick={() => act(meta.post(`/runs/${r.id}/remember`), "Guardado como episodio en la memoria")}>Recordar</button></>}
          {!live(r.status) && <button type="button" className="mini-btn ghost" onClick={() => { if (window.confirm("¿Eliminar esta ejecución y su traza?")) void meta.del(`/runs/${r.id}`).then(onDeleted); }}>✕</button>}
        </span></header>
      <p className="meta-q">{r.request}</p>
      <div className="phase-line">{r.phases.map((p: string) => <span key={p} className={r.done_phases.includes(p) ? "done" : r.phase === p ? "now" : ""}>{PH[p] ?? p}</span>)}</div>
      <div className="stat-row">
        <Stat label="Complejidad" value={r.complexity?.label ? `${r.complexity.label} · ${r.complexity.score}` : "—"} />
        <Stat label="Llamadas" value={String(r.calls)} /><Stat label="Tokens salida" value={nd(r.tokens_out)} />
        <Stat label="Coste" value={nd(r.cost_usd, " $")} /><Stat label="Duración" value={r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)} s` : "—"} />
        <Stat label="Hechos con respaldo" value={ver.checked ? `${ver.supported}/${ver.checked}` : "N/D"} />
      </div>
      <p className="mini-note">Modelos: {r.models.join(", ") || "—"}{r.local_only ? " · solo modelos locales (privacidad)" : ""}{r.research_id ? ` · investigación #${r.research_id}` : ""}</p>
      {msg && <p className="small">{msg}</p>}
      {r.error && <p className="warn-line l-warn">{r.error}</p>}
      {r.answer && <div className="ai-text meta-answer"><Md text={r.answer} /></div>}
      {(res.hechos?.length || res.hipotesis?.length || res.inferencias?.length || res.opiniones?.length || res.incertidumbres?.length) ? (
        <div className="meta-kinds">
          {!!res.hechos?.length && <div className="sc-block facts"><h4>Hechos</h4><ul>{res.hechos.map((h: Row, i: number) => { const c = claims[h.texto]; return (
            <li key={i}>{h.texto} {h.evidencia && <small>[{h.evidencia}]</small>} {c && <span className={`lab-tag t-${c.status === "respaldado" ? "commercial" : c.status === "debil" ? "prototype" : "speculative"}`}>{VS[c.status]}</span>}</li>); })}</ul></div>}
          {[["hipotesis", "Hipótesis", "hyp"], ["inferencias", "Inferencias", "hyp"], ["opiniones", "Opiniones", "pred"], ["incertidumbres", "Incertidumbres", "pred"], ["siguientes_pasos", "Siguientes pasos", ""]]
            .map(([k, l, c]) => res[k]?.length ? <div key={k} className={`sc-block ${c}`}><h4>{l}</h4><ul>{res[k].map((x: string) => <li key={x}>{x}</li>)}</ul></div> : null)}
        </div>) : null}
      {!!r.critique?.issues?.length && (
        <details open className="meta-sec"><summary>Crítico y verificación · {r.critique.issues.length} aviso(s){r.critique.veredicto ? ` · veredicto: ${r.critique.veredicto}` : ""}</summary>
          <ul className="disc-list">{r.critique.issues.map((i: Row, k: number) => <li key={k}><b>{i.tipo}</b> <span className={`lab-tag t-${i.gravedad === "alta" ? "rel-baja" : i.gravedad === "media" ? "rel-media" : "rel-alta"}`}>{i.gravedad}</span>
            <small>{i.por}{i.afecta ? ` · afecta: ${i.afecta}` : ""}</small><p className="small">{i.detalle}</p></li>)}</ul>
          {!!r.critique.comprobado?.length && <p className="mini-note">El crítico comprobó: {r.critique.comprobado.join(" · ")}</p>}
          {ver.note && <p className="mini-note">{ver.note}</p>}
        </details>)}
      {r.specialists && <details className="meta-sec"><summary>Especialistas ({Object.keys(r.specialists).length}) · análisis independientes</summary>
        {Object.entries(r.specialists as Record<string, Row>).map(([k, s]) => <div key={k} className="sc-card"><b>{s.agent}</b><small>{s.model} · confianza {s.confianza}</small>
          <p className="small">{s.analisis}</p>{!!s.riesgos?.length && <p className="mini-note">Riesgos: {s.riesgos.join("; ")}</p>}
          {!!s.incertidumbres?.length && <p className="mini-note">Incertidumbres: {s.incertidumbres.join("; ")}</p>}</div>)}</details>}
      {!!r.evidence?.length && <details className="meta-sec"><summary>Evidencias ({r.evidence.length})</summary>
        <ul className="disc-list">{r.evidence.map((e: Row) => <li key={e.id}><b>{e.id}</b> {e.url ? <a href={e.url} target="_blank" rel="noreferrer noopener">{e.label}</a> : e.label}
          <small>{e.kind}{e.reliability ? ` · fiabilidad ${e.reliability}` : ""}{e.accessed_at ? ` · consultada ${fmtDate(e.accessed_at)}` : ""}</small><p className="small">{e.text.slice(0, 260)}</p></li>)}</ul></details>}
      <details className="meta-sec" open={live(r.status)}><summary>Traza ({r.trace?.length ?? 0} eventos)</summary>
        <ol className="trace">{(r.trace ?? []).map((t: Row, i: number) => <li key={i} className={t.ok ? "" : "bad"}><time>{t.t.slice(11, 19)}</time><b>{PH[t.phase] ?? t.phase}</b><span>{t.actor}</span><p>{t.msg}</p></li>)}</ol></details>
    </section>
  );
}
