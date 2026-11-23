import { Link, Route, Routes } from "react-router-dom";
import { AtlasProvider } from "./components/AtlasContext";
import { Layout } from "./components/Layout";
import { NAV } from "./components/nav";
import { Brain } from "./pages/Brain";
import { ControlCenter } from "./pages/ControlCenter";
import { Memory } from "./pages/Memory";
import { Tasks } from "./pages/Tasks";
import { ModulePage } from "./pages/ModulePage";
import { Settings } from "./pages/Settings";

const BUILT = new Set(["dashboard", "settings", "ai", "memory", "tasks"]);

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
          {NAV.filter((n) => !BUILT.has(n.id)).map((n) => (
            <Route key={n.id} path={n.path.slice(1)} element={<ModulePage id={n.id} />} />
          ))}
          <Route path="*" element={<div className="page"><h1>Ruta no encontrada</h1><Link to="/">Volver al dashboard</Link></div>} />
        </Route>
      </Routes>
    </AtlasProvider>
  );
}
