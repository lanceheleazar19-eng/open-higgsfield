import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { Creator } from "@/escaparate/creator";
import { safeCurrentUser } from "@/escaparate/server/viewer";

export const metadata: Metadata = {
  title: "Crear fotos de producto",
  alternates: { canonical: "/escaparate/crear" },
};

export default async function CrearPage() {
  const user = await safeCurrentUser();
  if (!user) redirect("/escaparate/entrar?siguiente=/escaparate/crear");
  return (
    <main className="esc-wrap">
      <div style={{ paddingTop: 32 }}>
        <h1 style={{ fontSize: "clamp(28px, 4vw, 40px)", margin: "0 0 8px" }}>Crea fotos que venden</h1>
        <p className="esc-lead" style={{ marginBottom: 0 }}>
          Sube una foto de tu producto hecha con el móvil y en un minuto tendrás 4 fotos profesionales, un
          vídeo y el texto para publicarlo.
        </p>
      </div>
      <Creator initialCredits={user.credits} />
    </main>
  );
}
