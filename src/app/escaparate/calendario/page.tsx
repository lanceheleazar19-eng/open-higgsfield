import type { Metadata } from "next";
import Link from "next/link";

import { daysUntil, everydayIdea, todayInSpain, upcomingOccasions } from "@/escaparate/calendar";
import { sectorById } from "@/escaparate/content";

export const metadata: Metadata = {
  title: "Calendario de publicaciones para comercios",
  description:
    "Las fechas comerciales de España con ideas de qué publicar: rebajas, San Valentín, Día de la Madre, Black Friday, Navidad y más.",
  alternates: { canonical: "/escaparate/calendario" },
};

/* Recomputed per request so "today" is always today. */
export const dynamic = "force-dynamic";

export default function CalendarioPage() {
  const today = todayInSpain();
  const occasions = upcomingOccasions(today, 120);
  const todayIdea = everydayIdea(today);
  const next = occasions[0];

  return (
    <main className="esc-wrap esc-creator">
      <div>
        <h1 style={{ fontSize: "clamp(28px, 4vw, 40px)", margin: "0 0 4px" }}>¿Qué publico hoy?</h1>
        <p className="esc-note" style={{ margin: 0 }}>
          Las fechas que más venden en España, con ideas listas para tu comercio.
        </p>
      </div>

      <section className="esc-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
        <div className="esc-card">
          <h3>
            {todayIdea.emoji} Idea para hoy · {todayIdea.title}
          </h3>
          <p>{todayIdea.idea}</p>
          <div style={{ marginTop: 12 }}>
            <Link href="/escaparate/crear" className="esc-btn esc-btn-ghost esc-btn-small">
              Crear publicación
            </Link>
          </div>
        </div>
        {next ? (
          <div className="esc-card esc-card-featured">
            <h3>
              {next.emoji} Próxima fecha: {next.title}
            </h3>
            <p>
              {formatDate(next.date)} · {countdown(daysUntil(next.date, today))}. {next.idea}
            </p>
            <div style={{ marginTop: 12 }}>
              <Link href={`/escaparate/crear?ocasion=${next.id}`} className="esc-btn esc-btn-primary esc-btn-small">
                Preparar contenido
              </Link>
            </div>
          </div>
        ) : null}
      </section>

      <section className="esc-panel">
        <h2 className="esc-panel-title">Próximos 4 meses</h2>
        <ol className="esc-timeline">
          {occasions.map((occasion) => {
            const left = daysUntil(occasion.date, today);
            const startNow = left <= occasion.leadDays;
            return (
              <li key={`${occasion.id}-${occasion.date.getFullYear()}`} className="esc-timeline-item">
                <div className="esc-timeline-date">
                  <strong>{occasion.date.getDate()}</strong>
                  <span>{occasion.date.toLocaleDateString("es-ES", { month: "short" })}</span>
                </div>
                <div className="esc-timeline-body">
                  <h3>
                    {occasion.emoji} {occasion.title}{" "}
                    <span className={startNow ? "esc-pill esc-pill-hot" : "esc-pill"}>{countdown(left)}</span>
                  </h3>
                  <p className="esc-note" style={{ margin: "2px 0 8px" }}>
                    {occasion.idea}
                    {occasion.sectors.length && occasion.sectors.length <= 3 ? ` Ideal para: ${occasion.sectors.map((id) => sectorById(id).label.toLowerCase()).join(", ")}.` : ""}
                  </p>
                  <Link href={`/escaparate/crear?ocasion=${occasion.id}`} className="esc-btn esc-btn-ghost esc-btn-small">
                    {startNow ? "Preparar ya" : "Preparar contenido"}
                  </Link>
                </div>
              </li>
            );
          })}
        </ol>
      </section>
    </main>
  );
}

function formatDate(date: Date): string {
  return date.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" });
}

function countdown(days: number): string {
  if (days <= 0) return "¡es hoy!";
  if (days === 1) return "mañana";
  return `en ${days} días`;
}
