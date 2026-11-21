"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";

import { hasPlatformCredentials, savePlatformCredentials, submitGeneration } from "@/generation/actions";
import { watchRequest } from "@/generation/poll";
import { uploadMedia } from "@/generation/upload";
import { saveFile } from "@/openhiggsfield/download";

import {
  FORMATS,
  IMAGE_MODEL,
  SECTORS,
  STYLES,
  VIDEO_MODEL,
  formatById,
  imagePrompts,
  salesCopy,
  videoPrompt,
  type FormatId,
  type SectorId,
  type StyleId,
} from "./content";

type Slot =
  | { state: "pending" }
  | { state: "done"; url: string; video?: VideoState }
  | { state: "failed"; reason: string };

type VideoState = { state: "pending" } | { state: "done"; url: string } | { state: "failed"; reason: string };

const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 12 * 1024 * 1024;

export function Creator() {
  const [keyState, setKeyState] = useState<"checking" | "missing" | "ready">("checking");
  const [photo, setPhoto] = useState<{ preview: string; url: string | null; error?: string } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [sector, setSector] = useState<SectorId>("comida");
  const [style, setStyle] = useState<StyleId>("estudio");
  const [format, setFormat] = useState<FormatId>("post");
  const [productName, setProductName] = useState("");
  const [price, setPrice] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [city, setCity] = useState("");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [running, setRunning] = useState(false);
  const [runFormat, setRunFormat] = useState<FormatId>("post");
  const [error, setError] = useState<string | null>(null);
  const previewRef = useRef<string | null>(null);

  useEffect(() => {
    hasPlatformCredentials()
      .then((has) => setKeyState(has ? "ready" : "missing"))
      .catch(() => setKeyState("missing"));
    return () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    };
  }, []);

  const copy = useMemo(
    () => salesCopy({ sector, productName, price, businessName, city }),
    [sector, productName, price, businessName, city],
  );

  async function takeFile(file: File | undefined) {
    if (!file) return;
    if (!ACCEPTED.includes(file.type)) {
      setPhoto({ preview: "", url: null, error: "Usa una foto en JPG, PNG o WEBP." });
      return;
    }
    if (file.size > MAX_BYTES) {
      setPhoto({ preview: "", url: null, error: "La foto pesa demasiado (máximo 12 MB)." });
      return;
    }
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    const preview = URL.createObjectURL(file);
    previewRef.current = preview;
    setPhoto({ preview, url: null });
    try {
      const { url } = await uploadMedia(file);
      setPhoto({ preview, url });
    } catch {
      setPhoto({ preview, url: null, error: "No hemos podido subir la foto. Inténtalo de nuevo." });
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragOver(false);
    void takeFile(event.dataTransfer.files[0]);
  }

  async function generate() {
    if (!photo?.url || running) return;
    setError(null);
    setRunning(true);
    setRunFormat(format);
    const prompts = imagePrompts({ sector, style, productName });
    const aspectRatio = formatById(format).aspectRatio;
    setSlots(prompts.map(() => ({ state: "pending" })));

    const reference = [{ id: "producto", url: photo.url, role: "reference" as const }];
    const jobs = prompts.map(async (prompt, index) => {
      try {
        const queued = await submitGeneration({
          model: IMAGE_MODEL,
          prompt: { text: prompt },
          media: { reference },
          settings: { aspectRatio, resolution: "1k" },
        });
        const status = await watchRequest(queued.requestId);
        const url = status.images?.[0]?.url;
        updateSlot(index, url ? { state: "done", url } : { state: "failed", reason: failureReason(status.status) });
      } catch {
        updateSlot(index, { state: "failed", reason: "No se pudo generar esta foto." });
      }
    });
    await Promise.all(jobs);
    setRunning(false);
  }

  async function makeVideo(index: number) {
    const slot = slots[index];
    if (slot?.state !== "done" || slot.video?.state === "pending") return;
    updateSlot(index, { ...slot, video: { state: "pending" } });
    try {
      const queued = await submitGeneration({
        model: VIDEO_MODEL,
        prompt: { text: videoPrompt(style) },
        media: { start: [{ id: "foto", url: slot.url, role: "start" }] },
        settings: { duration: 5, resolution: "720p", aspectRatio: formatById(runFormat).aspectRatio },
      });
      const status = await watchRequest(queued.requestId);
      const url = status.video?.url;
      updateSlot(index, {
        ...slot,
        video: url ? { state: "done", url } : { state: "failed", reason: failureReason(status.status) },
      });
    } catch {
      updateSlot(index, { ...slot, video: { state: "failed", reason: "No se pudo crear el vídeo." } });
    }
  }

  function updateSlot(index: number, next: Slot) {
    setSlots((current) => current.map((slot, at) => (at === index ? next : slot)));
  }

  async function download(url: string, name: string) {
    const ok = await saveFile(url, name);
    if (!ok) window.open(url, "_blank", "noopener");
  }

  if (keyState === "checking") {
    return <p className="esc-note">Cargando…</p>;
  }
  if (keyState === "missing") {
    return <KeyForm onSaved={() => setKeyState("ready")} />;
  }

  const canGenerate = Boolean(photo?.url) && !running;
  const ratio = formatById(runFormat).aspectRatio === "9:16" ? "9 / 16" : "1 / 1";
  const fileBase = (productName.trim() || "producto").toLowerCase().replace(/[^a-z0-9]+/gi, "-");

  return (
    <div className="esc-creator">
      <section className="esc-panel">
        <h2 className="esc-panel-title">1. Sube la foto de tu producto</h2>
        <label
          className="esc-drop"
          data-over={dragOver}
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          <input
            type="file"
            accept={ACCEPTED.join(",")}
            aria-label="Elegir foto del producto"
            onChange={(event: ChangeEvent<HTMLInputElement>) => void takeFile(event.target.files?.[0])}
          />
          {photo?.preview ? (
            <img src={photo.preview} alt="Tu producto" />
          ) : (
            <span aria-hidden style={{ fontSize: 40 }}>
              📷
            </span>
          )}
          <span>
            {photo?.preview
              ? photo.url
                ? "Foto lista ✓ · Toca para cambiarla"
                : photo.error ?? "Subiendo foto…"
              : "Toca para elegir una foto o arrástrala aquí"}
          </span>
        </label>
        {!photo?.preview && photo?.error ? (
          <p className="esc-msg-error" role="alert">
            {photo.error}
          </p>
        ) : null}
      </section>

      <section className="esc-panel">
        <h2 className="esc-panel-title">2. Cuéntanos de tu producto</h2>
        <div className="esc-form-row">
          <label className="esc-label">
            ¿Qué es?
            <input
              className="esc-input"
              placeholder="Ej.: tarta de queso casera"
              value={productName}
              onChange={(event) => setProductName(event.target.value)}
            />
          </label>
          <label className="esc-label">
            Precio (opcional)
            <input
              className="esc-input"
              inputMode="decimal"
              placeholder="Ej.: 18,50"
              value={price}
              onChange={(event) => setPrice(event.target.value)}
            />
          </label>
        </div>
        <div className="esc-form-row">
          <label className="esc-label">
            Nombre de tu negocio (opcional)
            <input className="esc-input" value={businessName} onChange={(event) => setBusinessName(event.target.value)} />
          </label>
          <label className="esc-label">
            Ciudad (opcional)
            <input className="esc-input" value={city} onChange={(event) => setCity(event.target.value)} />
          </label>
        </div>
        <ChipGroup
          label="Sector"
          options={SECTORS.map((item) => ({ id: item.id, label: `${item.emoji} ${item.label}` }))}
          value={sector}
          onChange={setSector}
        />
      </section>

      <section className="esc-panel">
        <h2 className="esc-panel-title">3. Elige estilo y formato</h2>
        <ChipGroup
          label="Estilo"
          options={STYLES.map((item) => ({ id: item.id, label: item.label, hint: item.hint }))}
          value={style}
          onChange={setStyle}
        />
        <ChipGroup
          label="Formato"
          options={FORMATS.map((item) => ({ id: item.id, label: item.label, hint: item.hint }))}
          value={format}
          onChange={setFormat}
        />
        <div>
          <button className="esc-btn esc-btn-primary" type="button" disabled={!canGenerate} onClick={() => void generate()}>
            {running ? "Creando tus fotos…" : "Crear 4 fotos profesionales"}
          </button>
          {!photo?.url ? <p className="esc-note">Primero sube la foto de tu producto.</p> : null}
          {error ? (
            <p className="esc-msg-error" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      </section>

      {slots.length ? (
        <section className="esc-panel" aria-live="polite">
          <h2 className="esc-panel-title">Tus fotos</h2>
          <div className="esc-results" data-format={runFormat}>
            {slots.map((slot, index) => (
              <div className="esc-result" key={index}>
                {slot.state === "pending" ? (
                  <div className="esc-skeleton" style={{ aspectRatio: ratio }} aria-label="Generando foto" />
                ) : slot.state === "failed" ? (
                  <div className="esc-copy-block" style={{ aspectRatio: ratio }}>
                    {slot.reason}
                  </div>
                ) : (
                  <>
                    {slot.video?.state === "done" ? (
                      <video
                        className="esc-result-media"
                        style={{ aspectRatio: ratio }}
                        src={slot.video.url}
                        controls
                        loop
                        playsInline
                      />
                    ) : (
                      <img
                        className="esc-result-media"
                        style={{ aspectRatio: ratio }}
                        src={slot.url}
                        alt={`Foto profesional ${index + 1} de ${productName || "tu producto"}`}
                      />
                    )}
                    <div className="esc-result-actions">
                      <button
                        className="esc-btn esc-btn-ghost esc-btn-small"
                        type="button"
                        onClick={() => void download(slot.url, `escaparate-${fileBase}-${index + 1}.png`)}
                      >
                        Descargar
                      </button>
                      {slot.video?.state === "done" ? (
                        <button
                          className="esc-btn esc-btn-ghost esc-btn-small"
                          type="button"
                          onClick={() => void download((slot.video as { url: string }).url, `escaparate-${fileBase}-${index + 1}.mp4`)}
                        >
                          Descargar vídeo
                        </button>
                      ) : (
                        <button
                          className="esc-btn esc-btn-ghost esc-btn-small"
                          type="button"
                          disabled={slot.video?.state === "pending"}
                          onClick={() => void makeVideo(index)}
                        >
                          {slot.video?.state === "pending" ? "Creando vídeo…" : "🎬 Crear vídeo"}
                        </button>
                      )}
                    </div>
                    {slot.video?.state === "failed" ? <p className="esc-msg-error">{slot.video.reason}</p> : null}
                  </>
                )}
              </div>
            ))}
          </div>
          <p className="esc-note">El vídeo tarda 1–3 minutos. Puedes seguir copiando el texto mientras tanto.</p>
        </section>
      ) : null}

      <section className="esc-panel">
        <h2 className="esc-panel-title">Texto para vender</h2>
        <div className="esc-copy">
          <CopyBlock title="Publicación de Instagram" text={`${copy.titulo}\n\n${copy.texto}\n\n${copy.hashtags}`} />
          <CopyBlock title="Mensaje para tus clientes de WhatsApp" text={copy.whatsapp} />
        </div>
      </section>
    </div>
  );
}

function ChipGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Array<{ id: T; label: string; hint?: string }>;
  value: T;
  onChange: (next: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="esc-label">
      {label}
      <div className="esc-chips">
        {options.map((option) => (
          <button
            key={option.id}
            type="button"
            className="esc-chip"
            aria-pressed={option.id === value}
            onClick={() => onChange(option.id)}
          >
            {option.label}
            {option.hint ? <small>{option.hint}</small> : null}
          </button>
        ))}
      </div>
    </div>
  );
}

function CopyBlock({ title, text }: { title: string; text: string }) {
  const [copied, setCopied] = useState(false);
  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div>
      <div className="esc-copy-head">
        {title}
        <button className="esc-btn esc-btn-ghost esc-btn-small" type="button" onClick={() => void onCopy()}>
          {copied ? "¡Copiado!" : "Copiar"}
        </button>
      </div>
      <div className="esc-copy-block">{text}</div>
    </div>
  );
}

