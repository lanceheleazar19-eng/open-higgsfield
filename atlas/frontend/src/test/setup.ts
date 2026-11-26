import "@testing-library/jest-dom/vitest";

// La pantalla de arranque se prueba aparte; en el resto de pruebas se entra directamente.
beforeEach(() => { try { localStorage.setItem("atlas.welcome", "0"); } catch { /* */ } });

// jsdom no implementa matchMedia; lightweight-charts lo usa al redibujar en un frame posterior al test.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) => ({ matches: false, media: query, onchange: null, addListener: () => {}, removeListener: () => {},
    addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false }) as MediaQueryList;
}
