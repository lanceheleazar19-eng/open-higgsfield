# Escaparate — plan de negocio (España)

> Nombre provisional. Antes de invertir en marca hay que comprobar en la OEPM
> (marcas) y en un registrador (dominio .es / .com) que "Escaparate" está libre,
> o elegir otro.

## 1. El problema

- España tiene unos **3,43 millones de autónomos** (Ministerio, diciembre 2025) y
  cientos de miles de comercios pequeños que compiten contra Amazon, Shein y las
  grandes cadenas.
- **WhatsApp lo usa el 94,6 % de los internautas** (CNMC, IV trimestre 2025) y uno
  de cada cuatro usuarios ya compra dentro de redes sociales (IAB Spain 2026).
- Aun así, **solo ~2 de cada 10 pymes y autónomos usan bien las redes** para vender
  (BeeDIGITAL). La razón más repetida: no tienen tiempo, ni fotógrafo, ni saben
  diseñar.
- El uso de IA en pymes pasó del 7,4 % (2022) al 23,3 % (2025) (Hiscox): el mercado
  está listo, pero las herramientas actuales son en inglés, genéricas o caras.

**Necesidad concreta:** "tengo el producto, pero mis fotos son malas y no sé qué
publicar".

## 2. La solución

Escaparate convierte **una foto del móvil** en:

1. 4 fotos profesionales del producto (estudio, lifestyle, mediterráneo, premium).
2. Un vídeo de 5 segundos para Reels, TikTok y estados de WhatsApp.
3. El texto de venta: publicación de Instagram, mensaje para clientes de WhatsApp y
   hashtags de su ciudad.

**Ya construido (prototipo, en este repositorio):**

- `/escaparate` — landing page con precios y lista de espera.
- `/escaparate/crear` — la herramienta: subir foto → elegir sector, estilo y formato
  → 4 fotos → vídeo con un clic → textos listos para copiar.

- Cuentas sin contraseña (código por correo), créditos con historial y
  devolución automática si algo falla.
- Pagos con Stripe: planes mensuales, packs de créditos y portal del cliente.
  Guía: `docs/escaparate/PUESTA-EN-MARCHA.md`.

- Galería «Mis creaciones» (guardada de forma permanente) y textos de venta
  escritos con IA según el tono del negocio.

- Catálogo de productos y calendario comercial de España («¿Qué publico hoy?»).
- Borrado de cuenta (RGPD) y subidas protegidas.

**Ideas para después del lanzamiento** (según lo que pidan los clientes):

1. Plantillas por sector: panadería, moda, peluquería, ferretería, bodega…
2. Fiestas locales por ciudad (Fallas, Feria de Abril, San Fermín…).
3. Publicar directamente en Instagram y en el catálogo de WhatsApp Business.
4. Recordatorio semanal por correo con la idea de la semana.

## 3. Precios

| Plan | Precio | Incluye |
|---|---|---|
| Gratis | 0 € | 12 créditos de regalo al registrarse |
| Comercio | 9 €/mes, IVA incl. | 100 créditos al mes |
| Pro | 24 €/mes, IVA incl. | 350 créditos al mes |
| Pack | 6 € (pago único) | 60 créditos que no caducan |

1 foto = 1 crédito · 1 vídeo = 10 créditos. Todo se cambia en
`src/escaparate/plans.ts`.

**Costes a vigilar:** cada foto cuesta céntimos y cada vídeo corto bastante más
(estimación: 0,20–0,50 €). Por eso el vídeo cuesta 10 créditos. Hay que
confirmar los precios reales del proveedor antes de lanzar.

## 4. Servicios (dinero desde el primer mes)

| Servicio | Precio orientativo |
|---|---|
| "Te lo hacemos": contenido del mes (≈30 posts + 8 vídeos) | desde 79 €/mes |
| Sesión de catálogo: fotos de todos los productos de la tienda | 99–299 € (pago único) |
| Puesta a punto de Instagram + WhatsApp Business (catálogo, perfil, respuestas rápidas) | 149 € |
| Taller "Vende más con IA" para asociaciones de comerciantes y cámaras de comercio | 300–600 € |
| Gestión de anuncios en Meta/TikTok para comercios locales | desde 150 €/mes |

Los servicios se hacen **con la propia app**, así que cada encargo es también una
prueba del producto.

## 5. Competencia

| Competidor | Qué hace | Precio aprox. | Por qué podemos ganar |
|---|---|---|---|
| **Canva Pro** | Diseño general con IA | ~12 €/mes | Hay que diseñar a mano; no parte de tu foto |
| **Photoroom** | Quitar fondo y fotos de producto | ~13 €/mes | Solo imagen: sin vídeo ni texto de venta |
| **Pebblely** | Escenas de producto con IA | 19–39 $/mes | Solo imagen, en inglés, en dólares |
| **Creatify** | Vídeos de anuncio con IA | desde ~19–39 $/mes | Caro y pensado para e-commerce grande |
| **AdCreative.ai** | Anuncios con IA | desde ~39 $/mes | Para marcas con presupuesto de ads |
| **Predis.ai** | Posts para redes con IA | ~24–32 $/mes | Genérico, en inglés |
| **CapCut** | Edición de vídeo | Freemium | Hay que saber editar |
| **Fotógrafo / agencia local** | Hecho a mano | 150–600 €/sesión | Caro y no es diario |

*Precios de comparativas públicas; varían según la fuente. Confirmar en la web de
cada herramienta.*

