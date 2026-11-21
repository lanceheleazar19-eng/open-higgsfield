import type Stripe from "stripe";

import { packById, planById } from "@/escaparate/plans";
import { grantCredits } from "@/escaparate/server/credits";
import { db } from "@/escaparate/server/db";
import { stripe } from "@/escaparate/server/stripe";

export const runtime = "nodejs";

/* Stripe webhook. Credits for a subscription are granted on every paid
   invoice (the first one included), for a pack on the completed checkout.
   Each event is processed once; each grant is keyed by its Stripe id, so a
   replay can never add credits twice. */
export async function POST(request: Request): Promise<Response> {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  const signature = request.headers.get("stripe-signature");
  if (!secret || !signature) return new Response("Missing signature", { status: 400 });

  let event: Stripe.Event;
  try {
    event = stripe().webhooks.constructEvent(await request.text(), signature, secret);
  } catch {
    return new Response("Invalid signature", { status: 400 });
  }

  const sql = db();
  const [fresh] = await sql`
    INSERT INTO esc_stripe_events (id, type) VALUES (${event.id}, ${event.type})
    ON CONFLICT (id) DO NOTHING RETURNING id`;
  if (!fresh) return Response.json({ received: true, duplicate: true });

  try {
    await handle(event);
  } catch (caught) {
    // Let Stripe retry: forget the event so the retry is processed.
    await sql`DELETE FROM esc_stripe_events WHERE id = ${event.id}`;
    console.error("[escaparate] webhook failed", event.type, caught);
    return new Response("Webhook handler failed", { status: 500 });
  }
  return Response.json({ received: true });
}

async function handle(event: Stripe.Event): Promise<void> {
  const sql = db();
  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object;
      const userId = session.metadata?.userId ?? session.client_reference_id;
      if (!userId) return;
      if (typeof session.customer === "string") {
        await sql`UPDATE esc_users SET stripe_customer_id = COALESCE(stripe_customer_id, ${session.customer}) WHERE id = ${userId}`;
      }
      if (session.mode === "payment" && session.payment_status === "paid") {
        const pack = packById(session.metadata?.packId ?? "");
        if (pack) await grantCredits(userId, pack.credits, `Compra: ${pack.name}`, `checkout:${session.id}`);
      }
      return;
    }
    case "invoice.paid": {
      const invoice = event.data.object;
      const meta = subscriptionMetadata(invoice);
      const plan = planById(meta.planId ?? "");
      const userId = meta.userId ?? (await userIdForCustomer(invoice.customer));
      if (!plan || !userId) return;
      await grantCredits(userId, plan.monthlyCredits, `Plan ${plan.name}: créditos del mes`, `invoice:${invoice.id}`);
      return;
    }
    case "customer.subscription.created":
    case "customer.subscription.updated":
    case "customer.subscription.deleted": {
      const subscription = event.data.object;
      const userId = subscription.metadata?.userId ?? (await userIdForCustomer(subscription.customer));
      if (!userId) return;
      const active = subscription.status === "active" || subscription.status === "trialing";
      const plan = active ? (planById(subscription.metadata?.planId ?? "")?.id ?? "gratis") : "gratis";
      await sql`
        UPDATE esc_users
        SET plan = ${plan}, subscription_status = ${subscription.status}, stripe_subscription_id = ${subscription.id}
        WHERE id = ${userId}`;
      return;
    }
    default:
      return;
  }
}

/** Where the subscription's metadata sits moved between Stripe API versions;
    read both places. */
function subscriptionMetadata(invoice: Stripe.Invoice): { userId?: string; planId?: string } {
  const record = invoice as unknown as Record<string, unknown>;
  const parent = record.parent as { subscription_details?: { metadata?: Record<string, string> } } | undefined;
  const fromParent = parent?.subscription_details?.metadata;
  const legacy = (record.subscription_details as { metadata?: Record<string, string> } | undefined)?.metadata;
  const metadata = fromParent ?? legacy ?? {};
  return { userId: metadata.userId, planId: metadata.planId };
}

async function userIdForCustomer(customer: string | { id: string } | null): Promise<string | null> {
  const id = typeof customer === "string" ? customer : customer?.id;
  if (!id) return null;
  const [row] = await db()<{ id: string }[]>`SELECT id FROM esc_users WHERE stripe_customer_id = ${id}`;
  return row?.id ?? null;
}
