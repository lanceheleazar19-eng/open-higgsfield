"use server";

import { del, list } from "@vercel/blob";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { db } from "./db";
import { SESSION_COOKIE, currentUser } from "./session";
import { stripe } from "./stripe";

/** RGPD right to erasure: cancels any subscription, deletes the shop's files
    and every row about it, and signs it out. Stripe keeps its own invoices, as
    tax law requires. */
export async function deleteAccount(formData: FormData): Promise<void> {
  const user = await currentUser();
  if (!user) redirect("/escaparate");
  if (String(formData.get("confirm") ?? "").trim().toUpperCase() !== "BORRAR") {
    redirect("/escaparate/cuenta?borrar=confirmar");
  }

  const sql = db();
  const [account] = await sql<{ stripe_subscription_id: string | null; subscription_status: string | null }[]>`
    SELECT stripe_subscription_id, subscription_status FROM esc_users WHERE id = ${user.id}`;
  if (account?.stripe_subscription_id && account.subscription_status !== "canceled") {
    try {
      await stripe().subscriptions.cancel(account.stripe_subscription_id);
    } catch (caught) {
      console.error("[escaparate] could not cancel subscription on delete", caught instanceof Error ? caught.message : caught);
      redirect("/escaparate/cuenta?borrar=error");
    }
  }

  await deleteFiles(user.id);
  await sql`DELETE FROM esc_users WHERE id = ${user.id}`;
  const jar = await cookies();
  jar.set(SESSION_COOKIE, "", { path: "/", maxAge: 0 });
  redirect("/escaparate?cuenta=borrada");
}

async function deleteFiles(userId: string): Promise<void> {
  const token = process.env.OPEN_HIGGSFIELD_READ_WRITE_TOKEN;
  if (!token) return;
  const sql = db();
  const rows = await sql<{ url: string }[]>`
    SELECT photo_url AS url FROM esc_products WHERE user_id = ${userId}
    UNION SELECT result_url FROM esc_generations WHERE user_id = ${userId} AND result_url IS NOT NULL`;
  const urls = rows.map((row) => row.url).filter((url) => url.includes(".blob.vercel-storage.com"));
  try {
    let cursor: string | undefined;
    do {
      const page = await list({ prefix: `escaparate/resultados/${userId}/`, cursor, token });
      urls.push(...page.blobs.map((blob) => blob.url));
      cursor = page.hasMore ? page.cursor : undefined;
    } while (cursor);
    const unique = [...new Set(urls)];
    for (let index = 0; index < unique.length; index += 100) {
      await del(unique.slice(index, index + 100), { token });
    }
  } catch (caught) {
    // The account is still deleted; leftover files are logged for manual cleanup.
    console.error("[escaparate] could not delete all files for", userId, caught instanceof Error ? caught.message : caught);
  }
}
