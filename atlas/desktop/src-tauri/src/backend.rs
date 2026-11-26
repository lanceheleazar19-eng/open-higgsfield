//! Gestión del backend local de VISTAN (el mismo FastAPI de siempre, la misma base de datos).
//!
//! Orden de arranque, sin duplicar instancias:
//! 1. Si ya hay un VISTAN funcionando (data/runtime.json o sondeo de 8000-8019 con identificación), se reutiliza.
//! 2. En macOS, si está instalado el servicio en segundo plano (autostart.sh), se le pide a launchd que lo arranque.
//! 3. Si no, VISTAN Desktop lo arranca con `scripts/start.sh` en un puerto libre de 127.0.0.1, en su propio grupo
//!    de procesos. Al salir solo se detiene ESE grupo: nunca se matan procesos ajenos.

use serde::Serialize;
use serde_json::Value;
use std::fs::OpenOptions;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU16, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub static CURRENT_PORT: AtomicU16 = AtomicU16::new(0);
#[cfg(target_os = "macos")]
const LAUNCHD_LABEL: &str = "com.atlas.personal";

#[derive(Clone, Debug, Serialize, Default)]
pub struct Status {
    /// starting | ready | failed | stopped
    pub phase: String,
    pub message: String,
    pub port: Option<u16>,
    pub url: Option<String>,
    /// true = lo arrancó esta app y lo detendrá al salir
    pub owned: bool,
    /// desktop | launchd | web | desconocido
    pub launcher: String,
    pub log_tail: Vec<String>,
    pub repo: Option<String>,
    pub needs_repo: bool,
}

enum SpawnErr {
    PortBusy(u16),
    Other(String),
}

#[derive(Default)]
pub struct Backend {
    pub status: Mutex<Status>,
    child: Mutex<Option<Child>>,
    restarts: Mutex<Vec<Instant>>,
    pub busy: AtomicBool,
    pub quitting: AtomicBool,
    last_exit: Mutex<Option<String>>,
    /// Backend que arrancó una ejecución anterior de esta app (p. ej. tras un cierre forzado): se adopta para cerrarlo al salir.
    adopted: Mutex<Option<i32>>,
}

pub fn now_s() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

// ───────── HTTP mínimo contra 127.0.0.1 (sin dependencias de red externas) ─────────
pub fn http_get(port: u16, path: &str, timeout: Duration) -> Option<(u16, String)> {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let mut s = TcpStream::connect_timeout(&addr, timeout.min(Duration::from_millis(1500))).ok()?;
    s.set_read_timeout(Some(timeout)).ok()?;
    s.set_write_timeout(Some(timeout)).ok()?;
    write!(s, "GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUser-Agent: VISTAN-Desktop\r\nConnection: close\r\n\r\n").ok()?;
    let mut buf = Vec::new();
    s.read_to_end(&mut buf).ok()?;
    let text = String::from_utf8_lossy(&buf).to_string();
    let (head, body) = text.split_once("\r\n\r\n")?;
    let code = head.split_whitespace().nth(1)?.parse().ok()?;
    let chunked = head.to_ascii_lowercase().contains("transfer-encoding: chunked");
    Some((code, if chunked { dechunk(body) } else { body.to_string() }))
}

fn dechunk(body: &str) -> String {
    let mut out = String::new();
    let mut rest = body;
    while let Some((size, after)) = rest.split_once("\r\n") {
        let n = usize::from_str_radix(size.trim(), 16).unwrap_or(0);
        if n == 0 || after.len() < n {
            break;
        }
        out.push_str(&after[..n]);
        rest = after[n..].trim_start_matches("\r\n");
    }
    out
}

/// ¿Responde VISTAN en este puerto? Comprueba la identificación para no confundir otro programa con VISTAN.
pub fn health(port: u16) -> Option<Value> {
    let (code, body) = http_get(port, "/api/system/health", Duration::from_secs(4))?;
    if code != 200 {
        return None;
    }
    let v: Value = serde_json::from_str(&body).ok()?;
    let id = v.get("app").and_then(|a| a.as_str()) == Some("vistan");
    let legacy = v.get("status").is_some() && v.get("version").is_some() && v.get("database").is_some() && v.get("ai").is_some();
    (id || legacy).then_some(v)
}

pub fn port_free(port: u16) -> bool {
    TcpListener::bind(("127.0.0.1", port)).is_ok()
}

