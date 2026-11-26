import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { desktop, isDesktop, type AppInfo, type BackendStatus, type DesktopSettings as DS } from "../lib/desktop";
import { Logo } from "../components/Logo";

type Check = "idle" | "ok" | "fail" | "busy";

function Row({ title, desc, children }: { title: string; desc: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="dk-row">
      <div><h3>{title}</h3><p>{desc}</p></div>
      {children && <div className="dk-ctl">{children}</div>}
    </div>
  );
}

const LAUNCHER: Record<string, string> = { desktop: "arrancado por VISTAN Desktop", launchd: "servicio en segundo plano de macOS", web: "VISTAN Web (start.sh)", desconocido: "instancia existente" };

/** Ventana «Permisos y privacidad» de VISTAN Desktop. En el navegador explica qué ofrece la app y no muestra controles falsos. */
export function DesktopSettings() {
  const desk = isDesktop();
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [st, setSt] = useState<BackendStatus | null>(null);
  const [cfg, setCfg] = useState<DS | null>(null);
  const [shortcut, setShortcut] = useState("");
  const [notif, setNotif] = useState<NotificationPermission | null>(null);
  const [mic, setMic] = useState<Check>("idle");
  const [clip, setClip] = useState<Check>("idle");
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!desk) return;
    try {
      const [i, s, c, n] = await Promise.all([desktop.info(), desktop.status(), desktop.settings(), desktop.notificationPermission()]);
      setInfo(i); setSt(s); setCfg(c); setShortcut(c.global_shortcut); setNotif(n);
    } catch (e) { setMsg((e as Error).message ?? String(e)); }
  }, [desk]);
  useEffect(() => { void load(); }, [load]);

  const save = async (ch: Parameters<typeof desktop.saveSettings>[0], ok: string) => {
    try { setCfg(await desktop.saveSettings(ch)); setMsg(ok); } catch (e) { setMsg(String(e)); }
  };
  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    try { const r = await fn(); setMsg(ok ?? (typeof r === "string" ? r : "Hecho")); void load(); } catch (e) { const t = String(e); if (t !== "Cancelado") setMsg(t); }
  };
  const testMic = async () => {
    setMic("busy");
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      s.getTracks().forEach((t) => t.stop()); // no se graba ni se guarda nada
      setMic("ok");
    } catch { setMic("fail"); }
  };
  const testClip = async () => {
    setClip("busy");
    try { await desktop.copy("VISTAN · prueba de portapapeles"); setClip("ok"); } catch { setClip("fail"); }
  };

  return (
    <div className="dk-page">
      <header className="dk-head" data-tauri-drag-region>
        <Logo size={40} />
        <div data-tauri-drag-region>
          <h1>Permisos y privacidad</h1>
          <p>VISTAN Desktop {info ? `· ${info.version}` : ""}</p>
        </div>
      </header>

      {!desk && (
        <section className="dk-card">
          <p>Estás en <b>VISTAN Web</b>. Estos ajustes solo existen en la aplicación de escritorio para macOS (<code>atlas/desktop</code>), que usa este mismo backend y los mismos datos.</p>
          <p><Link to="/settings">Volver a Configuración</Link></p>
        </section>
      )}

      {desk && (
        <>
          {msg && <p className="dk-msg" role="status">{msg}</p>}
          {info?.rebuild_needed && (
            <p className="dk-warn">El proyecto tiene una versión nueva de la app de escritorio ({info.repo_desktop_version}). Recompílala con <code>./atlas/desktop/scripts/build-macos.sh</code>.</p>
          )}

          <section className="dk-card">
            <h2>Sistema</h2>
            <Row title="Backend local" desc={st ? <>{st.phase === "ready" ? "Funcionando" : st.message} · <code>{st.url ?? "—"}</code> · {LAUNCHER[st.launcher] ?? st.launcher}{st.owned ? " (se detiene al salir de la app)" : " (sigue funcionando al salir de la app)"}</> : "…"}>
              <button type="button" className="btn" onClick={() => void run(desktop.restart)}>Reiniciar</button>
            </Row>
            <Row title="Datos" desc={<>La misma base de datos que VISTAN Web: <code>{info?.data_dir ?? "—"}</code>. Proyecto: <code>{info?.repo ?? "—"}</code></>}>
              <button type="button" className="btn" onClick={() => void run(desktop.openInBrowser, "Abierto en tu navegador")}>Abrir VISTAN Web</button>
            </Row>
            <Row title="Actualizaciones" desc="Descarga los cambios del proyecto (git pull --ff-only, nunca sobrescribe cambios tuyos) y reinicia el backend. Te pedirá confirmación.">
              <button type="button" className="btn" onClick={() => void run(async () => { const r = await desktop.update(); return r.rebuild_needed ? "Actualizado. La app de escritorio también cambió: recompílala." : "VISTAN actualizado"; })}>Actualizar VISTAN…</button>
            </Row>
            <Row title="Registro" desc={<>Mensajes del arranque y del backend: <code>{info?.log ?? "—"}</code></>}>
              <button type="button" className="btn" onClick={() => void run(desktop.openLogs, "Registro mostrado en el Finder")}>Mostrar</button>
            </Row>
          </section>

          <section className="dk-card">
            <h2>Escritorio</h2>
            <Row title="Abrir al iniciar sesión" desc="VISTAN se abre solo al encender el Mac (elemento de inicio de tu usuario).">
              <label className="dk-switch"><input type="checkbox" checked={!!cfg?.autostart} onChange={(e) => void save({ autostart: e.target.checked }, e.target.checked ? "Inicio automático activado" : "Inicio automático desactivado")} /><span /></label>
            </Row>
            <Row title="Atajo global" desc="Muestra u oculta VISTAN desde cualquier aplicación. Ejemplos: Alt+Space, CmdOrCtrl+Shift+V.">
              <label className="dk-switch"><input type="checkbox" checked={!!cfg?.shortcut_enabled} onChange={(e) => void save({ shortcut_enabled: e.target.checked }, "Atajo actualizado")} aria-label="Activar atajo global" /><span /></label>
              <input className="dk-input" value={shortcut} onChange={(e) => setShortcut(e.target.value)} aria-label="Atajo global" />
              <button type="button" className="btn" onClick={() => void save({ global_shortcut: shortcut }, `Atajo: ${shortcut}`)}>Guardar</button>
            </Row>
            <Row title="Atajos de teclado" desc="⌘1…⌘9 módulos · ⌘, configuración · ⇧⌘, esta ventana · ⌘R recargar · ⌘[ / ⌘] atrás/adelante · ⌃⌘F pantalla completa · ⌘W ocultar ventana · ⌘Q salir." />
          </section>

          <section className="dk-card">
            <h2>Permisos de macOS</h2>
            <Row title="Notificaciones" desc={`Recordatorios y avisos de VISTAN como notificaciones nativas. Estado: ${notif === "granted" ? "permitidas" : notif === "denied" ? "bloqueadas (cámbialo en Ajustes del Sistema › Notificaciones)" : "sin decidir"}.`}>
              {notif !== "granted" && <button type="button" className="btn" onClick={() => void run(async () => setNotif(await desktop.requestNotificationPermission()), "Permiso solicitado")}>Permitir</button>}
              <button type="button" className="btn" onClick={() => void run(() => desktop.notify("VISTAN", "Las notificaciones funcionan."), "Notificación enviada")}>Probar</button>
            </Row>
            <Row title="Micrófono" desc={`Solo se usa cuando activas la voz. macOS te preguntará la primera vez. La prueba no graba ni guarda nada. ${mic === "ok" ? "✔ Acceso concedido." : mic === "fail" ? "✖ Acceso denegado: Ajustes del Sistema › Privacidad y seguridad › Micrófono." : ""}`}>
              <button type="button" className="btn" disabled={mic === "busy"} onClick={() => void testMic()}>Probar micrófono</button>
            </Row>
            <Row title="Archivos" desc="VISTAN solo lee los archivos que eliges tú en el selector nativo o arrastras a la ventana (documentos, imágenes, contratos…). No recorre tus carpetas." />
            <Row title="Portapapeles" desc={`VISTAN solo escribe en el portapapeles cuando pulsas copiar. ${clip === "ok" ? "✔ Funciona." : clip === "fail" ? "✖ No disponible." : ""}`}>
              <button type="button" className="btn" disabled={clip === "busy"} onClick={() => void testClip()}>Probar</button>
            </Row>
            <Row title="Enlaces externos" desc="Las webs se abren siempre en tu navegador predeterminado; la ventana de VISTAN solo muestra VISTAN." />
          </section>

          <section className="dk-card">
            <h2>Privacidad y seguridad</h2>
            <ul className="dk-list">
              <li>El backend escucha solo en <code>127.0.0.1</code> y rechaza peticiones con un dominio ajeno (protección contra DNS rebinding). No se expone a la red.</li>
              <li>Las claves API siguen en el Llavero de macOS, gestionadas por el backend; la app y la interfaz nunca las reciben.</li>
              <li>La interfaz solo puede pedir a la app una lista cerrada de acciones (notificar, copiar, abrir enlaces, ajustes, reiniciar). No puede ejecutar comandos ni leer archivos por su cuenta.</li>
              <li>Al salir, la app solo detiene el backend que ella misma arrancó. Nunca cierra otros programas.</li>
              <li>Tus datos no salen del Mac salvo las integraciones que tú configures.</li>
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
