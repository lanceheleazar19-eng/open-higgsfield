/* Spanish retail calendar: the dates a small shop should be posting about,
   computed for any year (moving feasts included), each with a ready idea. */

import type { SectorId } from "./content";

export type Occasion = {
  id: string;
  date: Date;
  emoji: string;
  title: string;
  /** What to post, in the shop owner's words. */
  idea: string;
  /** Extra brief for the AI copywriter. */
  brief: string;
  /** Sectors it suits best; empty means everyone. */
  sectors: readonly SectorId[];
  /** How many days ahead it is worth starting to post. */
  leadDays: number;
};

type Template = Omit<Occasion, "date"> & { on: (year: number) => Date };

const day = (year: number, month: number, date: number) => new Date(year, month - 1, date);

/** Easter Sunday (Gregorian, anonymous algorithm). */
export function easterSunday(year: number): Date {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const date = ((h + l - 7 * m + 114) % 31) + 1;
  return day(year, month, date);
}

/** The n-th given weekday (0 = Sunday) of a month. */
function nthWeekday(year: number, month: number, weekday: number, n: number): Date {
  const first = day(year, month, 1);
  const offset = (weekday - first.getDay() + 7) % 7;
  return day(year, month, 1 + offset + (n - 1) * 7);
}

function addDays(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

/** Black Friday: the day after the fourth Thursday of November. */
function blackFriday(year: number): Date {
  return addDays(nthWeekday(year, 11, 4, 4), 1);
}

const TEMPLATES: readonly Template[] = [
  {
    id: "reyes",
    on: (y) => day(y, 1, 6),
    emoji: "👑",
    title: "Reyes Magos",
    idea: "Último empujón de regalos: «¿Aún te falta un regalo? Te lo preparamos hoy».",
    brief: "Campaña de Reyes Magos: regalos de última hora, envolvemos para regalo, urgencia amable.",
    sectors: ["moda", "belleza", "hogar", "artesania", "comida", "otro"],
    leadDays: 14,
  },
  {
    id: "rebajas-invierno",
    on: (y) => day(y, 1, 7),
    emoji: "🏷️",
    title: "Rebajas de invierno",
    idea: "Enseña lo que rebajas y el porcentaje real. Publica varios días seguidos.",
    brief: "Rebajas de invierno. Solo menciona descuentos si el comercio ha dado el porcentaje en los detalles.",
    sectors: ["moda", "hogar", "belleza", "otro"],
    leadDays: 5,
  },
  {
    id: "san-valentin",
    on: (y) => day(y, 2, 14),
    emoji: "❤️",
    title: "San Valentín",
    idea: "Ideas de regalo para pareja; los packs y las ediciones especiales funcionan muy bien.",
    brief: "San Valentín: regalo para la pareja, detalle especial, reservas con antelación.",
    sectors: ["comida", "belleza", "moda", "artesania", "otro"],
    leadDays: 14,
  },
  {
    id: "dia-padre",
    on: (y) => day(y, 3, 19),
    emoji: "👔",
    title: "Día del Padre",
    idea: "«El regalo para papá»: un producto estrella con foto lifestyle.",
    brief: "Día del Padre (19 de marzo, San José): regalo para papá.",
    sectors: [],
    leadDays: 14,
  },
  {
    id: "semana-santa",
    on: (y) => addDays(easterSunday(y), -3),
    emoji: "🌿",
    title: "Semana Santa",
    idea: "Horarios de Semana Santa y productos típicos (torrijas, monas, escapadas).",
    brief: "Semana Santa: horarios especiales, productos de temporada, vacaciones.",
    sectors: ["comida", "hogar", "otro"],
    leadDays: 10,
  },
  {
    id: "sant-jordi",
    on: (y) => day(y, 4, 23),
    emoji: "🌹",
    title: "Sant Jordi / Día del Libro",
    idea: "Rosas, libros y regalos con detalle. Muy fuerte en Cataluña.",
    brief: "Sant Jordi y Día del Libro (23 de abril): rosa, libro, regalo con detalle.",
    sectors: ["artesania", "belleza", "moda", "otro"],
    leadDays: 10,
  },
  {
    id: "dia-madre",
    on: (y) => nthWeekday(y, 5, 0, 1),
    emoji: "💐",
    title: "Día de la Madre",
    idea: "La fecha más fuerte de la primavera: regalos, packs y «reserva el tuyo».",
    brief: "Día de la Madre (primer domingo de mayo): regalo para mamá, emoción, reservas.",
    sectors: [],
    leadDays: 15,
  },
  {
    id: "verano",
    on: (y) => day(y, 6, 21),
    emoji: "☀️",
    title: "Llega el verano",
    idea: "Novedades de temporada y horario de verano.",
    brief: "Comienzo del verano: temporada, calor, terraza, vacaciones, horario de verano.",
    sectors: [],
    leadDays: 7,
  },
  {
    id: "san-juan",
    on: (y) => day(y, 6, 23),
    emoji: "🔥",
    title: "Noche de San Juan",
    idea: "Planes de la verbena: coca, bebidas, decoración.",
    brief: "Noche de San Juan (23 de junio): verbena, fiesta, coca de San Juan.",
    sectors: ["comida", "hogar", "otro"],
    leadDays: 7,
  },
  {
    id: "rebajas-verano",
    on: (y) => day(y, 7, 1),
    emoji: "🏖️",
    title: "Rebajas de verano",
    idea: "Enseña las rebajas reales y avisa de la primera semana.",
    brief: "Rebajas de verano. Solo menciona descuentos si el comercio ha dado el porcentaje en los detalles.",
    sectors: ["moda", "hogar", "belleza", "otro"],
    leadDays: 5,
  },
  {
    id: "vuelta-al-cole",
    on: (y) => day(y, 9, 1),
    emoji: "🎒",
    title: "Vuelta al cole y a la rutina",
    idea: "Vuelta a la rutina: novedades de otoño y «volvemos con horario normal».",
    brief: "Septiembre: vuelta al cole y a la rutina, nueva temporada.",
    sectors: [],
    leadDays: 10,
  },
  {
    id: "halloween",
    on: (y) => day(y, 10, 31),
    emoji: "🎃",
    title: "Halloween y Todos los Santos",
    idea: "Producto con toque otoñal (huesos de santo, buñuelos, decoración).",
    brief: "Halloween y Todos los Santos (1 de noviembre): otoño, buñuelos, huesos de santo, decoración.",
    sectors: ["comida", "hogar", "artesania", "otro"],
    leadDays: 10,
  },
  {
    id: "black-friday",
    on: blackFriday,
    emoji: "🖤",
    title: "Black Friday",
    idea: "Oferta clara y por tiempo limitado. Anúnciala unos días antes.",
    brief: "Black Friday: oferta por tiempo limitado. Solo menciona descuentos si el comercio los ha indicado en los detalles.",
    sectors: [],
    leadDays: 10,
  },
  {
    id: "loteria",
    on: (y) => day(y, 12, 22),
    emoji: "🍀",
    title: "Lotería de Navidad",
    idea: "Ambiente navideño y «compra local estas fiestas».",
    brief: "Sorteo de la Lotería de Navidad (22 de diciembre): ambiente navideño, compra local.",
    sectors: [],
    leadDays: 5,
  },
  {
    id: "navidad",
    on: (y) => day(y, 12, 25),
    emoji: "🎄",
    title: "Navidad",
    idea: "Regalos, encargos y horarios de fiestas. Empieza pronto y publica a menudo.",
    brief: "Navidad: regalos, encargos con antelación, horarios de fiestas, comercio local.",
    sectors: [],
    leadDays: 30,
  },
  {
    id: "nochevieja",
    on: (y) => day(y, 12, 31),
    emoji: "🥂",
    title: "Nochevieja",
    idea: "Despide el año dando las gracias a tus clientes.",
    brief: "Nochevieja: agradecer a los clientes el año, celebración, próximo año.",
    sectors: [],
    leadDays: 5,
  },
];

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** Occasions from today on, soonest first, within `days`. */
export function upcomingOccasions(today: Date, days = 90): Occasion[] {
  const from = startOfDay(today);
  const until = addDays(from, days);
  const occasions: Occasion[] = [];
  for (const year of [from.getFullYear(), from.getFullYear() + 1]) {
    for (const { on, ...rest } of TEMPLATES) {
      const date = on(year);
      if (date >= from && date <= until) occasions.push({ ...rest, date });
    }
  }
  return occasions.sort((a, b) => a.date.getTime() - b.date.getTime());
}

/** The occasion worth posting about right now, if any (within its lead time). */
export function currentOccasion(today: Date, sector?: SectorId): Occasion | null {
  const from = startOfDay(today);
  return (
    upcomingOccasions(today, 45).find((occasion) => {
      const daysLeft = Math.round((occasion.date.getTime() - from.getTime()) / 86_400_000);
      const fits = !sector || occasion.sectors.length === 0 || occasion.sectors.includes(sector);
      return daysLeft <= occasion.leadDays && fits;
    }) ?? null
  );
}

export function occasionById(id: string, today: Date): Occasion | null {
  return upcomingOccasions(today, 366).find((occasion) => occasion.id === id) ?? null;
}

export function daysUntil(date: Date, today: Date): number {
  return Math.round((startOfDay(date).getTime() - startOfDay(today).getTime()) / 86_400_000);
}

/** Weekly posting ideas for days with no occasion. */
export const EVERYDAY_IDEAS: readonly { emoji: string; title: string; idea: string }[] = [
  { emoji: "⭐", title: "Lunes: producto estrella", idea: "Empieza la semana con tu producto más vendido." },
  { emoji: "🆕", title: "Martes: novedad", idea: "Enseña algo nuevo o que acaba de llegar." },
  { emoji: "🙋", title: "Miércoles: detrás del mostrador", idea: "Cómo se hace, quién lo prepara, tu día a día." },
  { emoji: "💬", title: "Jueves: lo que dicen tus clientes", idea: "Comparte una opinión real (con permiso)." },
  { emoji: "🎉", title: "Viernes: plan de fin de semana", idea: "Algo perfecto para el finde y tu horario del sábado." },
  { emoji: "📍", title: "Sábado: ven a vernos", idea: "Recuerda dónde estás y que se puede reservar por WhatsApp." },
  { emoji: "😴", title: "Domingo: descanso", idea: "Programa el contenido de la semana que viene." },
];

/** Index 0 = Monday. */
export function everydayIdea(today: Date) {
  return EVERYDAY_IDEAS[(today.getDay() + 6) % 7];
}

/** "Today" as a shop in Spain sees it, wherever the server runs (Vercel is UTC). */
export function todayInSpain(): Date {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Madrid",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const get = (type: string) => Number(parts.find((part) => part.type === type)?.value);
  return new Date(get("year"), get("month") - 1, get("day"));
}
