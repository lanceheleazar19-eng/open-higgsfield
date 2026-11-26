//! Órdenes nativas que la interfaz puede pedir. Lista cerrada: no hay ejecución de comandos arbitrarios,
//! ni acceso a archivos fuera de lo que tú eliges, ni ninguna clave API (esas siguen en el Llavero vía el backend).

use crate::backend::{self, log_line, Backend, Status, CURRENT_PORT};
use crate::settings::{self, DesktopSettings};
use crate::{guard_window, register_shortcut, show_main, start_backend, AppState};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::process::Command;
use std::sync::atomic::Ordering;
use tauri::{AppHandle, Manager, State, Url, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_autostart::ManagerExt as _;
use tauri_plugin_clipboard_manager::ClipboardExt;
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};
use tauri_plugin_notification::{NotificationExt, PermissionState};
use tauri_plugin_opener::OpenerExt;

type R<T> = Result<T, String>;

#[tauri::command]
pub fn backend_status(be: State<Backend>) -> Status {
    be.snapshot()
}

/// Reinicio controlado. Solo reinicia el backend que arrancó esta app o el servicio de macOS de VISTAN;
/// un VISTAN abierto a mano en una Terminal no se toca.
#[tauri::command]
pub async fn restart_backend(app: AppHandle) -> R<String> {
    let be = app.state::<Backend>();
    let st = app.state::<AppState>();
    let s = be.snapshot();
    log_line(&st.log, "reinicio pedido por ti");
    if s.phase == "ready" && !s.owned {
        #[cfg(target_os = "macos")]
        if s.launcher == "launchd" {
            let uid = unsafe { libc::getuid() };
            let _ = Command::new("/bin/launchctl").args(["kickstart", "-k", &format!("gui/{uid}/com.atlas.personal")]).status();
            be.set(|x| {
                x.phase = "starting".into();
                x.message = "Reiniciando el servicio de VISTAN…".into();
            });
            std::thread::sleep(std::time::Duration::from_secs(2));
            start_backend(&app);
            return Ok("Reiniciando el servicio en segundo plano de VISTAN".into());
        }
        return Err("Este VISTAN lo arrancaste fuera de la app (por ejemplo, en una Terminal). Reinícialo desde allí.".into());
    }
    be.stop(&st.log);
    start_backend(&app);
    Ok("Reiniciando VISTAN".into())
}

/// Selector nativo de carpeta para indicar dónde está el proyecto VISTAN (solo se lee su estructura).
#[tauri::command]
pub async fn choose_repo(app: AppHandle) -> R<String> {
    let Some(picked) = app.dialog().file().set_title("Elige la carpeta «atlas» de VISTAN").blocking_pick_folder() else {
        return Err("Cancelado".into());
    };
    let path = picked.into_path().map_err(|e| e.to_string())?;
    let path = if settings::is_repo(&path) { path } else { path.join("atlas") };
    if !settings::is_repo(&path) {
        return Err("Esa carpeta no es un proyecto VISTAN (falta scripts/start.sh, backend/ o frontend/)".into());
    }
    let st = app.state::<AppState>();
    {
        let mut s = st.settings.lock().unwrap();
        s.repo_path = Some(path.display().to_string());
        s.save(&st.config_dir).map_err(|e| e.to_string())?;
    }
    start_backend(&app);
    Ok(path.display().to_string())
}

#[tauri::command]
pub fn app_info(app: AppHandle) -> Value {
    let st = app.state::<AppState>();
    let repo = st.repo();
    let repo_version = repo.as_ref().and_then(|r| desktop_version_in_repo(r));
    json!({
        "version": app.package_info().version.to_string(),
        "repo": repo.as_ref().map(|r| r.display().to_string()),
        "data_dir": repo.as_ref().map(|r| backend::data_dir(r).display().to_string()),
        "log": st.log.display().to_string(),
        "config_dir": st.config_dir.display().to_string(),
        "platform": std::env::consts::OS,
        "arch": std::env::consts::ARCH,
        "repo_desktop_version": repo_version,
        "rebuild_needed": repo_version.map(|v| v != app.package_info().version.to_string()).unwrap_or(false),
    })
}

