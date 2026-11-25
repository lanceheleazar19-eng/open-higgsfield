export interface NodeDef {
  id: string;
  label: string;
  icon: string;
  route: string;
  orbit: number;
  phase: number; // ángulo inicial (rad)
  size: number; // tamaño relativo del planeta
  hue: string; // tono del planeta (siempre dentro de la paleta carmesí)
  description: string;
}

const Q = Math.PI / 2;
/** Los 15 planetas de VISTAN en 4 órbitas: 3 a 120° en la interior y 4 a 90° en las otras tres. */
export const NODE_DEFS: NodeDef[] = [
  { id: "ai", label: "Intelligence", icon: "ai", route: "/ai", orbit: 0, phase: 0.3, size: 1.0, hue: "#e11d35", description: "Cerebro conversacional, modelos y razonamiento." },
  { id: "lab", label: "Innovation Lab", icon: "lab", route: "/lab", orbit: 0, phase: 0.3 + (4 * Math.PI) / 3, size: 0.95, hue: "#e11d35", description: "Laboratorio privado: radar tecnológico, investigación, experimentos y prototipos." },
  { id: "memory", label: "Memory", icon: "memory", route: "/memory", orbit: 0, phase: 0.3 + (2 * Math.PI) / 3, size: 0.95, hue: "#c2142a", description: "Lo que VISTAN sabe de ti: preferencias, objetivos y decisiones." },
  { id: "agents", label: "Agents", icon: "agents", route: "/agents", orbit: 2, phase: 1.75 + 3 * Q, size: 1, hue: "#b51224", description: "Agentes especializados coordinados por VISTAN CORE." },
  { id: "life", label: "Life OS", icon: "life", route: "/life", orbit: 1, phase: 1.05 + 3 * Q, size: 1, hue: "#e11d35", description: "Desarrollo personal y empresarial: negocios, aprendizaje, disciplina, decisiones." },
  { id: "research", label: "Research", icon: "research", route: "/research", orbit: 1, phase: 1.05, size: 1, hue: "#d01a31", description: "Investigaciones con fuentes, contradicciones y confianza." },
  { id: "projects", label: "Projects", icon: "projects", route: "/projects", orbit: 1, phase: 1.05 + Q, size: 1.05, hue: "#a51022", description: "Workspaces con tareas, notas, documentos e informes." },
  { id: "tasks", label: "Tasks", icon: "tasks", route: "/tasks", orbit: 1, phase: 1.05 + 2 * Q, size: 1, hue: "#e11d35", description: "Tareas, prioridades y plan de la semana." },
  { id: "calendar", label: "Calendar", icon: "calendar", route: "/calendar", orbit: 2, phase: 1.75, size: 0.95, hue: "#b51224", description: "Eventos de iCloud y de VISTAN, con solapes." },
  { id: "workflows", label: "Automations", icon: "workflows", route: "/workflows", orbit: 2, phase: 1.75 + Q, size: 0.95, hue: "#8f0e1e", description: "Daily Briefing, Weekly Review y tus automatizaciones." },
  { id: "gym", label: "Fitness", icon: "gym", route: "/gym", orbit: 2, phase: 1.75 + 2 * Q, size: 1.1, hue: "#e11d35", description: "Entrenos, progresión, fotos de físico y Progress." },
  { id: "nutrition", label: "Nutrition", icon: "nutrition", route: "/nutrition", orbit: 3, phase: 0.6, size: 1, hue: "#c2142a", description: "Comidas, fotos de platos, macros y asesor nutricional." },
  { id: "finance", label: "Finance", icon: "finance", route: "/finance", orbit: 3, phase: 0.6 + Q, size: 1.05, hue: "#b51224", description: "Dinero real: ingresos, gastos y presupuestos." },
  { id: "trading", label: "Trading", icon: "trading", route: "/trading", orbit: 3, phase: 0.6 + 2 * Q, size: 0.95, hue: "#7d0c1b", description: "Operaciones SIMULADAS con capital virtual." },
  { id: "betting", label: "Betting Lab", icon: "betting", route: "/betting", orbit: 3, phase: 0.6 + 3 * Q, size: 0.9, hue: "#9a0f22", description: "Pronósticos deportivos SIMULADOS con dinero ficticio." },
];

/** Relaciones reales entre módulos (comparten datos o contexto): por ellas viajan partículas. */
export const LINKS: [string, string][] = [
  ["ai", "agents"], ["memory", "research"], ["memory", "projects"], ["projects", "tasks"], ["life", "memory"], ["lab", "research"], ["tasks", "calendar"],
  ["workflows", "agents"], ["gym", "nutrition"], ["finance", "trading"], ["trading", "betting"],
];
