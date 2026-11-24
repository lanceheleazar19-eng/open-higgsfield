/** Voz de VISTAN con VoiceStudio (app de voz local en tu Mac, a través del núcleo de VISTAN).
 *  Si VoiceStudio no responde, cada frase se lee con la voz del navegador (`fallback`). */
import { request } from "../api/client";

export interface VsVoice { id: string; name: string; type: string | null; language: string | null }
export interface VsStatus { url: string; local: boolean; reachable: boolean; ping_ms: number | null; protocol: string | null; voices: VsVoice[]; error: string | null;
  synthesis: { count: number; errors: number; last_ms: number | null; avg_ms: number | null } }

export const vsStatus = () => request<VsStatus>("/api/voicestudio/status");

const ENGINE_KEY = "vistan.voice.engine";
const VS_VOICE_KEY = "vistan.voice.vs_voice";
export type VoiceEngine = "browser" | "voicestudio";

export function loadEngine(): { engine: VoiceEngine; vsVoice: string | null } {
  try {
    return { engine: localStorage.getItem(ENGINE_KEY) === "voicestudio" ? "voicestudio" : "browser", vsVoice: localStorage.getItem(VS_VOICE_KEY) };
  } catch {
    return { engine: "browser", vsVoice: null };
  }
}

export function saveEngine(p: { engine?: VoiceEngine; vsVoice?: string | null }) {
  try {
    if (p.engine) localStorage.setItem(ENGINE_KEY, p.engine);
    if (p.vsVoice !== undefined) {
      if (p.vsVoice) localStorage.setItem(VS_VOICE_KEY, p.vsVoice);
      else localStorage.removeItem(VS_VOICE_KEY);
    }
  } catch { /* sin almacenamiento */ }
}

export const usingVoiceStudio = () => typeof Audio !== "undefined" && loadEngine().engine === "voicestudio";

/** Si una frase tarda más que esto, esa respuesta sigue con la voz del navegador (no te deja esperando). */
export const VS_WAIT_MS = 7000;

/** Pide el audio a VISTAN (que lo pide a VoiceStudio). null si no está disponible o tarda demasiado. */
export async function vsSynth(text: string, rate: number, waitMs = VS_WAIT_MS): Promise<Blob | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), waitMs);
  try {
    const res = await fetch("/api/voicestudio/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice: loadEngine().vsVoice, speed: Math.max(0.25, Math.min(4, rate)), language: "es" }),
      signal: ctrl.signal,
    });
    if (!res.ok) return null;
    return await res.blob();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** Carga el modelo de VoiceStudio en memoria antes de la primera respuesta (sin reproducir nada). */
let warmed = false;
export function vsWarmup(force = false) {
  if ((warmed && !force) || !usingVoiceStudio()) return;
  warmed = true;
  void vsSynth("Hola.", 1, 120000);
}

let audio: HTMLAudioElement | null = null;
const player = () => (audio ??= new Audio());
let generation = 0;
let degraded = -1; // respuesta (generation) que ya pasó a la voz del navegador por lentitud o fallo
let tail: Promise<void> = Promise.resolve();

function play(blob: Blob, gen: number): Promise<void> {
  return new Promise((resolve) => {
    if (gen !== generation) return resolve();
    const a = player();
    const url = URL.createObjectURL(blob);
    const done = () => { a.onended = a.onerror = null; URL.revokeObjectURL(url); resolve(); };
    a.onended = done;
    a.onerror = done;
    a.src = url;
    a.play().catch(done);
  });
}

/** Corta lo que esté sonando y lo que haya en cola. */
export function vsStop() {
  generation += 1;
  tail = Promise.resolve();
  if (audio) { audio.pause(); audio.removeAttribute("src"); }
}

/** Añade una frase a la cola. El audio se pide en cuanto llega (en paralelo) y suena en orden. */
export function vsEnqueue(text: string, rate: number, onStart: () => void, onEnd: () => void, fallback: () => void) {
  const gen = generation;
  if (degraded === gen) { tail = tail.then(() => { if (gen === generation) fallback(); }); return; }
  const blob = vsSynth(text, rate, 60000);
  tail = tail.then(async () => {
    // El plazo cuenta desde que le toca sonar (las frases siguientes se generan mientras suena la anterior)
    const b = degraded === gen ? null
      : await Promise.race([blob, new Promise<null>((r) => setTimeout(() => r(null), VS_WAIT_MS))]);
    if (gen !== generation) return;
    if (!b) { degraded = gen; fallback(); return; }
    onStart();
    await play(b, gen);
    onEnd();
  });
}

/** iPhone: el audio solo puede sonar sin toque si el reproductor se «estrena» en un toque. */
export function vsUnlock() {
  if (typeof Audio === "undefined") return;
  try {
    const a = player();
    a.src = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
    void a.play().catch(() => undefined);
  } catch { /* sin audio */ }
}