fn desktop_version_in_repo(repo: &std::path::Path) -> Option<String> {
    let raw = std::fs::read_to_string(repo.join("desktop/src-tauri/tauri.conf.json")).ok()?;
    serde_json::from_str::<Value>(&raw).ok()?.get("version")?.as_str().map(String::from)
}

#[derive(Serialize)]
pub struct SettingsOut {
    #[serde(flatten)]
    settings: DesktopSettings,
    autostart: bool,
}

#[tauri::command]
pub fn get_desktop_settings(app: AppHandle) -> SettingsOut {
    let st = app.state::<AppState>();
    let settings = st.settings.lock().unwrap().clone();
    SettingsOut { settings, autostart: app.autolaunch().is_enabled().unwrap_or(false) }
}

#[derive(Deserialize)]
pub struct SettingsIn {
    global_shortcut: Option<String>,
    shortcut_enabled: Option<bool>,
    autostart: Option<bool>,
    port: Option<u16>,
}

#[tauri::command]
pub fn set_desktop_settings(app: AppHandle, changes: SettingsIn) -> R<SettingsOut> {
    let st = app.state::<AppState>();
    {
        let mut s = st.settings.lock().unwrap();
        if let Some(sc) = changes.global_shortcut {
            s.global_shortcut = settings::validate_shortcut(&sc)?;
        }
        if let Some(e) = changes.shortcut_enabled {
            s.shortcut_enabled = e;
        }
        if let Some(p) = changes.port {
            if !(1024..=65000).contains(&p) {
                return Err("Puerto no válido (1024-65000)".into());
            }
            s.port = p;
        }
        s.save(&st.config_dir).map_err(|e| e.to_string())?;
    }
    if let Some(a) = changes.autostart {
        let al = app.autolaunch();
        let r = if a { al.enable() } else { al.disable() };
        r.map_err(|e| format!("No se pudo cambiar el inicio automático: {e}"))?;
        log_line(&st.log, &format!("inicio automático {}", if a { "activado" } else { "desactivado" }));
    }
    register_shortcut(&app);
    Ok(get_desktop_settings(app.clone()))
}

#[tauri::command]
pub fn notify(app: AppHandle, title: String, body: Option<String>) -> R<()> {
    let title: String = title.chars().take(120).collect();
    let body: String = body.unwrap_or_default().chars().take(400).collect();
    app.notification().builder().title(title).body(body).show().map_err(|e| e.to_string())
}

fn perm(p: PermissionState) -> &'static str {
    match p {
        PermissionState::Granted => "granted",
        PermissionState::Denied => "denied",
        _ => "default",
    }
}

#[tauri::command]
pub fn notification_permission(app: AppHandle) -> String {
    app.notification().permission_state().map(perm).unwrap_or("default").into()
}

#[tauri::command]
pub fn request_notification_permission(app: AppHandle) -> String {
    app.notification().request_permission().map(perm).unwrap_or("default").into()
}

