import { afterEach, describe, expect, it, vi } from "vitest";
import { speakText } from "../hooks/useVoice";
import { saveEngine, VS_WAIT_MS } from "../lib/voicestudio";

const flush = () => new Promise((r) => setTimeout(r, 20));

describe("voz con VoiceStudio", () => {
  afterEach(() => { vi.restoreAllMocks(); localStorage.clear(); });

  it("pide el audio a VISTAN y lo reproduce", async () => {
    saveEngine({ engine: "voicestudio", vsVoice: "p1" });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, blob: async () => new Blob(["mp3"]) } as unknown as Response);
    globalThis.URL.createObjectURL = vi.fn(() => "blob:x");
    globalThis.URL.revokeObjectURL = vi.fn();
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (this: HTMLMediaElement) {
      setTimeout(() => this.onended?.(new Event("ended")), 0);
      return Promise.resolve();
    });
    const onStart = vi.fn(); const onEnd = vi.fn();
    speakText("Hola.", onStart, onEnd);
    await flush(); await flush();
    expect(fetchMock).toHaveBeenCalledWith("/api/voicestudio/speak", expect.objectContaining({ method: "POST" }));
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string);
    expect(body).toMatchObject({ text: "Hola.", voice: "p1", language: "es" });
    expect(play).toHaveBeenCalled();
    expect(onStart).toHaveBeenCalledTimes(1);
    expect(onEnd).toHaveBeenCalledTimes(1);
  });

  it("si VoiceStudio no responde, usa la voz del navegador", async () => {
    saveEngine({ engine: "voicestudio" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 503 }));
    const spoken: string[] = [];
    (window as unknown as { speechSynthesis: unknown }).speechSynthesis = {
      cancel: vi.fn(), getVoices: () => [{ name: "Mónica", lang: "es-ES", voiceURI: "m", localService: true }],
      speak: (u: { text: string }) => spoken.push(u.text), addEventListener: vi.fn(), removeEventListener: vi.fn(),
    };
    (globalThis as unknown as { SpeechSynthesisUtterance: unknown }).SpeechSynthesisUtterance ??= class { constructor(public text: string) {} };
    speakText("Respaldo.");
    await flush(); await flush();
    expect(spoken).toEqual(["Respaldo."]);
  });

  it("si VoiceStudio tarda demasiado, esa respuesta sigue con la voz del navegador", async () => {
    vi.useFakeTimers();
    saveEngine({ engine: "voicestudio" });
    vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise(() => undefined));
    const spoken: string[] = [];
    (window as unknown as { speechSynthesis: unknown }).speechSynthesis = {
      cancel: vi.fn(), getVoices: () => [{ name: "Mónica", lang: "es-ES", voiceURI: "m", localService: true }],
      speak: (u: { text: string }) => spoken.push(u.text), addEventListener: vi.fn(), removeEventListener: vi.fn(),
    };
    speakText("Primera frase. Segunda frase.");
    await vi.advanceTimersByTimeAsync(VS_WAIT_MS + 500);
    expect(spoken.join(" ")).toContain("Primera frase.");
    vi.useRealTimers();
  });

  it("si ya empezó a hablar con VoiceStudio, no cambia a otra voz a mitad de respuesta", async () => {
    vi.useFakeTimers();
    saveEngine({ engine: "voicestudio" });
    let n = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(() => (++n === 1
      ? Promise.resolve({ ok: true, blob: async () => new Blob(["a"]) } as unknown as Response)
      : new Promise(() => undefined)));
    globalThis.URL.createObjectURL = vi.fn(() => "blob:x");
    globalThis.URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (this: HTMLMediaElement) {
      setTimeout(() => this.onended?.(new Event("ended")), 10);
      return Promise.resolve();
    });
    const spoken: string[] = [];
    (window as unknown as { speechSynthesis: unknown }).speechSynthesis = {
      cancel: vi.fn(), getVoices: () => [], speak: (u: { text: string }) => spoken.push(u.text), addEventListener: vi.fn(), removeEventListener: vi.fn(),
    };
    speakText("Primera frase completa aquí. " + "Segunda frase bastante larga para que vaya en otro trozo. ".repeat(8));
    await vi.advanceTimersByTimeAsync(VS_WAIT_MS * 3);
    expect(spoken).toEqual([]);
    vi.useRealTimers();
  });
});
