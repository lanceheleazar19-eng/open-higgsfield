/** Escena WebGL del núcleo de ATLAS (three.js, cargado bajo demanda).
 *
 *  Núcleo neuronal (esfera de neuronas + sinapsis), anillos giroscópicos,
 *  órbitas, campo de partículas y líneas de energía hacia cada módulo con
 *  pulsos de datos. Todo con mezcla aditiva para el efecto holográfico. */
import * as THREE from "three";
import { ORBITS, orbitPoint, type Vec3 } from "./orbits";

export type CoreState = "idle" | "listening" | "thinking" | "researching" | "executing" | "speaking" | "responding" | "error";

interface StateLook {
  color: THREE.Color;
  accent: THREE.Color;
  spin: number; // multiplicador de rotación
  sparks: number; // sinapsis por segundo
  pulseSpeed: number; // velocidad de los pulsos de datos
  pulseDir: 1 | -1; // 1: hacia el núcleo (recibe), -1: hacia los módulos (responde)
  glow: number;
}

const LOOKS: Record<CoreState, StateLook> = {
  idle: { color: new THREE.Color("#b51224"), accent: new THREE.Color("#e11d35"), spin: 1, sparks: 18, pulseSpeed: 0.16, pulseDir: 1, glow: 0.95 },
  listening: { color: new THREE.Color("#e11d35"), accent: new THREE.Color("#ffc2c9"), spin: 1.4, sparks: 45, pulseSpeed: 0.35, pulseDir: 1, glow: 1.25 },
  thinking: { color: new THREE.Color("#e11d35"), accent: new THREE.Color("#ffffff"), spin: 4, sparks: 170, pulseSpeed: 0.9, pulseDir: 1, glow: 1.55 },
  researching: { color: new THREE.Color("#b51224"), accent: new THREE.Color("#ff8f9b"), spin: 2.6, sparks: 120, pulseSpeed: 1.1, pulseDir: -1, glow: 1.4 },
  executing: { color: new THREE.Color("#e11d35"), accent: new THREE.Color("#ffffff"), spin: 3.2, sparks: 140, pulseSpeed: 1.3, pulseDir: -1, glow: 1.6 },
  speaking: { color: new THREE.Color("#e11d35"), accent: new THREE.Color("#ffd0d5"), spin: 1.8, sparks: 70, pulseSpeed: 0.7, pulseDir: -1, glow: 1.35 },
  responding: { color: new THREE.Color("#e11d35"), accent: new THREE.Color("#ffd0d5"), spin: 2, sparks: 75, pulseSpeed: 0.7, pulseDir: -1, glow: 1.35 },
  error: { color: new THREE.Color("#650b19"), accent: new THREE.Color("#e11d35"), spin: 0.35, sparks: 6, pulseSpeed: 0.08, pulseDir: 1, glow: 0.7 },
};

export interface FrameInput {
  dt: number;
  time: number;
  rx: number;
  ry: number;
  camZ: number;
  nodePositions: Vec3[]; // espacio local (antes de la rotación de vista)
  hovered: number;
}

export interface AtlasScene {
  render(f: FrameInput): void;
  resize(w: number, h: number, camZ: number): void;
  setState(s: CoreState): void;
  ripple(): void;
  dispose(): void;
}

function dotTexture(): THREE.Texture {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.25, "rgba(255,255,255,0.8)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c);
  return t;
}

function fibonacciSphere(n: number, r: number): Float32Array {
  const out = new Float32Array(n * 3);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const y = 1 - (i / (n - 1)) * 2;
    const rad = Math.sqrt(1 - y * y);
    const th = golden * i;
    const jitter = r * (0.94 + Math.random() * 0.12);
    out[i * 3] = Math.cos(th) * rad * jitter;
    out[i * 3 + 1] = y * jitter;
    out[i * 3 + 2] = Math.sin(th) * rad * jitter;
  }
  return out;
}

