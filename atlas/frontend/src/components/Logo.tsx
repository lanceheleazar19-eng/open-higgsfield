/** Emblema de VISTAN: una «V» carmesí atravesada por una órbita (el núcleo y su sistema). */
export function Logo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className="logo">
      <defs>
        <linearGradient id="vlg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ff5a6a" /><stop offset="1" stopColor="#b51224" />
        </linearGradient>
      </defs>
      <ellipse cx="32" cy="33" rx="29" ry="10" fill="none" stroke="#e11d35" strokeOpacity=".45" strokeWidth="1.6" transform="rotate(-16 32 33)" />
      <path d="M8 10h12l12 30 12-30h12L37 56H27z" fill="url(#vlg)" />
      <circle cx="55" cy="25" r="2.6" fill="#eaeaea" />
    </svg>
  );
}
