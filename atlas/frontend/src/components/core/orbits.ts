/** Geometría orbital compartida por la escena WebGL y la capa HTML de nodos.
 *  Ambas usan exactamente la misma proyección para que los nodos (HTML, nítidos
 *  y pulsables) queden alineados con las líneas de energía dibujadas en WebGL. */

export type Vec3 = [number, number, number];

export interface Orbit {
  radius: number;
  tiltX: number; // inclinación del plano orbital (rad)
  tiltZ: number;
  speed: number; // rad/s — igual en todas: el sistema gira como un conjunto y los nodos nunca se amontonan
}

export const ORBITS: Orbit[] = [
  { radius: 2.4, tiltX: 0.66, tiltZ: 0.2, speed: 0.04 },
  { radius: 3.1, tiltX: 0.56, tiltZ: -0.16, speed: 0.04 },
  { radius: 3.8, tiltX: 0.47, tiltZ: 0.06, speed: 0.04 },
];

export const FOV = 45;

export function orbitPoint(o: Orbit, angle: number): Vec3 {
  const x0 = Math.cos(angle) * o.radius;
  const z0 = Math.sin(angle) * o.radius;
  // rotación sobre X
  const y1 = -z0 * Math.sin(o.tiltX);
  const z1 = z0 * Math.cos(o.tiltX);
  // rotación sobre Z
  const x2 = x0 * Math.cos(o.tiltZ) - y1 * Math.sin(o.tiltZ);
  const y2 = x0 * Math.sin(o.tiltZ) + y1 * Math.cos(o.tiltZ);
  return [x2, y2, z1];
}

/** Rotación de vista (paralaje del cursor): Y y luego X, igual que el grupo raíz en three (orden 'XY'). */
export function rotateView([x, y, z]: Vec3, rx: number, ry: number): Vec3 {
  const x1 = x * Math.cos(ry) + z * Math.sin(ry);
  const z1 = -x * Math.sin(ry) + z * Math.cos(ry);
  const y2 = y * Math.cos(rx) - z1 * Math.sin(rx);
  const z2 = y * Math.sin(rx) + z1 * Math.cos(rx);
  return [x1, y2, z2];
}

/** Distancia de cámara mínima para que todas las órbitas quepan, teniendo en cuenta la
 *  perspectiva (los nodos cercanos se ven más separados). `narrow`: etiquetas hacia dentro. */
export function cameraDistance(aspect: number, narrow = false): number {
  const halfV = Math.tan(((FOV / 2) * Math.PI) / 180);
  const limX = narrow ? 0.86 : 0.9; // fracción del semiancho utilizable (las etiquetas del borde derecho giran hacia dentro)
  const limY = narrow ? 0.8 : 0.74;
  const pts: Vec3[] = [];
  for (const o of ORBITS) for (let i = 0; i < 48; i++) pts.push(orbitPoint(o, (i / 48) * Math.PI * 2));
  for (let camZ = 7; camZ < 30; camZ += 0.2) {
    const fits = pts.every(([x, y, z]) => {
      const d = camZ - z;
      return Math.abs(x) / (d * halfV * aspect) <= limX && Math.abs(y) / (d * halfV) <= limY;
    });
    if (fits) return camZ;
  }
  return 30;
}

export function project(p: Vec3, camZ: number, w: number, h: number) {
  const halfV = Math.tan(((FOV / 2) * Math.PI) / 180);
  const dist = camZ - p[2];
  const ndcX = p[0] / (dist * halfV * (w / h));
  const ndcY = p[1] / (dist * halfV);
  return { x: ((ndcX + 1) / 2) * w, y: ((1 - ndcY) / 2) * h, scale: camZ / dist, depth: p[2] };
}
