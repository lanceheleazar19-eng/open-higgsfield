import "server-only";

import { db } from "./db";

/** Takes credits only if the balance covers them. Returns the new balance, or
    null when there were not enough. One statement, so two tabs pressing at once
    can never spend the same credits twice. */
export async function spendCredits(userId: string, amount: number, reason: string): Promise<number | null> {
  return db().begin(async (tx) => {
    const [row] = await tx<{ credits: number }[]>`
      UPDATE esc_users SET credits = credits - ${amount}
      WHERE id = ${userId} AND credits >= ${amount}
      RETURNING credits`;
    if (!row) return null;
    await tx`INSERT INTO esc_credit_ledger (user_id, delta, reason) VALUES (${userId}, ${-amount}, ${reason})`;
    return row.credits;
  });
}

/** Adds credits once per `ref`: a replayed webhook or a double refund is a no-op.
    Returns whether credits were added. */
export async function grantCredits(userId: string, amount: number, reason: string, ref: string): Promise<boolean> {
  return db().begin(async (tx) => {
    const [entry] = await tx<{ id: number }[]>`
      INSERT INTO esc_credit_ledger (user_id, delta, reason, ref)
      VALUES (${userId}, ${amount}, ${reason}, ${ref})
      ON CONFLICT (ref) DO NOTHING RETURNING id`;
    if (!entry) return false;
    await tx`UPDATE esc_users SET credits = credits + ${amount} WHERE id = ${userId}`;
    return true;
  });
}
