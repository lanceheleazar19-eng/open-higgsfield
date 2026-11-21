import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { LoginForm } from "@/escaparate/login-form";
import { safeCurrentUser } from "@/escaparate/server/viewer";

export const metadata: Metadata = { title: "Entrar", robots: { index: false } };

export default async function EntrarPage({ searchParams }: { searchParams: Promise<{ siguiente?: string }> }) {
  const { siguiente } = await searchParams;
  const next = siguiente?.startsWith("/escaparate") ? siguiente : "/escaparate/crear";
  if (await safeCurrentUser()) redirect(next);
  return (
    <main className="esc-wrap" style={{ maxWidth: 520, padding: "48px 16px 64px" }}>
      <LoginForm next={next} />
    </main>
  );
}
