import { useEffect, useState } from "react";

export function Clock({ timeZone }: { timeZone?: string }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const time = new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone }).format(now);
  const date = new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone }).format(now);
  const dateCap = date.charAt(0).toUpperCase() + date.slice(1);
  return (
    <div className="clock">
      <time className="clock-time mono">{time}</time>
      <div className="clock-date">{dateCap}</div>
    </div>
  );
}
