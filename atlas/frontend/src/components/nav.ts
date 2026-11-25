export interface NavItem {
  id: string;
  path: string;
  label: string;
  group: string;
}

/** Orden de la barra lateral. El estado (activo/fase) llega de /api/system/modules. */
export const NAV_GROUPS = ["Sistema", "Inteligencia", "Organización", "Personal", "Finanzas", "Configuración"] as const;

export const NAV: NavItem[] = [
  { id: "dashboard", path: "/", label: "Núcleo", group: "Sistema" },
  { id: "command", path: "/command", label: "Command Center", group: "Sistema" },
  { id: "reports", path: "/reports", label: "Analytics", group: "Sistema" },
  { id: "ai", path: "/ai", label: "Inteligencia", group: "Inteligencia" },
  { id: "agents", path: "/agents", label: "Agentes", group: "Inteligencia" },
  { id: "memory", path: "/memory", label: "Memoria", group: "Inteligencia" },
  { id: "knowledge", path: "/knowledge", label: "Conocimiento", group: "Inteligencia" },
  { id: "research", path: "/research", label: "Investigación", group: "Inteligencia" },
  { id: "projects", path: "/projects", label: "Proyectos", group: "Organización" },
  { id: "tasks", path: "/tasks", label: "Tareas", group: "Organización" },
  { id: "calendar", path: "/calendar", label: "Calendario", group: "Organización" },
  { id: "workflows", path: "/workflows", label: "Automatizaciones", group: "Organización" },
  { id: "life", path: "/life", label: "Life OS", group: "Personal" },
  { id: "gym", path: "/gym", label: "Fitness", group: "Personal" },
  { id: "progress", path: "/progress", label: "Progress", group: "Personal" },
  { id: "nutrition", path: "/nutrition", label: "Nutrición", group: "Personal" },
  { id: "finance", path: "/finance", label: "Finanzas", group: "Finanzas" },
  { id: "trading", path: "/trading", label: "Trading", group: "Finanzas" },
  { id: "betting", path: "/betting", label: "Paper Betting", group: "Finanzas" },
  { id: "settings", path: "/settings", label: "Configuración", group: "Configuración" },
];
