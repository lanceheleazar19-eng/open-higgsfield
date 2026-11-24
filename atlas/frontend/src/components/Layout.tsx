import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Header } from "./Header";
import { Reminders } from "./Reminders";
import { CommandPalette } from "./CommandPalette";
import { Sidebar } from "./Sidebar";

export function Layout() {
  const [open, setOpen] = useState(false);
  const hud = useLocation().pathname === "/"; // centro de control a pantalla completa: menú como carril de iconos
  return (
    <div className={`shell ${hud ? "is-hud" : ""}`}>
      <Header menuOpen={open} onMenu={() => setOpen((o) => !o)} />
      <Sidebar open={open} onNavigate={() => setOpen(false)} />
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />}
      <main className="main">
        <Outlet />
      </main>
      <Reminders />
      <CommandPalette />
    </div>
  );
}
