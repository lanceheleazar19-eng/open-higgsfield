import { NavLink } from "react-router-dom";
import { useAtlas } from "./AtlasContext";
import { Icon } from "./Icon";
import { NAV } from "./nav";

export function Sidebar({ open, onNavigate }: { open: boolean; onNavigate: () => void }) {
  const { modules, health, healthError } = useAtlas();
  const byId = new Map(modules.map((m) => [m.id, m]));
  const online = health?.status === "online" && !healthError;

  return (
    <aside className={`sidebar ${open ? "is-open" : ""}`} aria-label="Navegación principal">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">A</div>
        <div>
          <div className="brand-name">ATLAS</div>
          <div className="brand-sub">Personal Intelligence System</div>
        </div>
      </div>
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
      <div className="sidebar-foot">
        <span className={`dot ${online ? "dot-on" : "dot-off"}`} aria-hidden="true" />
        <span>{online ? `Núcleo en línea · v${health!.version}` : "Núcleo sin conexión"}</span>
      </div>
    </aside>
  );
}