/// Abre un enlace en tu navegador predeterminado. Solo http(s) y mailto.
#[tauri::command]
pub fn open_external(app: AppHandle, url: String) -> R<()> {
    let u = Url::parse(&url).map_err(|_| "Enlace no válido".to_string())?;
    if !matches!(u.scheme(), "http" | "https" | "mailto") {
        return Err("Solo se abren enlaces web (http/https) o de correo".into());
    }
    app.opener().open_url(u.as_str(), None::<&str>).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn copy_text(app: AppHandle, text: String) -> R<()> {
    if text.len() > 1_000_000 {
        return Err("Texto demasiado largo para el portapapeles".into());
    }
    app.clipboard().write_text(text).map_err(|e| e.to_string())
}

/// Muestra el registro de VISTAN Desktop en el Finder (solo esa carpeta).
#[tauri::command]
pub fn open_logs(app: AppHandle) -> R<()> {
    let st = app.state::<AppState>();
    if !st.log.exists() {
        log_line(&st.log, "registro creado");
    }
    app.opener().reveal_item_in_dir(&st.log).map_err(|e| e.to_string())
}

/// Ventana secundaria nativa: Permisos y privacidad.
#[tauri::command]
pub async fn open_preferences(app: AppHandle) -> R<()> {
    open_prefs_window(&app)
}

pub fn open_prefs_window(app: &AppHandle) -> R<()> {
    if let Some(w) = app.get_webview_window("prefs") {
        let _ = w.show();
        let _ = w.set_focus();
        return Ok(());
    }
    let port = CURRENT_PORT.load(Ordering::SeqCst);
    if port == 0 {
        show_main(app);
        return Err("VISTAN aún está arrancando".into());
    }
    let url = Url::parse(&format!("http://127.0.0.1:{port}/desktop")).unwrap();
    let b = WebviewWindowBuilder::new(app, "prefs", WebviewUrl::External(url))
        .title("VISTAN · Permisos y privacidad")
        .inner_size(860.0, 780.0)
        .min_inner_size(640.0, 560.0)
        .theme(Some(tauri::Theme::Dark))
        .background_color(tauri::window::Color(8, 8, 8, 255))
        .disable_drag_drop_handler();
    #[cfg(target_os = "macos")]
    let b = b.title_bar_style(tauri::TitleBarStyle::Overlay).hidden_title(true);
    guard_window(b, app).build().map_err(|e| e.to_string())?;
    Ok(())
}

/// Actualiza VISTAN con `git pull --ff-only` (nunca fusiona ni borra cambios tuyos) tras tu confirmación,
/// y reinicia el backend: start.sh reinstala dependencias y recompila la interfaz solo si hace falta.
#[tauri::command]
pub async fn update_vistan(app: AppHandle) -> R<Value> {
    let st = app.state::<AppState>();
    let repo = st.repo().ok_or("No encuentro la carpeta del proyecto")?;
    let ok = app
        .dialog()
        .message(format!("Se descargarán los últimos cambios de VISTAN en\n{}\ny se reiniciará el backend. Tus datos no se tocan.", repo.display()))
        .title("Actualizar VISTAN")
        .kind(MessageDialogKind::Info)
        .buttons(MessageDialogButtons::OkCancelCustom("Actualizar".into(), "Cancelar".into()))
        .blocking_show();
    if !ok {
        return Err("Cancelado".into());
    }
    // la raíz del repositorio git es la carpeta padre de «atlas»
    let root = repo.parent().unwrap_or(&repo).to_path_buf();
    let out = Command::new("git")
        .args(["-C", &root.display().to_string(), "pull", "--ff-only"])
        .env("PATH", st.path_env())
        .output()
        .map_err(|e| format!("No se pudo ejecutar git: {e}"))?;
    let text = format!("{}{}", String::from_utf8_lossy(&out.stdout), String::from_utf8_lossy(&out.stderr));
    log_line(&st.log, &format!("git pull: {}", text.trim()));
    if !out.status.success() {
        return Err(format!("git pull no se completó (no se ha cambiado nada):\n{}", text.trim()));
    }
    let restarted = restart_backend(app.clone()).await;
    let info = app_info(app.clone());
    Ok(json!({
        "output": text.trim(),
        "restart": restarted.unwrap_or_else(|e| e),
        "rebuild_needed": info["rebuild_needed"],
        "repo_desktop_version": info["repo_desktop_version"],
    }))
}

/// VISTAN Web: la misma instancia y los mismos datos, en tu navegador (administración / desarrollo).
#[tauri::command]
pub fn open_in_browser(app: AppHandle) -> R<()> {
    let port = CURRENT_PORT.load(Ordering::SeqCst);
    if port == 0 {
        return Err("VISTAN aún está arrancando".into());
    }
    app.opener().open_url(format!("http://127.0.0.1:{port}/"), None::<&str>).map_err(|e| e.to_string())
}
