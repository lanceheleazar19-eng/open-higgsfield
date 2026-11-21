import "server-only";

import { cookies } from "next/headers";

import { currentUser, type User } from "./session";

/** The signed-in shop, or null — also when the database is not configured or
    unreachable, so public pages keep rendering. */
export async function safeCurrentUser(): Promise<User | null> {
  /* Read the cookie jar outside the try: it is how Next learns this render is
     per-request, and that signal must not be swallowed by the catch below. */
  await cookies();
  try {
    return await currentUser();
  } catch (caught) {
    console.error("[escaparate] could not read the session", caught instanceof Error ? caught.message : caught);
    return null;
  }
}