// ───────── rutas del proyecto ─────────
pub fn data_dir(repo: &Path) -> PathBuf {
    let backend = repo.join("backend");
    let configured = std::fs::read_to_string(backend.join(".env")).ok().and_then(|env| {
        env.lines().find_map(|l| {
            let l = l.trim();
            l.strip_prefix("ATLAS_DATA_DIR=").map(|v| v.trim().trim_matches('"').trim_matches('\'').to_string())
        })
    });
    let p = match configured.filter(|v| !v.is_empty()) {
        Some(v) if Path::new(&v).is_absolute() => PathBuf::from(v),
        Some(v) => backend.join(v),
        None => repo.join("data"),
    };
    p.canonicalize().unwrap_or(p)
}

pub fn runtime_pid(repo: &Path) -> Option<i32> {
    let raw = std::fs::read_to_string(data_dir(repo).join("runtime.json")).ok()?;
    serde_json::from_str::<Value>(&raw).ok()?.get("pid")?.as_i64().map(|p| p as i32)
}

/// ¿Es un proceso que lanzó VISTAN Desktop? (líder de su propio grupo, como los arranca esta app)
#[cfg(unix)]
pub fn own_group(pid: i32) -> bool {
    pid > 1 && unsafe { libc::getpgid(pid) } == pid
}
#[cfg(not(unix))]
pub fn own_group(_pid: i32) -> bool {
    false
}

pub fn runtime_port(repo: &Path) -> Option<(u16, String)> {
    let raw = std::fs::read_to_string(data_dir(repo).join("runtime.json")).ok()?;
    let v: Value = serde_json::from_str(&raw).ok()?;
    let port = v.get("port")?.as_u64()? as u16;
    let launcher = v.get("launcher").and_then(|l| l.as_str()).unwrap_or("web").to_string();
    Some((port, launcher))
}

/// PATH de tu sesión: las apps abiertas desde el Dock no heredan el de la Terminal (Homebrew, uv, Node…).
pub fn user_path() -> String {
    let mut parts: Vec<String> = Vec::new();
    if cfg!(unix) {
        let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".into());
        if let Ok(mut child) = Command::new(&shell)
            .args(["-ilc", "printf '\\n__VISTAN_PATH__%s\\n' \"$PATH\""])
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
        {
            let t0 = Instant::now();
            loop {
                match child.try_wait() {
                    Ok(Some(_)) => break,
                    Ok(None) if t0.elapsed() < Duration::from_secs(5) => std::thread::sleep(Duration::from_millis(50)),
                    _ => {
                        let _ = child.kill();
                        break;
                    }
                }
            }
            let mut out = String::new();
            if let Some(mut so) = child.stdout.take() {
                let _ = so.read_to_string(&mut out);
            }
            let _ = child.wait();
            if let Some(line) = out.lines().find_map(|l| l.strip_prefix("__VISTAN_PATH__")) {
                parts.extend(line.split(':').filter(|p| !p.is_empty()).map(String::from));
            }
        }
    }
    if let Ok(p) = std::env::var("PATH") {
        parts.extend(p.split(':').map(String::from));
    }
    let home = std::env::var("HOME").unwrap_or_default();
    for extra in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"] {
        parts.push(extra.into());
    }
    for extra in [".local/bin", ".cargo/bin", ".volta/bin"] {
        parts.push(format!("{home}/{extra}"));
    }
    let mut seen = std::collections::HashSet::new();
    parts.retain(|p| seen.insert(p.clone()));
    parts.join(":")
}

pub fn log_line(log: &Path, msg: &str) {
    if let Some(d) = log.parent() {
        let _ = std::fs::create_dir_all(d);
    }
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(log) {
        let _ = writeln!(f, "[{}] [desktop] {msg}", now_s());
    }
}

pub fn tail(log: &Path, n: usize) -> Vec<String> {
    let s = std::fs::read_to_string(log).unwrap_or_default();
    let lines: Vec<&str> = s.lines().filter(|l| !l.trim().is_empty()).collect();
    lines[lines.len().saturating_sub(n)..].iter().map(|l| l.chars().take(400).collect()).collect()
}

impl Backend {
    pub fn snapshot(&self) -> Status {
        self.status.lock().map(|s| s.clone()).unwrap_or_default()
    }

    pub fn set(&self, f: impl FnOnce(&mut Status)) {
        if let Ok(mut s) = self.status.lock() {
            f(&mut s);
        }
    }

