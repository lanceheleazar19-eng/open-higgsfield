/** Iconos SVG inline (trazo 1.6, heredan currentColor). */
const PATHS: Record<string, string> = {
  dashboard: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z",
  ai: "M12 3a4 4 0 0 1 4 4v1a3 3 0 0 1 3 3v2a3 3 0 0 1-3 3v1a4 4 0 0 1-8 0v-1a3 3 0 0 1-3-3v-2a3 3 0 0 1 3-3V7a4 4 0 0 1 4-4zM9.5 11h.01M14.5 11h.01M9.5 14.5c1.5 1 3.5 1 5 0",
  tasks: "M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2",
  gym: "M3 10v4M6 7v10M18 7v10M21 10v4M6 12h12",
  finance: "M4 19V9M10 19V5M16 19v-7M22 19H2",
  trading: "M3 17l5-5 4 3 8-8M15 7h5v5",
  projects: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  memory: "M12 3c4.4 0 8 1.3 8 3v12c0 1.7-3.6 3-8 3s-8-1.3-8-3V6c0-1.7 3.6-3 8-3zM4 6c0 1.7 3.6 3 8 3s8-1.3 8-3M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  reports: "M6 3h9l5 5v13H6zM14 3v6h6M9 13h8M9 17h5",
  settings: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  research: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4M8 11h6M11 8v6",
  agents: "M12 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM5 15a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM19 15a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM12 8v4M12 12l-5.5 3.5M12 12l5.5 3.5",
  mic: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
  send: "M4 12l16-8-6 16-2.5-6.5L4 12zM11.5 13.5 20 4",
  volume: "M4 9h4l5-4v14l-5-4H4zM16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11",
  mute: "M4 9h4l5-4v14l-5-4H4zM17 9l5 6M22 9l-5 6",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
  stop: "M7 7h10v10H7z",
  lab: "M9 3h6M10 3v6L4.5 18.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3M7 15h10",
  life: "M12 2l2.4 5.1 5.6.6-4.2 3.8 1.2 5.5L12 14.2 7 17l1.2-5.5L4 7.7l5.6-.6zM5 21h14",
  betting: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7l3 2.2-1.2 3.5h-3.6L9 9.2zM12 3v4M21 12l-6-2.8M3 12l6-2.8M7 19.5l3.2-6.8M17 19.5l-3.2-6.8",
  phone: "M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2",
  nutrition: "M7 3v8a2 2 0 0 0 2 2h0a2 2 0 0 0 2-2V3M9 3v18M17 3c-1.7 0-3 2-3 5s1.3 5 3 5v8",
  camera: "M4 8h3l2-3h6l2 3h3v11H4zM12 11a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
  menu: "M4 7h16M4 12h16M4 17h16",
  close: "M6 6l12 12M18 6L6 18",
  knowledge: "M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM18 17H8a3 3 0 0 0-3 3M9 8h5M9 11h4",
  workflows: "M5 5h5v5H5zM14 14h5v5h-5zM7.5 10v4a2 2 0 0 0 2 2H14M16.5 14V9.5a2 2 0 0 0-2-2H10",
  command: "M4 5h16v12H4zM8 21h8M12 17v4M7 9l3 2-3 2M12 13h4",
  bell: "M6 9a6 6 0 0 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9zM10 20a2 2 0 0 0 4 0",
  graph: "M6 6a2 2 0 1 0 0 .1M18 8a2 2 0 1 0 0 .1M8 18a2 2 0 1 0 0 .1M7.8 6.8l8.4 1.4M7 16.2l-.8-8.4M9.8 17.2l6.8-7.6",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
  plus: "M12 5v14M5 12h14",
  progress: "M4 19h16M6 16l4-5 3 3 5-7M15 7h3v3",
  alert: "M12 9v4M12 17h.01M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
};

export function Icon({ name, size = 18 }: { name: keyof typeof PATHS | string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name] ?? ""} />
    </svg>
  );
}
