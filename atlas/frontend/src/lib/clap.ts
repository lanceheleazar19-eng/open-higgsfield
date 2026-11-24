/** Detección de dos palmadas con el micrófono, 100 % local (Web Audio). No graba ni guarda audio:
 *  solo mide el volumen instantáneo y busca dos golpes secos separados 0,2–0,9 s. */
export interface ClapDetector { stop: () => void }

export function detectTransient(level: number, baseline: number): boolean {
  return level > 0.28 && level > baseline * 5;
}

export async function startClapDetector(onDouble: () => void): Promise<ClapDetector> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
  const AC = (window as unknown as { AudioContext: typeof AudioContext }).AudioContext;
  const ctx = new AC();
  const src = ctx.createMediaStreamSource(stream);
  const an = ctx.createAnalyser();
  an.fftSize = 512;
  src.connect(an);
  const buf = new Float32Array(an.fftSize);
  let baseline = 0.02, lastClap = 0, cooldown = 0, quietSince = 0, raf = 0, stopped = false;
  const loop = (t: number) => {
    if (stopped) return;
    an.getFloatTimeDomainData(buf);
    let peak = 0;
    for (let i = 0; i < buf.length; i++) peak = Math.max(peak, Math.abs(buf[i]));
    if (t > cooldown && detectTransient(peak, baseline) && t - quietSince > 60) {
      if (lastClap && t - lastClap > 200 && t - lastClap < 900) {
        lastClap = 0; cooldown = t + 1500; onDouble();
      } else lastClap = t;
      quietSince = t + 120; // ignora la cola del mismo golpe
    }
    if (lastClap && t - lastClap > 900) lastClap = 0;
    baseline = baseline * 0.97 + Math.min(peak, 0.2) * 0.03;
    raf = requestAnimationFrame(loop);
  };
  raf = requestAnimationFrame(loop);
  return { stop: () => { stopped = true; cancelAnimationFrame(raf); stream.getTracks().forEach((tr) => tr.stop()); void ctx.close(); } };
}
