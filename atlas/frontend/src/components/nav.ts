export interface NavItem {
  id: string;
  path: string;
  label: string;
}

/** Orden de la barra lateral. El estado (activo/fase) llega de /api/system/modules. */
export const NAV: NavItem[] = [
  { id: "dashboard", path: "/", label: "Núcleo" },
  { id: "command", path: "/command", label: "Command Center" },
  { id: "ai", path: "/ai", label: "Inteligencia" },
  { id: "agents", path: "/agents", label: "Agentes" },
  { id: "memory", path: "/memory", label: "Memoria" },
  { id: "knowledge", path: "/knowledge", label: "Conocimiento" },
  { id: "research", path: "/research", label: "Investigación" },
  { id: "projects", path: "/projects", label: "Proyectos" },
  { id: "tasks", path: "/tasks", label: "Tareas" },
  { id: "calendar", path: "/calendar", label: "Calendario" },
  { id: "gym", path: "/gym", label: "Fitness" },
  { id: "nutrition", path: "/nutrition", label: "Nutrición" },
  { id: "finance", path: "/finance", label: "Finanzas" },
  { id: "trading", path: "/trading", label: "Trading" },
  { id: "workflows", path: "/workflows", label: "Automatizaciones" },
  { id: "reports", path: "/reports", label: "Analytics" },
  { id: "settings", path: "/settings", label: "Configuración" },
];
