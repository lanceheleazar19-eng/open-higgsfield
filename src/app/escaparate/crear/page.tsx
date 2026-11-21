import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentOccasion, daysUntil, occasionById, todayInSpain } from "@/escaparate/calendar";
import { SECTORS, type SectorId } from "@/escaparate/content";
import { Creator, type CreatorOccasion, type CreatorProduct } from "@/escaparate/creator";
import { db } from "@/escaparate/server/db";
import { safeCurrentUser } from "@/escaparate/server/viewer";

export const metadata: Metadata = {
  title: "Crear fotos de producto",
  alternates: { canonical: "/escaparate/crear" },
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function CrearPage({
  searchParams,
}: {
  searchParams: Promise<{ producto?: string; ocasion?: string }>;
}) {
  const user = await safeCurrentUser();
  if (!user) redirect("/escaparate/entrar?siguiente=/escaparate/crear");
  const { producto, ocasion } = await searchParams;

  let product: CreatorProduct | undefined;
  if (producto && UUID.test(producto)) {
    const [row] = await db()<
      { id: string; name: string; price: string; details: string; sector: string; photo_url: string }[]
    >`
      SELECT id, name, price, details, sector, photo_url FROM esc_products
      WHERE id = ${producto} AND user_id = ${user.id}`;
    if (row) {
      product = {
        id: row.id,
        name: row.name,
        price: row.price,
        details: row.details,
        sector: (SECTORS.find((item) => item.id === row.sector)?.id ?? "otro") as SectorId,
        photoUrl: row.photo_url,
      };
    }
  }

  // An occasion picked in the calendar wins; otherwise suggest the one in season.
  const today = todayInSpain();
  const found = ocasion ? occasionById(ocasion, today) : currentOccasion(today, product?.sector);
  const occasion: CreatorOccasion | undefined = found
    ? { id: found.id, emoji: found.emoji, title: found.title, idea: found.idea, daysLeft: daysUntil(found.date, today) }
    : undefined;

  return (
    <main className="esc-wrap">
      <div style={{ paddingTop: 32 }}>
        <h1 style={{ fontSize: "clamp(28px, 4vw, 40px)", margin: "0 0 8px" }}>Crea fotos que venden</h1>
        <p className="esc-lead" style={{ marginBottom: 0 }}>
          Sube una foto de tu producto hecha con el móvil y en un minuto tendrás 4 fotos profesionales, un
          vídeo y el texto para publicarlo.
        </p>
      </div>
      <Creator
        key={`${product?.id ?? "nuevo"}-${occasion?.id ?? ""}`}
        initialCredits={user.credits}
        initialBusinessName={user.businessName}
        initialCity={user.city}
        product={product}
        occasion={occasion}
      />
    </main>
  );
}
