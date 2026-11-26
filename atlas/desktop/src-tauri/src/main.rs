// Sin ventana de consola en Windows en modo release (en macOS no aplica).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    vistan_desktop_lib::run()
}
