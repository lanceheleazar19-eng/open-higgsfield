//! Preferencias propias de VISTAN Desktop (no de VISTAN): carpeta del proyecto, puerto preferido y atajo global.
//! Se guardan en ~/Library/Application Support/com.vistan.desktop/desktop.json. Nunca contienen claves API.

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::str::FromStr;

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct DesktopSettings {
    /// Carpeta `atlas` del proyecto VISTAN (la que contiene scripts/start.sh y backend/).
    pub repo_path: Option<String>,
    /// Puerto preferido si VISTAN Desktop tiene que arrancar el backend él mismo.
    pub port: u16,
    /// Atajo global para mostrar/ocultar VISTAN desde cualquier aplicación.
    pub global_shortcut: String,
    pub shortcut_enabled: bool,
}

impl Default for DesktopSettings {
    fn default() -> Self {
        Self { repo_path: None, port: 8000, global_shortcut: "Alt+Space".into(), shortcut_enabled: true }
    }
}

impl DesktopSettings {
    pub fn load(dir: &Path) -> Self {
        std::fs::read_to_string(dir.join("desktop.json"))
            .ok()
            .and_then(|s| serde_json::from_str::<DesktopSettings>(&s).ok())
            .map(|mut s| {
                if s.port < 1024 {
                    s.port = 8000;
                }
                s
            })
            .unwrap_or_default()
    }

    pub fn save(&self, dir: &Path) -> std::io::Result<()> {
        std::fs::create_dir_all(dir)?;
        let tmp = dir.join("desktop.json.tmp");
        std::fs::write(&tmp, serde_json::to_vec_pretty(self).unwrap_or_default())?;
        std::fs::rename(tmp, dir.join("desktop.json"))
    }
}

/// Un atajo válido debe llevar al menos un modificador (para no secuestrar teclas normales).
pub fn validate_shortcut(s: &str) -> Result<String, String> {
    let s = s.trim();
    if s.is_empty() || s.len() > 40 {
        return Err("Atajo vacío o demasiado largo".into());
    }
    let lower = s.to_lowercase();
    let has_mod = ["alt", "option", "cmd", "command", "super", "ctrl", "control", "shift", "cmdorctrl", "commandorcontrol"]
        .iter()
        .any(|m| lower.split('+').any(|p| p.trim() == *m));
    if !has_mod {
        return Err("El atajo debe incluir un modificador (⌥, ⌘, ⌃ o ⇧)".into());
    }
    tauri_plugin_global_shortcut::Shortcut::from_str(s).map_err(|e| format!("Atajo no válido: {e}"))?;
    Ok(s.to_string())
}

/// ¿Es esta carpeta un proyecto VISTAN? (comprobación por estructura, sin ejecutar nada)
pub fn is_repo(p: &Path) -> bool {
    p.join("scripts/start.sh").is_file() && p.join("backend/pyproject.toml").is_file() && p.join("frontend/package.json").is_file()
}

/// Busca la carpeta del proyecto: la configurada, la de compilación y la ubicación habitual.
pub fn find_repo(s: &DesktopSettings) -> Option<PathBuf> {
    let mut cands: Vec<PathBuf> = Vec::new();
    if let Some(p) = &s.repo_path {
        cands.push(PathBuf::from(p));
    }
    if let Ok(p) = std::env::var("VISTAN_REPO") {
        cands.push(PathBuf::from(p));
    }
    // La app se compila dentro del propio proyecto: atlas/desktop/src-tauri → atlas
    cands.push(Path::new(env!("CARGO_MANIFEST_DIR")).join("../.."));
    if let Some(home) = std::env::var_os("HOME") {
        let h = PathBuf::from(home);
        cands.push(h.join("open-higgsfield/atlas"));
        cands.push(h.join("Developer/open-higgsfield/atlas"));
    }
    cands.into_iter().filter_map(|p| p.canonicalize().ok()).find(|p| is_repo(p))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shortcut_needs_modifier() {
        assert!(validate_shortcut("Alt+Space").is_ok());
        assert!(validate_shortcut("CmdOrCtrl+Shift+V").is_ok());
        assert!(validate_shortcut("A").is_err());
        assert!(validate_shortcut("").is_err());
        assert!(validate_shortcut("Alt+NoExiste").is_err());
    }

    #[test]
    fn settings_roundtrip_and_defaults() {
        let d = std::env::temp_dir().join(format!("vistan-settings-{}", std::process::id()));
        let mut s = DesktopSettings::load(&d);
        assert_eq!(s.port, 8000);
        s.port = 8001;
        s.save(&d).unwrap();
        assert_eq!(DesktopSettings::load(&d).port, 8001);
        std::fs::write(d.join("desktop.json"), "{roto").unwrap();
        assert_eq!(DesktopSettings::load(&d).port, 8000);
        let _ = std::fs::remove_dir_all(d);
    }
}
