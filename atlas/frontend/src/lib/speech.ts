/** Utilidades de síntesis de voz: elegir buenas voces en español y preparar el texto. */

export interface VoiceLike {
  name: string;
  lang: string;
  voiceURI: string;
  localService: boolean;
}

// Voces «de efectos» de macOS (también existen en español): suenan raras, nunca por defecto
const NOVELTY = /\b(eddy|flo|grandma|grandpa|abuel[oa]|reed|rocko|sandy|shelley|bad news|bahh|bells|boing|bubbles|cellos|good news|jester|organ|superstar|trinoids|whisper|wobble|zarvox|albert|fred|junior|kathy|ralph)\b/i;

export function isSpanish(v: VoiceLike): boolean {
  return v.lang.toLowerCase().replace("_", "-").startsWith("es");
}

/** Puntuación de calidad: mayor = mejor. */
export function voiceScore(v: VoiceLike): number {
  const n = v.name.toLowerCase();
  let s = 0;
  if (NOVELTY.test(n)) return -100;
  if (/premium/.test(n)) s += 60;
  if (/(enhanced|mejorada)/.test(n)) s += 50;
  if (/natural|neural|online/.test(n)) s += 45; // voces neuronales de Microsoft Edge
  if (/google/.test(n)) s += 40; // voz en línea de Chrome, muy clara
  if (/(m[oó]nica|paulina|jorge|marisol|juan|diego|isabela|helena|laura|pablo|elvira|alvaro|dalia)/.test(n)) s += 20;
  const lang = v.lang.toLowerCase().replace("_", "-");
  if (lang === "es-es") s += 8;
  else if (lang === "es-mx" || lang === "es-us") s += 5;
  return s;
}

export function spanishVoices<T extends VoiceLike>(voices: T[]): T[] {
  return voices.filter(isSpanish).sort((a, b) => voiceScore(b) - voiceScore(a) || a.name.localeCompare(b.name));
}

export function pickVoice<T extends VoiceLike>(voices: T[], preferredURI: string | null): T | null {
  if (preferredURI) {
    const v = voices.find((x) => x.voiceURI === preferredURI);
    if (v) return v;
  }
  const es = spanishVoices(voices).filter((v) => voiceScore(v) > -100);
  return es[0] ?? null;
}

export function qualityLabel(v: VoiceLike): string {
  const s = voiceScore(v);
  if (s < 0) return "efecto";
  if (s >= 40) return "alta calidad";
  if (s >= 20) return "buena";
  return "básica";
}

/** Quita marcas que no deben leerse en voz alta. */
export function cleanForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[*_#`>|~•«»"]/g, "")
    .replace(/^\s*[-–]\s+/gm, "")
    .replace(/\[(.*?)\]\(.*?\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

/** Trocea en frases cortas: Chrome corta o se traba con textos largos en una sola locución. */
export function speechChunks(text: string, max = 180): string[] {
  const sentences = cleanForSpeech(text).match(/[^.!?;:]+[.!?;:]*/g) ?? [];
  const out: string[] = [];
  let cur = "";
  for (const raw of sentences) {
    const s = raw.trim();
    if (!s) continue;
    if ((cur + " " + s).trim().length <= max) cur = (cur + " " + s).trim();
    else {
      if (cur) out.push(cur);
      if (s.length <= max) cur = s;
      else {
        // frase muy larga: cortar por comas o espacios
        let rest = s;
        while (rest.length > max) {
          let cut = rest.lastIndexOf(",", max);
          if (cut < max / 2) cut = rest.lastIndexOf(" ", max);
          if (cut <= 0) cut = max;
          out.push(rest.slice(0, cut + 1).trim());
          rest = rest.slice(cut + 1).trim();
        }
        cur = rest;
      }
    }
  }
  if (cur) out.push(cur);
  return out;
}

const VOICE_KEY = "atlas.voice";
const RATE_KEY = "atlas.rate";

export function loadVoicePrefs(): { voiceURI: string | null; rate: number } {
  try {
    const r = Number(localStorage.getItem(RATE_KEY));
    return { voiceURI: localStorage.getItem(VOICE_KEY), rate: r >= 0.6 && r <= 2 ? r : 1.05 };
  } catch {
    return { voiceURI: null, rate: 1.05 };
  }
}

export function saveVoicePrefs(p: { voiceURI?: string | null; rate?: number }) {
  try {
    if (p.voiceURI !== undefined) {
      if (p.voiceURI) localStorage.setItem(VOICE_KEY, p.voiceURI);
      else localStorage.removeItem(VOICE_KEY);
    }
    if (p.rate !== undefined) localStorage.setItem(RATE_KEY, String(p.rate));
  } catch { /* sin almacenamiento */ }
}
