/** Emblema de ATLAS: triángulo carmesí con brillo. */
export function Logo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className="logo">
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ff6b78" /><stop offset="1" stopColor="#b3101f" />
        </linearGradient>
      </defs>
      <path d="M32 6 58 56H45L32 30 19 56H6z" fill="url(#lg)" />
      <path d="M32 38 38 50H26z" fill="#ff2e42" opacity=".85" />
    </svg>
  );
}
