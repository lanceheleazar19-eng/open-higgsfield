import { cleanForSpeech, pickVoice, speechChunks, spanishVoices, voiceScore } from "../lib/speech";

const v = (name: string, lang = "es-ES") => ({ name, lang, voiceURI: name, localService: true });

test("prioriza voces de calidad y nunca elige voces de efectos", () => {
  const voices = [v("Eddy (Spanish (Spain))"), v("Monica"), v("Grandpa (Spanish (Mexico))", "es-MX"),
    v("Google español"), v("Samantha", "en-US"), v("Mónica (Mejorada)")];
  expect(spanishVoices(voices)[0].name).toBe("Mónica (Mejorada)");
  expect(pickVoice(voices, null)!.name).toBe("Mónica (Mejorada)");
  expect(pickVoice([v("Eddy (Spanish (Spain))"), v("Monica")], null)!.name).toBe("Monica");
  expect(voiceScore(v("Grandpa (Spanish (Mexico))", "es-MX"))).toBeLessThan(0);
  expect(pickVoice(voices, "Google español")!.name).toBe("Google español"); // la elegida por el usuario manda
  expect(spanishVoices(voices).some((x) => x.lang === "en-US")).toBe(false);
});

test("limpia el texto y lo trocea en frases cortas", () => {
  expect(cleanForSpeech("**Hola** • «ATLAS»\n- uno")).toBe("Hola ATLAS uno");
  const long = "Primera frase. " + "palabra ".repeat(60) + "fin. Última.";
  const chunks = speechChunks(long, 180);
  expect(chunks.every((c) => c.length <= 181)).toBe(true);
  expect(chunks.join(" ")).toContain("Primera frase.");
  expect(chunks[chunks.length - 1]).toContain("Última.");
});
