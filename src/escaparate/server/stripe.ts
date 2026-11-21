import "server-only";

import Stripe from "stripe";

const globalForStripe = globalThis as unknown as { escStripe?: Stripe };

export function stripe(): Stripe {
  if (globalForStripe.escStripe) return globalForStripe.escStripe;
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw new Error("Missing STRIPE_SECRET_KEY");
  globalForStripe.escStripe = new Stripe(key);
  return globalForStripe.escStripe;
}

export function siteOrigin(): string {
  const explicit = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (explicit) return explicit.replace(/\/+$/, "");
  const vercel = process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim();
  if (vercel) return `https://${vercel.replace(/^https?:\/\//, "").replace(/\/+$/, "")}`;
  return "http://localhost:3000";
}
