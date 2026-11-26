//! VISTAN Desktop: ventana nativa de macOS para el VISTAN existente.
//! La interfaz y la lógica son las de siempre (servidas por el backend local en 127.0.0.1); esta capa añade
//! ventana propia, Dock, menú, atajos, notificaciones nativas y la gestión automática del backend.

mod backend;
mod commands;
mod menu;
mod settings;

use backend::{log_line, Backend, CURRENT_PORT};
use settings::DesktopSettings;
use std::collections::HashSet;
use std::path::PathBuf;
use std::sync::atomic::Ordering;
use std::sync::Mutex;
use std::time::Duration;
use tauri::ipc::CapabilityBuilder;
use tauri::webview::NewWindowResponse;
use tauri::{AppHandle, Manager, RunEvent, Url, WebviewWindow, WebviewWindowBuilder, WindowEvent};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};
use tauri_plugin_opener::OpenerExt;

pub struct AppState {
    pub settings: Mutex<DesktopSettings>,
    pub config_dir: PathBuf,
    pub log: PathBuf,
    pub path_env: Mutex<Option<String>>,
    granted_ports: Mutex<HashSet<u16>>,
}

impl AppState {
    pub fn repo(&self) -> Option<PathBuf> {
        settings::find_repo(&self.settings.lock().unwrap())
    }
    pub fn path_env(&self) -> String {
        let mut g = self.path_env.lock().unwrap();
        if g.is_none() {
            *g = Some(backend::user_path());
        }
        g.clone().unwrap_or_default()
    }
}

/// Órdenes que puede usar la interfaz de VISTAN (solo desde 127.0.0.1:<puerto activo>).
const REMOTE_PERMISSIONS: &[&str] = &[
    "core:window:allow-start-dragging",
    "core:window:allow-internal-toggle-maximize",
    "allow-backend-status",
    "allow-restart-backend",
    "allow-app-info",
    "allow-get-desktop-settings",
    "allow-set-desktop-settings",
    "allow-notify",
    "allow-notification-permission",
    "allow-request-notification-permission",
    "allow-open-external",
    "allow-copy-text",
    "allow-open-logs",
    "allow-open-preferences",
    "allow-update-vistan",
    "allow-open-in-browser",
];

pub fn splash_url(query: &str) -> Url {
    let base = if cfg!(windows) { "http://tauri.localhost/index.html" } else { "tauri://localhost/index.html" };
    Url::parse(&format!("{base}{query}")).unwrap()
}

/// Solo se navega dentro de VISTAN; cualquier otra dirección se abre en tu navegador predeterminado.
pub fn allowed_navigation(app: &AppHandle, url: &Url) -> bool {
    match url.scheme() {
        "tauri" | "about" | "data" | "blob" => return true,
        "http" | "https" => {}
        _ => return false,
    }
    let host = url.host_str().unwrap_or("");
    if host == "tauri.localhost" {
        return true;
    }
    let port = CURRENT_PORT.load(Ordering::SeqCst);
    if (host == "127.0.0.1" || host == "localhost") && port != 0 && url.port() == Some(port) {
        return true;
    }
    let _ = app.opener().open_url(url.as_str(), None::<&str>);
    false
}

/// Concede a la interfaz servida en ESTE puerto (y solo a ella) las órdenes mínimas de escritorio.
fn grant_port(app: &AppHandle, port: u16) {
    let st = app.state::<AppState>();
    if !st.granted_ports.lock().unwrap().insert(port) {
        return;
    }
    for host in ["127.0.0.1", "localhost"] {
        let mut cap = CapabilityBuilder::new(format!("vistan-{host}-{port}"))
            .remote(format!("http://{host}:{port}/*"))
            .windows(["main", "prefs"]);
        for p in REMOTE_PERMISSIONS {
            cap = cap.permission(*p);
        }
        if let Err(e) = app.add_capability(cap) {
            log_line(&st.log, &format!("no se pudo conceder permisos a {host}:{port}: {e}"));
        }
    }
}

pub fn show_main(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.unminimize();
        let _ = w.show();
        let _ = w.set_focus();
    }
}

fn toggle_main(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        if w.is_visible().unwrap_or(false) && w.is_focused().unwrap_or(false) {
            let _ = w.hide();
        } else {
            show_main(app);
        }
    }
}

