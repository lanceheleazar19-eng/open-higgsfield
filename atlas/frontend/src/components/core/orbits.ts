/** Geometría del sistema solar de VISTAN, compartida por la escena WebGL y la capa HTML de planetas.
 *  Todas las órbitas son concéntricas y coplanarias: así sus proyecciones nunca se cruzan (una transformación
 *  proyectiva conserva que dos curvas no se corten) y los planetas de órbitas distintas no se superponen. */

export type Vec3 = [number, number, number];

export interface Orbit {
  radius: number;
  tiltX: number;
  tiltZ: number;
  speed: number; // rad/s — las interiores giran más rápido, como en un sistema solar real
}

export const ORBITS: Orbit[] = [
  { radius: 2.7, tiltX: 0, tiltZ: 0, speed: 0.085 },
  { radius: 3.95, tiltX: 0, tiltZ: 0, speed: 0.062 },
  { radius: 5.2, tiltX: 0, tiltZ: 0, speed: 0.047 },
  { radius: 6.45, tiltX: 0, tiltZ: 0, speed: 0.036 },
];

export const FOV = 45;
export const DEFAULT_PITCH = 0.66; // elevación de la cámara sobre el plano orbital (rad)
export const NARROW_PITCH = 0.98; // en pantallas estrechas se ve más «desde arriba» para aprovechar la altura
export const pitchFor = (w: number) => (w < 640 ? NARROW_PITCH : DEFAULT_PITCH);

export function orbitPoint(o: Orbit, angle: number): Vec3 {
  const x0 = Math.cos(angle) * o.radius;
  const z0 = Math.sin(angle) * o.radius;
  const y1 = -z0 * Math.sin(o.tiltX);
  const z1 = z0 * Math.cos(o.tiltX);
  const x2 = x0 * Math.cos(o.tiltZ) - y1 * Math.sin(o.tiltZ);
  const y2 = x0 * Math.sin(o.tiltZ) + y1 * Math.cos(o.tiltZ);
  return [x2, y2, z1];
}

/** Rotación de vista: guiñada (Y) y después cabeceo (X), igual que el grupo raíz en three (orden 'XY'). */
export function rotateView([x, y, z]: Vec3, rx: number, ry: number): Vec3 {
  const x1 = x * Math.cos(ry) + z * Math.sin(ry);
  const z1 = -x * Math.sin(ry) + z * Math.cos(ry);
  const y2 = y * Math.cos(rx) - z1 * Math.sin(rx);
  const z2 = y * Math.sin(rx) + z1 * Math.cos(rx);
  return [x1, y2, z2];
}

/** Distancia de cámara para que el sistema completo quepa con margen para planetas y etiquetas. */
export function cameraDistance(aspect: number, narrow = false, pitch = DEFAULT_PITCH): number {
  const halfV = Math.tan(((FOV / 2) * Math.PI) / 180);
  const limX = narrow ? 0.7 : 0.84;
  const limY = narrow ? 0.72 : 0.8;
  const pts: Vec3[] = [];
  for (const o of ORBITS) for (let i = 0; i < 64; i++) pts.push(rotateView(orbitPoint(o, (i / 64) * Math.PI * 2), pitch, 0));
  for (let camZ = 6; camZ < 40; camZ += 0.2) {
    const fits = pts.every(([x, y, z]) => {
      const d = camZ - z;
      return Math.abs(x) / (d * halfV * aspect) <= limX && Math.abs(y) / (d * halfV) <= limY;
    });
    if (fits) return camZ;
  }
  return 40;
}

export function project(p: Vec3, camZ: number, w: number, h: number) {
  const halfV = Math.tan(((FOV / 2) * Math.PI) / 180);
  const dist = Math.max(0.5, camZ - p[2]);
  const ndcX = p[0] / (dist * halfV * (w / h));
  const ndcY = p[1] / (dist * halfV);
  return { x: ((ndcX + 1) / 2) * w, y: ((1 - ndcY) / 2) * h, scale: camZ / dist, depth: p[2] };
}

export function sub(a: Vec3, b: Vec3): Vec3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

export interface Placed { x: number; y: number; r: number; depth: number; scale: number }
export interface View { pitch: number; yaw: number; camZ: number; w: number; h: number; target: Vec3 }
export interface Body { orbit: number; phase: number; size: number }

export function planetRadius(size: number, scale: number, w: number): number {
  return Math.max(24, Math.min(88, (w < 640 ? 30 : 40) * size * scale)) / 2;
}

export function placeAll(defs: Body[], t: number, offsets: number[], v: View): { local: Vec3[]; placed: Placed[] } {
  const local = defs.map((n, i) => orbitPoint(ORBITS[n.orbit], n.phase + t * ORBITS[n.orbit].speed + offsets[i]));
  const placed = local.map((l, i) => {
    const p = project(sub(rotateView(l, v.pitch, v.yaw), v.target), v.camZ, v.w, v.h);
    return { ...p, r: planetRadius(defs[i].size, p.scale, v.w) };
  });
  return { local, placed };
}

/** Evita solapes entre planetas de órbitas distintas: cuando dos se acercan demasiado en pantalla, cada uno se
 *  desplaza un poco a lo largo de SU órbita en el sentido que más los separa (el interior, más rápido, cede más).
 *  Es una relajación local: nunca saca un planeta de su órbita. Modifica `offsets`. */
export function separate(defs: Body[], t: number, offsets: number[], v: View, margin = 6, iters = 12): { local: Vec3[]; placed: Placed[] } {
  let res = placeAll(defs, t, offsets, v);
  const one = (i: number, off: number): Placed => {
    const l = orbitPoint(ORBITS[defs[i].orbit], defs[i].phase + t * ORBITS[defs[i].orbit].speed + off);
    const p = project(sub(rotateView(l, v.pitch, v.yaw), v.target), v.camZ, v.w, v.h);
    return { ...p, r: planetRadius(defs[i].size, p.scale, v.w) };
  };
  const eps = 0.01;
  for (let k = 0; k < iters; k++) {
    let moved = false;
    for (let i = 0; i < defs.length; i++) {
      for (let j = i + 1; j < defs.length; j++) {
        if (defs[i].orbit === defs[j].orbit) continue;
        const a = res.placed[i], b = res.placed[j];
        const gap = Math.hypot(a.x - b.x, a.y - b.y) - a.r - b.r;
        if (gap >= margin) continue;
        moved = true;
        const push = 0.01 * Math.min(4, 1 + (margin - gap) / 10);
        for (const [me, other] of [[i, b], [j, a]] as [number, Placed][]) {
          const d = (o: number) => { const q = one(me, o); return Math.hypot(q.x - other.x, q.y - other.y); };
          const grad = d(offsets[me] + eps) - d(offsets[me] - eps);
          const faster = ORBITS[defs[me].orbit].speed >= ORBITS[defs[me === i ? j : i].orbit].speed;
          offsets[me] += Math.sign(grad || -1) * push * (faster ? 1 : 0.5);
        }
      }
    }
    if (!moved) break;
    res = placeAll(defs, t, offsets, v);
  }
  return res;
}
