/** Fase 9 — voz manos libres: palabra de activación, órdenes de voz y filtro de eco. Funciones puras. */

export function norm(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9ñ ]+/g, " ").replace(/\s+/g, " ").trim();
}

// «atlas», «oye atlas», «hey atlas»… y lo que suelen entender mal los reconocedores («hatlas», «at las»)
const WAKE = /(?:^|\s)(?:(?:hola|oye|hey|ey|eh|ok|okay|vale)\s+)?h?at\s?las(?=\s|$)/;

/** Busca la palabra de activación. Devuelve lo que se dijo DESPUÉS de ella (puede estar vacío) o null. */
export function matchWake(transcript: string): { rest: string } | null {
  const t = norm(transcript);
  const m = WAKE.exec(t);
  if (!m) return null;
  return { rest: t.slice(m.index + m[0].length).trim() };
}

export type VoiceIntent = "stop" | "end" | "repeat" | "slower" | "faster";

const INTENTS: [VoiceIntent, RegExp][] = [
  ["stop", /^(para|parate|calla|callate|basta|stop|silencio|espera|cancela|cancelar)( ya| atlas| por favor)?$/],
  ["end", /^(eso es todo|nada mas|ya esta|gracias|muchas gracias|adios|hasta luego|terminamos|fin)( atlas| por ahora| por hoy)?$/],
  ["repeat", /^(repite|repitelo|repitemelo|que has dicho|como|perdona|otra vez|repite por favor)( atlas| por favor)?$/],
  ["slower", /^(habla )?(mas despacio|mas lento|despacio)( por favor)?$/],
  ["faster", /^(habla )?(mas rapido|mas deprisa|rapido)( por favor)?$/],
];

/** Órdenes que se resuelven en el navegador sin pasar por la IA. Solo frases cortas y completas. */
export function voiceIntent(text: string): VoiceIntent | null {
  const t = norm(text);
  for (const [k, rx] of INTENTS) if (rx.test(t)) return k;
  return null;
}

/** ¿Lo que oye el micrófono es la propia voz de ATLAS saliendo por los altavoces? */
export function isEcho(heard: string, spoken: string): boolean {
  const h = norm(heard), s = norm(spoken);
  if (!h || !s) return false;
  if (s.includes(h)) return true;
  const words = h.split(" ").filter((w) => w.length > 2);
  if (words.length < 3) return false;
  const hits = words.filter((w) => s.includes(w)).length;
  return hits / words.length >= 0.7;
}

const HF_KEY = "atlas.handsfree";
export interface HandsFree { wake: boolean; continuous: boolean; clap: boolean }

export function loadHandsFree(): HandsFree {
  try {
    const v = JSON.parse(localStorage.getItem(HF_KEY) ?? "{}") as Partial<HandsFree>;
    return { wake: v.wake === true, continuous: v.continuous !== false, clap: v.clap === true };
  } catch {
    return { wake: false, continuous: true, clap: false };
  }
}

export function saveHandsFree(p: Partial<HandsFree>): HandsFree {
  const next = { ...loadHandsFree(), ...p };
  try { localStorage.setItem(HF_KEY, JSON.stringify(next)); window.dispatchEvent(new Event("atlas-handsfree")); } catch { /* sin almacenamiento */ }
  return next;
}

/** Lo dicho después de «ATLAS» conservando mayúsculas y tildes (para la IA y los intérpretes). */
export function afterWake(original: string): string | null {
  const m = /(?:^|[\s,.¿¡])(?:(?:hola|oye|hey|ey|eh|ok|okay|vale)[\s,]+)?h?[aá]t\s?l[aá]s(?=[\s,.:;!?¿¡]|$)[\s,.:;!]*/i.exec(original);
  return m ? original.slice(m.index + m[0].length).trim() : null;
}
