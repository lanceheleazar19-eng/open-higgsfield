// Las órdenes propias se declaran aquí para que cada ventana solo pueda usar las que su capacidad permita.
const COMMANDS: &[&str] = &[
    "backend_status", "restart_backend", "choose_repo", "app_info", "get_desktop_settings", "set_desktop_settings",
    "notify", "notification_permission", "request_notification_permission", "open_external", "copy_text",
    "open_logs", "open_preferences", "update_vistan", "open_in_browser",
];

fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(tauri_build::AppManifest::new().commands(COMMANDS)))
        .expect("error al preparar la compilación de VISTAN Desktop");
}
