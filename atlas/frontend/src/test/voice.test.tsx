import { act, renderHook } from "@testing-library/react";
import { useVoice } from "../hooks/useVoice";

type Res = ArrayLike<{ transcript: string }> & { isFinal: boolean };
class FakeRec {
  static all: FakeRec[] = [];
  lang = ""; interimResults = false; continuous = false; running = false;
  onresult: ((e: { resultIndex: number; results: Res[] }) => void) | null = null;
  onerror: ((e: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  start() { this.running = true; FakeRec.all.push(this); }
  stop() { this.running = false; this.onend?.(); }
  abort() { this.running = false; }
  say(text: string, isFinal = true) { this.onresult?.({ resultIndex: 0, results: [Object.assign([{ transcript: text }], { isFinal })] }); }
}
const live = () => FakeRec.all.filter((r) => r.running);

beforeEach(() => {
  FakeRec.all = [];
  vi.stubGlobal("webkitSpeechRecognition", FakeRec);
  vi.stubGlobal("SpeechSynthesisUtterance", class { constructor(public text: string) {} onend?: () => void; onstart?: () => void });
  vi.stubGlobal("speechSynthesis", { speak: vi.fn(), cancel: vi.fn(), getVoices: () => [{ name: "Mónica", lang: "es-ES", voiceURI: "m", localService: true }],
    addEventListener: vi.fn(), removeEventListener: vi.fn() });
  localStorage.setItem("atlas.handsfree", JSON.stringify({ wake: true, continuous: true }));
});
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });

test("«Oye VISTAN, …» en una frase envía la pregunta sin la palabra de activación", () => {
  const onFinal = vi.fn();
  const { result } = renderHook(() => useVoice(onFinal));
  expect(result.current.wakeActive).toBe(true);
  const bg = live()[0];
  expect(bg.continuous).toBe(true);
  act(() => bg.say("me voy a la ducha")); // sin «VISTAN»: se ignora
  expect(onFinal).not.toHaveBeenCalled();
  act(() => bg.say("Oye VISTAN, ¿qué tengo mañana?"));
  expect(onFinal).toHaveBeenCalledWith("¿qué tengo mañana?");
  expect(result.current.conversing).toBe(true);
});

test("solo «VISTAN» abre el micrófono y lo siguiente va a VISTAN; «repite» se resuelve en local", () => {
  const onFinal = vi.fn();
  const { result } = renderHook(() => useVoice(onFinal));
  act(() => live()[0].say("atlas"));
  const fg = live().find((r) => !r.continuous)!;
  expect(fg).toBeTruthy();
  expect(result.current.listening).toBe(true);
  act(() => { fg.say("apúntame comprar creatina"); fg.stop(); });
  expect(onFinal).toHaveBeenCalledWith("apúntame comprar creatina");
  act(() => result.current.enqueue("Hecho, apuntado."));
  act(() => result.current.listen());
  const fg2 = live().find((r) => !r.continuous)!;
  act(() => { fg2.say("repite"); fg2.stop(); });
  expect(onFinal).toHaveBeenCalledTimes(1);
});

test("con «Oye VISTAN» apagado no se escucha en segundo plano", () => {
  localStorage.setItem("atlas.handsfree", JSON.stringify({ wake: false, continuous: true }));
  const { result } = renderHook(() => useVoice(vi.fn()));
  expect(result.current.wakeActive).toBe(false);
  expect(live()).toHaveLength(0);
});

test("llamada: escucha, responde, vuelve a escuchar sola y se interrumpe hablando", () => {
  vi.useFakeTimers();
  localStorage.setItem("atlas.handsfree", JSON.stringify({ wake: false, continuous: false }));
  const utters: { text: string; onend?: () => void }[] = [];
  vi.stubGlobal("speechSynthesis", { speak: (u: { text: string }) => utters.push(u), cancel: vi.fn(),
    getVoices: () => [{ name: "Mónica", lang: "es-ES", voiceURI: "m", localService: true }], addEventListener: vi.fn(), removeEventListener: vi.fn() });
  const onFinal = vi.fn();
  let busy = false;
  const { result, rerender } = renderHook(() => useVoice(onFinal, busy));
  act(() => result.current.startCall());
  expect(result.current.inCall).toBe(true);
  const fg = live().find((r) => !r.continuous)!;
  act(() => { fg.say("¿qué tengo hoy?"); fg.stop(); });
  expect(onFinal).toHaveBeenCalledWith("¿qué tengo hoy?");
  // VISTAN responde (la voz cuenta como «hablando» desde que se encola)
  busy = true; rerender();
  act(() => result.current.enqueue("Tienes dos tareas pendientes y una reunión a las cinco de la tarde."));
  busy = false; rerender();
  expect(result.current.speaking).toBe(true);
  // Interrumpir hablando (no hace falta decir «VISTAN»)
  act(() => { vi.advanceTimersByTime(50); });
  const bg = live().find((r) => r.continuous)!;
  expect(bg).toBeTruthy();
  act(() => bg.say("espera una cosa más", false));
  expect(result.current.speaking).toBe(false);
  const fg2 = live().find((r) => !r.continuous)!;
  act(() => { fg2.say("pon la reunión a las seis"); fg2.stop(); });
  expect(onFinal).toHaveBeenLastCalledWith("espera una cosa más pon la reunión a las seis");
  // Silencio: la llamada sigue y el micrófono se vuelve a abrir solo
  const fg3Before = FakeRec.all.length;
  act(() => { vi.advanceTimersByTime(600); });
  const fg3 = live().find((r) => !r.continuous);
  if (fg3) act(() => fg3.stop());
  act(() => { vi.advanceTimersByTime(600); });
  expect(FakeRec.all.length).toBeGreaterThan(fg3Before);
  expect(result.current.inCall).toBe(true);
  act(() => result.current.endCall());
  expect(result.current.inCall).toBe(false);
  vi.useRealTimers();
});
