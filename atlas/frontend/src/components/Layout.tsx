import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Icon } from "./Icon";
import { Reminders } from "./Reminders";
import { Sidebar } from "./Sidebar";

export function Layout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="shell">
      <header className="topbar">
        <button className="icon-btn" onClick={() => setOpen((o) => !o)} aria-label={open ? "Cerrar menú" : "Abrir menú"} aria-expanded={open}>
          <Icon name={open ? "close" : "menu"} />
        </button>
        <span className="brand-name">ATLAS</span>
      </header>
      <Sidebar open={open} onNavigate={() => setOpen(false)} />
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />}
      <main className="main">
        <Outlet />
      </main>
      <Reminders />
    </div>
  );
}
