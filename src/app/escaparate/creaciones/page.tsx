import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { db } from "@/escaparate/server/db";
import { hideCreation, toggleFavorite } from "@/escaparate/server/gallery-actions";
import { safeCurrentUser } from "@/escaparate/server/viewer";

export const metadata: Metadata = { title: "Mis creaciones", robots: { index: false } };

const FILTERS = [
  { id: "todo", label: "Todo" },
  { id: "fotos", label: "Fotos" },
  { id: "videos", label: "Vídeos" },
  { id: "favoritas", label: "⭐ Favoritas" },
] as const;
type FilterId = (typeof FILTERS)[number]["id"];

const PAGE_SIZE = 48;

type Row = {
  request_id: string;
  kind: "image" | "video";
  result_url: string;
  product_name: string;
  format: string;
  favorite: boolean;
  created_at: Date;
};

export default async function CreacionesPage({ searchParams }: { searchParams: Promise<{ ver?: string }> }) {
  const user = await safeCurrentUser();
  if (!user) redirect("/escaparate/entrar?siguiente=/escaparate/creaciones");
  const { ver } = await searchParams;
  const filter: FilterId = FILTERS.some((item) => item.id === ver) ? (ver as FilterId) : "todo";

  const sql = db();
  const rows = await sql<Row[]>`
    SELECT request_id, kind, result_url, product_name, format, favorite, created_at
    FROM esc_generations
    WHERE user_id = ${user.id} AND status = 'completed' AND result_url IS NOT NULL AND NOT hidden
      ${filter === "fotos" ? sql`AND kind = 'image'` : sql``}
      ${filter === "videos" ? sql`AND kind = 'video'` : sql``}
      ${filter === "favoritas" ? sql`AND favorite` : sql``}
    ORDER BY created_at DESC
    LIMIT ${PAGE_SIZE}`;

  return (
    <main className="esc-wrap esc-creator">
      <div>
        <h1 style={{ fontSize: "clamp(28px, 4vw, 40px)", margin: "0 0 4px" }}>Mis creaciones</h1>
        <p className="esc-note" style={{ margin: 0 }}>Todas tus fotos y vídeos, guardados para que los descargues cuando quieras.</p>
      </div>

      <nav className="esc-chips" aria-label="Filtrar creaciones">
        {FILTERS.map((item) => (
          <Link
            key={item.id}
            href={item.id === "todo" ? "/escaparate/creaciones" : `/escaparate/creaciones?ver=${item.id}`}
            className="esc-chip"
            aria-pressed={item.id === filter}
            aria-current={item.id === filter ? "page" : undefined}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      {rows.length === 0 ? (
        <section className="esc-panel" style={{ textAlign: "center" }}>
          <p style={{ fontSize: 40, margin: 0 }} aria-hidden>
            📸
          </p>
          <p style={{ margin: 0 }}>
            {filter === "favoritas"
              ? "Aún no tienes favoritas. Marca con ⭐ las que más te gusten."
              : "Aún no has creado nada. ¡Empieza con tu primer producto!"}
          </p>
          <div>
            <Link href="/escaparate/crear" className="esc-btn esc-btn-primary">
              Crear fotos
            </Link>
          </div>
        </section>
      ) : (
        <section className="esc-gallery">
          {rows.map((row) => (
            <figure className="esc-gallery-item" key={row.request_id}>
              {row.kind === "video" ? (
                <video
                  className="esc-result-media"
                  style={{ aspectRatio: row.format === "estado" ? "9 / 16" : "1 / 1" }}
                  src={row.result_url}
                  controls
                  loop
                  playsInline
                  preload="metadata"
                />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  className="esc-result-media"
                  style={{ aspectRatio: row.format === "estado" ? "9 / 16" : "1 / 1" }}
                  src={row.result_url}
                  alt={row.product_name ? `Foto de ${row.product_name}` : "Foto de producto"}
                  loading="lazy"
                />
              )}
              <figcaption>
                <span className="esc-gallery-name">
                  {row.kind === "video" ? "🎬 " : ""}
                  {row.product_name || "Producto"}
                </span>
                <span className="esc-note" style={{ margin: 0 }}>
                  {row.created_at.toLocaleDateString("es-ES", { day: "numeric", month: "short" })}
                </span>
              </figcaption>
              <div className="esc-result-actions">
                <a className="esc-btn esc-btn-ghost esc-btn-small" href={row.result_url} target="_blank" rel="noopener" download>
                  Descargar
                </a>
                <form action={toggleFavorite}>
                  <input type="hidden" name="requestId" value={row.request_id} />
                  <button
                    className="esc-btn esc-btn-ghost esc-btn-small"
                    type="submit"
                    aria-label={row.favorite ? "Quitar de favoritas" : "Marcar como favorita"}
                    aria-pressed={row.favorite}
                  >
                    {row.favorite ? "⭐" : "☆"}
                  </button>
                </form>
                <form action={hideCreation}>
                  <input type="hidden" name="requestId" value={row.request_id} />
                  <button className="esc-btn esc-btn-ghost esc-btn-small" type="submit" aria-label="Quitar de la galería">
                    🗑
                  </button>
                </form>
              </div>
            </figure>
          ))}
        </section>
      )}
      {rows.length === PAGE_SIZE ? <p className="esc-note">Mostrando las {PAGE_SIZE} más recientes.</p> : null}
    </main>
  );
}