    /// ¿El backend que arrancamos nosotros ha terminado?
    pub fn child_exited(&self) -> bool {
        let mut g = match self.child.lock() {
            Ok(g) => g,
            Err(_) => return false,
        };
        match g.as_mut().map(|c| c.try_wait()) {
            Some(Ok(Some(status))) => {
                *g = None;
                *self.last_exit.lock().unwrap() = Some(format!("{status}"));
                true
            }
            Some(Err(e)) => {
                *g = None;
                *self.last_exit.lock().unwrap() = Some(format!("error al consultar el proceso: {e}"));
                true
            }
            _ => false,
        }
    }

    /// Registra un reinicio y dice si aún se permite (máx. 5 en 10 minutos).
    pub fn allow_restart(&self) -> bool {
        let mut r = self.restarts.lock().unwrap();
        r.retain(|t| t.elapsed() < Duration::from_secs(600));
        if r.len() >= 5 {
            return false;
        }
        r.push(Instant::now());
        true
    }

    /// Busca una instancia de VISTAN ya en marcha (de VISTAN Web, del servicio de macOS o de esta app).
    pub fn discover(&self, repo: Option<&Path>) -> Option<(u16, String)> {
        if let Some((port, launcher)) = repo.and_then(runtime_port) {
            if health(port).is_some() {
                return Some((port, launcher));
            }
        }
        (8000..8020).find(|p| !port_free(*p) && health(*p).is_some()).map(|p| (p, "desconocido".to_string()))
    }

    /// Asegura que hay un backend disponible. Bloqueante: se llama desde un hilo.
    pub fn ensure(&self, repo: Option<PathBuf>, pref_port: u16, path_env: &str, log: &Path) -> Result<u16, String> {
        let repo_s = repo.as_ref().map(|r| r.display().to_string());
        self.set(|s| {
            s.phase = "starting".into();
            s.message = "Buscando VISTAN…".into();
            s.repo = repo_s.clone();
            s.needs_repo = false;
        });
        if let Some((port, launcher)) = self.discover(repo.as_deref()) {
            let adopted = (launcher == "desktop").then(|| repo.as_deref().and_then(runtime_pid)).flatten().filter(|pid| own_group(*pid));
            if let Some(pid) = adopted {
                log_line(log, &format!("adopto el backend que arrancó VISTAN Desktop anteriormente (pid {pid}, puerto {port})"));
                *self.adopted.lock().unwrap() = Some(pid);
            } else {
                log_line(log, &format!("reutilizo VISTAN ya en marcha en el puerto {port} ({launcher})"));
            }
            self.ready(port, adopted.is_some(), &launcher);
            return Ok(port);
        }
        let Some(repo) = repo else {
            self.set(|s| {
                s.phase = "failed".into();
                s.needs_repo = true;
                s.message = "No encuentro la carpeta del proyecto VISTAN. Elígela (la carpeta «atlas» de open-higgsfield).".into();
            });
            return Err("sin proyecto".into());
        };
        #[cfg(target_os = "macos")]
        if let Some(port) = self.try_launchd(&repo, log) {
            return Ok(port);
        }
        self.spawn(&repo, pref_port, path_env, log)
    }

    #[cfg(target_os = "macos")]
    fn try_launchd(&self, repo: &Path, log: &Path) -> Option<u16> {
        let home = std::env::var("HOME").ok()?;
        let plist = PathBuf::from(&home).join(format!("Library/LaunchAgents/{LAUNCHD_LABEL}.plist"));
        if !plist.is_file() {
            return None;
        }
        // Solo usamos el servicio si apunta a ESTE proyecto (no a otra copia)
        let content = std::fs::read_to_string(&plist).ok()?;
        if !content.contains(&repo.display().to_string()) {
            log_line(log, "el servicio en segundo plano apunta a otra carpeta: no lo uso");
            return None;
        }
        self.set(|s| s.message = "Arrancando el servicio de VISTAN en segundo plano…".into());
        let uid = unsafe { libc::getuid() };
        let _ = Command::new("/bin/launchctl").args(["kickstart", &format!("gui/{uid}/{LAUNCHD_LABEL}")]).status();
        log_line(log, "pedido a launchd que arranque el servicio de VISTAN");
        let t0 = Instant::now();
        while t0.elapsed() < Duration::from_secs(120) {
            if let Some((port, _)) = self.discover(Some(repo)) {
                self.ready(port, false, "launchd");
                return Some(port);
            }
            std::thread::sleep(Duration::from_millis(700));
        }
        log_line(log, "el servicio en segundo plano no respondió en 120 s");
        None
    }

