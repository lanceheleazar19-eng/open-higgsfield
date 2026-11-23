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
  { id: "ai", label: "Intelligence", icon: "ai", color: "#4da3ff", route: "/ai", orbit: 0, phase: 0.35 },
  { id: "memory", label: "Memory", icon: "memory", color: "#a78bfa", route: "/memory", orbit: 0, phase: 2.235 },
  { id: "agents", label: "Agents", icon: "agents", color: "#818cf8", route: "/agents", orbit: 0, phase: 4.12 },
  { id: "tasks", label: "Tasks", icon: "tasks", color: "#22d3ee", route: "/tasks", orbit: 1, phase: 0.978 },
  { id: "calendar", label: "Calendar", icon: "calendar", color: "#38bdf8", route: "/calendar", orbit: 1, phase: 2.863 },
  { id: "projects", label: "Projects", icon: "projects", color: "#60a5fa", route: "/projects", orbit: 1, phase: 4.748 },
  { id: "research", label: "Research", icon: "research", color: "#2dd4bf", route: "/research", orbit: 0, phase: 6.005 },
  { id: "gym", label: "Fitness", icon: "gym", color: "#34d399", route: "/gym", orbit: 2, phase: 1.607 },
  { id: "finance", label: "Finance", icon: "finance", color: "#fbbf24", route: "/finance", orbit: 2, phase: 3.492 },
  { id: "trading", label: "Trading", icon: "trading", color: "#f472b6", route: "/trading", orbit: 2, phase: 5.377 },
];
