"use server";

import { getModel, parseSettings } from "@/generation/catalog";
import type { GenerationPlane } from "@/generation/catalog/types";
import { createPlatformClient } from "@/generation/platform";
import { toPlatform } from "@/generation/to-platform";

import {
  FORMATS,
  IMAGE_MODEL,
  SECTORS,
  STYLES,
  VIDEO_MODEL,
  formatById,
  imagePrompts,
  videoPrompt,
  type FormatId,
  type SectorId,
  type StyleId,
} from "../content";
import { COST } from "../plans";
import { grantCredits, spendCredits } from "./credits";
import { db } from "./db";
import { currentUser } from "./session";
import { persistResult } from "./storage";

export type StartResult =
  | { ok: true; requestIds: string[]; credits: number }
  | { ok: false; error: "login" | "credits" | "input" | "platform"; credits?: number };

export type JobStatus = {
  requestId: string;
  state: "pending" | "done" | "failed";
  url?: string;
  reason?: string;
};

const TERMINAL_FAIL = new Set(["failed", "nsfw", "canceled"]);

/* The shop pays for generations with credits, so the platform key is the
   business's own, held in the server environment — never the visitor's. */
function platform() {
  const apiKey = process.env.ESCAPARATE_PLATFORM_KEY;
  const baseUrl = process.env.HF_API_BASE_URL;
  if (!apiKey || !baseUrl) throw new Error("Missing ESCAPARATE_PLATFORM_KEY or HF_API_BASE_URL");
  return createPlatformClient({ apiKey, baseUrl });
}

async function submit(plane: GenerationPlane) {
  const model = getModel(plane.model);
  const { path, body } = toPlatform({ ...plane, settings: parseSettings(model, plane.settings) });
  return platform().submit(path, body);
}

export async function startImages(data: unknown): Promise<StartResult> {
  const user = await currentUser();
  if (!user) return { ok: false, error: "login" };
  const input = parseImageInput(data);
  if (!input) return { ok: false, error: "input" };

  const prompts = imagePrompts(input);
  const cost = prompts.length * COST.image;
  const balance = await spendCredits(user.id, cost, `${prompts.length} fotos`);
  if (balance === null) return { ok: false, error: "credits", credits: user.credits };

  const aspectRatio = formatById(input.format).aspectRatio;
  const reference = [{ id: "producto", url: input.photoUrl, role: "reference" as const }];
  const settled = await Promise.allSettled(
    prompts.map((text) =>
      submit({ model: IMAGE_MODEL, prompt: { text }, media: { reference }, settings: { aspectRatio, resolution: "1k" } }),
    ),
  );

  const requestIds: string[] = [];
  for (const result of settled) {
    if (result.status === "fulfilled") requestIds.push(result.value.requestId);
    else console.error("[escaparate] image submit failed", result.reason);
  }
  if (requestIds.length) {
    const sql = db();
    await sql`
      INSERT INTO esc_generations ${sql(
        requestIds.map((requestId) => ({
          request_id: requestId,
          user_id: user.id,
          kind: "image",
          credits: COST.image,
          product_name: input.productName,
          format: input.format,
        })),
      )}`;
  }

  const failed = prompts.length - requestIds.length;
  let credits = balance;
  if (failed > 0) {
    await grantCredits(user.id, failed * COST.image, "Devolución: no se pudo enviar", `submit-refund:${crypto.randomUUID()}`);
    credits += failed * COST.image;
  }
  if (!requestIds.length) return { ok: false, error: "platform", credits };
  return { ok: true, requestIds, credits };
}

export async function startVideo(data: unknown): Promise<StartResult> {
  const user = await currentUser();
  if (!user) return { ok: false, error: "login" };
  const input = parseVideoInput(data);
  if (!input) return { ok: false, error: "input" };

  /* Only a photo this shop already made can be animated: it keeps credits
     tied to the product flow and stops the endpoint animating arbitrary URLs. */
  const [owned] = await db()<{ product_name: string }[]>`
    SELECT product_name FROM esc_generations
    WHERE user_id = ${user.id} AND kind = 'image' AND (result_url = ${input.imageUrl} OR source_url = ${input.imageUrl})
    LIMIT 1`;
  if (!owned) return { ok: false, error: "input" };

  const balance = await spendCredits(user.id, COST.video, "1 vídeo");
  if (balance === null) return { ok: false, error: "credits", credits: user.credits };

  try {
    const queued = await submit({
      model: VIDEO_MODEL,
      prompt: { text: videoPrompt(input.style) },
      media: { start: [{ id: "foto", url: input.imageUrl, role: "start" }] },
      settings: { duration: 5, resolution: "720p", aspectRatio: formatById(input.format).aspectRatio },
    });
    await db()`
      INSERT INTO esc_generations (request_id, user_id, kind, credits, product_name, format)
      VALUES (${queued.requestId}, ${user.id}, 'video', ${COST.video}, ${owned.product_name}, ${input.format})`;
    return { ok: true, requestIds: [queued.requestId], credits: balance };
  } catch (caught) {
    console.error("[escaparate] video submit failed", caught);
    await grantCredits(user.id, COST.video, "Devolución: no se pudo enviar", `submit-refund:${crypto.randomUUID()}`);
    return { ok: false, error: "platform", credits: balance + COST.video };
  }
}

