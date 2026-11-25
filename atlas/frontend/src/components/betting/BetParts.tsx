import { useEffect, useState } from "react";
import { bets, type BEvent, type LegIn, type Meta, type OddsRow, type Prediction, type SlipAnalysis } from "../../api/betting";
import { dt, money, num, pct, toNum } from "../desk/ui";

export const pp = (p: number | null | undefined, d = 1) => (p === null || p === undefined ? "N/D" : `${num(p * 100, d)} %`);
const SPORT_ICON: Record<string, string> = { football: "⚽", basketball: "🏀", tennis: "🎾", f1: "🏁", other: "◆" };
export const sportIcon = (s: string) => SPORT_ICON[s] ?? "◆";

/* ─────────── Lista de eventos ─────────── */
export function EventList({ events, meta, selected, onSelect, onReload }: {
  events: BEvent[]; meta: Meta; selected: number | null; onSelect: (id: number) => void; onReload: () => void;
}) {
  const [sport, setSport] = useState("");
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ sport: "football", competition: "", home: "", away: "", participants: "", starts_at: "", notes: "" });
  const [err, setErr] = useState<string | null>(null);
  const list = events.filter((e) => (!sport || e.sport === sport) && (!q || `${e.name} ${e.competition}`.toLowerCase().includes(q.toLowerCase())));
  return (
    <aside className="watch bet-events">
      <header className="dpanel-head"><span>EVENTOS</span><button type="button" className="link-btn" onClick={() => setAdding(!adding)}>{adding ? "cerrar" : "+ manual"}</button></header>
      <div className="filters pad">
        <select value={sport} onChange={(e) => setSport(e.target.value)} aria-label="Deporte">
          <option value="">Todos</option>{Object.entries(meta.sports).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar…" aria-label="Buscar evento" />
      </div>
      {adding && (
        <form className="mini-form" onSubmit={(e) => {
          e.preventDefault(); setErr(null);
          bets.createEvent({ sport: f.sport as BEvent["sport"], competition: f.competition || undefined, home: f.home || undefined, away: f.away || undefined,
            name: f.sport === "f1" ? f.competition || "Gran Premio" : undefined, participants: f.participants.split(",").map((x) => x.trim()).filter(Boolean),
            starts_at: new Date(f.starts_at).toISOString(), notes: f.notes || undefined })
            .then((ev) => { setAdding(false); onReload(); onSelect(ev.id); }).catch((x: Error) => setErr(x.message));
        }}>
          <select value={f.sport} onChange={(e) => setF({ ...f, sport: e.target.value })} aria-label="Deporte del evento">{Object.entries(meta.sports).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <input value={f.competition} onChange={(e) => setF({ ...f, competition: e.target.value })} placeholder={f.sport === "f1" ? "Gran Premio" : "Competición"} aria-label="Competición" />
          {f.sport === "f1" ? (
            <input value={f.participants} onChange={(e) => setF({ ...f, participants: e.target.value })} placeholder="Pilotos (separados por comas)" aria-label="Pilotos" />
          ) : (
            <>
              <input value={f.home} onChange={(e) => setF({ ...f, home: e.target.value })} placeholder={f.sport === "tennis" ? "Jugador 1" : "Local"} aria-label="Local" required />
              <input value={f.away} onChange={(e) => setF({ ...f, away: e.target.value })} placeholder={f.sport === "tennis" ? "Jugador 2" : "Visitante"} aria-label="Visitante" required />
            </>
          )}
          <input type="datetime-local" value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} aria-label="Inicio" required />
          <textarea value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} placeholder="Notas: bajas confirmadas, contexto… (opcional)" rows={2} aria-label="Notas" />
          <button type="submit" className="btn">Crear evento</button>
          {err && <p className="error-line">{err}</p>}
        </form>
      )}
      {!list.length ? <p className="desk-empty">Sin eventos. Importa calendarios reales en «Fuentes» o crea uno manual.</p> : (
        <ul>{list.map((e) => (
          <li key={e.id}><button type="button" className={selected === e.id ? "on" : ""} onClick={() => onSelect(e.id)}>
            <span className="w-sym">{sportIcon(e.sport)} {e.name}</span>
            <span className="mono w-px">{dt(e.starts_at)}</span>
            <span className="w-ch small">{e.competition ?? ""} · {statusLabel(e.status)}{e.result && "home" in e.result ? ` · ${String(e.result.home)}-${String(e.result.away)}` : ""}</span>
          </button></li>
        ))}</ul>
      )}
    </aside>
  );
}

