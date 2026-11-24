import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { TaskItem } from "../api/types";

/** Comprueba cada 30 s si hay recordatorios vencidos. Funciona mientras VISTAN esté abierto. */
export function useReminders(intervalMs = 30_000) {
  const [items, setItems] = useState<TaskItem[]>([]);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const { items: due } = await api.dueReminders();
        if (!alive || !due.length) return;
        setItems((prev) => [...prev, ...due.filter((d) => !prev.some((p) => p.id === d.id))]);
        if (typeof Notification !== "undefined" && Notification.permission === "granted") {
          for (const t of due) new Notification("VISTAN · Recordatorio", { body: t.title, tag: `atlas-task-${t.id}` });
        }
      } catch { /* núcleo sin conexión: se reintenta */ }
    };
    void check();
    const id = setInterval(() => void check(), intervalMs);
    return () => { alive = false; clearInterval(id); };
  }, [intervalMs]);

  return { items, dismiss: (id: number) => setItems((l) => l.filter((t) => t.id !== id)) };
}
