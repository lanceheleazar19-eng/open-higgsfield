import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { PaperTradeItem, TradeAgg } from "../api/types";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { LineChart } from "../components/LineChart";
import { Empty, Panel } from "../components/Panel";
import { formatDayLabel } from "../lib/tasks";
import { parseNum } from "../lib/format";

const f2 = (v: number | null | undefined, suf = "") =>
  v === null || v === undefined ? "—" : `${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 }).format(v)}${suf}`;
const signed = (v: number) => `${v > 0 ? "+" : ""}${f2(v)}`;
const MISTAKES = ["sin stop", "moví el stop", "fomo", "sobreoperar", "entrada tardía", "salida antes de tiempo", "riesgo excesivo", "contra tendencia", "venganza"];

export function Trading() {
  const stats = useAsync(api.tradingStats);
  const trades = useAsync(api.trades);
  const reload = async () => { await Promise.all([stats.reload(), trades.reload()]); };
  const s = stats.data;
  const closed = (trades.data ?? []).filter((t) => t.status === "closed");

  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Fase 6 · activo · SIMULACIÓN</p>
        <h1><Icon name="trading" size={26} /> Trading <span className="badge live">PAPER · capital virtual</span></h1>
        <p className="lead">Diario de operaciones <strong>simuladas</strong>. Nada de lo que hagas aquí llega a un bróker ni toca tu dinero real (que está en Finanzas). Las estadísticas salen solo de las operaciones que registras.</p>
      </header>
      <div className="grid grid-tasks">
        <div className="stack">
          <Capital current={s?.initial_capital ?? null} onSaved={reload} />
          <OpenTrade onSaved={reload} />
          <Panel title={`Posiciones abiertas (simuladas)${s ? ` · riesgo ${f2(s.open_risk)}` : ""}`}>
            {!s?.open.length ? <Empty>No hay operaciones abiertas.</Empty> : s.open.map((t) => <OpenPosition key={t.id} t={t} onDone={reload} />)}
          </Panel>
        </div>
        <div className="stack">
          <Panel title="Rendimiento (simulado)">
            {!s || s.overall.trades === 0 ? <Empty>Cierra operaciones para ver win rate, P&amp;L y R múltiple.</Empty> : (
              <>
                <dl className="kv">
                  {s.equity !== null && <div><dt>Capital virtual</dt><dd className="mono">{f2(s.equity)} {s.return_pct !== null && <span className={s.return_pct >= 0 ? "pos" : "neg"}>({signed(s.return_pct)} %)</span>}</dd></div>}
                  <Agg a={s.overall} />
                  <div><dt>Máx. drawdown</dt><dd className="mono neg">{f2(s.max_drawdown)}{s.max_drawdown_pct !== null && ` · ${f2(s.max_drawdown_pct)} %`}</dd></div>
                  {s.without_stop > 0 && <div><dt>Operaciones sin stop</dt><dd className="mono t-warn">{s.without_stop}</dd></div>}
                </dl>
                {s.curve.length > 1 && (
                  <LineChart ariaLabel="Curva de capital simulado" labels={s.curve.map((c) => formatDayLabel(c.date))} height={180}
                    series={[{ label: "Capital", color: "#e11d35", values: s.curve.map((c) => c.equity) }]} />
                )}
              </>
            )}
          </Panel>
          {s && s.by_strategy.length > 0 && (
            <Panel title="Por estrategia">
              <table className="data-table">
                <thead><tr><th>Estrategia</th><th>Ops</th><th>Win rate</th><th>P&amp;L</th><th>PF</th><th>R medio</th></tr></thead>
                <tbody>{s.by_strategy.map((x) => (
                  <tr key={x.strategy}><td>{x.strategy}</td><td className="mono">{x.trades}</td><td className="mono">{f2(x.win_rate, " %")}</td>
                    <td className={`mono ${x.pnl >= 0 ? "pos" : "neg"}`}>{signed(x.pnl)}</td><td className="mono">{f2(x.profit_factor)}</td><td className="mono">{f2(x.avg_r, "R")}</td></tr>
                ))}</tbody>
              </table>
            </Panel>
          )}
          {s && s.mistakes.length > 0 && (
            <Panel title="Errores recurrentes">
              <table className="data-table">
                <thead><tr><th>Error</th><th>Veces</th><th>P&amp;L asociado</th></tr></thead>
                <tbody>{s.mistakes.map((m) => (
                  <tr key={m.mistake}><td>{m.mistake}</td><td className="mono">{m.count}</td><td className={`mono ${m.pnl >= 0 ? "pos" : "neg"}`}>{signed(m.pnl)}</td></tr>
                ))}</tbody>
              </table>
            </Panel>
          )}
          <Panel title="Historial">
            {!closed.length ? <Empty>Sin operaciones cerradas.</Empty> : (
              <table className="data-table">
                <thead><tr><th>Cierre</th><th>Activo</th><th>Lado</th><th>Entrada → salida</th><th>P&amp;L</th><th>R</th><th /></tr></thead>
                <tbody>{closed.map((t) => (
                  <tr key={t.id}>
                    <td>{formatDayLabel(t.closed_at!.slice(0, 10))}</td><td>{t.symbol}{t.strategy ? <span className="muted small"> · {t.strategy}</span> : null}</td>
                    <td>{t.side === "long" ? "Largo" : "Corto"}</td><td className="mono">{f2(t.entry_price)} → {f2(t.exit_price)}</td>
                    <td className={`mono ${(t.pnl ?? 0) >= 0 ? "pos" : "neg"}`}>{signed(t.pnl ?? 0)}</td><td className="mono">{f2(t.r, "R")}</td>
                    <td><button className="mini-btn danger" aria-label={`Borrar operación ${t.symbol} ${t.id}`}
                      onClick={async () => { if (confirm("¿Borrar esta operación simulada?")) { await api.deleteTrade(t.id); await reload(); } }}>×</button></td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Agg({ a }: { a: TradeAgg }) {
  return (
    <>
      <div><dt>Operaciones cerradas</dt><dd className="mono">{a.trades} ({a.wins} ganadas · {a.losses} perdidas)</dd></div>
      <div><dt>Win rate</dt><dd className="mono">{f2(a.win_rate, " %")}</dd></div>
      <div><dt>P&amp;L total</dt><dd className={`mono ${a.pnl >= 0 ? "pos" : "neg"}`}>{signed(a.pnl)}</dd></div>
      <div><dt>Profit factor</dt><dd className="mono">{f2(a.profit_factor)}</dd></div>
      <div><dt>Expectativa por operación</dt><dd className="mono">{a.expectancy === null ? "—" : signed(a.expectancy)}</dd></div>
      <div><dt>R múltiple medio</dt><dd className="mono">{f2(a.avg_r, "R")}</dd></div>
      <div><dt>Ganancia media / pérdida media</dt><dd className="mono">{f2(a.avg_win)} / {f2(a.avg_loss)}</dd></div>
    </>
  );
}

function Capital({ current, onSaved }: { current: number | null; onSaved: () => Promise<void> }) {
  const [v, setV] = useState("");
  const amount = parseNum(v);
  return (
    <Panel title="Capital virtual inicial">
      <p className="muted small">{current === null ? "Fíjalo para calcular la rentabilidad y el drawdown en %." : `Actual: ${f2(current)} (virtual, no es dinero real).`}</p>
      <form className="form" onSubmit={async (e) => { e.preventDefault(); if (amount && amount > 0) { await api.setPaperCapital(amount); setV(""); await onSaved(); } }}>
        <div className="form-row">
          <label><span>Capital virtual</span><input inputMode="decimal" placeholder="10000" value={v} onChange={(e) => setV(e.target.value)} /></label>
        </div>
        <div className="form-actions"><button className="btn" type="submit" disabled={!amount || amount <= 0}>Guardar capital</button></div>
      </form>
    </Panel>
  );
}

function OpenTrade({ onSaved }: { onSaved: () => Promise<void> }) {
  const empty = { symbol: "", side: "long" as "long" | "short", quantity: "", entry: "", sl: "", tp: "", strategy: "", notes: "" };
  const [f, setF] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const qty = parseNum(f.quantity), entry = parseNum(f.entry), sl = parseNum(f.sl), tp = parseNum(f.tp);
  const risk = qty && entry && sl ? Math.abs(entry - sl) * qty : null;
  const rr = entry && sl && tp && entry !== sl ? Math.abs(tp - entry) / Math.abs(entry - sl) : null;
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!f.symbol.trim() || !qty || !entry) return;
    setError(null);
    try {
      await api.openTrade({ symbol: f.symbol, side: f.side, quantity: qty, entry_price: entry, stop_loss: sl, take_profit: tp,
        strategy: f.strategy.trim() || null, notes: f.notes.trim() || null });
      setF(empty);
      await onSaved();
    } catch (err) { setError((err as Error).message); }
  }
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <Panel title="Abrir operación simulada">
      <form className="form" onSubmit={save}>
        <div className="form-row">
          <label><span>Activo</span><input value={f.symbol} placeholder="EURUSD, BTC, AAPL…" maxLength={32} onChange={set("symbol")} /></label>
          <label><span>Dirección</span>
            <select value={f.side} onChange={set("side")}><option value="long">Largo (compra)</option><option value="short">Corto (venta)</option></select>
          </label>
          <label><span>Cantidad</span><input inputMode="decimal" value={f.quantity} onChange={set("quantity")} /></label>
        </div>
        <div className="form-row">
          <label><span>Entrada</span><input inputMode="decimal" value={f.entry} onChange={set("entry")} /></label>
          <label><span>Stop loss</span><input inputMode="decimal" value={f.sl} onChange={set("sl")} /></label>
          <label><span>Take profit</span><input inputMode="decimal" value={f.tp} onChange={set("tp")} /></label>
        </div>
        <div className="form-row">
          <label><span>Estrategia</span><input value={f.strategy} maxLength={64} placeholder="breakout, pullback…" onChange={set("strategy")} /></label>
          <label><span>Motivo / notas</span><input value={f.notes} maxLength={2000} onChange={set("notes")} /></label>
        </div>
        <p className="muted small">Riesgo: <span className="mono">{f2(risk)}</span> · R:B planificado: <span className="mono">{rr ? `1:${f2(rr)}` : "—"}</span>{!f.sl && " · sin stop loss"}</p>
        <div className="form-actions">
          <button className="btn" type="submit" disabled={!f.symbol.trim() || !qty || !entry}>Abrir (simulado)</button>
          {error && <span className="neg small">{error}</span>}
        </div>
      </form>
    </Panel>
  );
}

function OpenPosition({ t, onDone }: { t: PaperTradeItem; onDone: () => Promise<void> }) {
  const [exit, setExit] = useState("");
  const [mistakes, setMistakes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const px = parseNum(exit);
  const preview = px ? (px - t.entry_price) * t.quantity * (t.side === "long" ? 1 : -1) : null;
  return (
    <div className="goal">
      <div className="goal-head">
        <strong>{t.symbol}</strong> <span className="muted small">{t.side === "long" ? "Largo" : "Corto"} · {f2(t.quantity)} @ {f2(t.entry_price)} · SL {f2(t.stop_loss)} · TP {f2(t.take_profit)}{t.strategy ? ` · ${t.strategy}` : ""}</span>
      </div>
      <form className="form" onSubmit={async (e) => {
        e.preventDefault();
        if (!px) return;
        try { await api.closeTrade(t.id, px, mistakes); await onDone(); } catch (err) { setError((err as Error).message); }
      }}>
        <div className="form-row">
          <label><span>Precio de salida</span><input inputMode="decimal" value={exit} onChange={(e) => setExit(e.target.value)} /></label>
          <span className="small mono">{preview !== null && <span className={preview >= 0 ? "pos" : "neg"}>{signed(preview)}</span>}</span>
        </div>
        <div className="set-chips" role="group" aria-label={`Errores en ${t.symbol}`}>
          {MISTAKES.map((m) => (
            <button key={m} type="button" className={`chip ${mistakes.includes(m) ? "on" : ""}`} aria-pressed={mistakes.includes(m)}
              onClick={() => setMistakes(mistakes.includes(m) ? mistakes.filter((x) => x !== m) : [...mistakes, m])}>{m}</button>
          ))}
        </div>
        <div className="form-actions">
          <button className="btn" type="submit" disabled={!px}>Cerrar operación</button>
          <button className="mini-btn danger" type="button" onClick={async () => { if (confirm("¿Borrar esta operación simulada?")) { await api.deleteTrade(t.id); await onDone(); } }}>Borrar</button>
          {error && <span className="neg small">{error}</span>}
        </div>
      </form>
    </div>
  );
}
