import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

type Calls = { cmd: string; args?: Record<string, unknown> }[];
function fakeTauri(responses: Record<string, unknown> = {}) {
  const calls: Calls = [];
  (window as unknown as { __TAURI_INTERNALS__: unknown }).__TAURI_INTERNALS__ = {
    invoke: vi.fn(async (cmd: string, args?: Record<string, unknown>) => { calls.push({ cmd, args }); return responses[cmd] ?? null; }),
  };
  return calls;
}
afterEach(() => {
  delete (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__;
  document.documentElement.className = "";
  vi.resetModules();
});

test("En el navegador (VISTAN Web) el puente no hace nada", async () => {
  const { isDesktop, installDesktopBridge } = await import("../lib/desktop");
  const before = window.Notification;
  installDesktopBridge();
  expect(isDesktop()).toBe(false);
  expect(document.documentElement.classList.contains("desktop")).toBe(false);
  expect(window.Notification).toBe(before);
});

test("En VISTAN Desktop: notificaciones nativas y enlaces externos al navegador predeterminado", async () => {
  const calls = fakeTauri({ notification_permission: "granted" });
  const { isDesktop, installDesktopBridge } = await import("../lib/desktop");
  installDesktopBridge();
  expect(isDesktop()).toBe(true);
  expect(document.documentElement.classList.contains("desktop")).toBe(true);
  await waitFor(() => expect(Notification.permission).toBe("granted"));
  new Notification("VISTAN · Recordatorio", { body: "Entrenar" });
  await waitFor(() => expect(calls.find((c) => c.cmd === "notify")?.args).toEqual({ title: "VISTAN · Recordatorio", body: "Entrenar" }));
  render(<div><a href="https://finnhub.io/docs">docs</a><a href="/trading">interno</a></div>);
  fireEvent.click(screen.getByText("docs"));
  expect(calls.find((c) => c.cmd === "open_external")?.args).toEqual({ url: "https://finnhub.io/docs" });
  fireEvent.click(screen.getByText("interno"));
  expect(calls.filter((c) => c.cmd === "open_external")).toHaveLength(1);
});

test("Ventana de permisos: sin app de escritorio no muestra controles falsos", async () => {
  const { DesktopSettings } = await import("../pages/DesktopSettings");
  render(<MemoryRouter><DesktopSettings /></MemoryRouter>);
  expect(screen.getByText(/Estás en/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Reiniciar/ })).toBeNull();
});

test("Ventana de permisos en VISTAN Desktop: estado real y ajustes validados por la app", async () => {
  const calls = fakeTauri({
    app_info: { version: "1.0.0", repo: "/Users/ana/open-higgsfield/atlas", data_dir: "/Users/ana/open-higgsfield/atlas/data", log: "/x/backend.log", config_dir: "/x", platform: "macos", arch: "aarch64", repo_desktop_version: "1.0.0", rebuild_needed: false },
    backend_status: { phase: "ready", message: "VISTAN listo", port: 8001, url: "http://127.0.0.1:8001/", owned: false, launcher: "launchd", repo: null },
    get_desktop_settings: { repo_path: null, port: 8000, global_shortcut: "Alt+Space", shortcut_enabled: true, autostart: false },
    set_desktop_settings: { repo_path: null, port: 8000, global_shortcut: "Alt+Space", shortcut_enabled: true, autostart: true },
    notification_permission: "default",
  });
  const { DesktopSettings } = await import("../pages/DesktopSettings");
  render(<MemoryRouter><DesktopSettings /></MemoryRouter>);
  expect(await screen.findByText(/servicio en segundo plano de macOS/)).toBeInTheDocument();
  expect(screen.getByText("/Users/ana/open-higgsfield/atlas/data")).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole("checkbox")[0]);
  await waitFor(() => expect(calls.find((c) => c.cmd === "set_desktop_settings")?.args).toEqual({ changes: { autostart: true } }));
  expect(await screen.findByText("Inicio automático activado")).toBeInTheDocument();
});
