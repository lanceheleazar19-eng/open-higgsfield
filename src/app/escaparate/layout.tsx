import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import type { ReactNode } from "react";

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

export default function EscaparateLayout({ children }: { children: ReactNode }) {
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
          <Link href="/escaparate/crear" className="esc-btn esc-btn-primary esc-btn-small">
            Probar ahora
          </Link>
        </div>
      </header>
      {children}
      <footer className="esc-footer">
        <div className="esc-wrap">
          © {new Date().getFullYear()} Escaparate · Hecho para el comercio local en España
        </div>
      </footer>
    </div>
  );
}
