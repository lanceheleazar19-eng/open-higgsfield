import { useCallback, useEffect, useState } from "react";
import { desk, type DeskAccount, type DeskState, type Order, type Position } from "../../api/desk";
import { dt, held, KindTag, money, num, price, toNum, tone } from "./ui";

type Tab = "positions" | "pending" | "history" | "closed";

/** Posiciones abiertas, órdenes pendientes, historial de órdenes y operaciones cerradas (todo simulado). */
export function Blotter({ account, state, accounts, onChange, onSelect, onSnap }: {
  account: DeskAccount; state: DeskState | null; accounts: DeskAccount[]; onChange: () => void;
  onSelect: (symbol: string) => void; onSnap?: (positionId: number) => void;
}) {
  const [tab, setTab] = useState<Tab>("positions");
  const [edit, setEdit] = useState<{ id: number; sl: string; tp: string } | null>(null);
  const [closing, setClosing] = useState<{ id: number; qty: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState({ account: String(account.id), status: "", symbol: "", start: "", end: "", result: "" });
  const [hist, setHist] = useState<Order[] | null>(null);
  const [closed, setClosed] = useState<Position[] | null>(null);
  useEffect(() => { setF((x) => ({ ...x, account: String(account.id) })); }, [account.id]);

  const loadHist = useCallback(() => {
    const acc = f.account ? Number(f.account) : undefined;
    if (tab === "history") desk.orders({ account_id: acc, status: f.status || undefined, symbol: f.symbol || undefined, start: f.start || undefined, end: f.end || undefined })
      .then(setHist).catch((e: Error) => setErr(e.message));
    if (tab === "closed") desk.positions({ account_id: acc, status: "closed", symbol: f.symbol || undefined, start: f.start || undefined, end: f.end || undefined, result: f.result || undefined })
      .then(setClosed).catch((e: Error) => setErr(e.message));
  }, [tab, f]);
  useEffect(() => { loadHist(); }, [loadHist, state?.open_positions, state?.pending.length]);

  const run = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try { await fn(); onChange(); loadHist(); } catch (e) { setErr((e as Error).message); }
  };
  const ccy = account.currency;
  const symbols = [...new Set([...(state?.positions ?? []).map((p) => p.symbol), ...(hist ?? []).map((o) => o.symbol), ...(closed ?? []).map((p) => p.symbol)])];

  return (
    <section className="blotter">
      <div className="dtabs">
        {([["positions", `Posiciones abiertas (${state?.positions.length ?? 0})`], ["pending", `Órdenes pendientes (${state?.pending.length ?? 0})`],
          ["history", "Historial de órdenes"], ["closed", "Operaciones cerradas"]] as [Tab, string][]).map(([k, l]) => (
          <button type="button" key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {err && <p className="error-line" role="alert">{err}</p>}
      {(tab === "history" || tab === "closed") && (
        <div className="filters">
          <select value={f.account} onChange={(e) => setF({ ...f, account: e.target.value })} aria-label="Cuenta">
            <option value="">Todas las cuentas</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}{a.active ? "" : " (archivada)"}</option>)}
          </select>
          {tab === "history" && (
            <select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} aria-label="Estado">
              <option value="">Todos los estados</option><option value="pending">Pendientes</option><option value="filled">Ejecutadas</option>
              <option value="cancelled">Canceladas</option><option value="rejected">Rechazadas</option>
            </select>
          )}
          {tab === "closed" && (
            <select value={f.result} onChange={(e) => setF({ ...f, result: e.target.value })} aria-label="Resultado">
              <option value="">Todos los resultados</option><option value="win">Ganadoras</option><option value="loss">Perdedoras</option>
            </select>
          )}
          <select value={f.symbol} onChange={(e) => setF({ ...f, symbol: e.target.value })} aria-label="Activo">
            <option value="">Todos los activos</option>{symbols.map((s) => <option key={s}>{s}</option>)}
          </select>
          <input type="date" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} aria-label="Desde" />
          <input type="date" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} aria-label="Hasta" />
        </div>
      )}
      <div className="table-scroll">
        {tab === "positions" && (
          !state?.positions.length ? <p className="desk-empty">Sin posiciones abiertas en {account.name}.</p> : (
            <table className="dtable">
              <thead><tr><th>Activo</th><th>Dir.</th><th>Entrada</th><th>Actual</th><th>Cant.</th><th>SL</th><th>TP</th><th>P&L no realizado</th><th>Abierta</th><th /></tr></thead>
              <tbody>{state.positions.map((p) => (
                <tr key={p.id}>
                  <td><button type="button" className="link-btn" onClick={() => onSelect(p.symbol)}>{p.symbol}</button></td>
                  <td className={p.side === "long" ? "up" : "down"}>{p.side === "long" ? "LARGO" : "CORTO"}</td>
                  <td className="mono">{price(p.entry_price)}</td>
                  <td className="mono">{price(p.price)} <KindTag kind={p.price_kind} /></td>
                  <td className="mono">{num(p.qty, 4)}</td>
                  {edit?.id === p.id ? (
                    <>
                      <td><input className="cell-in" value={edit.sl} onChange={(e) => setEdit({ ...edit, sl: e.target.value })} aria-label="Nuevo stop loss" /></td>
                      <td><input className="cell-in" value={edit.tp} onChange={(e) => setEdit({ ...edit, tp: e.target.value })} aria-label="Nuevo take profit" /></td>
                    </>
                  ) : (<><td className="mono down">{p.sl ? price(p.sl) : "—"}</td><td className="mono up">{p.tp ? price(p.tp) : "—"}</td></>)}
                  <td className={`mono ${tone(p.unrealized)}`}>{money(p.unrealized, ccy, true)}</td>
                  <td className="mono">{held(p.opened_at)}</td>
                  <td className="row-actions">
                    {edit?.id === p.id ? (
                      <>
                        <button type="button" className="mini-btn" onClick={() => void run(async () => { await desk.modify(p.id, toNum(edit.sl), toNum(edit.tp)); setEdit(null); })}>Guardar</button>
                        <button type="button" className="mini-btn ghost" onClick={() => setEdit(null)}>✕</button>
                      </>
                    ) : closing?.id === p.id ? (
                      <>
                        <input className="cell-in" value={closing.qty} onChange={(e) => setClosing({ ...closing, qty: e.target.value })} aria-label="Cantidad a cerrar" />
                        <button type="button" className="mini-btn danger" onClick={() => void run(async () => { await desk.close(p.id, toNum(closing.qty)); setClosing(null); })}>Cerrar</button>
                        <button type="button" className="mini-btn ghost" onClick={() => setClosing(null)}>✕</button>
                      </>
                    ) : (
                      <>
                        <button type="button" className="mini-btn ghost" onClick={() => setEdit({ id: p.id, sl: p.sl ? String(p.sl) : "", tp: p.tp ? String(p.tp) : "" })}>Modificar</button>
                        <button type="button" className="mini-btn ghost" onClick={() => setClosing({ id: p.id, qty: String(p.qty) })} title="Cierre parcial o total">Parcial</button>
                        <button type="button" className="mini-btn danger" onClick={() => void run(() => desk.close(p.id))}>Cerrar</button>
                        {onSnap && <button type="button" className="mini-btn ghost" onClick={() => onSnap(p.id)} title="Guardar captura del gráfico en el diario">📷</button>}
                      </>
                    )}
                  </td>
                </tr>
              ))}</tbody>
            </table>
          ))}
        {tab === "pending" && (
          !state?.pending.length ? <p className="desk-empty">Sin órdenes pendientes.</p> : (
            <table className="dtable">
              <thead><tr><th>Creada</th><th>Activo</th><th>Tipo</th><th>Lado</th><th>Cant.</th><th>Precio</th><th>SL</th><th>TP</th><th /></tr></thead>
              <tbody>{state.pending.map((o) => (
                <tr key={o.id}>
                  <td className="mono">{dt(o.created_at)}</td><td>{o.symbol}</td><td>{o.type.toUpperCase()}</td>
                  <td className={o.side === "buy" ? "up" : "down"}>{o.side.toUpperCase()}</td><td className="mono">{num(o.qty, 4)}</td>
                  <td className="mono">{price(o.limit_price ?? o.stop_price)}</td><td className="mono">{o.sl ? price(o.sl) : "—"}</td><td className="mono">{o.tp ? price(o.tp) : "—"}</td>
                  <td><button type="button" className="mini-btn ghost" onClick={() => void run(() => desk.cancelOrder(o.id))}>Cancelar</button></td>
                </tr>
              ))}</tbody>
            </table>
          ))}
        {tab === "history" && (
          !hist?.length ? <p className="desk-empty">No hay órdenes con estos filtros.</p> : (
            <table className="dtable">
              <thead><tr><th>Fecha</th><th>Activo</th><th>Tipo</th><th>Lado</th><th>Cant.</th><th>Estado</th><th>Ejecución</th><th>Costes</th><th>Dato</th><th>Motivo</th></tr></thead>
              <tbody>{hist.map((o) => (
                <tr key={o.id}>
                  <td className="mono">{dt(o.created_at)}</td><td>{o.symbol}</td><td>{o.type.toUpperCase()}</td>
                  <td className={o.side === "buy" ? "up" : "down"}>{o.side.toUpperCase()}</td><td className="mono">{num(o.qty, 4)}</td>
                  <td><span className={`st st-${o.status}`}>{{ pending: "Pendiente", filled: "Ejecutada", cancelled: "Cancelada", rejected: "Rechazada" }[o.status]}</span></td>
                  <td className="mono">{price(o.fill_price)}</td><td className="mono">{money(o.fees, ccy)}</td>
                  <td><KindTag kind={o.data_kind as never} source={o.data_source} /></td><td className="small">{o.reason ?? ""}</td>
                </tr>
              ))}</tbody>
            </table>
          ))}
        {tab === "closed" && (
          !closed?.length ? <p className="desk-empty">Aún no hay operaciones cerradas con estos filtros.</p> : (
            <table className="dtable">
              <thead><tr><th>Cerrada</th><th>Activo</th><th>Dir.</th><th>Cant.</th><th>Entrada</th><th>Salida</th><th>Motivo</th><th>P&L neto</th><th>Estrategia</th><th>Diario</th></tr></thead>
              <tbody>{closed.map((p) => (
                <tr key={p.id}>
                  <td className="mono">{dt(p.closed_at)}</td><td>{p.symbol}</td><td className={p.side === "long" ? "up" : "down"}>{p.side === "long" ? "LARGO" : "CORTO"}</td>
                  <td className="mono">{num(p.qty, 4)}</td><td className="mono">{price(p.entry_price)}</td><td className="mono">{price(p.exit_price)}</td>
                  <td>{{ manual: "Manual", stop_loss: "Stop loss", take_profit: "Take profit" }[p.exit_reason ?? ""] ?? p.exit_reason}</td>
                  <td className={`mono ${tone(p.realized_pnl)}`}>{money(p.realized_pnl, ccy, true)}</td><td>{p.strategy ?? "—"}</td>
                  <td>{p.journaled ? "✓" : "—"}</td>
                </tr>
              ))}</tbody>
            </table>
          ))}
      </div>
    </section>
  );
}
