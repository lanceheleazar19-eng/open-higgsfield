import { afterEach, describe, expect, it, vi } from "vitest";
import { speakText } from "../hooks/useVoice";
import { saveEngine } from "../lib/voicestudio";

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
});
