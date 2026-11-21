"use server";

import { revalidatePath } from "next/cache";

import { db } from "./db";
import { currentUser } from "./session";

export async function toggleFavorite(formData: FormData): Promise<void> {
  const user = await currentUser();
  const requestId = String(formData.get("requestId") ?? "");
  if (!user || !requestId) return;
  await db()`
    UPDATE esc_generations SET favorite = NOT favorite
    WHERE request_id = ${requestId} AND user_id = ${user.id}`;
  revalidatePath("/escaparate/creaciones");
}

/** Hides a result from the gallery. Kept in the database: it still explains
    the credits it used in the account history. */
export async function hideCreation(formData: FormData): Promise<void> {
  const user = await currentUser();
  const requestId = String(formData.get("requestId") ?? "");
  if (!user || !requestId) return;
  await db()`
    UPDATE esc_generations SET hidden = true, favorite = false
    WHERE request_id = ${requestId} AND user_id = ${user.id}`;
  revalidatePath("/escaparate/creaciones");
}
