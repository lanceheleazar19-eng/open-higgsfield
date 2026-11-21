// Applies src/escaparate/server/schema.sql to DATABASE_URL.
import { readFile } from "node:fs/promises";

import postgres from "postgres";

const url = process.env.DATABASE_URL;
if (!url) {
  console.error("Missing DATABASE_URL");
  process.exit(1);
}

const sql = postgres(url, { max: 1, onnotice: () => {} });
try {
  const schema = await readFile(new URL("../src/escaparate/server/schema.sql", import.meta.url), "utf8");
  await sql.unsafe(schema);
  console.log("Escaparate schema is up to date.");
} finally {
  await sql.end();
}
