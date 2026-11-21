"use server";

import { occasionById, todayInSpain } from "../calendar";
import { SECTORS, salesCopy, type SalesCopy, type SectorId } from "../content";
import { TONES, writeCopy, type Tone } from "./copywriter";
import { db } from "./db";
import { currentUser } from "./session";

/** Free for shops, but capped per day so one account cannot run up the bill. */
const DAILY_LIMIT = 40;

export type CopyResult =
  | { ok: true; copy: SalesCopy; source: "ia" | "plantilla" }
  | { ok: false; error: string };

export async function generateCopy(data: unknown): Promise<CopyResult> {
  const user = await currentUser();
  if (!user) return { ok: false, error: "Tu sesión ha caducado. Vuelve a entrar." };
  const input = parse(data);
  if (!input) return { ok: false, error: "Faltan datos del producto." };

  const sql = db();
  const [{ count }] = await sql<[{ count: number }]>`
    SELECT count(*)::int AS count FROM esc_copy_log
    WHERE user_id = ${user.id} AND created_at > now() - interval '1 day'`;
  if (count >= DAILY_LIMIT) {
    return { ok: false, error: "Has llegado al límite de textos de hoy. Mañana puedes pedir más." };
  }
  await sql`INSERT INTO esc_copy_log (user_id) VALUES (${user.id})`;

  // Remember the shop's details so the next product starts pre-filled.
  if (input.businessName || input.city) {
    await sql`
      UPDATE esc_users SET
        business_name = CASE WHEN ${input.businessName} <> '' THEN ${input.businessName} ELSE business_name END,
        city = CASE WHEN ${input.city} <> '' THEN ${input.city} ELSE city END
      WHERE id = ${user.id}`;
  }

  const occasion = input.occasionId ? occasionById(input.occasionId, todayInSpain()) : null;
  const written = await writeCopy({ ...input, occasion: occasion?.brief });
  if (written) return { ok: true, copy: written, source: "ia" };
  return {
    ok: true,
    copy: salesCopy({ ...input, occasion: occasion ? `${occasion.emoji} ${occasion.title}` : undefined }),
    source: "plantilla",
  };
}

function parse(data: unknown) {
  if (data === null || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const text = (key: string, max: number) => (typeof record[key] === "string" ? (record[key] as string).trim().slice(0, max) : "");
  const sector = SECTORS.find((item) => item.id === record.sector)?.id as SectorId | undefined;
  const tone = (TONES as readonly string[]).includes(String(record.tone)) ? (record.tone as Tone) : "cercano";
  if (!sector) return null;
  return {
    sector,
    tone,
    productName: text("productName", 80),
    price: text("price", 12),
    businessName: text("businessName", 80),
    city: text("city", 60),
    details: text("details", 300),
    occasionId: text("occasionId", 40),
  };
}
