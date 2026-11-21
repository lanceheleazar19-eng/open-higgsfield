/* Prices and credit costs in one place: the landing page, the account page and
   the Stripe webhook all read from here. Shared by client and server — no
   secrets. Stripe price ids live in env vars, resolved on the server only. */

export const COST = { image: 1, video: 10 } as const;

/** Credits a new account starts with. */
export const SIGNUP_CREDITS = 12;

export type PlanId = "comercio" | "pro";
export type PackId = "pack60";

export type Plan = {
  id: PlanId;
  name: string;
  priceEuros: number;
  monthlyCredits: number;
  perks: readonly string[];
};

export const PLANS: readonly Plan[] = [
  {
    id: "comercio",
    name: "Comercio",
    priceEuros: 9,
    monthlyCredits: 100,
    perks: ["100 créditos al mes", "Fotos y vídeos", "Textos de venta", "Soporte por WhatsApp"],
  },
  {
    id: "pro",
    name: "Pro",
    priceEuros: 24,
    monthlyCredits: 350,
    perks: ["350 créditos al mes", "Fotos y vídeos", "Ideal para tiendas con mucho catálogo", "Soporte prioritario"],
  },
];

export type Pack = { id: PackId; name: string; priceEuros: number; credits: number };

export const PACKS: readonly Pack[] = [{ id: "pack60", name: "Pack 60 créditos", priceEuros: 6, credits: 60 }];

export function planById(id: string): Plan | undefined {
  return PLANS.find((plan) => plan.id === id);
}

export function packById(id: string): Pack | undefined {
  return PACKS.find((pack) => pack.id === id);
}

export function planName(id: string): string {
  return planById(id)?.name ?? "Gratis";
}
