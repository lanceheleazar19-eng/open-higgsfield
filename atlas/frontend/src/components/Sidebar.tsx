import { NavLink } from "react-router-dom";
import { useAtlas } from "./AtlasContext";
import { Icon } from "./Icon";
import { NAV } from "./nav";
import { SystemStatus } from "./SystemStatus";

export function Sidebar({ open, onNavigate }: { open: boolean; onNavigate: () => void }) {
  const { modules } = useAtlas();
  const byId = new Map(modules.map((m) => [m.id, m]));

  return (
    <aside className={`sidebar ${open ? "is-open" : ""}`} aria-label="Navegación principal">
      <nav>
        <ul>
          {NAV.map((item) => {
            const m = byId.get(item.id);
            const planned = m?.status === "planned";
            return (
              <li key={item.id}>
                <NavLink
                  to={item.path}
                  end={item.path === "/"}
                  onClick={onNavigate}
                  className={({ isActive }) => `nav-link ${isActive ? "is-active" : ""} ${planned ? "is-planned" : ""}`}
                >
                  <Icon name={item.id} />
                  <span className="nav-label">{item.label}</span>
                  {planned && <span className="phase-tag" title={`Se construye en la Fase ${m!.phase}`}>F{m!.phase}</span>}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>
      <SystemStatus />
    </aside>
  );
}
