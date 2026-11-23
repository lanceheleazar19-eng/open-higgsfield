import "@testing-library/jest-dom/vitest";

// La pantalla de arranque se prueba aparte; en el resto de pruebas se entra directamente.
beforeEach(() => { try { localStorage.setItem("atlas.welcome", "0"); } catch { /* */ } });
