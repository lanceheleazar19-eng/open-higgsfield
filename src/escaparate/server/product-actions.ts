"use server";

import { revalidatePath } from "next/cache";

import { SECTORS } from "../content";
import { db } from "./db";
import { currentUser } from "./session";

export type SaveProductResult = { ok: true; productId: string } | { ok: false; error: string };

/** Creates the product, or updates it when `productId` is one of the shop's own. */
export async function saveProduct(data: unknown): Promise<SaveProductResult> {
  const user = await currentUser();
  if (!user) return { ok: false, error: "login" };
  const input = parse(data);
  if (!input) return { ok: false, error: "input" };

  const sql = db();
  if (input.productId) {
    const [updated] = await sql<{ id: string }[]>`
      UPDATE esc_products SET
        name = ${input.name}, price = ${input.price}, details = ${input.details},
        sector = ${input.sector}, photo_url = ${input.photoUrl}, updated_at = now()
      WHERE id = ${input.productId} AND user_id = ${user.id}
      RETURNING id`;
    if (updated) return { ok: true, productId: updated.id };
  }
  const [created] = await sql<{ id: string }[]>`
    INSERT INTO esc_products (user_id, name, price, details, sector, photo_url)
    VALUES (${user.id}, ${input.name}, ${input.price}, ${input.details}, ${input.sector}, ${input.photoUrl})
    RETURNING id`;
  return { ok: true, productId: created.id };
}

export async function deleteProduct(formData: FormData): Promise<void> {
  const user = await currentUser();
  const productId = String(formData.get("productId") ?? "");
  if (!user || !UUID.test(productId)) return;
  await db()`DELETE FROM esc_products WHERE id = ${productId} AND user_id = ${user.id}`;
  revalidatePath("/escaparate/catalogo");
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function parse(data: unknown) {
  if (data === null || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const text = (key: string, max: number) => (typeof record[key] === "string" ? (record[key] as string).trim().slice(0, max) : "");
  const photoUrl = text("photoUrl", 1000);
  try {
    if (new URL(photoUrl).protocol !== "https:") return null;
  } catch {
    return null;
  }
  const sector = SECTORS.find((item) => item.id === record.sector)?.id ?? "otro";
  const productId = text("productId", 40);
  return {
    productId: UUID.test(productId) ? productId : null,
    name: text("name", 80),
    price: text("price", 12),
    details: text("details", 300),
    sector,
    photoUrl,
  };
}
