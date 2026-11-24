import { v4 } from "../api/v4";
import { useAsync } from "../api/useAsync";
import { Icon } from "../components/Icon";
import { LineChart } from "../components/LineChart";
import { Empty, Panel } from "../components/Panel";
import { formatMoney } from "../lib/format";
import { formatDayLabel } from "../lib/tasks";

const mlabel = (m: string) => new Intl.DateTimeFormat("es-ES", { month: "short" }).format(new Date(`${m}-15`));
const n0 = (v: number) => new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(v);

export function Analytics() {
  const a = useAsync(v4.analytics);
  const d = a.data;
  return (
    <div className="page page-wide">
      <header className="page-head">
        <p className="eyebrow">Analytics</p>
        <h1><Icon name="reports" size={26} /> Estadísticas</h1>
        <p className="lead">Solo tus datos registrados. Donde no hay datos, lo verás indicado: nada se rellena ni se estima.</p>
      </header>
      {!d ? <Empty>Cargando…</Empty> : (
        <div className="grid grid-2">
          <Panel title="Fitness · últimas 12 semanas">
            {!d.fitness.has_data ? <Empty>No hay entrenamientos registrados.</Empty> : <>
              <LineChart ariaLabel="Sesiones por semana" labels={d.fitness.weeks.map((w) => formatDayLabel(w.week))} height={170}
                series={[{ label: "Sesiones", color: "#e11d35", values: d.fitness.weeks.map((w) => w.sessions) }]} />
              <LineChart ariaLabel="Tonelaje por semana" unit=" kg" labels={d.fitness.weeks.map((w) => formatDayLabel(w.week))} height={170}
                series={[{ label: "Tonelaje", color: "#eaeaea", values: d.fitness.weeks.map((w) => w.tonnage) }]} />
            </>}
          </Panel>
          <Panel title="Finanzas · dinero real (12 meses)">
            {!d.finance.has_data ? <Empty>No hay movimientos registrados.</Empty> : <>
              <LineChart ariaLabel="Ingresos y gastos por mes" labels={d.finance.months.map((m) => mlabel(m.month))} height={190}
                series={[{ label: "Ingresos", color: "#3ccf7a", values: d.finance.months.map((m) => m.income_cents / 100) },
                         { label: "Gastos", color: "#e11d35", values: d.finance.months.map((m) => m.expense_cents / 100) }]} />
              <dl className="kv">
                <div><dt>Este mes</dt><dd className="mono">{formatMoney(d.finance.current.net_cents)} netos{d.finance.current.savings_rate !== null ? ` · ${d.finance.current.savings_rate} % ahorro` : ""}</dd></div>
              </dl>
            </>}
          </Panel>
          <Panel title="Trading · SIMULACIÓN">
            {!d.trading.has_data ? <Empty>No hay operaciones simuladas cerradas.</Empty> : <>
              {d.trading.curve.length > 1 && <LineChart ariaLabel="Curva de capital simulado" labels={d.trading.curve.map((c) => formatDayLabel(c.date))} height={170}
                series={[{ label: "Capital", color: "#e11d35", values: d.trading.curve.map((c) => c.equity) }]} />}
              <dl className="kv">
                <div><dt>Operaciones</dt><dd className="mono">{d.trading.overall.trades}</dd></div>
                <div><dt>Win rate</dt><dd className="mono">{d.trading.overall.win_rate ?? "—"} %</dd></div>
                <div><dt>P&amp;L</dt><dd className="mono">{n0(d.trading.overall.pnl)}</dd></div>
                <div><dt>Profit factor / R medio</dt><dd className="mono">{d.trading.overall.profit_factor ?? "—"} / {d.trading.overall.avg_r ?? "—"}R</dd></div>
                <div><dt>Máx. drawdown</dt><dd className="mono">{n0(d.trading.max_drawdown)}</dd></div>
              </dl>
              {d.trading.by_strategy.map((s) => <p key={s.strategy} className="small">{s.strategy}: {s.trades} ops · {n0(s.pnl)} · {s.win_rate ?? "—"} %</p>)}
            </>}
          </Panel>
          <Panel title="Proyectos">
            {!d.projects.has_data ? <Empty>No hay proyectos ni tareas completadas.</Empty> : <>
              <LineChart ariaLabel="Tareas completadas por semana" labels={d.projects.done_by_week.map((w) => formatDayLabel(w.week))} height={150}
                series={[{ label: "Completadas", color: "#3ccf7a", values: d.projects.done_by_week.map((w) => w.done) }]} />
              {d.projects.items.map((p) => (
                <div className="macro" key={p.id}>
                  <div className="macro-head"><span>{p.name}{p.overdue ? <span className="neg small"> · {p.overdue} atrasadas</span> : null}</span>
                    <span className="mono">{p.done}/{p.total}{p.progress !== null ? ` (${p.progress} %)` : ""}</span></div>
                  <div className="goal-bar"><span style={{ width: `${p.progress ?? 0}%` }} /></div>
                </div>
              ))}
            </>}
          </Panel>
        </div>
      )}
    </div>
  );
}
