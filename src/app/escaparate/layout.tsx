import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import type { ReactNode } from "react";

import { safeCurrentUser } from "@/escaparate/server/viewer";

import "@/escaparate/escaparate.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-esc", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Escaparate — Fotos y vídeos de producto con IA", template: "%s — Escaparate" },
  description:
    "Haz una foto a tu producto con el móvil y recibe fotos profesionales, vídeo para Reels y estados de WhatsApp, y el texto para venderlo. Para comercios y autónomos de España.",
  alternates: { canonical: "/escaparate" },
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#fbf7f2",
};

export default async function EscaparateLayout({ children }: { children: ReactNode }) {
  const user = await safeCurrentUser();
  return (
    <div className={`esc ${inter.variable}`} lang="es-ES">
      <header className="esc-header">
        <div className="esc-wrap">
          <Link href="/escaparate" className="esc-logo">
            <span className="esc-logo-mark" aria-hidden>
              E
            </span>
            Escaparate
          </Link>
          {user ? (
            <nav style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Link href="/escaparate/creaciones" className="esc-btn esc-btn-ghost esc-btn-small" aria-label="Mis creaciones">
                <span aria-hidden className="esc-show-sm">🖼️</span>
                <span className="esc-hide-sm">Mis creaciones</span>
              </Link>
              <Link href="/escaparate/cuenta" className="esc-btn esc-btn-ghost esc-btn-small" aria-label="Mi cuenta">
                <span aria-hidden className="esc-show-sm">👤</span>
                <span className="esc-hide-sm">Mi cuenta</span>
              </Link>
              <Link href="/escaparate/crear" className="esc-btn esc-btn-primary esc-btn-small">
                Crear
              </Link>
            </nav>
          ) : (
            <nav style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Link href="/escaparate/entrar" className="esc-btn esc-btn-ghost esc-btn-small">
                Entrar
              </Link>
              <Link href="/escaparate/crear" className="esc-btn esc-btn-primary esc-btn-small">
                Probar gratis
              </Link>
            </nav>
          )}
        </div>
      </header>
      {children}
      <footer className="esc-footer">
        <div className="esc-wrap">
          © {new Date().getFullYear()} Escaparate · Hecho para el comercio local en España ·{" "}
          <Link href="/escaparate/legal">Aviso legal y privacidad</Link>
        </div>
      </footer>
    </div>
  );
}
