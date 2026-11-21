import "server-only";

import { createHash, randomBytes, randomInt, timingSafeEqual } from "node:crypto";

import { cookies } from "next/headers";

import { SIGNUP_CREDITS } from "../plans";
import { db } from "./db";

export const SESSION_COOKIE = "esc_session";
const SESSION_DAYS = 30;
const CODE_MINUTES = 10;
const MAX_CODES_PER_HOUR = 5;
const MAX_ATTEMPTS = 5;

export type User = {
  id: string;
  email: string;
  businessName: string;
  city: string;
  credits: number;
  plan: string;
  subscriptionStatus: string | null;
  stripeCustomerId: string | null;
};

export function hash(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

/** Creates a 6-digit code for this email, or null when too many were asked for. */
export async function createLoginCode(email: string): Promise<string | null> {
  const sql = db();
  const [{ count }] = await sql<[{ count: number }]>`
    SELECT count(*)::int AS count FROM esc_login_codes
    WHERE email = ${email} AND created_at > now() - interval '1 hour'`;
  if (count >= MAX_CODES_PER_HOUR) return null;
  const code = String(randomInt(0, 1_000_000)).padStart(6, "0");
  await sql`
    INSERT INTO esc_login_codes (email, code_hash, expires_at)
    VALUES (${email}, ${hash(`${email}:${code}`)}, now() + ${`${CODE_MINUTES} minutes`}::interval)`;
  return code;
}

export type VerifyResult = "ok" | "invalid" | "expired" | "locked";

/** Checks the latest code for the email; on success creates the account if
    needed and opens a session cookie. */
export async function verifyLoginCode(email: string, code: string): Promise<VerifyResult> {
  const sql = db();
  const [row] = await sql<{ id: number; code_hash: string; attempts: number; used: boolean; expired: boolean }[]>`
    SELECT id, code_hash, attempts, used, expires_at < now() AS expired
    FROM esc_login_codes WHERE email = ${email}
    ORDER BY created_at DESC LIMIT 1`;
  if (!row || row.used) return "invalid";
  if (row.expired) return "expired";
  if (row.attempts >= MAX_ATTEMPTS) return "locked";

  const expected = Buffer.from(row.code_hash, "hex");
  const given = Buffer.from(hash(`${email}:${code}`), "hex");
  if (!timingSafeEqual(expected, given)) {
    await sql`UPDATE esc_login_codes SET attempts = attempts + 1 WHERE id = ${row.id}`;
    return row.attempts + 1 >= MAX_ATTEMPTS ? "locked" : "invalid";
  }

  const userId = await sql.begin(async (tx) => {
    await tx`UPDATE esc_login_codes SET used = true WHERE id = ${row.id}`;
    const [created] = await tx<{ id: string }[]>`
      INSERT INTO esc_users (email, credits) VALUES (${email}, ${SIGNUP_CREDITS})
      ON CONFLICT (email) DO NOTHING RETURNING id`;
    if (created) {
      await tx`
        INSERT INTO esc_credit_ledger (user_id, delta, reason, ref)
        VALUES (${created.id}, ${SIGNUP_CREDITS}, 'Regalo de bienvenida', ${`signup:${created.id}`})`;
      return created.id;
    }
    const [existing] = await tx<{ id: string }[]>`SELECT id FROM esc_users WHERE email = ${email}`;
    return existing.id;
  });

  const token = randomBytes(32).toString("base64url");
  await sql`
    INSERT INTO esc_sessions (token_hash, user_id, expires_at)
    VALUES (${hash(token)}, ${userId}, now() + ${`${SESSION_DAYS} days`}::interval)`;
  const jar = await cookies();
  jar.set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_DAYS * 24 * 60 * 60,
  });
  return "ok";
}

export async function currentUser(): Promise<User | null> {
  const jar = await cookies();
  const token = jar.get(SESSION_COOKIE)?.value;
  if (!token) return null;
  const [row] = await db()<
    {
      id: string;
      email: string;
      business_name: string;
      city: string;
      credits: number;
      plan: string;
      subscription_status: string | null;
      stripe_customer_id: string | null;
    }[]
  >`
    SELECT u.id, u.email, u.business_name, u.city, u.credits, u.plan, u.subscription_status, u.stripe_customer_id
    FROM esc_sessions s JOIN esc_users u ON u.id = s.user_id
    WHERE s.token_hash = ${hash(token)} AND s.expires_at > now()`;
  if (!row) return null;
  return {
    id: row.id,
    email: row.email,
    businessName: row.business_name,
    city: row.city,
    credits: row.credits,
    plan: row.plan,
    subscriptionStatus: row.subscription_status,
    stripeCustomerId: row.stripe_customer_id,
  };
}

export async function endSession(): Promise<void> {
  const jar = await cookies();
  const token = jar.get(SESSION_COOKIE)?.value;
  if (token) await db()`DELETE FROM esc_sessions WHERE token_hash = ${hash(token)}`;
  jar.set(SESSION_COOKIE, "", { path: "/", maxAge: 0 });
}
