import { useCallback, useEffect, useRef, useState } from "react";
import { loadVoicePrefs, pickVoice, saveVoicePrefs, speechChunks } from "../lib/speech";
import { afterWake, isEcho, loadHandsFree, matchWake, saveHandsFree, voiceIntent, type HandsFree } from "../lib/wake";

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
  /** Manos libres (Fase 9) */
  handsFree: HandsFree;
  setHandsFree: (p: Partial<HandsFree>) => void;
  /** Escuchando en segundo plano la palabra «ATLAS». */
  wakeActive: boolean;
  /** La conversación actual empezó por voz: las respuestas se leen y se sigue escuchando. */
  conversing: boolean;
  endConversation: () => void;
  /** Empieza una respuesta nueva (para «repite» y el filtro de eco). */
  beginReply: () => void;
}

const LANG = "es-ES";

function beep() {
  try {
    const AC = (window as unknown as { AudioContext?: typeof AudioContext }).AudioContext;
    if (!AC) return;
    const ctx = new AC();
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.value = 880;
    g.gain.setValueAtTime(0.0001, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.18);
    o.connect(g).connect(ctx.destination);
    o.start();
    o.stop(ctx.currentTime + 0.2);
    o.onended = () => void ctx.close();
  } catch { /* sin audio */ }
}

/** Reconocimiento (micrófono → texto), síntesis (texto → voz) y modo manos libres del navegador.
 *  `busy`: ATLAS está generando una respuesta (no se reabre el micrófono hasta que termine). */