    fn spawn(&self, repo: &Path, pref_port: u16, path_env: &str, log: &Path) -> Result<u16, String> {
        // Si el puerto elegido resulta ocupado al arrancar (carrera con otro programa), se prueba el siguiente
        let mut from = pref_port;
        for _ in 0..3 {
            match self.spawn_once(repo, from, path_env, log) {
                Err(SpawnErr::PortBusy(p)) => from = p.saturating_add(1),
                Err(SpawnErr::Other(m)) => return Err(m),
                Ok(p) => return Ok(p),
            }
        }
        let m = "No se encontró un puerto libre tras varios intentos".to_string();
        self.fail(&m, log);
        Err(m)
    }

    fn spawn_once(&self, repo: &Path, pref_port: u16, path_env: &str, log: &Path) -> Result<u16, SpawnErr> {
        let port = (pref_port..pref_port.saturating_add(20)).find(|p| port_free(*p)).ok_or_else(|| {
            let m = format!("No hay puertos libres entre {pref_port} y {}", pref_port + 19);
            self.fail(&m, log);
            SpawnErr::Other(m)
        })?;
        self.set(|s| s.message = "Preparando VISTAN (la primera vez puede tardar unos minutos)…".into());
        log_line(log, &format!("arranco el backend con scripts/start.sh en 127.0.0.1:{port}"));
        let out = OpenOptions::new().create(true).append(true).open(log).map_err(|e| SpawnErr::Other(e.to_string()))?;
        let err = out.try_clone().map_err(|e| SpawnErr::Other(e.to_string()))?;
        let mut cmd = Command::new("/bin/bash");
        cmd.arg(repo.join("scripts/start.sh"))
            .current_dir(repo)
            .env("PATH", path_env)
            .env("ATLAS_HOST", "127.0.0.1") // nunca expuesto a la red
            .env("ATLAS_PORT", port.to_string())
            .env("ATLAS_STRICT_PORT", "1")
            .env("ATLAS_LAUNCHER", "desktop")
            .stdin(Stdio::null())
            .stdout(Stdio::from(out))
            .stderr(Stdio::from(err));
        #[cfg(unix)]
        {
            use std::os::unix::process::CommandExt;
            cmd.process_group(0); // grupo propio: al salir detenemos solo lo nuestro
        }
        let child = cmd.spawn().map_err(|e| {
            let m = format!("No se pudo arrancar el backend: {e}");
            self.fail(&m, log);
            SpawnErr::Other(m)
        })?;
        *self.child.lock().unwrap() = Some(child);
        let t0 = Instant::now();
        while t0.elapsed() < Duration::from_secs(900) {
            if self.quitting.load(Ordering::SeqCst) {
                return Err(SpawnErr::Other("saliendo".into()));
            }
            if self.child_exited() {
                // start.sh termina sin error si otro VISTAN con los mismos datos ya funciona: se reutiliza ese
                if let Some((p, launcher)) = self.discover(Some(repo)) {
                    self.ready(p, false, &launcher);
                    return Ok(p);
                }
                if tail(log, 3).iter().any(|l| l.contains(&format!("puerto {port} está ocupado"))) {
                    log_line(log, &format!("el puerto {port} estaba ocupado: pruebo el siguiente"));
                    return Err(SpawnErr::PortBusy(port));
                }
                let code = self.last_exit.lock().unwrap().clone().unwrap_or_default();
                let m = format!("El backend se ha detenido durante el arranque ({code}). Revisa el registro.");
                self.fail(&m, log);
                return Err(SpawnErr::Other(m));
            }
            if health(port).is_some() {
                self.ready(port, true, "desktop");
                return Ok(port);
            }
            if let Some(l) = tail(log, 12).iter().rev().find(|l| l.starts_with('▸')) {
                let l = l.clone();
                self.set(|s| s.message = l.trim_start_matches('▸').trim().to_string());
            }
            std::thread::sleep(Duration::from_millis(500));
        }
        self.stop(log);
        let m = "El backend no respondió en 15 minutos.".to_string();
        self.fail(&m, log);
        Err(SpawnErr::Other(m))
    }

    fn ready(&self, port: u16, owned: bool, launcher: &str) {
        CURRENT_PORT.store(port, Ordering::SeqCst);
        self.set(|s| {
            s.phase = "ready".into();
            s.message = "VISTAN listo".into();
            s.port = Some(port);
            s.url = Some(format!("http://127.0.0.1:{port}/"));
            s.owned = owned;
            s.launcher = launcher.into();
            s.log_tail.clear();
        });
    }

    pub fn fail(&self, msg: &str, log: &Path) {
        log_line(log, msg);
        let t = tail(log, 25);
        self.set(|s| {
            s.phase = "failed".into();
            s.message = msg.into();
            s.log_tail = t;
        });
    }

