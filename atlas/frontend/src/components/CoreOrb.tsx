/** Indicador visual del estado del núcleo. Animación pausada con prefers-reduced-motion. */
export function CoreOrb({ state }: { state: "online" | "degraded" | "offline" }) {
  return (
    <div className={`orb orb-${state}`} role="img" aria-label={`Estado de ATLAS: ${state}`}>
      <span className="orb-ring r1" />
      <span className="orb-ring r2" />
      <span className="orb-core" />
    </div>
  );
}
