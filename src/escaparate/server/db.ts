import "server-only";

import postgres from "postgres";

type Sql = ReturnType<typeof postgres>;

const globalForDb = globalThis as unknown as { escSql?: Sql };

/** One pool per server instance; reused across hot reloads in development. */
export function db(): Sql {
  if (globalForDb.escSql) return globalForDb.escSql;
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("Missing DATABASE_URL");
  const sql = postgres(url, { max: 5, idle_timeout: 20, prepare: false, onnotice: () => {} });
  globalForDb.escSql = sql;
  return sql;
}