/// Lleva la ventana principal a VISTAN cuando el backend está listo.
fn open_vistan(app: &AppHandle, port: u16) {
    grant_port(app, port);
    if let Some(w) = app.get_webview_window("main") {
        let on_vistan = w.url().map(|u| u.port() == Some(port) && u.host_str() == Some("127.0.0.1")).unwrap_or(false);
        if !on_vistan {
            let _ = w.navigate(Url::parse(&format!("http://127.0.0.1:{port}/")).unwrap());
        }
    }
    if let Some(w) = app.get_webview_window("prefs") {
        let _ = w.navigate(Url::parse(&format!("http://127.0.0.1:{port}/desktop")).unwrap());
    }
}

/// Arranca (o reutiliza) el backend en segundo plano y abre VISTAN al terminar.
pub fn start_backend(app: &AppHandle) {
    let be = app.state::<Backend>();
    if be.busy.swap(true, Ordering::SeqCst) {
        return;
    }
    let app = app.clone();
    std::thread::spawn(move || {
        let st = app.state::<AppState>();
        let be = app.state::<Backend>();
        let repo = st.repo();
        let port_pref = st.settings.lock().unwrap().port;
        let path_env = st.path_env();
        let res = be.ensure(repo, port_pref, &path_env, &st.log);
        be.busy.store(false, Ordering::SeqCst);
        if let Ok(port) = res {
            let a = app.clone();
            let _ = app.run_on_main_thread(move || open_vistan(&a, port));
        }
    });
}

/// Vigilancia: si el backend deja de responder se reconecta o se reinicia (con límite), sin duplicar instancias.
fn monitor(app: AppHandle) {
    std::thread::spawn(move || {
        let mut fails = 0;
        let mut failed_since: Option<std::time::Instant> = None;
        loop {
            std::thread::sleep(Duration::from_secs(4));
            let be = app.state::<Backend>();
            if be.quitting.load(Ordering::SeqCst) {
                return;
            }
            let s = be.snapshot();
            // Arranque fallido: reintento automático con espera (máx. 5 reinicios en 10 min; después, solo con «Reintentar»)
            if s.phase == "failed" && !s.needs_repo && !be.busy.load(Ordering::SeqCst) {
                let since = *failed_since.get_or_insert_with(std::time::Instant::now);
                if since.elapsed() >= Duration::from_secs(10) && be.allow_restart() {
                    failed_since = None;
                    log_line(&app.state::<AppState>().log, "reintento automático del arranque");
                    start_backend(&app);
                }
                continue;
            }
            failed_since = None;
            if s.phase != "ready" || be.busy.load(Ordering::SeqCst) {
                fails = 0;
                continue;
            }
            let port = s.port.unwrap_or(0);
            let exited = s.owned && (be.child_exited() || be.adopted_exited());
            if !exited && backend::health(port).is_some() {
                fails = 0;
                continue;
            }
            fails += 1;
            if !exited && fails < 3 {
                continue;
            }
            fails = 0;
            let st = app.state::<AppState>();
            log_line(&st.log, &format!("el backend del puerto {port} no responde"));
            if !be.allow_restart() {
                be.fail("VISTAN se ha detenido varias veces en pocos minutos. No lo reinicio automáticamente: revisa el registro.", &st.log);
                let a = app.clone();
                let _ = app.run_on_main_thread(move || {
                    if let Some(w) = a.get_webview_window("main") {
                        let _ = w.navigate(splash_url("?state=failed"));
                    }
                });
                continue;
            }
            be.set(|x| {
                x.phase = "starting".into();
                x.message = "Reconectando con VISTAN…".into();
            });
            let a = app.clone();
            let _ = app.run_on_main_thread(move || {
                if let Some(w) = a.get_webview_window("main") {
                    let _ = w.navigate(splash_url("?state=reconnecting"));
                }
            });
            if !exited && s.owned {
                be.stop(&st.log);
            }
            start_backend(&app);
        }
    });
}

