import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { COST, PACKS, PLANS, planName } from "@/escaparate/plans";
import { signOut } from "@/escaparate/server/auth-actions";
import { openBillingPortal, startCheckout } from "@/escaparate/server/billing-actions";
import { db } from "@/escaparate/server/db";
import { safeCurrentUser } from "@/escaparate/server/viewer";

export const metadata: Metadata = { title: "Mi cuenta", robots: { index: false } };

const NOTICES: Record<string, { text: string; ok: boolean }> = {
  ok: { text: "¡Pago recibido! Tus créditos aparecerán en unos segundos (recarga la página si no los ves).", ok: true },
  cancelado: { text: "Has cancelado el pago. No se ha cobrado nada.", ok: false },
  "ya-suscrito": { text: "Ya tienes un plan activo. Puedes cambiarlo desde «Gestionar suscripción».", ok: false },
  error: { text: "No hemos podido abrir el pago. Inténtalo de nuevo.", ok: false },
};

export default async function CuentaPage({ searchParams }: { searchParams: Promise<{ pago?: string }> }) {
  const user = await safeCurrentUser();
  if (!user) redirect("/escaparate/entrar?siguiente=/escaparate/cuenta");
  const { pago } = await searchParams;
  const notice = pago ? NOTICES[pago] : undefined;

  const ledger = await db()<{ delta: number; reason: string; created_at: Date }[]>`
    SELECT delta, reason, created_at FROM esc_credit_ledger
    WHERE user_id = ${user.id} ORDER BY created_at DESC, id DESC LIMIT 15`;
  const subscribed = user.subscriptionStatus === "active" || user.subscriptionStatus === "trialing";

  return (
    <main className="esc-wrap esc-creator">
      <div>
        <h1 style={{ fontSize: "clamp(28px, 4vw, 40px)", margin: "0 0 4px" }}>Mi cuenta</h1>
        <p className="esc-note" style={{ margin: 0 }}>{user.email}</p>
      </div>

      {notice ? (
        <p className={notice.ok ? "esc-banner" : "esc-banner"} role="status">
          {notice.text}
        </p>
      ) : null}

      <section className="esc-panel">
        <h2 className="esc-panel-title">Tus créditos</h2>
        <div className="esc-price">
          {user.credits} <small>créditos</small>
        </div>
        <p className="esc-note" style={{ margin: 0 }}>
          1 foto = {COST.image} crédito · 1 vídeo = {COST.video} créditos. Si una generación falla, te devolvemos los
          créditos.
        </p>
        <p style={{ margin: 0 }}>
          Plan actual: <strong>{planName(user.plan)}</strong>
        </p>
        {user.stripeCustomerId ? (
          <form action={openBillingPortal}>
            <button className="esc-btn esc-btn-ghost esc-btn-small" type="submit">
              Gestionar suscripción y facturas
            </button>
          </form>
        ) : null}
      </section>

      {!subscribed ? (
        <section className="esc-panel">
          <h2 className="esc-panel-title">Elige un plan</h2>
          <div className="esc-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
            {PLANS.map((plan) => (
              <form action={startCheckout} className="esc-card" key={plan.id}>
                <input type="hidden" name="kind" value="plan" />
                <input type="hidden" name="id" value={plan.id} />
                <h3>{plan.name}</h3>
                <div className="esc-price">
                  {plan.priceEuros} € <small>/mes, IVA incl.</small>
                </div>
                <ul className="esc-list">
                  {plan.perks.map((perk) => (
                    <li key={perk}>{perk}</li>
                  ))}
                </ul>
                <button className="esc-btn esc-btn-primary" type="submit" style={{ marginTop: 16, width: "100%" }}>
                  Suscribirme
                </button>
              </form>
            ))}
          </div>
          <p className="esc-note" style={{ margin: 0 }}>Sin permanencia: cancelas cuando quieras desde tu cuenta.</p>
        </section>
      ) : null}

      <section className="esc-panel">
        <h2 className="esc-panel-title">¿Te faltan créditos?</h2>
        {PACKS.map((pack) => (
          <form action={startCheckout} key={pack.id} className="esc-hero-ctas" style={{ alignItems: "center" }}>
            <input type="hidden" name="kind" value="pack" />
            <input type="hidden" name="id" value={pack.id} />
            <span>
              <strong>{pack.name}</strong> · {pack.priceEuros} € (pago único, no caducan)
            </span>
            <button className="esc-btn esc-btn-ghost esc-btn-small" type="submit">
              Comprar
            </button>
          </form>
        ))}
      </section>

      <section className="esc-panel">
        <h2 className="esc-panel-title">Movimientos</h2>
        {ledger.length ? (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <tbody>
              {ledger.map((row, index) => (
                <tr key={index} style={{ borderTop: index ? "1px solid var(--line)" : undefined }}>
                  <td style={{ padding: "8px 0", color: "var(--tx3)", whiteSpace: "nowrap" }}>
                    {row.created_at.toLocaleDateString("es-ES", { day: "numeric", month: "short" })}
                  </td>
                  <td style={{ padding: "8px 12px" }}>{row.reason}</td>
                  <td
                    style={{
                      padding: "8px 0",
                      textAlign: "right",
                      fontWeight: 700,
                      fontVariantNumeric: "tabular-nums",
                      color: row.delta > 0 ? "var(--ok)" : "var(--tx)",
                    }}
                  >
                    {row.delta > 0 ? `+${row.delta}` : row.delta}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="esc-note" style={{ margin: 0 }}>Aún no hay movimientos.</p>
        )}
      </section>

      <form action={signOut}>
        <button className="esc-btn esc-btn-ghost esc-btn-small" type="submit">
          Cerrar sesión
        </button>
      </form>
    </main>
  );
}