export function useVoice(onFinal: (text: string) => void, busy = false): Voice {
  const Ctor = typeof window !== "undefined" ? getRecognition() : null;
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const bgRef = useRef<SpeechRecognitionLike | null>(null);
  const finalRef = useRef(onFinal);
  finalRef.current = onFinal;
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [handsFree, setHF] = useState<HandsFree>(loadHandsFree);
  const [wakeActive, setWakeActive] = useState(false);
  const [conversing, setConversing] = useState(false);
  const [bgTick, setBgTick] = useState(0);
  const conversingRef = useRef(false);
  const replyPending = useRef(false);
  const spokenRef = useRef(""); // lo que ATLAS ha dicho en esta respuesta (para «repite» y el filtro de eco)
  const speakingRef = useRef(false);
  speakingRef.current = speaking;
  const denied = useRef(false);
  const restarts = useRef<number[]>([]);

  const setConv = (v: boolean) => { conversingRef.current = v; setConversing(v); };

  useEffect(() => {
    const sync = () => setHF(loadHandsFree());
    window.addEventListener("atlas-handsfree", sync);
    return () => window.removeEventListener("atlas-handsfree", sync);
  }, []);

  const make = useCallback((continuous: boolean): SpeechRecognitionLike | null => {
    if (!Ctor) return null;
    const rec = new Ctor();
    rec.lang = LANG;
    rec.interimResults = true;
    rec.continuous = continuous;
    return rec;
  }, [Ctor]);

  const pending = useRef(0);
  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    pending.current = 0;
    setSpeaking(false);
  }, [canSpeak]); // eslint-disable-line react-hooks/exhaustive-deps

  const speak = useCallback((text: string) => {
    if (!canSpeak) return;
    pending.current = 0;
    spokenRef.current = text;
    speakText(text, () => setSpeaking(true), () => setSpeaking(false));
  }, [canSpeak]);

  const enqueue = useCallback((text: string) => {
    if (!canSpeak || !text.trim()) return;
    spokenRef.current += " " + text;
    queueSpeech(text, () => { pending.current += 1; setSpeaking(true); }, () => {
      pending.current = Math.max(0, pending.current - 1);
      if (pending.current === 0) setSpeaking(false);
    });
  }, [canSpeak]);

  /** Lo que el usuario dijo por voz: órdenes locales o pregunta para ATLAS. */
  const handleUtterance = useCallback((raw: string) => {
    const text = raw.trim();
    if (!text) return;
    const intent = voiceIntent(text);
    if (intent === "stop") { stopSpeaking(); setConv(false); replyPending.current = false; return; }
    if (intent === "end") { stopSpeaking(); setConv(false); replyPending.current = false; speak("De acuerdo."); return; }
    if (intent === "repeat") {
      const last = spokenRef.current.trim();
      if (last) { replyPending.current = conversingRef.current; speak(last); }
      return;
    }
    if (intent === "slower" || intent === "faster") {
      const rate = Math.min(1.6, Math.max(0.7, loadVoicePrefs().rate + (intent === "slower" ? -0.15 : 0.15)));
      saveVoicePrefs({ rate });
      replyPending.current = conversingRef.current;
      speak(intent === "slower" ? "Vale, hablaré más despacio." : "Vale, hablaré más rápido.");
      return;
    }
    setConv(true);
    replyPending.current = true;
    spokenRef.current = "";
    finalRef.current(text);
  }, [speak, stopSpeaking]);

  const stopBg = useCallback(() => {
    const r = bgRef.current;
    bgRef.current = null;
    setWakeActive(false);
    if (r) { r.onend = null; r.onresult = null; r.onerror = null; r.abort(); }
  }, []);

  const listen = useCallback((followUp = false) => {
    if (!Ctor || recRef.current) return;
    stopBg(); // solo puede haber un reconocedor activo
    stopSpeaking(); // interrumpe a ATLAS si estaba hablando
    const rec = make(false)!;
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
      if (e.error === "no-speech" || e.error === "aborted") return;
      if (e.error === "not-allowed") denied.current = true;
      setError(e.error === "not-allowed" ? "Permiso de micrófono denegado" : `Error de voz: ${e.error}`);
    };
    rec.onend = () => {
      setListening(false);
      setInterim("");
      recRef.current = null;
      // «ATLAS, …» al principio de lo dictado: se quita la palabra de activación
      const lead = /^\W*(?:(?:oye|hey|ey|eh|ok|okay|vale)\W+)?h?[aá]t\s?l[aá]s(?![a-zñ])/i.test(finalText);
      const said = (lead ? afterWake(finalText) ?? "" : finalText).trim();
      if (said) handleUtterance(said);
      else if (followUp) setConv(false); // silencio tras la respuesta → vuelve a esperar «ATLAS»
      setBgTick((t) => t + 1);
    };
    recRef.current = rec;
    setError(null);
    setListening(true);
    rec.start();
  }, [Ctor, make, stopBg, stopSpeaking, handleUtterance]);

  const stopListening = useCallback(() => recRef.current?.stop(), []);

  const endConversation = useCallback(() => { setConv(false); replyPending.current = false; }, []);
  const beginReply = useCallback(() => { spokenRef.current = ""; }, []);

  const setHandsFree = useCallback((p: Partial<HandsFree>) => {
    setHF(saveHandsFree(p));
    if (p.wake) denied.current = false;
  }, []);

  // Conversación continua: al terminar de hablar ATLAS, vuelve a escuchar sin pulsar nada
  useEffect(() => {
    if (!handsFree.continuous || !conversing || busy || speaking || listening || !replyPending.current) return;
    const t = setTimeout(() => {
      if (!replyPending.current || speakingRef.current) return;
      replyPending.current = false;
      listen(true);
    }, 450);
    return () => clearTimeout(t);
  }, [handsFree.continuous, conversing, busy, speaking, listening, listen]);

  // Escucha en segundo plano: palabra de activación y poder interrumpir a ATLAS hablando
  const bgWanted = !!Ctor && !denied.current && !listening && (handsFree.wake || (speaking && conversing));
  useEffect(() => {
    if (!bgWanted) { stopBg(); return; }
    if (bgRef.current || document.visibilityState === "hidden") return;
    const now = Date.now();
    restarts.current = restarts.current.filter((t) => now - t < 10_000);
    if (restarts.current.length > 6) { // el navegador corta sin parar: espera antes de reintentar
      const t = setTimeout(() => { restarts.current = []; setBgTick((x) => x + 1); }, 8000);
      return () => clearTimeout(t);
    }
    restarts.current.push(now);
    const rec = make(true)!;
    let handled = false;
    rec.onresult = (e) => {
      if (handled) return;
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        const heard = r[0].transcript;
        if (speakingRef.current && isEcho(heard, spokenRef.current)) continue; // es la voz de ATLAS
        const w = handsFree.wake || speakingRef.current ? matchWake(heard) : null;
        const stopWord = speakingRef.current && voiceIntent(heard) === "stop";
        const words = w ? w.rest.split(" ").filter(Boolean).length : 0;
        if (speakingRef.current && (w || stopWord)) { // interrumpir a ATLAS mientras habla
          handled = true;
          stopSpeaking();
          stopBg();
          if (stopWord) { setConv(false); replyPending.current = false; setBgTick((t) => t + 1); }
          else if (r.isFinal && words >= 2) handleUtterance(afterWake(heard) || w!.rest);
          else { setConv(true); listen(); } // sigue escuchando lo que dices después de «ATLAS»
          return;
        }
        if (!w || !r.isFinal) continue; // espera al final de la frase
        handled = true;
        stopBg();
        if (words >= 2) handleUtterance(afterWake(heard) || w.rest);
        else { beep(); setConv(true); listen(); }
        return;
      }
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        denied.current = true;
        setError("Permiso de micrófono denegado: «Oye ATLAS» no puede escuchar");
      }
    };
    rec.onend = () => { if (bgRef.current === rec) { bgRef.current = null; setWakeActive(false); setTimeout(() => setBgTick((t) => t + 1), 300); } };
    bgRef.current = rec;
    try { rec.start(); setWakeActive(handsFree.wake); } catch { bgRef.current = null; }
  }, [bgWanted, bgTick, handsFree.wake, make, stopBg, stopSpeaking, handleUtterance, listen]);

  // Al volver a la pestaña, reanuda la escucha
  useEffect(() => {
    const vis = () => { if (document.visibilityState === "visible") setBgTick((t) => t + 1); else stopBg(); };
    document.addEventListener("visibilitychange", vis);
    return () => document.removeEventListener("visibilitychange", vis);
  }, [stopBg]);

  useEffect(() => () => {
    recRef.current?.abort();
    const b = bgRef.current;
    bgRef.current = null;
    b?.abort();
    window.speechSynthesis?.cancel();
  }, [canSpeak]);

  return {
    canListen: !!Ctor, canSpeak, listening, speaking, interim, error, listen: () => listen(false), stopListening, speak, enqueue, stopSpeaking,
    handsFree, setHandsFree, wakeActive, conversing, endConversation, beginReply,
  };
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
