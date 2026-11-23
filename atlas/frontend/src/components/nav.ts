export interface NavItem {
  id: string;
  path: string;
  label: string;
}

/** Orden de la barra lateral. El estado (activo/fase) llega de /api/system/modules. */
export const NAV: NavItem[] = [
  { id: "dashboard", path: "/", label: "Dashboard" },
  { id: "ai", path: "/ai", label: "Inteligencia artificial" },
  { id: "tasks", path: "/tasks", label: "Tareas" },
  { id: "gym", path: "/gym", label: "Gimnasio" },
  { id: "nutrition", path: "/nutrition", label: "Nutrición" },
  { id: "finance", path: "/finance", label: "Finanzas" },
  { id: "trading", path: "/trading", label: "Trading" },
  { id: "projects", path: "/projects", label: "Proyectos" },
  { id: "calendar", path: "/calendar", label: "Calendario" },
  { id: "memory", path: "/memory", label: "Memoria" },
  { id: "research", path: "/research", label: "Investigación" },
  { id: "agents", path: "/agents", label: "Agentes" },
  { id: "reports", path: "/reports", label: "Informes" },
  { id: "settings", path: "/settings", label: "Configuración" },
];