/** Status of this shop's own jobs. A job that fails gives its credits back,
    once. */
export async function checkJobs(data: unknown): Promise<{ jobs: JobStatus[]; credits: number } | null> {
  const user = await currentUser();
  if (!user) return null;
  const ids = Array.isArray((data as { requestIds?: unknown })?.requestIds)
    ? ((data as { requestIds: unknown[] }).requestIds.filter((id) => typeof id === "string") as string[]).slice(0, 20)
    : [];
  if (!ids.length) return { jobs: [], credits: user.credits };

  const sql = db();
  const rows = await sql<
    { request_id: string; kind: "image" | "video"; status: string; result_url: string | null; credits: number; refunded: boolean }[]
  >`
    SELECT request_id, kind, status, result_url, credits, refunded FROM esc_generations
    WHERE user_id = ${user.id} AND request_id IN ${sql(ids)}`;

  const client = platform();
  let refundedNow = 0;
  const jobs = await Promise.all(
    rows.map(async (row): Promise<JobStatus> => {
      if (row.status === "completed" && row.result_url) {
        return { requestId: row.request_id, state: "done", url: row.result_url };
      }
      if (TERMINAL_FAIL.has(row.status)) {
        return { requestId: row.request_id, state: "failed", reason: failureReason(row.status) };
      }
      try {
        const status = await client.status(row.request_id);
        const url = status.images?.[0]?.url ?? status.video?.url;
        if (status.status === "completed" && url) {
          const kept = (await persistResult(url, user.id, row.request_id, row.kind)) ?? url;
          await sql`
            UPDATE esc_generations SET status = 'completed', result_url = ${kept}, source_url = ${url}
            WHERE request_id = ${row.request_id}`;
          return { requestId: row.request_id, state: "done", url: kept };
        }
        if (TERMINAL_FAIL.has(status.status) || status.status === "completed") {
          const finalStatus = status.status === "completed" ? "failed" : status.status;
          await sql`UPDATE esc_generations SET status = ${finalStatus} WHERE request_id = ${row.request_id}`;
          if (!row.refunded) {
            const granted = await grantCredits(user.id, row.credits, "Devolución: generación fallida", `refund:${row.request_id}`);
            if (granted) {
              await sql`UPDATE esc_generations SET refunded = true WHERE request_id = ${row.request_id}`;
              refundedNow += row.credits;
            }
          }
          return { requestId: row.request_id, state: "failed", reason: failureReason(finalStatus) };
        }
        return { requestId: row.request_id, state: "pending" };
      } catch {
        return { requestId: row.request_id, state: "pending" };
      }
    }),
  );
  return { jobs, credits: user.credits + refundedNow };
}

function failureReason(status: string): string {
  if (status === "nsfw") return "La foto no ha pasado el filtro de contenido. Te devolvemos los créditos.";
  return "No se pudo generar. Te devolvemos los créditos.";
}

function parseImageInput(data: unknown) {
  if (data === null || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const photoUrl = typeof record.photoUrl === "string" ? record.photoUrl : "";
  if (!isHttpsUrl(photoUrl)) return null;
  const sector = SECTORS.find((item) => item.id === record.sector)?.id;
  const style = STYLES.find((item) => item.id === record.style)?.id;
  const format = FORMATS.find((item) => item.id === record.format)?.id;
  if (!sector || !style || !format) return null;
  const productName = typeof record.productName === "string" ? record.productName.slice(0, 80) : "";
  return { photoUrl, sector: sector as SectorId, style: style as StyleId, format: format as FormatId, productName };
}

function parseVideoInput(data: unknown) {
  if (data === null || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const imageUrl = typeof record.imageUrl === "string" ? record.imageUrl : "";
  const style = STYLES.find((item) => item.id === record.style)?.id;
  const format = FORMATS.find((item) => item.id === record.format)?.id;
  if (!isHttpsUrl(imageUrl) || !style || !format) return null;
  return { imageUrl, style: style as StyleId, format: format as FormatId };
}

function isHttpsUrl(value: string): boolean {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}
