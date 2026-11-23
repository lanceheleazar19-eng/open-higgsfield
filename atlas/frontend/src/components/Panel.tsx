import type { ReactNode } from "react";

export function Panel({ title, icon, aside, className = "", children }: {
  title: string; icon?: ReactNode; aside?: ReactNode; className?: string; children: ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-head">
        <h2>{icon}{title}</h2>
        {aside}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}