export const statusLabel = (s: string) => ({ scheduled: "programado", live: "en juego", finished: "terminado", postponed: "aplazado", cancelled: "cancelado" }[s] ?? s);

/* ─────────── Selector de mercado (añadir al boleto) ─────────── */
export function MarketPicker({ ev, meta, onAdd, preset }: {
  ev: BEvent; meta: Meta; onAdd: (leg: LegIn & { label: string }) => void; preset?: Partial<LegIn> | null;
}) {
  const markets = Object.entries(meta.markets).filter(([, m]) => m.sports.includes(ev.sport));
  const [market, setMarket] = useState(markets[0]?.[0] ?? "");
  const [pick, setPick] = useState("");
  const [line, setLine] = useState("");
  const [opp, setOpp] = useState("");
  const [stat, setStat] = useState({ name: "", side: "over" });
  const [odds, setOdds] = useState("");
  const [src, setSrc] = useState("manual");
  const [mp, setMp] = useState<number | null>(null);
  useEffect(() => {
    if (!preset) return;
    if (preset.market) setMarket(preset.market);
    if (preset.pick) setPick(preset.pick);
    setLine(preset.line != null ? String(preset.line) : "");
    if (preset.odds) setOdds(String(preset.odds));
    setSrc(preset.odds_source ?? "manual");
    setMp(preset.model_prob ?? null);
  }, [preset]);
  const def = meta.markets[market];
  const people = ev.sport === "f1" ? ev.participants : [];
  const finalPick = market === "player_stat" ? `${stat.name}:${stat.side}` : pick;
  const label = def?.picks ? `${def.name}: ${({ home: ev.home, away: ev.away } as Record<string, string | null>)[pick] ?? meta.pick_labels[pick] ?? pick}${line ? ` ${line}` : ""}` : `${def?.name}: ${finalPick}${line ? ` ${line}` : ""}`;
  return (
    <div className="mkt-picker">
      <div className="filters">
        <select value={market} onChange={(e) => { setMarket(e.target.value); setPick(""); setMp(null); setSrc("manual"); }} aria-label="Mercado">
          {markets.map(([k, m]) => <option key={k} value={k}>{m.name}</option>)}
        </select>
        {def?.picks ? (
          <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Selección">
            <option value="">Selección…</option>
            {def.picks.map((p) => <option key={p} value={p}>{({ home: ev.home, away: ev.away } as Record<string, string | null>)[p] ?? meta.pick_labels[p] ?? p}</option>)}
          </select>
        ) : market === "player_stat" ? (
          <>
            <input value={stat.name} onChange={(e) => setStat({ ...stat, name: e.target.value })} placeholder="Jugador y estadística (p. ej. Haaland goles)" aria-label="Estadística" />
            <select value={stat.side} onChange={(e) => setStat({ ...stat, side: e.target.value })} aria-label="Más o menos"><option value="over">Más de</option><option value="under">Menos de</option></select>
          </>
        ) : people.length ? (
          <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Piloto"><option value="">Piloto…</option>{people.map((p) => <option key={p}>{p}</option>)}</select>
        ) : (
          <input value={pick} onChange={(e) => setPick(e.target.value)} placeholder={market === "correct_score" || market === "sets_exact" ? "2-1" : "Piloto"} aria-label="Selección" />
        )}
        {market === "h2h" && <input value={opp} onChange={(e) => setOpp(e.target.value)} placeholder="Rival del duelo" aria-label="Rival" />}
        {def?.line && <input inputMode="decimal" value={line} onChange={(e) => setLine(e.target.value)} placeholder="Línea (2.5)" aria-label="Línea" style={{ width: 90 }} />}
        <input inputMode="decimal" value={odds} onChange={(e) => { setOdds(e.target.value); setSrc("manual"); }} placeholder="Cuota (2,10)" aria-label="Cuota decimal" style={{ width: 100 }} />
        <button type="button" className="btn" disabled={!finalPick || finalPick.startsWith(":") || !toNum(odds) || (def?.line && toNum(line) === null)}
          onClick={() => onAdd({ event_id: ev.id, market, pick: finalPick, line: def?.line ? toNum(line) : null, opponent: market === "h2h" ? opp : null,
            odds: toNum(odds)!, odds_source: src, model_prob: mp, label })}>Añadir al boleto</button>
      </div>
      <p className="mini-note">Las cuotas las introduces tú (de dónde las veas) o vienen de The Odds API. VISTAN nunca inventa cuotas.</p>
    </div>
  );
}

