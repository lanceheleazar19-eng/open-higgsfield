import { NODE_DEFS } from "../components/core/nodes";
import { ORBITS, cameraDistance, pitchFor, separate } from "../components/core/orbits";
/** Recorre un ciclo orbital completo en muchos tamaños de pantalla y ángulos de cámara: los planetas de órbitas
 *  distintas nunca se acercan más que el margen de seguridad (ni sus halos se tocan). */
test("planetas: nunca se solapan en ningún tamaño de pantalla", () => {
  const out: string[] = [];
  for (const w of [340, 390, 700, 1100]) for (const h of [330, 460, 720]) {
    const m = w < 640 ? 16 : 10;
    const pitch = pitchFor(w), camZ = cameraDistance(w / h, w < 640, pitch);
    let worst = 1e9;
    for (const yaw of [0, 1.3]) {
      const off = NODE_DEFS.map(() => 0);
      const period = (Math.PI * 2) / Math.min(...ORBITS.map((o) => o.speed));
      for (let s = 0; s < 1500; s++) { const t = (s / 1500) * period;
        const P = separate(NODE_DEFS, t, off, { pitch, yaw, camZ, w, h, target: [0, 0, 0] }, m, 80).placed;
        for (let i = 0; i < NODE_DEFS.length; i++) for (let j = i + 1; j < NODE_DEFS.length; j++) worst = Math.min(worst, Math.hypot(P[i].x - P[j].x, P[i].y - P[j].y) - P[i].r - P[j].r); }
    }
    if (worst < m - 4) out.push(`${w}x${h} m=${m} worst=${worst.toFixed(1)}`);
  }
  expect(out).toEqual([]);
});
