"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { uploadMedia } from "@/generation/upload";
import { saveFile } from "@/openhiggsfield/download";

import { FORMATS, SECTORS, STYLES, formatById, salesCopy, type FormatId, type SectorId, type StyleId } from "./content";
import { COST } from "./plans";
import { checkJobs, startImages, startVideo, type JobStatus, type StartResult } from "./server/generate-actions";

type Slot =
  | { state: "pending"; requestId?: string }
  | { state: "done"; url: string; video?: VideoState }
  | { state: "failed"; reason: string };

type VideoState =
  | { state: "pending"; requestId: string }
  | { state: "done"; url: string }
  | { state: "failed"; reason: string };

const POLL_MS = 4000;

const START_ERRORS: Record<Exclude<StartResult, { ok: true }>["error"], string> = {
  login: "Tu sesión ha caducado. Vuelve a entrar.",
  credits: "No tienes créditos suficientes.",
  input: "Revisa la foto y las opciones e inténtalo de nuevo.",
  platform: "El servicio de generación no responde. No se te ha cobrado. Inténtalo en un momento.",
};

const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 12 * 1024 * 1024;

export function Creator({ initialCredits }: { initialCredits: number }) {
  const [credits, setCredits] = useState(initialCredits);
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

  useEffect(
    () => () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    },
    [],
  );

  /* Every job in flight is asked about in one round trip every few seconds. */
  const pendingIds = useMemo(
    () =>
      slots.flatMap((slot) =>
        slot.state === "pending" && slot.requestId
          ? [slot.requestId]
          : slot.state === "done" && slot.video?.state === "pending"
            ? [slot.video.requestId]
            : [],
      ),
    [slots],
  );
  const pendingKey = pendingIds.join(",");

  /* Bumped after every round so the next one is scheduled even when nothing
     finished (the set of pending ids is then unchanged). */
  const [pollRound, setPollRound] = useState(0);

  useEffect(() => {
    if (!pendingKey) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      const result = await checkJobs({ requestIds: pendingKey.split(",") }).catch(() => null);
      if (cancelled) return;
      if (result) {
        setCredits(result.credits);
        applyJobs(result.jobs);
      }
      setPollRound((round) => round + 1);
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [pendingKey, pollRound]);

  function applyJobs(jobs: JobStatus[]) {
    const byId = new Map(jobs.map((job) => [job.requestId, job]));
    setSlots((current) =>
      current.map((slot): Slot => {
        if (slot.state === "pending" && slot.requestId) {
          const job = byId.get(slot.requestId);
          if (job?.state === "done" && job.url) return { state: "done", url: job.url };
          if (job?.state === "failed") return { state: "failed", reason: job.reason ?? "No se pudo generar." };
          return slot;
        }
        if (slot.state === "done" && slot.video?.state === "pending") {
          const job = byId.get(slot.video.requestId);
          if (job?.state === "done" && job.url) return { ...slot, video: { state: "done", url: job.url } };
          if (job?.state === "failed") return { ...slot, video: { state: "failed", reason: job.reason ?? "No se pudo crear el vídeo." } };
        }
        return slot;
      }),
    );
  }

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
    setSlots([0, 1, 2, 3].map(() => ({ state: "pending" })));
    const result = await startImages({ photoUrl: photo.url, sector, style, format, productName }).catch(
      (): StartResult => ({ ok: false, error: "platform" }),
    );
    setRunning(false);
    if (typeof result.credits === "number") setCredits(result.credits);
    if (!result.ok) {
      setSlots([]);
      setError(START_ERRORS[result.error]);
      return;
    }
    setSlots(result.requestIds.map((requestId) => ({ state: "pending", requestId })));
  }

  async function makeVideo(index: number) {
    const slot = slots[index];
    if (slot?.state !== "done" || slot.video?.state === "pending") return;
    setError(null);
    const result = await startVideo({ imageUrl: slot.url, style, format: runFormat }).catch(
      (): StartResult => ({ ok: false, error: "platform" }),
    );
    if (typeof result.credits === "number") setCredits(result.credits);
    if (!result.ok) {
      updateSlot(index, { ...slot, video: { state: "failed", reason: START_ERRORS[result.error] } });
      return;
    }
    updateSlot(index, { ...slot, video: { state: "pending", requestId: result.requestIds[0] } });
  }

  function updateSlot(index: number, next: Slot) {
    setSlots((current) => current.map((slot, at) => (at === index ? next : slot)));
  }

  async function download(url: string, name: string) {
    const ok = await saveFile(url, name);
    if (!ok) window.open(url, "_blank", "noopener");
  }

  const photosCost = 4 * COST.image;
  const canGenerate = Boolean(photo?.url) && !running && credits >= photosCost;
  const ratio = formatById(runFormat).aspectRatio === "9:16" ? "9 / 16" : "1 / 1";
  const fileBase = (productName.trim() || "producto").toLowerCase().replace(/[^a-z0-9]+/gi, "-");

  return (
    <div className="esc-creator">
      <div className="esc-banner" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span>
          Tienes <strong>{credits} créditos</strong> · 4 fotos = {photosCost} créditos · 1 vídeo = {COST.video} créditos
        </span>
        <Link href="/escaparate/cuenta" className="esc-btn esc-btn-ghost esc-btn-small">
          Conseguir más
        </Link>
      </div>
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
            {running ? "Enviando…" : `Crear 4 fotos profesionales (${photosCost} créditos)`}
          </button>
          {!photo?.url ? <p className="esc-note">Primero sube la foto de tu producto.</p> : null}
          {photo?.url && credits < photosCost ? (
            <p className="esc-note">
              Te faltan créditos. <Link href="/escaparate/cuenta">Elige un plan o compra un pack</Link>.
            </p>
          ) : null}
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
                          {slot.video?.state === "pending" ? "Creando vídeo…" : `🎬 Crear vídeo (${COST.video})`}
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


