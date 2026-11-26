/** Puente con VISTAN Desktop (Tauri). En el navegador (VISTAN Web) todo esto es inerte: isDesktop() = false.
 *  La interfaz es la misma en los dos modos; aquí solo se añaden las capacidades nativas del Mac. */

type Invoke = (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
interface TauriWindow { __TAURI_INTERNALS__?: { invoke: Invoke }; __TAURI__?: { core?: { invoke: Invoke } }; __vistan?: { navigate: (p: string) => void } }

function invoker(): Invoke | null {
  const w = window as unknown as TauriWindow;
  return w.__TAURI__?.core?.invoke ?? w.__TAURI_INTERNALS__?.invoke ?? null;
}

export const isDesktop = (): boolean => invoker() !== null;
export const isMac = (): boolean => /Mac/i.test(navigator.userAgent);

export function call<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  const inv = invoker();
  if (!inv) return Promise.reject(new Error("Disponible solo en VISTAN Desktop"));
  return inv(cmd, args) as Promise<T>;
}

export interface BackendStatus { phase: string; message: string; port: number | null; url: string | null; owned: boolean; launcher: string; repo: string | null }
export interface AppInfo { version: string; repo: string | null; data_dir: string | null; log: string; config_dir: string; platform: string; arch: string; repo_desktop_version: string | null; rebuild_needed: boolean }
export interface DesktopSettings { repo_path: string | null; port: number; global_shortcut: string; shortcut_enabled: boolean; autostart: boolean }

export const desktop = {
  status: () => call<BackendStatus>("backend_status"),
  info: () => call<AppInfo>("app_info"),
  settings: () => call<DesktopSettings>("get_desktop_settings"),
  saveSettings: (changes: Partial<Omit<DesktopSettings, "repo_path">>) => call<DesktopSettings>("set_desktop_settings", { changes }),
  restart: () => call<string>("restart_backend"),
  notify: (title: string, body?: string) => call<void>("notify", { title, body }),
  notificationPermission: () => call<NotificationPermission>("notification_permission"),
  requestNotificationPermission: () => call<NotificationPermission>("request_notification_permission"),
  openExternal: (url: string) => call<void>("open_external", { url }),
  copy: (text: string) => call<void>("copy_text", { text }),
  openLogs: () => call<void>("open_logs"),
  openPreferences: () => call<void>("open_preferences"),
  update: () => call<{ output: string; restart: string; rebuild_needed: boolean; repo_desktop_version: string | null }>("update_vistan"),
  openInBrowser: () => call<void>("open_in_browser"),
};

/** Las notificaciones web no existen dentro de una app de macOS: se sustituye `Notification` por la nativa,
 *  así el código existente (recordatorios, campana) funciona igual sin duplicar nada. */
function installNotifications(): void {
  let permission: NotificationPermission = "default";
  desktop.notificationPermission().then((p) => { permission = p; }).catch(() => undefined);
  class NativeNotification {
    static get permission(): NotificationPermission { return permission; }
    static async requestPermission(): Promise<NotificationPermission> {
      permission = await desktop.requestNotificationPermission().catch(() => "denied" as NotificationPermission);
      return permission;
    }
    onclick: (() => void) | null = null;
    constructor(title: string, opts?: { body?: string }) {
      void desktop.notify(title, opts?.body).catch(() => undefined);
    }
    close(): void { /* las nativas se gestionan en el Centro de notificaciones */ }
  }
  (window as unknown as { Notification: unknown }).Notification = NativeNotification;
}

/** Enlaces a otras webs → navegador predeterminado (la ventana de VISTAN nunca se convierte en un navegador). */
function installLinks(): void {
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0) return;
    const a = (e.target as HTMLElement | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
    if (!a) return;
    let url: URL;
    try { url = new URL(a.href, location.href); } catch { return; }
    const external = url.origin !== location.origin && /^(https?|mailto):$/.test(url.protocol);
    if (external || (a.target === "_blank" && url.origin !== location.origin)) {
      e.preventDefault();
      void desktop.openExternal(url.href).catch(() => undefined);
    }
  }, true);
}

let installed = false;
/** Se llama una vez antes de montar React: añade las capacidades nativas (si estamos en VISTAN Desktop). */
export function installDesktopBridge(): void {
  if (installed || !isDesktop()) return;
  installed = true;
  const root = document.documentElement;
  root.classList.add("desktop");
  if (isMac()) root.classList.add("mac");
  installNotifications();
  installLinks();
}

/** Navegación de React Router para el menú nativo (⌘1…⌘9, ⌘,). */
export function setDesktopNavigate(navigate: (path: string) => void): void {
  (window as unknown as TauriWindow).__vistan = { navigate };
}