/* ─────────── Análisis del evento (modelo, forma, cuotas reales) ─────────── */
const MKT_NAME: Record<string, string> = {
  "1x2:home": "Local", "1x2:draw": "Empate", "1x2:away": "Visitante", "double_chance:1X": "1X", "double_chance:12": "12", "double_chance:X2": "X2",
  "total:over:1.5": "Más de 1,5", "total:over:2.5": "Más de 2,5", "total:under:2.5": "Menos de 2,5", "total:over:3.5": "Más de 3,5",
  "btts:yes": "Ambos marcan", "btts:no": "No marcan ambos", "handicap:home:-1.5": "Local −1,5", "handicap:away:1.5": "Visitante +1,5",
  "moneyline:home": "Local", "moneyline:away": "Visitante",
};

export function EventAnalysis({ ev, meta, onPick, onChanged }: {
  ev: BEvent; meta: Meta; onPick: (p: Partial<LegIn>) => void; onChanged: () => void;
}) {
  const [pred, setPred] = useState<Prediction | null>(null);
  const [busy, setBusy] = useState(false);
  const [odds, setOdds] = useState<{ markets: OddsRow[]; note: string | null } | null>(null);
  const [notes, setNotes] = useState(String(ev.meta.notes ?? ""));
  const [res, setRes] = useState({ status: "finished", home: "", away: "", sets: "", order: "", stats: "" });
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    setPred(null); setOdds(null); setMsg(null); setNotes(String(ev.meta.notes ?? ""));
    bets.odds(ev.id).then(setOdds).catch(() => setOdds(null));
  }, [ev.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = (explain: boolean) => { setBusy(true); bets.predict(ev.id, explain).then(setPred).catch((e: Error) => setMsg(e.message)).finally(() => setBusy(false)); };
  const started = new Date(ev.starts_at.endsWith("Z") ? ev.starts_at : ev.starts_at + "Z").getTime() <= Date.now();
  const m = pred?.model;
  const saveResult = () => {
    let result: Record<string, unknown> | null = null;
    if (res.status === "finished") {
      if (ev.sport === "f1") result = { order: res.order.split(",").map((x) => x.trim()).filter(Boolean) };
      else if (ev.sport === "tennis") result = { sets: res.sets.split(/\s+/).filter(Boolean).map((s) => s.split("-").map(Number)) };
      else result = { home: Number(res.home), away: Number(res.away) };
      if (res.stats.trim()) {
        const stats = Object.fromEntries(res.stats.split(",").map((x) => x.split("=").map((y) => y.trim())).filter((x) => x.length === 2).map(([k, v]) => [k, Number(v)]));
        result = { ...result, stats };
      }
    }
    bets.result(ev.id, res.status, result).then((r) => { setMsg(`Guardado. ${r.settled.length} pronóstico(s) liquidado(s).`); onChanged(); }).catch((e: Error) => setMsg(e.message));
  };
  return (
    <section className="chart-col bet-analysis">
      <div className="sym-head">
        <div>
          <h1>{sportIcon(ev.sport)} {ev.name}</h1>
          <span className="sub">{ev.competition ?? meta.sports[ev.sport]} · {dt(ev.starts_at)} · {statusLabel(ev.status)} · fuente: {ev.provider}</span>
        </div>
        {ev.result && <div className="sym-px"><b className="mono">{"home" in ev.result ? `${String(ev.result.home)} - ${String(ev.result.away)}` : "resultado"}</b><span className="small">{ev.result_source}</span></div>}
        <div className="sym-actions">
          <button type="button" className="mini-btn ghost" disabled={busy} onClick={() => run(false)}>Calcular probabilidades</button>
          <button type="button" className="btn" disabled={busy} onClick={() => run(true)}>{busy ? "Analizando…" : "Analizar con IA"}</button>
        </div>
      </div>
      {msg && <p className="ok-line">{msg}</p>}
      {pred && (
        <div className="mod-cols">
          <section className="dpanel grow">
            <header className="dpanel-head"><span>PREDICTION ENGINE {m?.model ? `· ${m.model}` : ""}</span></header>
            {m?.insufficient ? <p className="callout small">Datos insuficientes: {m.insufficient}. No se muestran probabilidades inventadas.</p> : (
              <>
                {m?.expected_goals && <p className="small">Goles esperados: <b className="mono">{num(m.expected_goals.home, 2)} – {num(m.expected_goals.away, 2)}</b></p>}
                {m?.expected_points && <p className="small">Puntos esperados: <b className="mono">{num(m.expected_points.home, 1)} – {num(m.expected_points.away, 1)}</b></p>}
                <table className="dtable compact">
                  <thead><tr><th>Mercado</th><th>Prob. modelo</th><th>Intervalo 80 %</th><th>Cuota justa</th><th /></tr></thead>
                  <tbody>{Object.entries(m?.probs ?? {}).map(([k, p]) => {
                    const [mkt, pick, line] = k.split(":");
                    const iv = m?.intervals_80?.[k];
                    return (
                      <tr key={k}>
                        <td>{MKT_NAME[k] ?? `${meta.markets[mkt]?.name ?? mkt} ${pick}${line ? ` ${line}` : ""}`}</td>
                        <td className="mono">{pp(p)}</td>
                        <td className="mono">{iv ? `${pp(iv[0], 0)} – ${pp(iv[1], 0)}` : "—"}</td>
                        <td className="mono">{p > 0 ? num(1 / p, 2) : "—"}</td>
                        <td>{meta.markets[mkt] && <button type="button" className="mini-btn ghost" onClick={() => onPick({ market: mkt, pick, line: line ? Number(line) : null, model_prob: p })}>usar</button>}</td>
                      </tr>
                    );
                  })}</tbody>
                </table>
                {m?.top_scores && <p className="small muted">Marcadores más probables: {m.top_scores.map((s) => `${s.score} (${pp(s.p)})`).join(" · ")}</p>}
                <p className="mini-note">{m?.method}</p>
              </>
            )}
            {pred.explanation && <div className="ai-text">{pred.explanation.split("\n").map((l, i) => <p key={i}>{l}</p>)}<small>{pred.explanation_model}</small></div>}
            {pred.explanation_error && <p className="error-line">{pred.explanation_error}</p>}
          </section>
          <section className="dpanel">
            <header className="dpanel-head"><span>DATOS USADOS</span></header>
            {pred.data.sources.map((s) => <p key={s} className="small">✓ {s}</p>)}
            {[pred.data.form_home, pred.data.form_away].filter(Boolean).map((f) => (
              <div key={f!.team} className="form-row">
                <b>{f!.team}</b>
                <span className="form-seq">{f!.last.map((x, i) => <i key={i} className={`f-${x}`}>{x}</i>)}</span>
                <span className="small muted">GF {f!.goals_for} · GC {f!.goals_against} · casa {f!.home_ppg ?? "N/D"} pts/p ({f!.home_games}) · fuera {f!.away_ppg ?? "N/D"} ({f!.away_games}) · descanso {f!.rest_days ?? "N/D"} días</span>
              </div>
            ))}
            {!!pred.data.h2h?.length && <p className="small">Cara a cara: {pred.data.h2h.map((h) => `${h.home} ${h.score} ${h.away} (${h.date})`).join(" · ")}</p>}
            {pred.data.standings_recent?.map((r) => <p key={r.race} className="small">{r.race}: {r.top5.join(", ")}</p>)}
            <header className="dpanel-head"><span>INFORMACIÓN QUE FALTA</span></header>
            <ul className="findings">{pred.data.missing.map((x) => <li key={x}>{x}</li>)}</ul>
          </section>
        </div>
      )}
      <section className="dpanel">
        <header className="dpanel-head"><span>CUOTAS (ODDS ANALYZER)</span>{odds?.markets.length ? <span>The Odds API</span> : null}</header>
        {odds?.note && <p className="muted small">{odds.note}</p>}
        {!!odds?.markets.length && (
          <div className="table-scroll"><table className="dtable compact">
            <thead><tr><th>Casa</th><th>Mercado</th><th>Margen</th><th>Selección</th><th>Cuota</th><th>Implícita</th><th>Justa</th><th>Modelo</th><th>Diferencia</th><th /></tr></thead>
            <tbody>{odds.markets.flatMap((r) => r.selections.map((s, i) => (
              <tr key={`${r.bookmaker}-${r.market}-${i}`}>
                <td>{i === 0 ? r.bookmaker : ""}</td><td>{i === 0 ? r.market : ""}</td><td className="mono">{i === 0 ? `${num(r.margin_pct, 2)} %` : ""}</td>
                <td>{s.name}</td><td className="mono">{num(s.odds, 2)}</td><td className="mono">{pp(s.implied)}</td><td className="mono">{pp(s.fair_prob)}</td>
                <td className="mono">{pp(s.model_prob)}</td>
                <td className={`mono ${s.edge ? (s.edge.edge_pct > 0 ? "up" : "down") : ""}`}>{s.edge ? `${s.edge.edge_pct > 0 ? "+" : ""}${num(s.edge.edge_pct, 1)} pp` : "—"}</td>
                <td><button type="button" className="mini-btn ghost" onClick={() => onPick({ market: s.market, pick: s.pick, line: s.line ?? null, odds: s.odds, odds_source: `${r.bookmaker} (The Odds API)`, model_prob: s.model_prob })}>usar</button></td>
              </tr>
            )))}</tbody>
          </table></div>
        )}
      </section>
      <section className="dpanel">
        <header className="dpanel-head"><span>NOTAS DEL EVENTO (bajas, contexto…)</span></header>
        <div className="filters">
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} style={{ flex: 1 }} aria-label="Notas del evento"
            placeholder="Información que tú confirmes: lesiones, rotaciones, clima… El agente la usará y la citará como aportada por ti." />
          <button type="button" className="mini-btn" onClick={() => bets.notes(ev.id, notes).then(() => setMsg("Notas guardadas")).catch((e: Error) => setMsg(e.message))}>Guardar</button>
        </div>
      </section>
      {started && ev.status !== "finished" && (
        <section className="dpanel">
          <header className="dpanel-head"><span>REGISTRAR RESULTADO REAL (manual)</span></header>
          <div className="filters">
            <select value={res.status} onChange={(e) => setRes({ ...res, status: e.target.value })} aria-label="Estado final">
              <option value="finished">Terminado</option><option value="postponed">Aplazado</option><option value="cancelled">Cancelado</option>
            </select>
            {res.status === "finished" && (ev.sport === "f1" ? <input value={res.order} onChange={(e) => setRes({ ...res, order: e.target.value })} placeholder="Orden de llegada: Norris, Verstappen, …" style={{ flex: 1 }} aria-label="Orden" />
              : ev.sport === "tennis" ? <input value={res.sets} onChange={(e) => setRes({ ...res, sets: e.target.value })} placeholder="Sets: 6-4 3-6 7-5" aria-label="Sets" />
                : <><input inputMode="numeric" value={res.home} onChange={(e) => setRes({ ...res, home: e.target.value })} placeholder={ev.home ?? "Local"} aria-label="Marcador local" style={{ width: 90 }} />
                  <input inputMode="numeric" value={res.away} onChange={(e) => setRes({ ...res, away: e.target.value })} placeholder={ev.away ?? "Visitante"} aria-label="Marcador visitante" style={{ width: 90 }} /></>)}
            <input value={res.stats} onChange={(e) => setRes({ ...res, stats: e.target.value })} placeholder="Estadísticas: Haaland goles=2 (opcional)" aria-label="Estadísticas individuales" />
            <button type="button" className="mini-btn" onClick={saveResult}>Guardar y liquidar</button>
          </div>
          <p className="mini-note">Úsalo solo con resultados oficiales que hayas comprobado. Con un proveedor conectado se hace solo.</p>
        </section>
      )}
    </section>
  );
}

