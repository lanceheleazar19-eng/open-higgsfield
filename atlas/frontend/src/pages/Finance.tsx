import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { BudgetItem } from "../api/types";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { LineChart } from "../components/LineChart";
import { Empty, Panel } from "../components/Panel";
import { formatMoney, parseMoneyInput } from "../lib/format";
import { formatDayLabel } from "../lib/tasks";

const thisMonth = () => new Date().toISOString().slice(0, 7);
const monthLabel = (m: string) => new Intl.DateTimeFormat("es-ES", { month: "short", year: "2-digit" }).format(new Date(`${m}-15`));

export function Finance() {
  const [month, setMonth] = useState(thisMonth());
  const sum = useAsync(() => api.financeSummary(month));
  const txs = useAsync(() => api.transactions(month));
  const cats = useAsync(api.financeCategories);
  const reload = async () => { await Promise.all([sum.reload(), txs.reload()]); };
  const s = sum.data;
  const cur = txs.data?.[0]?.currency ?? "EUR";
  const money = (c: number) => formatMoney(c, cur);

  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Fase 6 · activo · dinero real</p>
        <h1><Icon name="finance" size={26} /> Finanzas</h1>
        <p className="lead">Apunta ingresos y gastos aquí o en el chat («he gastado 12,50 en comida»). ATLAS solo registra y analiza: <strong>nunca hace pagos ni transferencias</strong>. El trading simulado va aparte.</p>
      </header>
      <div className="filters">
        <label className="field"><span>Mes</span>
          <input type="month" value={month} max={thisMonth()} onChange={(e) => { if (e.target.value) setMonth(e.target.value); }} />
        </label>
      </div>
      <div className="grid grid-tasks">
        <div className="stack">
          <Panel title="Resumen del mes">
            {!s ? <Empty>Cargando…</Empty> : (
              <dl className="kv">
                <div><dt>Ingresos</dt><dd className="mono pos">{money(s.income_cents)}</dd></div>
                <div><dt>Gastos</dt><dd className="mono neg">{money(s.expense_cents)}</dd></div>
                <div><dt>Ahorro del mes</dt><dd className={`mono ${s.net_cents < 0 ? "neg" : "pos"}`}>{money(s.net_cents)}{s.savings_rate !== null && ` · ${s.savings_rate} %`}</dd></div>
                <div><dt>Saldo registrado total</dt><dd className="mono">{money(s.balance_cents)}</dd></div>
                <div><dt>Movimientos</dt><dd className="mono">{s.count}</dd></div>
              </dl>
            )}
            {s && s.by_category.length > 0 && (
              <div className="bars" aria-label="Gastos por categoría">
                {s.by_category.map((c) => (
                  <div className="bar-row" key={c.category}>
                    <span className="bar-label">{c.category}</span>
                    <span className="bar-track"><span className="bar-fill bar-in" style={{ width: `${(100 * c.cents) / s.by_category[0].cents}%` }} /></span>
                    <span className="mono small">{money(c.cents)}</span>
                  </div>
                ))}
              </div>
            )}
          </Panel>
          <AddTx categories={cats.data} onSaved={reload} />
          <Budgets budgets={s?.budgets ?? []} categories={cats.data?.expense ?? []} money={money} onChange={reload} />
        </div>
        <div className="stack">
          <Panel title="Evolución (6 meses)">
            {s && s.months.some((m) => m.income_cents || m.expense_cents) ? (
              <LineChart ariaLabel="Ingresos y gastos por mes" labels={s.months.map((m) => monthLabel(m.month))} height={190}
                series={[{ label: "Ingresos", color: "#34d399", values: s.months.map((m) => m.income_cents / 100) },
                         { label: "Gastos", color: "#e11d35", values: s.months.map((m) => m.expense_cents / 100) }]} />
            ) : <Empty>Aún no hay movimientos registrados.</Empty>}
          </Panel>
          <Panel title="Movimientos">
            {!txs.data?.length ? <Empty>No hay movimientos este mes.</Empty> : (
              <table className="data-table">
                <thead><tr><th>Fecha</th><th>Concepto</th><th>Categoría</th><th>Importe</th><th /></tr></thead>
                <tbody>
                  {txs.data.map((t) => (
                    <tr key={t.id}>
                      <td>{formatDayLabel(t.occurred_on)}</td><td>{t.description ?? "—"}</td><td>{t.category ?? "otros"}</td>
                      <td className={`mono ${t.kind === "income" ? "pos" : "neg"}`}>{t.kind === "income" ? "+" : "−"}{money(t.amount_cents)}</td>
                      <td><button className="mini-btn danger" aria-label={`Borrar movimiento ${t.description ?? t.category ?? ""} ${t.occurred_on}`}
                        onClick={async () => { if (confirm("¿Borrar este movimiento?")) { await api.deleteTransaction(t.id); await reload(); } }}>×</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function AddTx({ categories, onSaved }: { categories: { expense: string[]; income: string[] } | null; onSaved: () => Promise<void> }) {
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState<string | null>(null);
  const cents = parseMoneyInput(amount);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!cents) return setError("Importe no válido");
    setError(null);
    try {
      await api.addTransaction({ kind, amount_cents: cents, category: category || null, description: description.trim() || null, occurred_on: day });
      setAmount(""); setDescription(""); setCategory("");
      await onSaved();
    } catch (err) { setError((err as Error).message); }
  }
  return (
    <Panel title="Nuevo movimiento">
      <form className="form" onSubmit={save}>
        <div className="form-row">
          <label><span>Tipo</span>
            <select value={kind} onChange={(e) => { setKind(e.target.value as "expense" | "income"); setCategory(""); }}>
              <option value="expense">Gasto</option><option value="income">Ingreso</option>
            </select>
          </label>
          <label><span>Importe (€)</span><input inputMode="decimal" placeholder="12,50" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
          <label><span>Fecha</span><input type="date" value={day} onChange={(e) => setDay(e.target.value)} /></label>
        </div>
        <div className="form-row">
          <label><span>Categoría</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">Automática</option>
              {(categories?.[kind] ?? []).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label><span>Concepto</span><input value={description} maxLength={500} onChange={(e) => setDescription(e.target.value)} /></label>
        </div>
        <div className="form-actions">
          <button className="btn" type="submit" disabled={!cents}>Guardar</button>
          {error && <span className="neg small">{error}</span>}
        </div>
      </form>
    </Panel>
  );
}

function Budgets({ budgets, categories, money, onChange }: { budgets: BudgetItem[]; categories: string[]; money: (c: number) => string; onChange: () => Promise<void> }) {
  const [cat, setCat] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);
  const cents = parseMoneyInput(amount);
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!cat || !cents) return;
    try { await api.setBudget(cat, cents); setAmount(""); setCat(""); setError(null); await onChange(); }
    catch (err) { setError((err as Error).message); }
  }
  return (
    <Panel title="Presupuestos mensuales">
      {budgets.length === 0 && <Empty>Sin presupuestos. Pon un límite a una categoría y ATLAS te avisará al llegar al 80 %.</Empty>}
      {budgets.map((b) => (
        <div className="macro" key={b.category}>
          <div className="macro-head">
            <span>{b.category} {b.status === "over" && <span className="neg small">· superado</span>}{b.status === "warning" && <span className="t-warn small">· cerca del límite</span>}</span>
            <span className="mono">{money(b.spent_cents)} / {money(b.monthly_cents)} ({b.pct} %)
              <button className="mini-btn danger" aria-label={`Quitar presupuesto de ${b.category}`} onClick={async () => { await api.deleteBudget(b.category); await onChange(); }}>×</button>
            </span>
          </div>
          <div className="goal-bar" role="progressbar" aria-label={`Presupuesto ${b.category}`} aria-valuenow={Math.min(100, b.pct)} aria-valuemin={0} aria-valuemax={100}>
            <span style={{ width: `${Math.min(100, b.pct)}%`, background: b.status === "over" ? "#e11d35" : b.status === "warning" ? "#fbbf24" : undefined }} />
          </div>
        </div>
      ))}
      <form className="form" onSubmit={save}>
        <div className="form-row">
          <label><span>Categoría</span>
            <select value={cat} onChange={(e) => setCat(e.target.value)}>
              <option value="">Elige…</option>
              {categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label><span>Límite al mes (€)</span><input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
        </div>
        <div className="form-actions">
          <button className="btn" type="submit" disabled={!cat || !cents}>Guardar presupuesto</button>
          {error && <span className="neg small">{error}</span>}
        </div>
      </form>
    </Panel>
  );
}