    /// Cierre limpio del backend que arrancamos nosotros (SIGTERM al grupo, y SIGKILL si no responde en 8 s).
    /// Si el backend es del servicio de macOS o de VISTAN Web, no se toca.
    pub fn stop(&self, log: &Path) {
        if let Some(pid) = self.adopted.lock().ok().and_then(|mut g| g.take()) {
            self.stop_group(pid, log);
            return;
        }
        let Some(mut child) = self.child.lock().ok().and_then(|mut g| g.take()) else { return };
        let pid = child.id() as i32;
        log_line(log, &format!("detengo el backend propio (grupo {pid})"));
        #[cfg(unix)]
        unsafe {
            libc::kill(-pid, libc::SIGTERM);
        }
        #[cfg(not(unix))]
        let _ = child.kill();
        let t0 = Instant::now();
        while t0.elapsed() < Duration::from_secs(8) {
            if let Ok(Some(_)) = child.try_wait() {
                self.set(|s| s.phase = "stopped".into());
                return;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        #[cfg(unix)]
        unsafe {
            libc::kill(-pid, libc::SIGKILL);
        }
        let _ = child.kill();
        let _ = child.wait();
        self.set(|s| s.phase = "stopped".into());
    }

    #[cfg(unix)]
    fn stop_group(&self, pid: i32, log: &Path) {
        if !own_group(pid) {
            return;
        }
        log_line(log, &format!("detengo el backend adoptado (grupo {pid})"));
        unsafe {
            libc::kill(-pid, libc::SIGTERM);
        }
        let t0 = Instant::now();
        while t0.elapsed() < Duration::from_secs(8) {
            if unsafe { libc::kill(pid, 0) } != 0 {
                self.set(|s| s.phase = "stopped".into());
                return;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        unsafe {
            libc::kill(-pid, libc::SIGKILL);
        }
        self.set(|s| s.phase = "stopped".into());
    }
    #[cfg(not(unix))]
    fn stop_group(&self, _pid: i32, _log: &Path) {}

    /// ¿Sigue vivo el backend adoptado? (si no, la vigilancia lo trata como caído)
    pub fn adopted_exited(&self) -> bool {
        #[cfg(unix)]
        if let Some(pid) = *self.adopted.lock().unwrap() {
            if unsafe { libc::kill(pid, 0) } != 0 {
                *self.adopted.lock().unwrap() = None;
                return true;
            }
        }
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dechunk_works() {
        assert_eq!(dechunk("5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n"), "hello world");
    }

    #[test]
    fn data_dir_reads_env() {
        let d = std::env::temp_dir().join(format!("vistan-repo-{}", std::process::id()));
        std::fs::create_dir_all(d.join("backend")).unwrap();
        assert_eq!(data_dir(&d), d.join("data"));
        std::fs::write(d.join("backend/.env"), "ATLAS_PORT=8001\nATLAS_DATA_DIR=../data\n").unwrap();
        assert_eq!(data_dir(&d), d.join("backend/../data")); // aún no existe: se devuelve tal cual
        std::fs::create_dir_all(d.join("data")).unwrap();
        assert_eq!(data_dir(&d), d.join("data").canonicalize().unwrap());
        std::fs::write(d.join("backend/.env"), "ATLAS_DATA_DIR=\"/tmp/x\"\n").unwrap();
        assert_eq!(data_dir(&d), PathBuf::from("/tmp/x"));
        let _ = std::fs::remove_dir_all(d);
    }

    #[test]
    fn foreign_server_is_not_vistan() {
        // Un servidor cualquiera en el puerto no se confunde con VISTAN
        let l = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = l.local_addr().unwrap().port();
        std::thread::spawn(move || {
            for s in l.incoming().take(1).flatten() {
                let mut s = s;
                let mut b = [0u8; 1024];
                let _ = s.read(&mut b);
                let _ = s.write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 15\r\n\r\n{\"status\":\"ok\"}");
            }
        });
        assert!(health(port).is_none());
    }

    #[test]
    fn vistan_server_is_recognised() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = l.local_addr().unwrap().port();
        std::thread::spawn(move || {
            for s in l.incoming().take(1).flatten() {
                let mut s = s;
                let mut b = [0u8; 1024];
                let _ = s.read(&mut b);
                let body = "{\"app\":\"vistan\",\"status\":\"online\"}";
                let _ = write!(s, "HTTP/1.1 200 OK\r\nContent-Length: {}\r\n\r\n{body}", body.len());
            }
        });
        assert_eq!(health(port).unwrap()["status"], "online");
    }
}
