"use server";

import { redirect } from "next/navigation";

import { sendLoginCode } from "./email";
import { createLoginCode, endSession, verifyLoginCode } from "./session";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export type AuthResult = { ok: true } | { ok: false; error: string };

export async function requestCode(data: unknown): Promise<AuthResult> {
  const email = readEmail(data);
  if (!email) return { ok: false, error: "Revisa tu correo electrónico." };
  try {
    const code = await createLoginCode(email);
    if (!code) return { ok: false, error: "Has pedido demasiados códigos. Espera un rato e inténtalo de nuevo." };
    await sendLoginCode(email, code);
    return { ok: true };
  } catch (caught) {
    console.error("[escaparate] login code failed", caught instanceof Error ? caught.message : caught);
    return { ok: false, error: "No hemos podido enviarte el código. Inténtalo de nuevo." };
  }
}

export async function verifyCode(data: unknown): Promise<AuthResult> {
  const email = readEmail(data);
  const code = typeof (data as { code?: unknown })?.code === "string" ? (data as { code: string }).code.replace(/\D/g, "") : "";
  if (!email || code.length !== 6) return { ok: false, error: "El código tiene 6 números." };
  try {
    const result = await verifyLoginCode(email, code);
    if (result === "ok") return { ok: true };
    if (result === "expired") return { ok: false, error: "El código ha caducado. Pide uno nuevo." };
    if (result === "locked") return { ok: false, error: "Demasiados intentos. Pide un código nuevo." };
    return { ok: false, error: "El código no es correcto." };
  } catch (caught) {
    console.error("[escaparate] verify failed", caught instanceof Error ? caught.message : caught);
    return { ok: false, error: "No hemos podido comprobar el código. Inténtalo de nuevo." };
  }
}

export async function signOut(): Promise<void> {
  await endSession();
  redirect("/escaparate");
}

function readEmail(data: unknown): string | null {
  const raw = (data as { email?: unknown })?.email;
  if (typeof raw !== "string") return null;
  const email = raw.trim().toLowerCase().slice(0, 200);
  return EMAIL.test(email) ? email : null;
}
