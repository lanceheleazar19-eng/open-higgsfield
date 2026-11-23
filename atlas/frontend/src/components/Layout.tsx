import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Header } from "./Header";
import { Reminders } from "./Reminders";
import { Sidebar } from "./Sidebar";

export function Layout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="shell">
      <Header menuOpen={open} onMenu={() => setOpen((o) => !o)} />
      <Sidebar open={open} onNavigate={() => setOpen(false)} />
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />}
      <main className="main">
        <Outlet />
      </main>
      <Reminders />
    </div>
  );
}
