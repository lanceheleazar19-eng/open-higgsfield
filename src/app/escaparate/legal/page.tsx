import type { Metadata } from "next";

export const metadata: Metadata = { title: "Aviso legal y privacidad" };

/* Plantilla base. Antes de abrir al público hay que completar los datos del
   titular (entre corchetes) y conviene que la revise un profesional. */
export default function LegalPage() {
  return (
    <main className="esc-wrap" style={{ maxWidth: 760, padding: "40px 16px 64px" }}>
      <h1 style={{ fontSize: "clamp(28px, 4vw, 40px)" }}>Aviso legal y privacidad</h1>

      <h2>Titular</h2>
      <p>
        [Nombre o razón social] · NIF [NIF] · [Domicilio] · Contacto: [correo de contacto]. En cumplimiento de la Ley
        34/2002 de Servicios de la Sociedad de la Información (LSSI).
      </p>

      <h2>Qué datos tratamos y para qué</h2>
      <ul>
        <li>
          <strong>Cuenta:</strong> tu correo electrónico, para enviarte el código de acceso y gestionar tu cuenta.
          Base legal: ejecución del contrato.
        </li>
        <li>
          <strong>Pagos:</strong> los gestiona Stripe. Nosotros no vemos ni guardamos los datos de tu tarjeta.
        </li>
        <li>
          <strong>Fotos:</strong> las fotos que subes se usan solo para generar tu contenido con proveedores de
          inteligencia artificial y se almacenan en servidores de Vercel.
        </li>
        <li>
          <strong>Lista de novedades:</strong> tu correo y los datos del negocio, solo si das tu consentimiento.
          Puedes retirarlo cuando quieras.
        </li>
      </ul>

      <h2>Tus derechos</h2>
      <p>
        Puedes acceder, rectificar, suprimir, oponerte, limitar el tratamiento y pedir la portabilidad de tus datos
        escribiendo a [correo de contacto]. También puedes reclamar ante la Agencia Española de Protección de Datos
        (aepd.es).
      </p>

      <h2>Condiciones de uso</h2>
      <ul>
        <li>Debes tener derecho a usar las fotos que subes (por ejemplo, fotos de tus propios productos).</li>
        <li>No está permitido generar contenido ilegal, engañoso o que infrinja derechos de terceros.</li>
        <li>
          Los créditos de los planes se renuevan cada mes. Los créditos comprados en packs no caducan mientras la
          cuenta esté activa. Si una generación falla, se devuelven los créditos.
        </li>
        <li>Puedes cancelar tu suscripción en cualquier momento desde tu cuenta; no hay permanencia.</li>
        <li>
          El contenido generado es tuyo para usarlo en tu negocio, dentro de las condiciones de los proveedores de
          IA que usamos.
        </li>
      </ul>
    </main>
  );
}
