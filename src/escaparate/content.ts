/* Escaparate: what a small shop in Spain picks before it generates — its sector,
   the look it wants and where the piece will be posted — and the sales copy that
   goes with the result. Prompts are written in English because the image models
   follow English best; everything a shop owner reads is in Spanish (Spain). */

export type SectorId = "comida" | "moda" | "belleza" | "hogar" | "artesania" | "otro";
export type StyleId = "estudio" | "lifestyle" | "mediterraneo" | "premium";
export type FormatId = "post" | "estado";

export type Sector = {
  id: SectorId;
  label: string;
  emoji: string;
  /** What the product is, for the prompt. */
  subject: string;
  hashtags: readonly string[];
};

export const SECTORS: readonly Sector[] = [
  {
    id: "comida",
    label: "Comida y bebida",
    emoji: "🥐",
    subject: "a food or drink product",
    hashtags: ["#comidacasera", "#productolocal", "#hechoenespaña", "#foodie"],
  },
  {
    id: "moda",
    label: "Moda y complementos",
    emoji: "👗",
    subject: "a fashion item or accessory",
    hashtags: ["#moda", "#tiendaonline", "#comerciolocal", "#estilo"],
  },
  {
    id: "belleza",
    label: "Belleza y cuidado",
    emoji: "💄",
    subject: "a beauty or personal care product",
    hashtags: ["#belleza", "#cosmetica", "#cuidadopersonal", "#skincare"],
  },
  {
    id: "hogar",
    label: "Hogar y decoración",
    emoji: "🪴",
    subject: "a home or decor item",
    hashtags: ["#decoracion", "#hogar", "#interiorismo", "#comerciolocal"],
  },
  {
    id: "artesania",
    label: "Artesanía y regalos",
    emoji: "🎁",
    subject: "a handmade craft or gift",
    hashtags: ["#artesania", "#hechoamano", "#regalos", "#handmade"],
  },
  {
    id: "otro",
    label: "Otro producto",
    emoji: "🛍️",
    subject: "a retail product",
    hashtags: ["#comerciolocal", "#tiendaonline", "#novedades", "#compralocal"],
  },
];

export type Style = {
  id: StyleId;
  label: string;
  hint: string;
  scene: string;
};

export const STYLES: readonly Style[] = [
  {
    id: "estudio",
    label: "Estudio",
    hint: "Fondo limpio, como en una tienda online",
    scene:
      "on a seamless soft neutral studio background, soft even lighting, subtle shadow, e-commerce catalogue photo",
  },
  {
    id: "lifestyle",
    label: "Lifestyle",
    hint: "En uso, en un ambiente real",
    scene:
      "in a bright, natural lifestyle setting where it would be used, warm daylight, shallow depth of field",
  },
  {
    id: "mediterraneo",
    label: "Mediterráneo",
    hint: "Luz cálida, terracota y madera",
    scene:
      "on a rustic wooden table with terracotta, linen and olive branches, warm Mediterranean afternoon sunlight",
  },
  {
    id: "premium",
    label: "Premium",
    hint: "Elegante, para destacar el producto",
    scene:
      "on a dark marble surface with dramatic soft rim lighting, luxury advertising photo, rich contrast",
  },
];

export type Format = {
  id: FormatId;
  label: string;
  hint: string;
  aspectRatio: "1:1" | "9:16";
};

export const FORMATS: readonly Format[] = [
  { id: "post", label: "Post de Instagram", hint: "Cuadrado 1:1", aspectRatio: "1:1" },
  { id: "estado", label: "Estado de WhatsApp / Reel", hint: "Vertical 9:16", aspectRatio: "9:16" },
];

/** Four takes per press: the same product, the same scene, four framings. */
const ANGLES = [
  "front three-quarter view, centered",
  "close-up detail shot",
  "top-down flat lay composition",
  "wide shot with space for text",
] as const;

export const IMAGE_MODEL = "flux-2";
export const VIDEO_MODEL = "kling-3-turbo";

