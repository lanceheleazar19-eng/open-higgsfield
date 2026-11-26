import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { setDesktopNavigate } from "../lib/desktop";
import { Header } from "./Header";
import { Reminders } from "./Reminders";
import { CommandPalette } from "./CommandPalette";
import { Sidebar } from "./Sidebar";

export function Layout() {
  const [open, setOpen] = useState(false);
  const path = useLocation().pathname;
  const navigate = useNavigate();
  useEffect(() => setDesktopNavigate((p) => navigate(p)), [navigate]); // menú nativo de VISTAN Desktop
  const hud = path === "/" || path === "/trading" || path === "/betting" || path === "/life" || path === "/lab" || path === "/meta" || path === "/legal" || path === "/academy"; // pantalla completa (centro de control y Trading Desk): menú como carril de iconos
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
