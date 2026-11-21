"use server";

import { redirect } from "next/navigation";

import { packById, planById } from "../plans";
import { db } from "./db";
import { currentUser } from "./session";
import { siteOrigin, stripe } from "./stripe";

/* Prices are sent inline (price_data) so no product has to be created by hand
   in the Stripe dashboard: plans.ts stays the single source of truth. Amounts
   include IVA. */

export async function startCheckout(formData: FormData): Promise<void> {
  const user = await currentUser();
  if (!user) redirect("/escaparate/entrar?siguiente=/escaparate/cuenta");

  const kind = String(formData.get("kind") ?? "");
  const id = String(formData.get("id") ?? "");
  const origin = siteOrigin();
  const customer = await ensureCustomer(user.id, user.email, user.stripeCustomerId);
  const common = {
    customer,
    client_reference_id: user.id,
    locale: "es" as const,
    success_url: `${origin}/escaparate/cuenta?pago=ok`,
    cancel_url: `${origin}/escaparate/cuenta?pago=cancelado`,
  };

  let url: string | null = null;
  if (kind === "plan") {
    const plan = planById(id);
    if (!plan) redirect("/escaparate/cuenta");
    if (user.subscriptionStatus === "active" || user.subscriptionStatus === "trialing") {
      redirect("/escaparate/cuenta?pago=ya-suscrito");
    }
    const session = await stripe().checkout.sessions.create({
      ...common,
      mode: "subscription",
      line_items: [
        {
          quantity: 1,
          price_data: {
            currency: "eur",
            unit_amount: plan.priceEuros * 100,
            recurring: { interval: "month" },
            product_data: { name: `Escaparate ${plan.name}` },
          },
        },
      ],
      subscription_data: { metadata: { userId: user.id, planId: plan.id } },
      metadata: { userId: user.id, planId: plan.id },
    });
    url = session.url;
  } else if (kind === "pack") {
    const pack = packById(id);
    if (!pack) redirect("/escaparate/cuenta");
    const session = await stripe().checkout.sessions.create({
      ...common,
      mode: "payment",
      line_items: [
        {
          quantity: 1,
          price_data: {
            currency: "eur",
            unit_amount: pack.priceEuros * 100,
            product_data: { name: `Escaparate · ${pack.name}` },
          },
        },
      ],
      metadata: { userId: user.id, packId: pack.id },
    });
    url = session.url;
  }
  if (!url) redirect("/escaparate/cuenta?pago=error");
  redirect(url);
}

/** Stripe's hosted portal: change card, download invoices, cancel. */
export async function openBillingPortal(): Promise<void> {
  const user = await currentUser();
  if (!user) redirect("/escaparate/entrar?siguiente=/escaparate/cuenta");
  if (!user.stripeCustomerId) redirect("/escaparate/cuenta");
  const session = await stripe().billingPortal.sessions.create({
    customer: user.stripeCustomerId,
    locale: "es",
    return_url: `${siteOrigin()}/escaparate/cuenta`,
  });
  redirect(session.url);
}

async function ensureCustomer(userId: string, email: string, existing: string | null): Promise<string> {
  if (existing) return existing;
  const customer = await stripe().customers.create({ email, metadata: { userId } });
  const [row] = await db()<{ stripe_customer_id: string }[]>`
    UPDATE esc_users SET stripe_customer_id = COALESCE(stripe_customer_id, ${customer.id})
    WHERE id = ${userId} RETURNING stripe_customer_id`;
  return row.stripe_customer_id;
}
