import type { Metadata } from "next";

import { Creator } from "@/escaparate/creator";

export const metadata: Metadata = {
  title: "Crear fotos de producto",
  alternates: { canonical: "/escaparate/crear" },
};

export default function CrearPage() {
  return (
    <main className="esc-wrap">
      <div style={{ paddingTop: 32 }}>
        <h1 style={{ fontSize: "clamp(28px, 4vw, 40px)", margin: "0 0 8px" }}>Crea fotos que venden</h1>
        <p className="esc-lead" style={{ marginBottom: 0 }}>
          Sube una foto de tu producto hecha con el móvil y en un minuto tendrás 4 fotos profesionales, un
          vídeo y el texto para publicarlo.
        </p>
      </div>
      <Creator />
    </main>
  );
}
