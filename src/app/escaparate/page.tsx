import Link from "next/link";

import { COST, PLANS, SIGNUP_CREDITS } from "@/escaparate/plans";
import { WaitlistForm } from "@/escaparate/waitlist-form";

const STEPS = [
  {
    title: "Haz una foto con el móvil",
    body: "Da igual el fondo o la luz. Encima del mostrador o en la mesa de la cocina sirve.",
  },
  {
    title: "Elige el estilo",
    body: "Estudio, lifestyle, mediterráneo o premium. Y si es para Instagram o para tu estado de WhatsApp.",
  },
  {
    title: "Publica y vende",
    body: "Recibes 4 fotos profesionales, un vídeo corto y el texto con precio y hashtags, listo para copiar.",
  },
];

const PRICING = [
  {
    name: "Gratis",
    price: "0 €",
    note: "al registrarte",
    featured: false,
    items: [`${SIGNUP_CREDITS} créditos de regalo`, "Fotos, vídeo y textos", "Sin tarjeta"],
  },
  ...PLANS.map((plan) => ({
    name: plan.name,
    price: `${plan.priceEuros} €`,
    note: "/mes, IVA incl.",
    featured: plan.id === "comercio",
    items: plan.perks,
  })),
];

export default function EscaparateLanding() {
  return (
    <main>
      <section className="esc-wrap esc-hero">
        <div>
          <span className="esc-eyebrow">Para comercios y autónomos de España</span>
          <h1>Fotos de producto que venden, hechas con tu móvil en 1 minuto</h1>
          <p className="esc-lead">
            Sube una foto normal de tu producto y Escaparate te devuelve fotos profesionales, un vídeo
            para Reels y estados de WhatsApp, y el texto para venderlo. Sin fotógrafo y sin saber
            diseñar.
          </p>
          <div className="esc-hero-ctas">
            <Link href="/escaparate/crear" className="esc-btn esc-btn-primary">
              Probar gratis con mi producto
            </Link>
            <a href="#lista" className="esc-btn esc-btn-ghost">
              Apuntarme a la lista
            </a>
          </div>
          <p className="esc-note">{SIGNUP_CREDITS} créditos de regalo al registrarte. Sin tarjeta.</p>
        </div>
        <div className="esc-ba" aria-label="Ejemplo de antes y después">
          <figure>
            <div className="esc-ba-tile esc-ba-before" aria-hidden>
              🥐
            </div>
            <figcaption>Antes: foto del móvil</figcaption>
          </figure>
          <figure>
            <div className="esc-ba-tile esc-ba-after" aria-hidden>
              🥐
            </div>
            <figcaption>Después: lista para vender</figcaption>
          </figure>
        </div>
      </section>

      <section className="esc-section esc-section-alt">
        <div className="esc-wrap">
          <h2>Así de fácil</h2>
          <div className="esc-grid">
            {STEPS.map((step, index) => (
              <div className="esc-card" key={step.title}>
                <div className="esc-step-num">{index + 1}</div>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="esc-section">
        <div className="esc-wrap">
          <h2>Pensado para quien vende por WhatsApp e Instagram</h2>
          <div className="esc-grid">
            <div className="esc-card">
              <h3>📱 Formatos listos</h3>
              <p>Post cuadrado para Instagram y vertical para estados de WhatsApp, Reels y TikTok.</p>
            </div>
            <div className="esc-card">
              <h3>✍️ Texto en tu idioma</h3>
              <p>Descripción, precio, mensaje para clientes de WhatsApp y hashtags de tu ciudad.</p>
            </div>
            <div className="esc-card">
              <h3>💶 Precio de barrio</h3>
              <p>Menos que un café al día. Sin pagar fotógrafo ni agencia cada mes.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="esc-section esc-section-alt">
        <div className="esc-wrap">
          <h2>Precios</h2>
          <div className="esc-grid">
            {PRICING.map((plan) => (
              <div className={`esc-card${plan.featured ? " esc-card-featured" : ""}`} key={plan.name}>
                <h3>{plan.name}</h3>
                <div className="esc-price">
                  {plan.price} <small>{plan.note}</small>
                </div>
                <ul className="esc-list">
                  {plan.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <p className="esc-note">
            1 foto = {COST.image} crédito · 1 vídeo = {COST.video} créditos. Sin permanencia. ¿Prefieres que lo hagamos
            por ti? Contenido del mes para tu negocio desde 79 €.
          </p>
        </div>
      </section>

      <section className="esc-section" id="lista">
        <div className="esc-wrap" style={{ maxWidth: 720 }}>
          <h2>¿Aún no te decides? Apúntate a las novedades</h2>
          <p className="esc-lead">Te avisamos de nuevas funciones, plantillas por sector y ofertas para comercios.</p>
          <WaitlistForm />
        </div>
      </section>
    </main>
  );
}