**Nuestra posición:** *"La foto, el vídeo y el texto para vender, en un minuto, en
español de España y por 9 €."* Todo en uno, pensado para WhatsApp e Instagram,
mucho más barato que juntar 2–3 herramientas.

**Riesgo principal:** que Canva o Photoroom copien la idea. Defensa: ir muy rápido
en el nicho (comercio local español), comunidad, plantillas por sector y servicios
que ellos no ofrecen.

## 6. Cómo darla a conocer

### Fase 0 — Antes de lanzar (semanas 1–4)
- Publicar la landing y abrir la lista de espera.
- **Visitar 30 comercios del barrio** (panaderías, tiendas de ropa, floristerías,
  pastelerías). Ofrecer: "Te hago 5 fotos profesionales gratis de tus productos a
  cambio de tu opinión y un testimonio".
- Guardar todos los **antes y después** (con permiso): son el mejor anuncio.

### Fase 1 — Lanzamiento (meses 1–2)
- **Un vídeo corto al día** en TikTok, Reels y Shorts con antes y después.
- Grupos de Facebook y foros de autónomos y emprendedores; aportar consejos, sin
  spam.
- **Programa de referidos:** el comercio que trae a otro gana 20 fotos gratis.
- Perfil de Google Business y artículos SEO: "cómo hacer fotos de producto con el
  móvil", "ideas para Instagram de una panadería"…

### Fase 2 — Crecimiento (meses 3–6)
- Acuerdos con **asociaciones de comerciantes, cámaras de comercio y ayuntamientos**
  (programas de digitalización del comercio local). Talleres gratuitos o de pago.
- **Gestorías y asesorías de autónomos:** tienen miles de clientes; ofrecerles
  comisión por recomendación.
- Microinfluencers de emprendimiento y comercio local (5k–50k seguidores), pagando
  por cliente conseguido.
- Anuncios en Meta e Instagram (5–10 €/día) con los vídeos que mejor funcionen.

### Guion de vídeo (30 s) — TikTok / Reels

| Tiempo | Imagen | Voz / texto |
|---|---|---|
| 0–3 s | Foto mala de una tarta en la encimera | "¿Tus fotos se ven así… y luego nadie te compra?" |
| 3–8 s | Se sube la foto a Escaparate | "Mira lo que pasa cuando la subo aquí." |
| 8–18 s | Aparecen 4 fotos profesionales y el vídeo | "En un minuto: fotos de catálogo y vídeo para tu estado de WhatsApp…" |
| 18–24 s | Se ve el texto con precio y hashtags | "…y hasta el texto para venderla, con el precio y todo." |
| 24–30 s | La dueña del negocio, sonriendo con el móvil | "Pruébalo gratis. Enlace en el perfil. Comenta TARTA y te regalo 10 fotos." |

Repetir con otros sectores: ropa, cosmética, cerámica, vino, flores. Medir cuál
funciona mejor y poner presupuesto solo en ese.

### Números a vigilar
- Visitas a la landing → registros (objetivo: 10–20 %).
- Registros que crean su primera foto el mismo día (objetivo: > 60 %).
- Gratis → pago (objetivo: 3–5 %).
- Clientes que siguen pagando al tercer mes (objetivo: > 70 %).

## 7. La visión grande

Empezar por las fotos y crecer hasta ser **la herramienta con la que el comercio
local vende en redes y WhatsApp**: catálogo, pedidos, reservas, cobros, clientes y
anuncios en un solo sitio. Primero España; después Portugal y Latinoamérica.

Con miles de comercios usándola cada día, encaja con empresas que quieren llegar al
pequeño comercio: plataformas de pago, de e-commerce, de diseño o la propia Meta.

## 8. Antes de abrir al público (temas legales)

- Política de privacidad y aviso legal (RGPD y LSSI). La lista de espera ya pide
  consentimiento expreso.
- Darse de alta como autónomo o crear una sociedad antes de facturar.
- Términos de uso: el cliente debe tener derechos sobre las fotos que sube.
- Comprobar las condiciones de uso comercial del proveedor de modelos de IA.

## Fuentes

- Ministerio de Inclusión — Afiliación de autónomos, dic. 2025: https://www.mites.gob.es/estadisticas/AUT/AUT_12_2025.pdf
- CNMC — Panel de Hogares (uso de WhatsApp): https://www.cnmc.es/ca/node/420468?back=news
- IAB Spain 2026 (compra en redes): https://finantresnoticias.com/negocios-y-autonomos/uno-cada-cuatro-usuarios-ya-compra-en-redes-deben-mirar-autonomos/
- BeeDIGITAL — pymes y redes sociales: https://www.lawandtrends.com/noticias/empresa/beedigital-destaca-que-solo-2-de-cada-10-pequen-os-negocios-tiene-redes-sociales-1.html
- GoDaddy — Redes sociales y pymes en España 2025: https://www.godaddy.com/resources/es/emprender/redes-sociales-y-pymes-en-espana-2025
- Holded — IA en autónomos: https://www.holded.com/es/blog/ia-autonomos
- Canva precios: https://www.canva.com/en_us/pricing/
- Photoroom precios: https://www.eesel.ai/blog/photoroom-pricing
- Pebblely precios: https://aisotools.com/pricing/pebblely
- AdCreative.ai precios: https://www.capterra.com/p/253052/AdCreativeai/pricing/
- Comparativa de generadores de anuncios con IA: https://www.trylapis.com/resources/ai-ad-generator-pricing-comparison
