# Escaparate — cómo ponerla en marcha

Guía paso a paso para publicar la app con cuentas, créditos y pagos reales.
Tiempo estimado: 1–2 horas. Todo se puede hacer primero en **modo prueba** sin
cobrar dinero real.

## Qué necesitas (todo tiene plan gratuito para empezar)

| Servicio | Para qué | Coste inicial |
|---|---|---|
| **Vercel** | Publicar la web | Gratis |
| **Neon** (o Supabase) | Base de datos Postgres: usuarios y créditos | Gratis |
| **Vercel Blob** | Guardar las fotos que suben los clientes | Gratis hasta cierto uso |
| **Resend** | Enviar el código de acceso por correo | Gratis (3.000 correos/mes) |
| **Stripe** | Cobrar suscripciones y packs | Sin cuota; comisión por pago |
| **Plataforma de IA** | Generar fotos y vídeos | Pago por uso |
| **Dominio** (.es o .com) | Tu dirección web | ~10–15 €/año |

## Paso 1 — Base de datos

1. Crea un proyecto en Neon y copia la *connection string* (`postgres://…`).
2. En tu ordenador, dentro del proyecto:
   ```bash
   DATABASE_URL="postgres://..." pnpm escaparate:migrate
   ```
   Crea las tablas. Se puede repetir sin miedo.

## Paso 2 — Correo (Resend)

1. Crea una cuenta en Resend y **verifica tu dominio** (te pide añadir unos
   registros DNS).
2. Crea una API key.
3. Variables: `RESEND_API_KEY` y `ESCAPARATE_EMAIL_FROM="Escaparate <hola@tudominio.es>"`.

## Paso 3 — Pagos (Stripe)

1. Crea la cuenta de Stripe y empieza en **modo prueba**.
2. Copia la clave secreta (`sk_test_…`) → `STRIPE_SECRET_KEY`.
3. En *Developers → Webhooks*, añade un endpoint:
   - URL: `https://tudominio.es/api/escaparate/stripe`
   - Eventos: `checkout.session.completed`, `invoice.paid`,
     `customer.subscription.created`, `customer.subscription.updated`,
     `customer.subscription.deleted`
   - Copia el *signing secret* (`whsec_…`) → `STRIPE_WEBHOOK_SECRET`.
4. En *Settings → Billing → Customer portal*, actívalo (para que los clientes
   cancelen y descarguen facturas solos).
5. No hace falta crear productos: los precios salen de `src/escaparate/plans.ts`.
6. Prueba con la tarjeta `4242 4242 4242 4242`. Cuando todo funcione, cambia a
   las claves `sk_live_…` y crea el webhook también en modo real.

## Paso 4 — Plataforma de IA

- `ESCAPARATE_PLATFORM_KEY` = tu clave `id:secreto` (la paga el negocio, los
  clientes no la ven nunca).
- `HF_API_BASE_URL` = la dirección de la API.
- **Antes de fijar precios**, mira cuánto te cuesta de verdad cada foto y cada
  vídeo y ajusta `COST`, `monthlyCredits` y precios en `src/escaparate/plans.ts`.

## Paso 5 — Publicar en Vercel

1. Importa el repositorio en Vercel.
2. Añade el almacén **Blob** al proyecto y pon su token en
   `OPEN_HIGGSFIELD_READ_WRITE_TOKEN`.
3. Añade todas las variables de `.env.example`.
4. Pon tu dominio y `NEXT_PUBLIC_SITE_URL=https://tudominio.es`.
5. **No** pongas `ESCAPARATE_LOG_LOGIN_CODES` en producción (solo sirve para
   pruebas locales).

## Paso 6 — Antes de abrir al público

- Completa los datos del titular en `/escaparate/legal` (nombre, NIF, dirección,
  correo) y, si puedes, que lo revise un profesional.
- Date de alta como autónomo (o crea una sociedad) para facturar. Los precios
  se muestran con IVA incluido; tu gestor te dirá cómo declararlo.
- Haz una compra real de 6 € con tu propia tarjeta y comprueba que llegan los
  créditos.

## Cómo funciona por dentro

- **Acceso sin contraseña:** el cliente pone su correo, recibe un código de 6
  números (caduca en 10 minutos, máximo 5 intentos y 5 códigos por hora).
- **Créditos:** 1 foto = 1 crédito, 1 vídeo = 10. Al registrarse recibe 12 de
  regalo. Si una generación falla, se devuelven automáticamente.
- **Pagos:** el plan mensual suma sus créditos cada vez que Stripe cobra la
  factura; el pack suma 60 créditos al pagarse. Cada pago se procesa una sola vez
  aunque Stripe lo envíe repetido.
- **Historial:** en «Mi cuenta» se ve cada movimiento de créditos.
