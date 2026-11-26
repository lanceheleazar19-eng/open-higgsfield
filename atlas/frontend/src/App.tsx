import { Link, Route, Routes } from "react-router-dom";
import { AtlasProvider } from "./components/AtlasContext";
import { Layout } from "./components/Layout";
import { NAV } from "./components/nav";
import { Brain } from "./pages/Brain";
import { ControlCenter } from "./pages/ControlCenter";
import { Memory } from "./pages/Memory";
import { Tasks } from "./pages/Tasks";
import { Gym } from "./pages/Gym";
import { Nutrition } from "./pages/Nutrition";
import { Calendar } from "./pages/Calendar";
import { Finance } from "./pages/Finance";
import { Trading } from "./pages/Trading";
import { TradingDesk } from "./pages/TradingDesk";
import { Betting } from "./pages/Betting";
import { Life } from "./pages/Life";
import { Lab } from "./pages/Lab";
import { MetaBrain } from "./pages/MetaBrain";
import { Legal } from "./pages/Legal";
import { Agents } from "./pages/Agents";
import { Analytics } from "./pages/Analytics";
import { CommandCenter } from "./pages/CommandCenter";
import { Knowledge } from "./pages/Knowledge";
import { Projects } from "./pages/Projects";
import { Research } from "./pages/Research";
import { Workflows } from "./pages/Workflows";
import { Progress } from "./pages/Progress";
import { ModulePage } from "./pages/ModulePage";
import { Settings } from "./pages/Settings";

const BUILT = new Set(["dashboard", "settings", "ai", "memory", "tasks", "gym", "nutrition", "calendar", "finance", "trading", "betting", "life", "lab", "meta", "legal", "agents", "reports", "command", "knowledge", "projects", "research", "workflows", "progress"]);

export function App() {
  return (
    <AtlasProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<ControlCenter />} />
          <Route path="settings" element={<Settings />} />
          <Route path="ai" element={<Brain />} />
          <Route path="memory" element={<Memory />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="gym" element={<Gym />} />
          <Route path="nutrition" element={<Nutrition />} />
          <Route path="calendar" element={<Calendar />} />
          <Route path="finance" element={<Finance />} />
          <Route path="trading" element={<TradingDesk />} />
          <Route path="trading/legacy" element={<Trading />} />
          <Route path="betting" element={<Betting />} />
          <Route path="life" element={<Life />} />
          <Route path="lab" element={<Lab />} />
          <Route path="meta" element={<MetaBrain />} />
          <Route path="legal" element={<Legal />} />
          <Route path="agents" element={<Agents />} />
          <Route path="reports" element={<Analytics />} />
          <Route path="command" element={<CommandCenter />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="projects" element={<Projects />} />
          <Route path="research" element={<Research />} />
          <Route path="workflows" element={<Workflows />} />
          <Route path="progress" element={<Progress />} />
          {NAV.filter((n) => !BUILT.has(n.id)).map((n) => (
            <Route key={n.id} path={n.path.slice(1)} element={<ModulePage id={n.id} />} />
          ))}
          <Route path="*" element={<div className="page"><h1>Ruta no encontrada</h1><Link to="/">Volver al dashboard</Link></div>} />
        </Route>
      </Routes>
    </AtlasProvider>
  );
}
