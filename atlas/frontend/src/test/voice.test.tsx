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
