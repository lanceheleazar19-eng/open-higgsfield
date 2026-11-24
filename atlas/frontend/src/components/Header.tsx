import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAtlas } from "./AtlasContext";
import { Avatar } from "./Avatar";
import { Icon } from "./Icon";
import { Logo } from "./Logo";
import { NotificationsBell } from "./NotificationsBell";

function HeaderClock({ timeZone }: { timeZone?: string }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id); }, []);
  const date = new Intl.DateTimeFormat("es-ES", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone }).format(now);
  const time = new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone }).format(now);
  return (
    <div className="hdr-clock">
      <span className="hdr-date">{date.charAt(0).toUpperCase() + date.slice(1)}</span>
      <time className="hdr-time mono">{time}</time>
    </div>
  );
}

/** Cabecera global: marca, estado real del sistema, fecha/hora y foto de perfil. */
export function Header({ menuOpen, onMenu }: { menuOpen: boolean; onMenu: () => void }) {
  const { health, healthError, profile, prefs } = useAtlas();
  const online = health?.status === "online" && !healthError;
  return (
    <header className="hdr">
      <button className="icon-btn hdr-menu" onClick={onMenu} aria-label={menuOpen ? "Cerrar menú" : "Abrir menú"} aria-expanded={menuOpen}>
        <Icon name={menuOpen ? "close" : "menu"} />
      </button>
      <Link to="/" className="hdr-brand" aria-label="VISTAN, ir al centro de control">
        <Logo size={42} />
        <span>
          <span className="hdr-title">VISTAN</span>
          <span className="hdr-sub">Personal Intelligence System</span>
        </span>
      </Link>
      <div className={`hdr-status ${online ? "on" : "off"}`} role="status">
        <i aria-hidden="true" />{online ? "Sistema activo" : health ? "Sistema degradado" : "Sin conexión"}
      </div>
      <div className="hdr-right">
        <button type="button" className="hdr-k" onClick={() => window.dispatchEvent(new Event("atlas-palette"))} aria-label="Abrir paleta de comandos">
          <Icon name="research" size={15} /><span>Buscar o ejecutar</span><kbd>⌘K</kbd>
        </button>
        <NotificationsBell />
        <HeaderClock timeZone={prefs?.timezone} />
        <Link to="/settings#perfil" className="hdr-avatar" aria-label="Mi perfil y configuración" title={profile?.display_name || "Mi perfil"}>
          <Avatar profile={profile} size={46} />
        </Link>
      </div>
    </header>
  );
}
