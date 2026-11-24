import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { v4, type SearchResults } from "../api/v4";
import { Icon } from "./Icon";
import { NAV } from "./nav";

interface Item { id: string; group: string; label: string; hint?: string; icon: string; run: () => Promise<string | void> | void }

/** Paleta de comandos (⌘K / Ctrl+K): módulos, acciones y búsqueda en tareas, memoria, documentos,
 *  proyectos e investigaciones. Cada acción hace algo real. */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [res, setRes] = useState<SearchResults | null>(null);
  const [active, setActive] = useState(0);
  const [note, setNote] = useState<string | null>(null);
  const nav = useNavigate();
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
      if (e.key === "Escape") setOpen(false);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("atlas-palette", onOpen);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("atlas-palette", onOpen); };
  }, []);
  useEffect(() => { if (open) { setQ(""); setRes(null); setNote(null); setActive(0); setTimeout(() => input.current?.focus(), 0); } }, [open]);
  useEffect(() => {
    if (q.trim().length < 2) { setRes(null); return; }
    const t = setTimeout(() => { v4.search(q).then(setRes).catch(() => setRes(null)); }, 200);
    return () => clearTimeout(t);
  }, [q]);

  const go = (path: string) => () => { nav(path); setOpen(false); };
  const items = useMemo<Item[]>(() => {
    const t = q.trim();
    const low = t.toLowerCase();
    const out: Item[] = [];
    if (t.length >= 3) {
      out.push({ id: "task", group: "Acciones", icon: "tasks", label: `Crear tarea: «${t}»`, run: async () => { await api.createTask({ title: t }); return "Tarea creada."; } });
      out.push({ id: "research", group: "Acciones", icon: "research", label: `Investigar: «${t}»`, run: async () => { const r = await v4.startResearch(t); nav(`/research?id=${r.id}`); setOpen(false); } });
      out.push({ id: "remember", group: "Acciones", icon: "memory", label: `Recordar: «${t}»`, run: async () => { await api.createMemory({ content: t, kind: "fact", source: "manual" }); return "Guardado en memoria."; } });
      out.push({ id: "ask", group: "Acciones", icon: "ai", label: `Preguntar a los agentes: «${t}»`, run: () => { nav(`/agents?tab=try`); setOpen(false); } });
    }
    for (const n of NAV) if (!low || n.label.toLowerCase().includes(low)) out.push({ id: `nav-${n.id}`, group: "Ir a", icon: n.id, label: n.label, run: go(n.path) });
    const cfg: [string, string][] = [["Modelos de IA y API keys", "/settings#modelos"], ["Seguridad y copias", "/settings#seguridad"], ["Perfil personal", "/settings#perfil"], ["Voz y «Hola VISTAN»", "/settings"], ["Proactividad", "/settings#proactividad"]];
    for (const [l, p] of cfg) if (!low || l.toLowerCase().includes(low)) out.push({ id: `cfg-${p}${l}`, group: "Configuración", icon: "settings", label: l, run: go(p) });
    if (res) {
      res.tasks.forEach((x) => out.push({ id: `t${x.id}`, group: "Tareas", icon: "tasks", label: x.title, hint: x.status === "done" ? "hecha" : "pendiente", run: go("/tasks") }));
      res.memories.forEach((x) => out.push({ id: `m${x.id}`, group: "Memoria", icon: "memory", label: x.content, run: go("/memory") }));
      res.documents.forEach((x) => out.push({ id: `d${x.id}`, group: "Documentos", icon: "knowledge", label: x.title, hint: x.snippet.slice(0, 60), run: go("/knowledge") }));
      res.projects.forEach((x) => out.push({ id: `p${x.id}`, group: "Proyectos", icon: "projects", label: x.name, run: go(`/projects?id=${x.id}`) }));
      res.research.forEach((x) => out.push({ id: `r${x.id}`, group: "Investigaciones", icon: "research", label: x.question, run: go(`/research?id=${x.id}`) }));
    }
    return out.slice(0, 40);
  }, [q, res]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null;
  const exec = async (it: Item) => {
    try { const m = await it.run(); if (m) setNote(m); } catch (e) { setNote((e as Error).message); }
  };
  let last = "";
  return (
    <div className="palette-scrim" onMouseDown={() => setOpen(false)}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Paleta de comandos" onMouseDown={(e) => e.stopPropagation()}>
        <div className="palette-in">
          <Icon name="research" size={18} />
          <input ref={input} value={q} placeholder="Busca, crea una tarea, investiga, abre un módulo…" aria-label="Comando"
            onChange={(e) => { setQ(e.target.value); setActive(0); setNote(null); }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(items.length - 1, a + 1)); }
              if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
              if (e.key === "Enter" && items[active]) { e.preventDefault(); void exec(items[active]); }
            }} />
          <kbd>esc</kbd>
        </div>
        {note && <p className="palette-note" role="status">{note}</p>}
        <ul className="palette-list" role="listbox" aria-label="Resultados">
          {items.map((it, i) => {
            const head = it.group !== last ? it.group : null;
            last = it.group;
            return (
              <li key={it.id} role="option" aria-selected={i === active}>
                {head && <span className="palette-group">{head}</span>}
                <button type="button" className={i === active ? "on" : ""} onMouseEnter={() => setActive(i)} onClick={() => void exec(it)}>
                  <Icon name={it.icon} size={15} /><span className="palette-label">{it.label}</span>{it.hint && <span className="muted small">{it.hint}</span>}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
