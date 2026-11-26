//! Barra de menús nativa de macOS con los atajos de teclado de VISTAN.

use crate::commands;
use crate::show_main;
use tauri::menu::{AboutMetadataBuilder, Menu, MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder};
use tauri::{AppHandle, Manager, Wry};

/// Módulos con atajo ⌘1…⌘9 (rutas reales de la interfaz).
pub const MODULES: &[(&str, &str, &str)] = &[
    ("Centro de control", "/", "CmdOrCtrl+1"),
    ("Cerebro IA", "/ai", "CmdOrCtrl+2"),
    ("Memoria", "/memory", "CmdOrCtrl+3"),
    ("Tareas", "/tasks", "CmdOrCtrl+4"),
    ("Trading Desk", "/trading", "CmdOrCtrl+5"),
    ("Agentes", "/agents", "CmdOrCtrl+6"),
    ("META-BRAIN", "/meta", "CmdOrCtrl+7"),
    ("Academy", "/academy", "CmdOrCtrl+8"),
    ("Legal", "/legal", "CmdOrCtrl+9"),
];

pub fn build(app: &AppHandle) -> tauri::Result<Menu<Wry>> {
    let about = AboutMetadataBuilder::new()
        .name(Some("VISTAN"))
        .version(Some(app.package_info().version.to_string()))
        .comments(Some("Personal Intelligence System"))
        .build();
    let app_menu = SubmenuBuilder::new(app, "VISTAN")
        .item(&PredefinedMenuItem::about(app, Some("Acerca de VISTAN"), Some(about))?)
        .separator()
        .item(&MenuItemBuilder::with_id("nav:/settings", "Configuración…").accelerator("CmdOrCtrl+,").build(app)?)
        .item(&MenuItemBuilder::with_id("prefs", "Permisos y privacidad…").accelerator("CmdOrCtrl+Shift+,").build(app)?)
        .separator()
        .item(&PredefinedMenuItem::services(app, None)?)
        .separator()
        .item(&PredefinedMenuItem::hide(app, Some("Ocultar VISTAN"))?)
        .item(&PredefinedMenuItem::hide_others(app, Some("Ocultar otros"))?)
        .item(&PredefinedMenuItem::show_all(app, Some("Mostrar todo"))?)
        .separator()
        .item(&PredefinedMenuItem::quit(app, Some("Salir de VISTAN"))?)
        .build()?;
    let edit = SubmenuBuilder::new(app, "Edición")
        .item(&PredefinedMenuItem::undo(app, Some("Deshacer"))?)
        .item(&PredefinedMenuItem::redo(app, Some("Rehacer"))?)
        .separator()
        .item(&PredefinedMenuItem::cut(app, Some("Cortar"))?)
        .item(&PredefinedMenuItem::copy(app, Some("Copiar"))?)
        .item(&PredefinedMenuItem::paste(app, Some("Pegar"))?)
        .item(&PredefinedMenuItem::select_all(app, Some("Seleccionar todo"))?)
        .build()?;
    let view = SubmenuBuilder::new(app, "Visualización")
        .item(&MenuItemBuilder::with_id("reload", "Recargar").accelerator("CmdOrCtrl+R").build(app)?)
        .item(&MenuItemBuilder::with_id("back", "Atrás").accelerator("CmdOrCtrl+[").build(app)?)
        .item(&MenuItemBuilder::with_id("forward", "Adelante").accelerator("CmdOrCtrl+]").build(app)?)
        .separator()
        .item(&PredefinedMenuItem::fullscreen(app, Some("Pantalla completa"))?)
        .build()?;
    let mut go = SubmenuBuilder::new(app, "Ir");
    for (label, path, acc) in MODULES {
        go = go.item(&MenuItemBuilder::with_id(format!("nav:{path}"), *label).accelerator(*acc).build(app)?);
    }
    let go = go.build()?;
    let service = SubmenuBuilder::new(app, "Sistema")
        .item(&MenuItemBuilder::with_id("restart_backend", "Reiniciar backend").build(app)?)
        .item(&MenuItemBuilder::with_id("update", "Actualizar VISTAN…").build(app)?)
        .separator()
        .item(&MenuItemBuilder::with_id("open_web", "Abrir VISTAN Web en el navegador").build(app)?)
        .item(&MenuItemBuilder::with_id("show_logs", "Mostrar registro").build(app)?)
        .build()?;
    let window = SubmenuBuilder::new(app, "Ventana")
        .item(&PredefinedMenuItem::minimize(app, Some("Minimizar"))?)
        .item(&PredefinedMenuItem::maximize(app, Some("Zoom"))?)
        .separator()
        .item(&MenuItemBuilder::with_id("show", "Mostrar VISTAN").build(app)?)
        .item(&PredefinedMenuItem::close_window(app, Some("Cerrar ventana"))?)
        .build()?;
    MenuBuilder::new(app).items(&[&app_menu, &edit, &view, &go, &service, &window]).build()
}

fn eval_main(app: &AppHandle, js: &str) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.eval(js);
    }
}

pub fn handle(app: &AppHandle, id: &str) {
    if let Some(path) = id.strip_prefix("nav:") {
        show_main(app);
        // la interfaz registra window.__vistan.navigate (React Router); si aún no está, navegación normal
        let p = serde_json::to_string(path).unwrap_or_else(|_| "\"/\"".into());
        eval_main(app, &format!("(window.__vistan && window.__vistan.navigate) ? window.__vistan.navigate({p}) : (location.protocol.startsWith('http') && location.assign({p}))"));
        return;
    }
    match id {
        "reload" => eval_main(app, "location.reload()"),
        "back" => eval_main(app, "history.back()"),
        "forward" => eval_main(app, "history.forward()"),
        "show" => show_main(app),
        "prefs" => {
            let _ = commands::open_prefs_window(app);
        }
        "open_web" => {
            let _ = commands::open_in_browser(app.clone());
        }
        "show_logs" => {
            let _ = commands::open_logs(app.clone());
        }
        "restart_backend" => {
            let a = app.clone();
            tauri::async_runtime::spawn(async move {
                let _ = commands::restart_backend(a).await;
            });
        }
        "update" => {
            let a = app.clone();
            tauri::async_runtime::spawn(async move {
                let r = commands::update_vistan(a.clone()).await;
                let msg = match r {
                    Ok(v) if v["rebuild_needed"].as_bool() == Some(true) => format!(
                        "VISTAN actualizado.\n\nLa app de escritorio también tiene cambios: recompílala con\n./atlas/desktop/scripts/build-macos.sh\n\n{}",
                        v["output"].as_str().unwrap_or("")
                    ),
                    Ok(v) => format!("VISTAN actualizado.\n\n{}", v["output"].as_str().unwrap_or("")),
                    Err(e) if e == "Cancelado" => return,
                    Err(e) => e,
                };
                use tauri_plugin_dialog::DialogExt;
                a.dialog().message(msg).title("Actualizar VISTAN").show(|_| {});
            });
        }
        _ => {}
    }
}
