import { useState } from "react";

/** Comparador antes/después: arrastra el control para revelar una u otra foto. */
export function PhotoCompare({ before, after, labelBefore, labelAfter }: { before: string; after: string; labelBefore: string; labelAfter: string }) {
  const [pos, setPos] = useState(50);
  return (
    <div className="compare">
      <div className="compare-stage">
        <img src={after} alt={labelAfter} draggable={false} />
        <img src={before} alt={labelBefore} draggable={false} style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }} className="compare-top" />
        <span className="compare-line" style={{ left: `${pos}%` }} aria-hidden="true" />
        <span className="compare-tag left">{labelBefore}</span><span className="compare-tag right">{labelAfter}</span>
      </div>
      <input type="range" min={0} max={100} value={pos} onChange={(e) => setPos(Number(e.target.value))} aria-label="Deslizar comparación" />
    </div>
  );
}
