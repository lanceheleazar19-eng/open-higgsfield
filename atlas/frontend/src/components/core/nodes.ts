export interface NodeDef {
  id: string;
  label: string; // identidad del módulo
  icon: string;
  color: string;
  route: string;
  orbit: number;
  phase: number; // ángulo inicial (rad)
}

/** Los 10 módulos que orbitan el núcleo. */
export const NODE_DEFS: NodeDef[] = [
  { id: "ai", label: "Inteligencia IA", icon: "ai", color: "#ff2e42", route: "/ai", orbit: 0, phase: 0.35 },
  { id: "memory", label: "Memoria", icon: "memory", color: "#ff2e42", route: "/memory", orbit: 0, phase: 2.235 },
  { id: "agents", label: "Agentes", icon: "agents", color: "#ff2e42", route: "/agents", orbit: 0, phase: 4.12 },
  { id: "tasks", label: "Tareas", icon: "tasks", color: "#ff2e42", route: "/tasks", orbit: 1, phase: 0.978 },
  { id: "calendar", label: "Calendario", icon: "calendar", color: "#ff2e42", route: "/calendar", orbit: 1, phase: 2.863 },
  { id: "projects", label: "Proyectos", icon: "projects", color: "#ff2e42", route: "/projects", orbit: 1, phase: 4.748 },
  { id: "research", label: "Investigación", icon: "research", color: "#ff2e42", route: "/research", orbit: 0, phase: 6.005 },
  { id: "gym", label: "Gimnasio", icon: "gym", color: "#ff2e42", route: "/gym", orbit: 2, phase: 1.607 },
  { id: "finance", label: "Finanzas", icon: "finance", color: "#ff2e42", route: "/finance", orbit: 2, phase: 3.492 },
  { id: "trading", label: "Trading", icon: "trading", color: "#ff2e42", route: "/trading", orbit: 2, phase: 5.377 },
];
