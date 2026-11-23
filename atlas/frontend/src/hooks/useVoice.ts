import { useCallback, useEffect, useRef, useState } from "react";
import { loadVoicePrefs, pickVoice, speechChunks } from "../lib/speech";

/* Tipos mínimos de la Web Speech API (no están en lib.dom). */
interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
}
type RecognitionCtor = new () => SpeechRecognitionLike;

function getRecognition(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export interface Voice {
  canListen: boolean;
  canSpeak: boolean;
  listening: boolean;
  speaking: boolean;
  interim: string;
  error: string | null;
  listen: () => void;
  stopListening: () => void;
  speak: (text: string) => void;
  /** Añade texto a la cola sin interrumpir lo que se está diciendo (lectura mientras se genera). */
  enqueue: (text: string) => void;
  stopSpeaking: () => void;
}

/** Reconocimiento (micrófono → texto) y síntesis (texto → voz) del navegador. */
export function useVoice(onFinal: (text: string) => void): Voice {
  const Ctor = typeof window !== "undefined" ? getRecognition() : null;
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const finalRef = useRef(onFinal);
  finalRef.current = onFinal;
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);

  const pending = useRef(0);
  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    pending.current = 0;
    setSpeaking(false);
  }, [canSpeak]);

  const listen = useCallback(() => {
    if (!Ctor) return;
    stopSpeaking(); // interrumpe a ATLAS si estaba hablando
    const rec = new Ctor();
    rec.lang = "es-ES";
    rec.interimResults = true;
    rec.continuous = false;
    let finalText = "";
    rec.onresult = (e) => {
      let live = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else live += r[0].transcript;
      }
      setInterim(finalText + live);
    };
    rec.onerror = (e) => {
      setError(e.error === "not-allowed" ? "Permiso de micrófono denegado" : `Error de voz: ${e.error}`);
    };
    rec.onend = () => {
      setListening(false);
      setInterim("");
      recRef.current = null;
      if (finalText.trim()) finalRef.current(finalText.trim());
    };
    recRef.current = rec;
    setError(null);
    setListening(true);
    rec.start();
  }, [Ctor, stopSpeaking]);

  const stopListening = useCallback(() => recRef.current?.stop(), []);

  const speak = useCallback((text: string) => {
    if (!canSpeak) return;
    pending.current = 0;
    speakText(text, () => setSpeaking(true), () => setSpeaking(false));
  }, [canSpeak]);

  const enqueue = useCallback((text: string) => {
    if (!canSpeak || !text.trim()) return;
    queueSpeech(text, () => { pending.current += 1; setSpeaking(true); }, () => {
      pending.current = Math.max(0, pending.current - 1);
      if (pending.current === 0) setSpeaking(false);
    });
  }, [canSpeak]);

  useEffect(() => () => {
    recRef.current?.abort();
    window.speechSynthesis?.cancel();
  }, [canSpeak]);

  return { canListen: !!Ctor, canSpeak, listening, speaking, interim, error, listen, stopListening, speak, enqueue, stopSpeaking };
}

/** Chrome carga las voces de forma asíncrona: al abrir la página getVoices() está vacío.
 *  Espera a que estén disponibles (máx. 1,5 s) para no usar la voz por defecto del navegador. */
export function voicesReady(timeoutMs = 1500): Promise<SpeechSynthesisVoice[]> {
  const synth = window.speechSynthesis;
  const now = synth.getVoices();
  if (now.length) return Promise.resolve(now);
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      synth.removeEventListener?.("voiceschanged", done);
      resolve(synth.getVoices());
    };
    const timer = setTimeout(done, timeoutMs);
    synth.addEventListener?.("voiceschanged", done);
  });
}

/** Lee un texto frase a frase con la voz y velocidad elegidas en Configuración (interrumpe lo anterior). */
export function speakText(text: string, onStart?: () => void, onEnd?: () => void, override?: { voiceURI?: string | null; rate?: number }) {
  window.speechSynthesis.cancel();
  void voicesReady().then((voices) => {
    const synth = window.speechSynthesis;
    const prefs = { ...loadVoicePrefs(), ...override };
    const voice = pickVoice(voices, prefs.voiceURI ?? null);
    const chunks = speechChunks(text);
    if (!chunks.length) return;
    chunks.forEach((chunk, i) => {
      const u = new SpeechSynthesisUtterance(chunk);
      u.lang = voice?.lang ?? "es-ES";
      if (voice) u.voice = voice;
      u.rate = prefs.rate;
      if (i === 0) u.onstart = () => onStart?.();
      if (i === chunks.length - 1) { u.onend = () => onEnd?.(); }
      u.onerror = () => onEnd?.();
      synth.speak(u);
    });
  });
}

/** Lista de voces del sistema (se cargan de forma asíncrona en Chrome). */
export function useSystemVoices(): SpeechSynthesisVoice[] {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const load = () => setVoices(window.speechSynthesis.getVoices());
    load();
    window.speechSynthesis.addEventListener?.("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", load);
  }, []);
  return voices;
}

/** Encola cada trozo como locución independiente; onStart/onEnd se llaman por trozo. */
let queueTail: Promise<unknown> = Promise.resolve();

function queueSpeech(text: string, onChunkStart: () => void, onChunkEnd: () => void) {
  // Encadenado para conservar el orden de las frases aunque las voces tarden en cargar
  queueTail = queueTail.then(() => voicesReady()).then((voices) => speakChunks(voices, text, onChunkStart, onChunkEnd));
}

function speakChunks(voices: SpeechSynthesisVoice[], text: string, onChunkStart: () => void, onChunkEnd: () => void) {
  const synth = window.speechSynthesis;
  const prefs = loadVoicePrefs();
  const voice = pickVoice(voices, prefs.voiceURI);
  for (const chunk of speechChunks(text)) {
    const u = new SpeechSynthesisUtterance(chunk);
    u.lang = voice?.lang ?? "es-ES";
    if (voice) u.voice = voice;
    u.rate = prefs.rate;
    onChunkStart();
    u.onend = onChunkEnd;
    u.onerror = onChunkEnd;
    synth.speak(u);
  }
}