export function sectorById(id: SectorId): Sector {
  return SECTORS.find((sector) => sector.id === id) ?? SECTORS[SECTORS.length - 1];
}

export function styleById(id: StyleId): Style {
  return STYLES.find((style) => style.id === id) ?? STYLES[0];
}

export function formatById(id: FormatId): Format {
  return FORMATS.find((format) => format.id === id) ?? FORMATS[0];
}

export function imagePrompts(input: {
  sector: SectorId;
  style: StyleId;
  productName: string;
}): string[] {
  const sector = sectorById(input.sector);
  const style = styleById(input.style);
  const named = input.productName.trim() ? ` (${input.productName.trim()})` : "";
  return ANGLES.map(
    (angle) =>
      `Professional product photograph of the exact product shown in the reference image${named}, ` +
      `${sector.subject}. Keep the product's shape, colours, label and details identical. ` +
      `Place it ${style.scene}. ${angle}. Photorealistic, sharp focus, high-end commercial photography, no text, no watermark.`,
  );
}

export function videoPrompt(style: StyleId): string {
  const scene = styleById(style);
  return (
    `Slow, smooth cinematic camera push-in around the product, ${scene.scene}. ` +
    `Gentle light movement, the product stays unchanged and in focus. Commercial advert, no text.`
  );
}

export type SalesCopy = { titulo: string; texto: string; whatsapp: string; hashtags: string };

/** Ready-to-paste copy built from the shop's own words. Template-based on
    purpose for the prototype: it costs nothing and never invents a claim the
    shop did not make. A language model can replace it once billing exists. */
export function salesCopy(input: {
  sector: SectorId;
  productName: string;
  price: string;
  businessName: string;
  city: string;
  /** e.g. "🖤 Black Friday" — leads the headline when the post is for a date. */
  occasion?: string;
}): SalesCopy {
  const sector = sectorById(input.sector);
  const product = input.productName.trim() || "nuestro producto estrella";
  const price = formatPrice(input.price);
  const shop = input.businessName.trim();
  const city = input.city.trim();
  const where = city ? ` en ${city}` : "";
  const by = shop ? ` en ${shop}` : "";

  const titulo = `${input.occasion ? `${input.occasion}: ` : "✨ "}${capitalise(product)}${price ? ` · ${price}` : ""}`;
  const texto = [
    `¡Ya lo tenemos${by}! ${capitalise(product)}, ${SECTOR_PITCH[sector.id]}.`,
    price ? `Precio: ${price}.` : "",
    `📍 Comercio local${where}. Escríbenos por WhatsApp y te lo reservamos.`,
  ]
    .filter(Boolean)
    .join("\n");
  const whatsapp =
    `Hola 👋 Te cuento una novedad${by}: ${product}${price ? ` por solo ${price}` : ""}. ` +
    `¿Te lo reservamos? Responde a este mensaje y te lo apartamos.`;
  const cityTag = city ? [`#${slugTag(city)}`, `#comercio${slugTag(city)}`] : [];
  const hashtags = [...sector.hashtags, ...cityTag].join(" ");
  return { titulo, texto, whatsapp, hashtags };
}

const SECTOR_PITCH: Record<SectorId, string> = {
  comida: "con ingredientes de calidad y todo el sabor de lo nuestro",
  moda: "la pieza que le faltaba a tu armario",
  belleza: "para cuidarte cada día como te mereces",
  hogar: "para dar a tu casa ese toque que buscabas",
  artesania: "elaboración artesanal, ideal para regalar",
  otro: "para que te enamore desde el primer día",
};

function formatPrice(raw: string): string {
  const cleaned = raw.trim().replace(/€/g, "").trim();
  if (!cleaned) return "";
  const value = Number(cleaned.replace(",", "."));
  if (!Number.isFinite(value) || value <= 0) return "";
  return `${value.toLocaleString("es-ES", { minimumFractionDigits: value % 1 ? 2 : 0, maximumFractionDigits: 2 })} €`;
}

function capitalise(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function slugTag(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-zA-Z0-9]/g, "")
    .toLowerCase();
}
