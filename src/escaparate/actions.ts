"use server";

import { randomUUID } from "node:crypto";

import { put } from "@vercel/blob";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export type WaitlistResult = { ok: true } | { ok: false; error: string };

/** Stores one waitlist sign-up as a private JSON blob. Private on purpose: the
    entries hold people's contact details and must never sit at a public URL. */
export async function joinWaitlist(data: unknown): Promise<WaitlistResult> {
  const entry = parseEntry(data);
  if (!("email" in entry)) return { ok: false, error: entry.error };

  const token =
    process.env.ESCAPARATE_WAITLIST_TOKEN ?? process.env.OPEN_HIGGSFIELD_READ_WRITE_TOKEN;
  if (!token) {
    console.error("[escaparate] waitlist storage is not configured");
    return { ok: false, error: "Ahora mismo no podemos guardar tu solicitud. Inténtalo más tarde." };
  }

  try {
    await put(
      `escaparate/waitlist/${Date.now()}-${randomUUID()}.json`,
      JSON.stringify({ ...entry, createdAt: new Date().toISOString() }),
      { access: "private", contentType: "application/json", token },
    );
    return { ok: true };
  } catch (caught) {
    console.error("[escaparate] waitlist write failed", caught instanceof Error ? caught.message : caught);
    return { ok: false, error: "No hemos podido guardar tu solicitud. Inténtalo de nuevo." };
  }
}

function parseEntry(data: unknown) {
  if (data === null || typeof data !== "object") return { error: "Datos no válidos." };
  const record = data as Record<string, unknown>;
  const email = text(record.email, 200).toLowerCase();
  if (!EMAIL.test(email)) return { error: "Revisa tu correo electrónico." };
  if (record.consent !== true) return { error: "Necesitamos tu permiso para escribirte." };
  return {
    email,
    business: text(record.business, 120),
    sector: text(record.sector, 40),
    city: text(record.city, 80),
  };
}

function text(value: unknown, max: number): string {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}
