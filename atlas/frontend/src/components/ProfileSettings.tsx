import { useEffect, useRef, useState, type FormEvent, type PointerEvent } from "react";
import { api } from "../api/client";
import { useAtlas } from "./AtlasContext";
import { Avatar } from "./Avatar";
import { Panel } from "./Panel";

const ACCEPT = ["image/jpeg", "image/png", "image/webp"];
const OUT = 512; // tamaño final (px)
const VIEW = 260; // tamaño del recortador en pantalla

/** Recortador circular: arrastrar para encuadrar y zoom. Exporta un cuadrado 512×512. */
export function Cropper({ src, onCancel, onDone }: { src: string; onCancel: () => void; onDone: (blob: Blob) => void }) {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [off, setOff] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  useEffect(() => {
    const i = new Image();
    i.onload = () => setImg(i);
    i.src = src;
  }, [src]);

  // escala mínima: la imagen siempre cubre el círculo
  const base = img ? Math.max(VIEW / img.naturalWidth, VIEW / img.naturalHeight) : 1;
  const scale = base * zoom;
  const w = img ? img.naturalWidth * scale : 0;
  const h = img ? img.naturalHeight * scale : 0;
  const clamp = (o: { x: number; y: number }) => ({
    x: Math.min((w - VIEW) / 2, Math.max(-(w - VIEW) / 2, o.x)),
    y: Math.min((h - VIEW) / 2, Math.max(-(h - VIEW) / 2, o.y)),
  });
  const pos = clamp(off);

  const down = (e: PointerEvent) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, ox: pos.x, oy: pos.y };
  };
  const move = (e: PointerEvent) => {
    if (!drag.current) return;
    setOff(clamp({ x: drag.current.ox + e.clientX - drag.current.x, y: drag.current.oy + e.clientY - drag.current.y }));
  };

  function save() {
    if (!img) return;
    const c = document.createElement("canvas");
    c.width = c.height = OUT;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const k = OUT / VIEW;
    ctx.drawImage(img, (VIEW / 2 - w / 2 + pos.x) * k, (VIEW / 2 - h / 2 + pos.y) * k, w * k, h * k);
    c.toBlob((b) => b && onDone(b), "image/webp", 0.92);
  }

  return (
    <div className="cropper">
      <div className="crop-view" style={{ width: VIEW, height: VIEW }} onPointerDown={down} onPointerMove={move}
        onPointerUp={() => { drag.current = null; }} role="img" aria-label="Vista previa del recorte (arrastra para encuadrar)">
        {img && <img src={src} alt="" draggable={false}
          style={{ width: w, height: h, transform: `translate(${VIEW / 2 - w / 2 + pos.x}px, ${VIEW / 2 - h / 2 + pos.y}px)` }} />}
        <span className="crop-mask" aria-hidden="true" />
      </div>
      <label className="field"><span>Zoom</span>
        <input type="range" min={1} max={3} step={0.01} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} aria-label="Zoom de la foto" />
      </label>
      <div className="form-actions">
        <button type="button" className="btn" onClick={save} disabled={!img}>Guardar foto</button>
        <button type="button" className="mini-btn ghost" onClick={onCancel}>Cancelar</button>
      </div>
    </div>
  );
}

/** Configuración › Perfil personal. La foto se queda en tu ordenador; nunca se envía a la IA. */
export function ProfileSettings() {
  const { profile, reloadProfile } = useAtlas();
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [prefsText, setPrefsText] = useState("");
  const [greeting, setGreeting] = useState("");
  const [pick, setPick] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ tone: "pos" | "neg"; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (profile) { setName(profile.display_name); setUsername(profile.username); setPrefsText(profile.preferences); setGreeting(profile.greeting ?? ""); }
  }, [profile]);
  useEffect(() => () => { if (pick) URL.revokeObjectURL(pick); }, [pick]);
  useEffect(() => {
    if (window.location.hash === "#perfil") document.getElementById("perfil")?.scrollIntoView?.({ block: "start" });
  }, []);

  function choose(f: File | undefined) {
    if (!f) return;
    if (!ACCEPT.includes(f.type)) { setMsg({ tone: "neg", text: "Formato no permitido: usa JPG, PNG o WEBP." }); return; }
    if (f.size > 10 * 1024 * 1024) { setMsg({ tone: "neg", text: "La imagen supera 10 MB." }); return; }
    setMsg(null);
    setPick(URL.createObjectURL(f));
  }

  async function upload(blob: Blob) {
    try {
      await api.uploadAvatar(blob);
      setPick(null);
      await reloadProfile();
      setMsg({ tone: "pos", text: "Foto de perfil guardada." });
    } catch (e) { setMsg({ tone: "neg", text: (e as Error).message }); }
  }

  async function remove() {
    if (!window.confirm("¿Eliminar tu foto de perfil? Volverás al avatar con tus iniciales.")) return;
    await api.deleteAvatar();
    await reloadProfile();
    setMsg({ tone: "pos", text: "Foto eliminada." });
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api.updateProfile({ display_name: name, username, preferences: prefsText, greeting });
      await reloadProfile();
      setMsg({ tone: "pos", text: "Perfil guardado." });
    } catch (err) { setMsg({ tone: "neg", text: (err as Error).message }); }
  }

  const created = profile ? new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "long", year: "numeric" }).format(new Date(profile.created_at)) : "—";
  return (
    <Panel title="Perfil personal" className="profile-panel">
      <div id="perfil" className="profile-grid">
        <div className="profile-photo">
          {pick ? <Cropper src={pick} onCancel={() => setPick(null)} onDone={(b) => void upload(b)} /> : (
            <>
              <Avatar profile={profile} size={120} />
              <div className="form-actions">
                <button type="button" className="btn" onClick={() => fileRef.current?.click()}>{profile?.has_avatar ? "Cambiar foto" : "Subir foto"}</button>
                {profile?.has_avatar && <button type="button" className="mini-btn danger" onClick={() => void remove()}>Eliminar</button>}
              </div>
              <input ref={fileRef} type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" hidden
                aria-label="Elegir foto de perfil" onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />
              <p className="muted small">JPG, PNG o WEBP. Se guarda solo en tu ordenador y nunca se envía a la IA ni a otros servicios.</p>
            </>
          )}
        </div>
        <form className="form" onSubmit={save}>
          <label><span>Nombre visible (aparece en el saludo)</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Tu nombre" /></label>
          <label><span>Nombre de usuario</span>
            <input value={username} onChange={(e) => setUsername(e.target.value)} maxLength={30} placeholder="p. ej. lance" pattern="[a-zA-Z0-9._\\-]{3,30}" /></label>
          <label><span>Saludo personalizado (usa {"{nombre}"}; vacío = «Buenos días/tardes/noches»)</span>
            <input value={greeting} onChange={(e) => setGreeting(e.target.value)} maxLength={120} placeholder="Ej.: A tus órdenes, {nombre}" /></label>
          <label><span>Preferencias personales</span>
            <textarea rows={3} value={prefsText} onChange={(e) => setPrefsText(e.target.value)} maxLength={2000}
              placeholder="Ej.: prefiero respuestas directas y con un plan concreto" /></label>
          <p className="muted small">Perfil creado el {created}.</p>
          <div className="form-actions">
            <button className="btn" type="submit">Guardar perfil</button>
            {msg && <span role="status" className={`small ${msg.tone}`}>{msg.text}</span>}
          </div>
        </form>
      </div>
    </Panel>
  );
}