pub fn guard_window<'a>(b: WebviewWindowBuilder<'a, tauri::Wry, AppHandle>, app: &AppHandle) -> WebviewWindowBuilder<'a, tauri::Wry, AppHandle> {
    let nav_app = app.clone();
    let new_app = app.clone();
    b.on_navigation(move |url| allowed_navigation(&nav_app, url)).on_new_window(move |url, _| {
        // target=_blank y window.open: fuera de VISTAN → navegador predeterminado; nunca una ventana web suelta
        if url.scheme() == "http" || url.scheme() == "https" || url.scheme() == "mailto" {
            let _ = new_app.opener().open_url(url.as_str(), None::<&str>);
        }
        NewWindowResponse::Deny
    })
}

fn create_main(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    let cfg = app.config().app.windows.iter().find(|w| w.label == "main").cloned().expect("ventana principal en tauri.conf.json");
    guard_window(WebviewWindowBuilder::from_config(app, &cfg)?, app).build()
}

pub fn register_shortcut(app: &AppHandle) {
    let gs = app.global_shortcut();
    let _ = gs.unregister_all();
    let st = app.state::<AppState>();
    let s = st.settings.lock().unwrap().clone();
    if s.shortcut_enabled {
        if let Err(e) = gs.register(s.global_shortcut.as_str()) {
            log_line(&st.log, &format!("no se pudo registrar el atajo global {}: {e}", s.global_shortcut));
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| show_main(app)))
        .plugin(
            tauri_plugin_window_state::Builder::default()
                .with_state_flags(tauri_plugin_window_state::StateFlags::all() & !tauri_plugin_window_state::StateFlags::VISIBLE)
                .with_denylist(&["prefs"])
                .build(),
        )
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_autostart::init(tauri_plugin_autostart::MacosLauncher::LaunchAgent, None))
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        toggle_main(app);
                    }
                })
                .build(),
        )
        .manage(Backend::default())
        .invoke_handler(tauri::generate_handler![
            commands::backend_status,
            commands::restart_backend,
            commands::choose_repo,
            commands::app_info,
            commands::get_desktop_settings,
            commands::set_desktop_settings,
            commands::notify,
            commands::notification_permission,
            commands::request_notification_permission,
            commands::open_external,
            commands::copy_text,
            commands::open_logs,
            commands::open_preferences,
            commands::update_vistan,
            commands::open_in_browser,
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            let config_dir = app.path().app_config_dir()?;
            let log = app.path().app_log_dir()?.join("backend.log");
            let settings = DesktopSettings::load(&config_dir);
            app.manage(AppState {
                settings: Mutex::new(settings),
                config_dir,
                log: log.clone(),
                path_env: Mutex::new(None),
                granted_ports: Mutex::new(HashSet::new()),
            });
            log_line(&log, &format!("VISTAN Desktop {} iniciado", app.package_info().version));
            create_main(&handle)?;
            app.set_menu(menu::build(&handle)?)?;
            app.on_menu_event(|app, ev| menu::handle(app, ev.id().as_ref()));
            register_shortcut(&handle);
            #[cfg(unix)]
            {
                // SIGTERM/SIGINT (cierre de sesión, kill, Ctrl+C) = salida limpia: se detiene el backend propio
                let h = handle.clone();
                if let Ok(mut signals) = signal_hook::iterator::Signals::new([signal_hook::consts::SIGTERM, signal_hook::consts::SIGINT, signal_hook::consts::SIGHUP]) {
                    std::thread::spawn(move || {
                        if signals.forever().next().is_some() {
                            h.exit(0);
                        }
                    });
                }
            }
            start_backend(&handle);
            monitor(handle);
            Ok(())
        })
        .on_window_event(|window, event| {
            // Cerrar la ventana principal no cierra VISTAN: queda en el Dock (como Mail o Música). ⌘Q sale.
            if let WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main" && cfg!(target_os = "macos") {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error al iniciar VISTAN Desktop");

    app.run(|app, event| match event {
        RunEvent::ExitRequested { .. } | RunEvent::Exit => {
            let be = app.state::<Backend>();
            if !be.quitting.swap(true, Ordering::SeqCst) {
                if let Some(st) = app.try_state::<AppState>() {
                    be.stop(&st.log); // solo el backend que arrancó esta app; el de VISTAN Web sigue funcionando
                    log_line(&st.log, "VISTAN Desktop cerrado");
                }
            }
        }
        #[cfg(target_os = "macos")]
        RunEvent::Reopen { .. } => show_main(app),
        _ => {}
    });
}
