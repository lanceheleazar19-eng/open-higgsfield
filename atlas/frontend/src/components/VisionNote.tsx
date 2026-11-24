import { body } from "../api/body";
import { useAsync } from "../api/useAsync";

/** Dice ANTES de analizar quién procesará la imagen (privacidad). */
export function VisionNote() {
  const r = useAsync(body.visionRoute);
  if (!r.data) return null;
  const d = r.data;
  return (
    <p className={`small ${d.local ? "muted" : "t-warn"}`}>
      🔒 {d.local
        ? d.available ? `Las fotos se analizan en tu Mac con ${d.model}. No salen de tu ordenador.` : `Análisis no disponible: ${d.note}`
        : `Las fotos se enviarían a ${d.label} (${d.model}); te pediré permiso cada vez.`}
    </p>
  );
}
