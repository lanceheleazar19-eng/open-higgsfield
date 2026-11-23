import { useCallback, useEffect, useRef, useState } from "react";

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

  const stopSpeaking = useCallback(() => {
    if (canSpeak) window.speechSynthesis.cancel();
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
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text.replace(/[•«»]/g, ""));
    u.lang = "es-ES";
    const es = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("es"));
    if (es) u.voice = es;
    u.onstart = () => setSpeaking(true);
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(u);
  }, [canSpeak]);

  useEffect(() => () => {
    recRef.current?.abort();
    if (canSpeak) window.speechSynthesis.cancel();
  }, [canSpeak]);

  return { canListen: !!Ctor, canSpeak, listening, speaking, interim, error, listen, stopListening, speak, stopSpeaking };
}