/** Une cada neurona con sus k vecinas más cercanas (conectoma). */
function neighbourLinks(pos: Float32Array, k: number): Float32Array {
  const n = pos.length / 3;
  const segs: number[] = [];
  const seen = new Set<string>();
  for (let i = 0; i < n; i++) {
    const best: [number, number][] = [];
    for (let j = 0; j < n; j++) {
      if (i === j) continue;
      const dx = pos[i * 3] - pos[j * 3], dy = pos[i * 3 + 1] - pos[j * 3 + 1], dz = pos[i * 3 + 2] - pos[j * 3 + 2];
      const d = dx * dx + dy * dy + dz * dz;
      if (best.length < k) { best.push([d, j]); best.sort((a, b) => a[0] - b[0]); }
      else if (d < best[k - 1][0]) { best[k - 1] = [d, j]; best.sort((a, b) => a[0] - b[0]); }
    }
    for (const [, j] of best) {
      const key = i < j ? `${i}-${j}` : `${j}-${i}`;
      if (seen.has(key)) continue;
      seen.add(key);
      segs.push(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2], pos[j * 3], pos[j * 3 + 1], pos[j * 3 + 2]);
    }
  }
  return new Float32Array(segs);
}

export function createScene(canvas: HTMLCanvasElement, nodeColors: string[], opts: { lite: boolean }): AtlasScene {
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, opts.lite ? 1.25 : 1.75));
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 9);

  const tex = dotTexture();
  const disposables: { dispose(): void }[] = [tex];
  const track = <T extends { dispose(): void }>(o: T) => (disposables.push(o), o);
  const additive = { transparent: true, depthWrite: false, blending: THREE.AdditiveBlending } as const;

  const root = new THREE.Group();
  scene.add(root);

  // ---------------- Núcleo ----------------
  const core = new THREE.Group();
  root.add(core);

  const halo = new THREE.Sprite(track(new THREE.SpriteMaterial({ map: tex, color: 0xe3192d, opacity: 0.55, ...additive })));
  halo.scale.setScalar(4.6);
  core.add(halo);
  const heart = new THREE.Sprite(track(new THREE.SpriteMaterial({ map: tex, color: 0xffc2c8, opacity: 0.9, ...additive })));
  heart.scale.setScalar(1.5);
  core.add(heart);

  const N = opts.lite ? 520 : 950;
  const neuronPos = fibonacciSphere(N, 1.08);
  const neuronGeo = track(new THREE.BufferGeometry());
  neuronGeo.setAttribute("position", new THREE.BufferAttribute(neuronPos, 3));
  const colors = new Float32Array(N * 3);
  const spark = new Float32Array(N); // brillo extra que decae
  neuronGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const neuronMat = track(new THREE.PointsMaterial({ size: 0.075, map: tex, vertexColors: true, opacity: 0.95, ...additive }));
  const neurons = new THREE.Points(neuronGeo, neuronMat);
  core.add(neurons);

  const linkGeo = track(new THREE.BufferGeometry());
  linkGeo.setAttribute("position", new THREE.BufferAttribute(neighbourLinks(neuronPos, 2), 3));
  const linkMat = track(new THREE.LineBasicMaterial({ color: 0xe3192d, opacity: 0.22, ...additive }));
  core.add(new THREE.LineSegments(linkGeo, linkMat));

  const shell = new THREE.LineSegments(
    track(new THREE.WireframeGeometry(track(new THREE.IcosahedronGeometry(1.42, 1)))),
    track(new THREE.LineBasicMaterial({ color: 0xff5a66, opacity: 0.1, ...additive })),
  );
  root.add(shell);

  // Anillos giroscópicos alrededor del núcleo
  const gyroMat = track(new THREE.LineBasicMaterial({ color: 0xff3346, opacity: 0.4, ...additive }));
  const gyros: THREE.LineLoop[] = [];
  for (const [r, rx, rz] of [[1.7, 1.2, 0.3], [1.9, 0.4, -0.9], [2.05, -0.7, 0.5]] as const) {
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i < 128; i++) {
      const a = (i / 128) * Math.PI * 2;
      // arco incompleto: da sensación de instrumento
      if (i % 32 > 26) continue;
      pts.push(new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, 0));
    }
    const ring = new THREE.LineLoop(track(new THREE.BufferGeometry().setFromPoints(pts)), gyroMat);
    ring.rotation.set(rx, 0, rz);
    root.add(ring);
    gyros.push(ring);
  }

  // ---------------- Plataforma holográfica ----------------
  const platform = new THREE.Group();
  platform.position.y = -2.2;
  const platMats: THREE.MeshBasicMaterial[] = [];
  [[0.8, 0.88, 0.55], [1.3, 1.35, 0.4], [1.9, 1.94, 0.3], [2.6, 2.63, 0.2], [3.3, 3.32, 0.12]].forEach(([r1, r2, op]) => {
    const m = track(new THREE.MeshBasicMaterial({ color: 0xff2e42, opacity: op, side: THREE.DoubleSide, ...additive }));
    platMats.push(m);
    const ring = new THREE.Mesh(track(new THREE.RingGeometry(r1, r2, 128)), m);
    ring.rotation.x = -Math.PI / 2;
    platform.add(ring);
  });
  const disc = new THREE.Mesh(track(new THREE.CircleGeometry(0.9, 64)),
    track(new THREE.MeshBasicMaterial({ map: tex, color: 0xff2e42, opacity: 0.55, ...additive })));
  disc.rotation.x = -Math.PI / 2;
  platform.add(disc);
  // haz vertical de luz
  const beam = new THREE.Mesh(track(new THREE.CylinderGeometry(0.5, 0.95, 1.6, 48, 1, true)),
    track(new THREE.MeshBasicMaterial({ color: 0xff2e42, opacity: 0.035, side: THREE.DoubleSide, ...additive })));
  beam.position.y = 0.8;
  platform.add(beam);
  root.add(platform);

  // ---------------- Órbitas ----------------
  const orbitMat = track(new THREE.LineBasicMaterial({ color: 0xd4142a, opacity: 0.2, ...additive }));
  for (const o of ORBITS) {
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i < 192; i++) pts.push(new THREE.Vector3(...orbitPoint(o, (i / 192) * Math.PI * 2)));
    root.add(new THREE.LineLoop(track(new THREE.BufferGeometry().setFromPoints(pts)), orbitMat));
  }

  // ---------------- Campo de partículas ----------------
  const P = opts.lite ? 380 : 900;
  const fieldPos = new Float32Array(P * 3);
  for (let i = 0; i < P; i++) {
    const r = 2.2 + Math.pow(Math.random(), 0.7) * 7;
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    fieldPos[i * 3] = r * Math.sin(ph) * Math.cos(th);
    fieldPos[i * 3 + 1] = r * Math.cos(ph) * 0.6;
    fieldPos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
  }
  const fieldGeo = track(new THREE.BufferGeometry());
  fieldGeo.setAttribute("position", new THREE.BufferAttribute(fieldPos, 3));
  const fieldMat = track(new THREE.PointsMaterial({ size: 0.04, map: tex, color: 0xff7f8a, opacity: 0.55, ...additive }));
  const field = new THREE.Points(fieldGeo, fieldMat);
  root.add(field);

  // ---------------- Conexiones a módulos + pulsos ----------------
  const links = nodeColors.map((c) => {
    const geo = track(new THREE.BufferGeometry());
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3));
    const mat = track(new THREE.LineBasicMaterial({ color: new THREE.Color(c), opacity: 0.18, ...additive }));
    const line = new THREE.Line(geo, mat);
    root.add(line);
    const pulseMat = track(new THREE.SpriteMaterial({ map: tex, color: new THREE.Color(c), opacity: 0.9, ...additive }));
    const pulse = new THREE.Sprite(pulseMat);
    pulse.scale.setScalar(0.16);
    root.add(pulse);
    const planet = new THREE.Sprite(track(new THREE.SpriteMaterial({ map: tex, color: new THREE.Color(c), opacity: 0.35, ...additive })));
    planet.scale.setScalar(0.6);
    root.add(planet);
    return { geo, mat, pulse, planet, t: Math.random() };
  });

  // Onda expansiva al recibir una consulta (mira siempre a cámara: fuera de root)
  const rippleMat = track(new THREE.MeshBasicMaterial({ color: 0xff6b78, opacity: 0, side: THREE.DoubleSide, ...additive }));
  const rippleMesh = new THREE.Mesh(track(new THREE.RingGeometry(0.992, 1, 128)), rippleMat);
  scene.add(rippleMesh);
  let rippleT = -1;

  let state: CoreState = "idle";
  const col = LOOKS.idle.color.clone();
  const acc = LOOKS.idle.accent.clone();
  let spin = 1, sparks = 18, pulseSpeed = 0.18, glow = 1;
  const tmpA = new THREE.Vector3(), tmpB = new THREE.Vector3();

  function render(f: FrameInput) {
    const L = LOOKS[state];
    const k = Math.min(1, f.dt * 2.5); // transición suave entre estados
    col.lerp(L.color, k);
    acc.lerp(L.accent, k);
    spin += (L.spin - spin) * k;
    sparks += (L.sparks - sparks) * k;
    pulseSpeed += (L.pulseSpeed - pulseSpeed) * k;
    glow += (L.glow - glow) * k;

    root.rotation.set(f.rx, f.ry, 0);
    core.rotation.y += f.dt * 0.12 * spin;
    core.rotation.x = Math.sin(f.time * 0.15) * 0.2;
    shell.rotation.y -= f.dt * 0.06 * spin;
    shell.rotation.z += f.dt * 0.03 * spin;
    gyros.forEach((g, i) => { g.rotation.z += f.dt * (0.15 + i * 0.07) * spin * (i % 2 ? -1 : 1); });
    field.rotation.y += f.dt * 0.012 * spin;
    platform.rotation.y += f.dt * 0.05 * spin;
    platMats.forEach((m, i) => { m.color.copy(col); m.opacity = (0.5 - i * 0.09) * (0.8 + 0.2 * Math.sin(f.time * 1.5 - i)) * glow; });

    const breathe = 1 + Math.sin(f.time * (state === "listening" ? 5 : 1.6)) * (state === "listening" ? 0.06 : 0.03);
    halo.scale.setScalar(4.6 * breathe * glow);
    heart.scale.setScalar(1.5 * breathe * (0.9 + glow * 0.1));
    (halo.material as THREE.SpriteMaterial).color.copy(col);
    (heart.material as THREE.SpriteMaterial).color.copy(acc).lerp(col, 0.4);
    linkMat.color.copy(col);
    linkMat.opacity = 0.16 + 0.1 * (glow - 1);
    gyroMat.color.copy(acc).lerp(col, 0.5);

    // Sinapsis: chispas aleatorias que decaen
    const fire = sparks * f.dt;
    const count = Math.floor(fire) + (Math.random() < fire % 1 ? 1 : 0);
    for (let s = 0; s < count; s++) spark[(Math.random() * N) | 0] = 1;
    const decay = Math.exp(-f.dt * 3.5);
    for (let i = 0; i < N; i++) {
      spark[i] *= decay;
      const base = 0.55 + 0.25 * Math.sin(i * 12.9898 + f.time * 0.8);
      const s = spark[i];
      colors[i * 3] = col.r * base * (1 - s) + acc.r * s * 1.6;
      colors[i * 3 + 1] = col.g * base * (1 - s) + acc.g * s * 1.6;
      colors[i * 3 + 2] = col.b * base * (1 - s) + acc.b * s * 1.6;
    }
    neuronGeo.attributes.color.needsUpdate = true;

    // Líneas de energía y pulsos de datos
    links.forEach((l, i) => {
      const p = f.nodePositions[i];
      if (!p) return;
      tmpB.set(p[0], p[1], p[2]);
      tmpA.copy(tmpB).normalize().multiplyScalar(1.25);
      const arr = l.geo.attributes.position.array as Float32Array;
      arr[0] = tmpA.x; arr[1] = tmpA.y; arr[2] = tmpA.z;
      arr[3] = tmpB.x; arr[4] = tmpB.y; arr[5] = tmpB.z;
      l.geo.attributes.position.needsUpdate = true;
      const hot = f.hovered === i;
      l.mat.opacity += ((hot ? 0.85 : 0.14 + (glow - 1) * 0.25) - l.mat.opacity) * Math.min(1, f.dt * 8);
      l.t = (l.t + f.dt * pulseSpeed * (hot ? 2.2 : 1)) % 1;
      const t = L.pulseDir === 1 ? 1 - l.t : l.t;
      l.pulse.position.lerpVectors(tmpA, tmpB, t);
      l.pulse.material.opacity = Math.sin(l.t * Math.PI) * (hot ? 1 : 0.8);
      l.planet.position.copy(tmpB);
      l.planet.material.opacity = hot ? 0.45 : 0.12;
    });

    if (rippleT >= 0) {
      rippleT += f.dt;
      const p = rippleT / 1.4;
      rippleMesh.scale.setScalar(1.2 + p * 3.8);
      rippleMat.opacity = Math.max(0, 0.9 * (1 - p) * (1 - p));
      rippleMat.color.copy(acc);
      if (p >= 1) { rippleT = -1; rippleMat.opacity = 0; }
    }

    camera.position.z = f.camZ;
    renderer.render(scene, camera);
  }

  return {
    render,
    resize(w, h, camZ) {
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.position.z = camZ;
      camera.updateProjectionMatrix();
    },
    setState(s) { state = s; },
    ripple() { rippleT = 0; },
    dispose() {
      disposables.forEach((d) => d.dispose());
      renderer.dispose();
    },
  };
}
