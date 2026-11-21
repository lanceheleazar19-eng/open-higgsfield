import "server-only";

import Anthropic from "@anthropic-ai/sdk";

import { sectorById, type SalesCopy, type SectorId } from "../content";

export type Tone = "cercano" | "profesional" | "divertido";

export const TONES: readonly Tone[] = ["cercano", "profesional", "divertido"];

const TONE_GUIDE: Record<Tone, string> = {
  cercano: "cercano y cálido, como el dueño de una tienda de barrio que conoce a sus clientes",
  profesional: "profesional y elegante, sin exagerar",
  divertido: "desenfadado y con gracia, con algún juego de palabras si encaja",
};

/* Frozen system prompt: identical bytes on every request, so it can be cached
   once traffic grows. Everything that varies goes in the user message. */
const SYSTEM = `Eres redactor publicitario para pequeños comercios de España.
Escribes en español de España (usa "vosotros", euros, expresiones naturales de aquí), en frases cortas y claras.
Reglas:
- No inventes datos que el comercio no ha dado: ni ingredientes, ni materiales, ni descuentos, ni plazos de envío. Si no hay precio, no menciones precio.
- Nada de promesas de salud, resultados garantizados ni superlativos absolutos ("el mejor de España").
- Emojis con moderación (2-4 en la publicación, 1-2 en el WhatsApp).
- La publicación de Instagram: un titular corto, 2-4 frases y una llamada a la acción para escribir por WhatsApp o pasarse por la tienda.
- El mensaje de WhatsApp: para enviarlo a clientes que ya conocen el comercio; personal, breve (máx. 3 frases) y termina con una pregunta.
- Hashtags: 5-8, en minúsculas, mezclando producto, sector y la ciudad si se da.`;

const SCHEMA = {
  type: "object",
  properties: {
    titulo: { type: "string", description: "Titular corto de la publicación (máx. 60 caracteres)" },
    texto: { type: "string", description: "Cuerpo de la publicación de Instagram, sin hashtags" },
    whatsapp: { type: "string", description: "Mensaje para enviar a clientes por WhatsApp" },
    hashtags: { type: "string", description: "Hashtags separados por espacios" },
  },
  required: ["titulo", "texto", "whatsapp", "hashtags"],
  additionalProperties: false,
} as const;

export function copywriterAvailable(): boolean {
  return Boolean(process.env.ANTHROPIC_API_KEY);
}

let client: Anthropic | null = null;

/** Writes the copy with Claude. Returns null when it cannot (no key, refusal,
    malformed output, API error) so the caller falls back to the templates. */
export async function writeCopy(input: {
  sector: SectorId;
  productName: string;
  price: string;
  businessName: string;
  city: string;
  details: string;
  tone: Tone;
  occasion?: string;
}): Promise<SalesCopy | null> {
  if (!copywriterAvailable()) return null;
  client ??= new Anthropic();

  const facts = [
    `Sector: ${sectorById(input.sector).label}`,
    `Producto: ${input.productName || "(sin nombre)"}`,
    input.price ? `Precio: ${input.price} €` : "Precio: (no indicado)",
    input.businessName ? `Comercio: ${input.businessName}` : "",
    input.city ? `Ciudad: ${input.city}` : "",
    input.details ? `Detalles que da el comercio: ${input.details}` : "",
    input.occasion ? `Ocasión de la publicación: ${input.occasion}` : "",
    `Tono: ${TONE_GUIDE[input.tone]}`,
  ]
    .filter(Boolean)
    .join("\n");

  try {
    const response = await client.beta.messages.create({
      model: "claude-opus-5-5",
      max_tokens: 4000,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      output_config: { effort: "low", format: { type: "json_schema", schema: SCHEMA } },
      system: SYSTEM,
      messages: [{ role: "user", content: `Escribe los textos de venta para este producto.\n\n${facts}` }],
    });
    if (response.stop_reason === "refusal" || response.stop_reason === "max_tokens") return null;
    const text = response.content.find((block) => block.type === "text");
    if (!text || text.type !== "text") return null;
    const parsed = JSON.parse(text.text) as Partial<SalesCopy>;
    if (![parsed.titulo, parsed.texto, parsed.whatsapp, parsed.hashtags].every((v) => typeof v === "string" && v)) {
      return null;
    }
    return parsed as SalesCopy;
  } catch (caught) {
    if (caught instanceof Anthropic.RateLimitError) console.warn("[escaparate] copywriter rate limited");
    else if (caught instanceof Anthropic.APIError) console.error("[escaparate] copywriter API error", caught.status, caught.message);
    else console.error("[escaparate] copywriter failed", caught);
    return null;
  }
}