function KeyForm({ onSaved }: { onSaved: () => void }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!/^[^:\s]+:[^\s]+$/.test(value.trim())) {
      setError("La clave tiene el formato id:secreto.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await savePlatformCredentials({ api_key: value.trim() });
      onSaved();
    } catch {
      setError("No hemos podido guardar la clave.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="esc-creator">
      <form className="esc-panel" onSubmit={onSubmit}>
        <h2 className="esc-panel-title">Versión de prueba</h2>
        <p className="esc-banner">
          Este prototipo usa tu propia clave de la plataforma de generación mientras preparamos las cuentas y
          los pagos. Se guarda solo en una cookie segura de este navegador.
        </p>
        <label className="esc-label">
          Clave de la plataforma (id:secreto)
          <input
            className="esc-input"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
        </label>
        {error ? (
          <p className="esc-msg-error" role="alert">
            {error}
          </p>
        ) : null}
        <div>
          <button className="esc-btn esc-btn-primary" type="submit" disabled={busy || !value.trim()}>
            {busy ? "Guardando…" : "Guardar y empezar"}
          </button>
        </div>
      </form>
    </div>
  );
}

function failureReason(status: string): string {
  if (status === "nsfw") return "La foto no ha pasado el filtro de contenido. Prueba con otra.";
  if (status === "canceled") return "Se canceló la generación.";
  return "No se pudo generar. Inténtalo de nuevo.";
}
