import { Link } from "react-router-dom";
import { useAtlas } from "../components/AtlasContext";
import { Icon } from "../components/Icon";
import { NAV } from "../components/nav";

/** Página de un módulo aún no construido: muestra con honestidad qué incluirá y en qué fase. */
export function ModulePage({ id }: { id: string }) {
  const { modules } = useAtlas();
  const m = modules.find((x) => x.id === id);
  const label = NAV.find((n) => n.id === id)?.label ?? id;
  return (
    <div className="page">
      <header className="page-head">
        <p className="eyebrow">{m ? `Fase ${m.phase} · en desarrollo` : "Módulo"}</p>
        <h1><Icon name={id} size={26} /> {label}</h1>
        {m && <p className="lead">{m.summary}</p>}
      </header>
      <section className="panel planned">
        <h2>Qué incluirá este módulo</h2>
        {m ? (
          <ul className="checklist">{m.planned.map((p) => <li key={p}>{p}</li>)}</ul>
        ) : (
          <p className="muted">Cargando información del módulo…</p>
        )}
        <p className="muted small">Este apartado aún no está activo, así que no muestra datos ni botones de acción. Mientras tanto, el <Link to="/">centro de control</Link> ya refleja cualquier dato registrado.</p>
      </section>
    </div>
  );
}
