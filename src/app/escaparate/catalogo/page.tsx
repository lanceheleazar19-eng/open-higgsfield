import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { sectorById, type SectorId } from "@/escaparate/content";
import { db } from "@/escaparate/server/db";
import { deleteProduct } from "@/escaparate/server/product-actions";
import { safeCurrentUser } from "@/escaparate/server/viewer";

export const metadata: Metadata = { title: "Mi catálogo", robots: { index: false } };

type Row = {
  id: string;
  name: string;
  price: string;
  sector: string;
  photo_url: string;
  creations: number;
  last_url: string | null;
};

export default async function CatalogoPage() {
  const user = await safeCurrentUser();
  if (!user) redirect("/escaparate/entrar?siguiente=/escaparate/catalogo");

  const products = await db()<Row[]>`
    SELECT p.id, p.name, p.price, p.sector, p.photo_url,
      (SELECT count(*)::int FROM esc_generations g
        WHERE g.product_id = p.id AND g.status = 'completed' AND NOT g.hidden) AS creations,
      (SELECT g.result_url FROM esc_generations g
        WHERE g.product_id = p.id AND g.kind = 'image' AND g.status = 'completed' AND NOT g.hidden
        ORDER BY g.created_at DESC LIMIT 1) AS last_url
    FROM esc_products p
    WHERE p.user_id = ${user.id}
    ORDER BY p.updated_at DESC
    LIMIT 200`;

  return (
    <main className="esc-wrap esc-creator">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "end", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: "clamp(28px, 4vw, 40px)", margin: "0 0 4px" }}>Mi catálogo</h1>
          <p className="esc-note" style={{ margin: 0 }}>
            Tus productos guardados. Sube la foto una vez y crea contenido nuevo cuando quieras.
          </p>
        </div>
        <Link href="/escaparate/crear" className="esc-btn esc-btn-primary">
          + Nuevo producto
        </Link>
      </div>

      {products.length === 0 ? (
        <section className="esc-panel" style={{ textAlign: "center" }}>
          <p style={{ fontSize: 40, margin: 0 }} aria-hidden>
            🛍️
          </p>
          <p style={{ margin: 0 }}>Tu catálogo está vacío. Cada producto con el que crees fotos se guarda aquí.</p>
          <div>
            <Link href="/escaparate/crear" className="esc-btn esc-btn-primary">
              Añadir mi primer producto
            </Link>
          </div>
        </section>
      ) : (
        <section className="esc-gallery">
          {products.map((product) => {
            const sector = sectorById(product.sector as SectorId);
            return (
              <article className="esc-gallery-item" key={product.id}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  className="esc-result-media"
                  style={{ aspectRatio: "1 / 1" }}
                  src={product.last_url ?? product.photo_url}
                  alt={product.name || "Producto"}
                  loading="lazy"
                />
                <div className="esc-gallery-caption">
                  <span className="esc-gallery-name">{product.name || "Producto sin nombre"}</span>
                  <span className="esc-note" style={{ margin: 0 }}>
                    {sector.emoji} {product.price ? `${product.price} € · ` : ""}
                    {product.creations} {product.creations === 1 ? "creación" : "creaciones"}
                  </span>
                </div>
                <div className="esc-result-actions">
                  <Link href={`/escaparate/crear?producto=${product.id}`} className="esc-btn esc-btn-primary esc-btn-small">
                    Crear contenido
                  </Link>
                  <form action={deleteProduct}>
                    <input type="hidden" name="productId" value={product.id} />
                    <button
                      className="esc-btn esc-btn-ghost esc-btn-small"
                      type="submit"
                      aria-label={`Quitar ${product.name || "producto"} del catálogo`}
                    >
                      🗑
                    </button>
                  </form>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}