/* ─────────── Boleto ─────────── */
export type SlipLeg = LegIn & { label: string; eventName: string };
export function Slip({ legs, onRemove, onClear, onPlaced, balance, ccy }: {
  legs: SlipLeg[]; onRemove: (i: number) => void; onClear: () => void; onPlaced: () => void; balance: number; ccy: string;
}) {
  const [stake, setStake] = useState("");
  const [reason, setReason] = useState("");
  const [strategy, setStrategy] = useState("");
  const [myProb, setMyProb] = useState("");
  const [an, setAn] = useState<SlipAnalysis | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    setErr(null);
    if (!legs.length) { setAn(null); return; }
    const t = setTimeout(() => bets.analyzeSlip(legs, toNum(stake)).then(setAn).catch((e: Error) => { setAn(null); setErr(e.message); }), 250);
    return () => clearTimeout(t);
  }, [legs, stake]);
  const place = () => {
    const up = toNum(myProb);
    bets.place({ legs, stake: toNum(stake) ?? 0, reasoning: reason, strategy, user_prob: up !== null ? up / 100 : null })
      .then((b) => { setMsg(`Pronóstico #${b.id} registrado (simulado)`); setStake(""); setReason(""); setMyProb(""); onClear(); onPlaced(); })
      .catch((e: Error) => setErr(e.message));
  };
  return (
    <section className="ticket">
      <header className="dpanel-head"><span>BOLETO {legs.length > 1 ? "COMBINADO" : "SIMPLE"}</span><span className="sim-dot">FICTICIO</span></header>
      {!legs.length ? <p className="desk-empty">Añade selecciones desde un evento. Con 2 o más se forma una combinada virtual.</p> : (
        <ul className="slip-legs">{legs.map((l, i) => (
          <li key={i}><div><b>{l.eventName}</b><span>{l.label}</span><small>{l.odds_source}{l.model_prob != null ? ` · modelo ${pp(l.model_prob)}` : ""}</small></div>
            <b className="mono">{num(l.odds, 2)}</b><button type="button" className="mini-btn ghost" onClick={() => onRemove(i)} aria-label="Quitar selección">✕</button></li>
        ))}</ul>
      )}
      <div className="tk-grid">
        <label>Importe ficticio<input inputMode="decimal" value={stake} onChange={(e) => setStake(e.target.value)} placeholder="10" aria-label="Importe ficticio" /></label>
        <label>Tu probabilidad %<input inputMode="decimal" value={myProb} onChange={(e) => setMyProb(e.target.value)} placeholder="opcional" aria-label="Tu probabilidad" /></label>
        <label className="wide">Estrategia<input value={strategy} onChange={(e) => setStrategy(e.target.value)} placeholder="p. ej. valor según modelo" aria-label="Estrategia del pronóstico" maxLength={64} /></label>
        <label className="wide">Razonamiento<textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} aria-label="Razonamiento" placeholder="¿Por qué crees que tiene valor?" /></label>
      </div>
      {an && (
        <div className="risk-box">
          <div><span>Cuota {legs.length > 1 ? "combinada" : ""}</span><strong className="mono">{num(an.odds, 2)}</strong></div>
          <div><span>Prob. implícita</span><strong className="mono">{pp(an.implied_prob)}</strong></div>
          <div><span>Prob. del modelo</span><strong className="mono">{pp(an.model_prob)}</strong></div>
          <div><span>Retorno potencial</span><strong className="mono up">{money(an.potential_return, ccy)}</strong></div>
          <div><span>Beneficio si aciertas</span><strong className="mono">{money(an.potential_profit, ccy)}</strong></div>
          <div><span>Pérdida si fallas</span><strong className="mono down">{an.stake ? money(-an.stake, ccy) : "—"}</strong></div>
          <div><span>Valor esperado</span><strong className={`mono ${an.expected_profit != null ? (an.expected_profit >= 0 ? "up" : "down") : ""}`}>{an.expected_profit != null ? money(an.expected_profit, ccy, true) : "N/D"}</strong></div>
          {legs.length > 1 && <div className="conds"><span>Para acertar tiene que cumplirse TODO:</span><ul>{an.conditions.map((c) => <li key={c}>{c}</li>)}</ul></div>}
        </div>
      )}
      {an?.warnings.map((w) => <p key={w} className="warn-line l-warn">⚠ {w}</p>)}
      {err && <p className="error-line">{err}</p>}
      <button type="button" className="btn send-order buy" disabled={!legs.length || !toNum(stake) || (toNum(stake) ?? 0) > balance} onClick={place}>
        Registrar pronóstico · {money(toNum(stake) ?? 0, ccy)} ficticios
      </button>
      {msg && <p className="ok-line">{msg}</p>}
      <p className="mini-note">Disponible: {money(balance, ccy)} ficticios. Sin depósitos ni retiradas: nada de esto es dinero real.</p>
    </section>
  );
}

export { pct };
