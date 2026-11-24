import { afterWake, isEcho, matchWake, voiceIntent } from "../lib/wake";

test("detecta la palabra de activación y lo que viene después", () => {
  expect(matchWake("Oye ATLAS, ¿qué tengo hoy?")).toEqual({ rest: "que tengo hoy" });
  expect(matchWake("Atlas")).toEqual({ rest: "" });
  expect(matchWake("Hola ATLAS, ¿qué tal?")).toEqual({ rest: "que tal" });
  expect(matchWake("hey hatlas apunta comprar leche")?.rest).toBe("apunta comprar leche");
  expect(matchWake("at las cuánto he gastado")?.rest).toBe("cuanto he gastado");
  expect(matchWake("el atlas de geografía")?.rest).toBe("de geografia");
  expect(matchWake("¿qué tal el día?")).toBeNull();
  expect(matchWake("atlántico")).toBeNull();
});

test("órdenes de voz locales solo con frases cortas", () => {
  expect(voiceIntent("Para")).toBe("stop");
  expect(voiceIntent("cállate ya")).toBe("stop");
  expect(voiceIntent("Eso es todo, ATLAS")).toBe("end");
  expect(voiceIntent("¿Repite?")).toBe("repeat");
  expect(voiceIntent("habla más despacio")).toBe("slower");
  expect(voiceIntent("más rápido por favor")).toBe("faster");
  expect(voiceIntent("para mañana apunta ir al gimnasio")).toBeNull();
  expect(voiceIntent("gracias por ayudarme con el plan")).toBeNull();
});

test("filtra el eco de la propia voz de ATLAS", () => {
  const spoken = "Hoy tienes dos tareas pendientes y entrenas espalda y bíceps a las seis.";
  expect(isEcho("tienes dos tareas pendientes", spoken)).toBe(true);
  expect(isEcho("entrenas espalda y biceps a las", spoken)).toBe(true);
  expect(isEcho("para", spoken)).toBe(false);
  expect(isEcho("qué tiempo hace mañana en Madrid", spoken)).toBe(false);
});

test("afterWake conserva tildes y mayúsculas", () => {
  expect(afterWake("Oye ATLAS, ¿qué tengo mañana?")).toBe("¿qué tengo mañana?");
  expect(afterWake("Átlas apúntame ir al médico")).toBe("apúntame ir al médico");
  expect(afterWake("qué tal")).toBeNull();
});

test("palmadas: solo golpes secos muy por encima del ruido de fondo", async () => {
  const { detectTransient } = await import("../lib/clap");
  expect(detectTransient(0.6, 0.02)).toBe(true);
  expect(detectTransient(0.2, 0.02)).toBe(false);
  expect(detectTransient(0.5, 0.15)).toBe(false);
});
