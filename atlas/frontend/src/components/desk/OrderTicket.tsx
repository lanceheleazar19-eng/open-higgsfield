import { useEffect, useState } from "react";
import { desk, RiskAckError, type DeskAccount, type Order, type Preview, type Quote, type RiskWarning } from "../../api/desk";
import { money, num, pct, price, toNum, KindTag } from "./ui";

type Side = "buy" | "sell";
type OType = "market" | "limit" | "stop";

/** Ticket de órdenes SIMULADAS con cálculo de riesgo en vivo (todo lo calcula el motor de VISTAN). */
export function OrderTicket({ account, symbol, quote, tf, onPlaced }: {
  account: DeskAccount; symbol: string; quote: Quote | null; tf: string; onPlaced: (o: Order) => void;
}) {
  const [side, setSide] = useState<Side>("buy");
  const [type, setType] = useState<OType>("market");
  const [qty, setQty] = useState("");
  const [lim, setLim] = useState("");
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [strategy, setStrategy] = useState("");
  const [pre, setPre] = useState<Preview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ack, setAck] = useState<RiskWarning[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => { setPre(null); setAck(null); setMsg(null); setErr(null); }, [symbol, account.id]);

  const body = () => ({
    account_id: account.id, symbol, side, type, qty: toNum(qty) ?? 0,
    limit_price: type === "limit" ? toNum(lim) : null, stop_price: type === "stop" ? toNum(lim) : null,
    sl: toNum(sl), tp: toNum(tp), strategy: strategy || null, timeframe: tf,
  });

  // Vista previa del riesgo (debounce)
  useEffect(() => {
    const q = toNum(qty);
    if (!q || q <= 0) { setPre(null); return; }
    const t = setTimeout(() => { desk.preview(body()).then(setPre).catch((e: Error) => setErr(e.message)); }, 350);
    return () => clearTimeout(t);
  }, [qty, lim, sl, tp, side, type, symbol, account.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (acknowledge = false) => {
    setBusy(true); setErr(null); setMsg(null);
    try {
      const o = await desk.placeOrder({ ...body(), acknowledge_risk: acknowledge });
      setAck(null);
      setMsg(o.status === "filled" ? `Ejecutada (simulada) a ${price(o.fill_price)}`
        : o.status === "pending" ? `Orden ${o.type} pendiente: se ejecutará cuando el precio cumpla la condición`
          : `Rechazada: ${o.reason}`);
      onPlaced(o);
    } catch (e) {
      if (e instanceof RiskAckError) setAck(e.warnings);
      else setErr((e as Error).message);
    } finally { setBusy(false); }
  };

  const useSuggested = () => { if (pre?.suggested_qty) setQty(String(pre.suggested_qty)); };
  const ccy = account.currency;
  return (
    <section className="ticket" aria-label="Ticket de orden simulada">
      <header className="dpanel-head"><span>ORDEN · {symbol}</span><span className="sim-dot">VIRTUAL</span></header>
      <div className="seg two">
        <button type="button" className={`buy ${side === "buy" ? "on" : ""}`} onClick={() => setSide("buy")}>BUY · Comprar</button>
        <button type="button" className={`sell ${side === "sell" ? "on" : ""}`} onClick={() => setSide("sell")}>SELL · Vender</button>
      </div>
      <div className="seg three">
        {(["market", "limit", "stop"] as OType[]).map((t) => (
          <button type="button" key={t} className={type === t ? "on" : ""} onClick={() => setType(t)}>{{ market: "Market", limit: "Limit", stop: "Stop" }[t]}</button>
        ))}
      </div>
      <p className="mini-note">
        {type === "market" ? "Al último precio disponible ± deslizamiento simulado."
          : type === "limit" ? (side === "buy" ? "Compra cuando el precio baje hasta tu límite (o mejor)." : "Vende cuando el precio suba hasta tu límite (o mejor).")
            : (side === "buy" ? "Compra cuando el precio SUBA hasta el stop (ruptura)." : "Vende cuando el precio BAJE hasta el stop.")}
      </p>
      <div className="tk-grid">
        <label>Cantidad<input inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="0" aria-label="Cantidad" /></label>
        {type !== "market" && (
          <label>{type === "limit" ? "Precio límite" : "Precio stop"}<input inputMode="decimal" value={lim} onChange={(e) => setLim(e.target.value)} placeholder={price(quote?.price)} aria-label="Precio de entrada" /></label>
        )}
        <label>Stop Loss<input inputMode="decimal" value={sl} onChange={(e) => setSl(e.target.value)} placeholder="opcional" aria-label="Stop loss" /></label>
        <label>Take Profit<input inputMode="decimal" value={tp} onChange={(e) => setTp(e.target.value)} placeholder="opcional" aria-label="Take profit" /></label>
        <label className="wide">Estrategia<input value={strategy} onChange={(e) => setStrategy(e.target.value)} placeholder="p. ej. ruptura, pullback EMA…" maxLength={64} aria-label="Estrategia" /></label>
      </div>
      <div className="risk-box">
        <div><span>Precio</span><strong className="mono">{price(pre?.price ?? quote?.price)}</strong> <KindTag kind={pre?.kind ?? quote?.kind} source={pre?.source ?? quote?.source} /></div>
        <div><span>Nominal</span><strong className="mono">{money(pre?.notional, ccy)}</strong></div>
        <div><span>Costes (ida y vuelta)</span><strong className="mono">{money(pre?.fees, ccy)}</strong></div>
        <div><span>Riesgo</span><strong className="mono down">{money(pre?.risk_money, ccy)} · {pct(pre?.risk_pct, false)}</strong></div>
        <div><span>Beneficio objetivo</span><strong className="mono up">{money(pre?.reward_money, ccy)}</strong></div>
        <div><span>Riesgo/beneficio</span><strong className="mono">{pre?.rr != null ? `1 : ${num(pre.rr)}` : "—"}</strong></div>
        <div><span>Tamaño sugerido</span><strong className="mono">{pre?.suggested_qty != null ? num(pre.suggested_qty, 4) : "—"}</strong>
          {pre?.suggested_qty ? <button type="button" className="link-btn" onClick={useSuggested}>usar</button> : null}</div>
        {pre?.fx && pre.quote_ccy !== pre.account_ccy && <p className="mini-note">Cambio {pre.quote_ccy}→{pre.account_ccy}: {num(pre.fx, 4)}</p>}
      </div>
      {pre?.warnings.filter((w) => w.level !== "info" || w.code === "delayed").map((w) => (
        <p key={w.code} className={`warn-line l-${w.level}`}>{w.level === "block" ? "⛔" : w.level === "warn" ? "⚠" : "ℹ"} {w.text}</p>
      ))}
      {ack ? (
        <div className="ack-box" role="alertdialog" aria-label="Confirmar riesgo">
          <strong>Esta operación supera tu gestión del riesgo</strong>
          <ul>{ack.filter((w) => w.level !== "info").map((w) => <li key={w.code}>{w.text}</li>)}</ul>
          <div className="row-btns">
            <button type="button" className="btn ghost" onClick={() => setAck(null)}>Revisar</button>
            <button type="button" className="btn danger" disabled={busy} onClick={() => void submit(true)}>Enviar igualmente (simulada)</button>
          </div>
        </div>
      ) : (
        <button type="button" className={`btn send-order ${side}`} disabled={busy || !toNum(qty)} onClick={() => void submit(false)}>
          {busy ? "Enviando…" : `${side === "buy" ? "COMPRAR" : "VENDER"} ${qty || ""} ${symbol} · simulada`}
        </button>
      )}
      {msg && <p className="ok-line" role="status">{msg}</p>}
      {err && <p className="error-line" role="alert">{err}</p>}
      <p className="mini-note">Cuenta <strong>{account.name}</strong>: riesgo máx. {account.max_risk_pct ?? "—"} % por operación{account.enforce_limits ? " · límites obligatorios" : " · solo avisos"}.</p>
    </section>
  );
}
