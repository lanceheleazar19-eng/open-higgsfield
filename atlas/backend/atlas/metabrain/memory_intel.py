"""Memory Intelligence sobre la memoria existente de VISTAN (no es una base de datos nueva):
- tipos: episódica (conversaciones guardadas y episodios que tú decides recordar), semántica (datos, documentos y grafo de
  conocimiento), de proyectos (recuerdos ligados a un proyecto), de preferencias y de procedimientos,
- deduplicación aproximada, detección de posibles contradicciones (reglas: mismo tema con cifras o negaciones distintas;
  opcionalmente confirmadas por un modelo), resolución (el recuerdo antiguo queda como histórico) e historial de cambios,
- control de acceso por recuerdo: all · local (nunca sale a la nube) · private (nunca entra en el contexto de la IA).
Nada se guarda automáticamente a partir de las conversaciones: solo lo que tú guardas o apruebas."""

from __future__ import annotations

import difflib
import re
from itertools import combinations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.metabrain.checks import _norm, _terms
from atlas.models import Conversation, Document, Entity, Memory, MemoryRevision, Relation
from atlas.services import memory as mem

TYPES = {
    "episodic": "Episódica: conversaciones guardadas y episodios que decides recordar",
    "semantic": "Semántica: datos, decisiones, objetivos, documentos y grafo de conocimiento",
    "project": "De proyectos: recuerdos ligados a un proyecto",
    "preference": "De preferencias",
    "procedure": "De procedimientos: cómo haces las cosas",
}
NEG = re.compile(r"\b(no|nunca|ya no|jamas|dej[eé] de)\b")


def mtype(m: Memory) -> str:
    if m.project_id:
        return "project"
    return {"preference": "preference", "procedure": "procedure", "episode": "episodic"}.get(m.kind, "semantic")


def overview(db: Session) -> dict:
    now = mem.utcnow()
    active = list(db.scalars(select(Memory).where(mem._active_clause(now))))
    counts = {k: 0 for k in TYPES}
    for m in active:
        counts[mtype(m)] += 1
    counts["episodic_conversations"] = db.scalar(select(func.count(Conversation.id))) or 0
    access = {a: sum(1 for m in active if (m.access or "all") == a) for a in ("all", "local", "private")}
    return {"types": TYPES, "counts": counts, "access": access, "total": len(active),
            "superseded": sum(1 for m in active if m.superseded_by),
            "documents": db.scalar(select(func.count(Document.id))) or 0,
            "graph": {"entities": db.scalar(select(func.count(Entity.id))) or 0, "relations": db.scalar(select(func.count(Relation.id))) or 0},
            "revisions": db.scalar(select(func.count(MemoryRevision.id))) or 0}


def _numbers(t: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", t))


def analyze_pairs(db: Session, limit: int = 400) -> dict:
    """Posibles duplicados (texto casi igual) y posibles contradicciones (mismo tema, cifras o negación distintas)."""
    now = mem.utcnow()
    items = [m for m in db.scalars(select(Memory).where(mem._active_clause(now), Memory.superseded_by.is_(None))
                                   .order_by(Memory.updated_at.desc()).limit(limit))]
    terms = {m.id: _terms(m.content) for m in items}
    dups, contra = [], []
    for a, b in combinations(items, 2):
        if a.project_id != b.project_id:
            continue
        ta, tb = terms[a.id], terms[b.id]
        if not ta or not tb:
            continue
        overlap = len(ta & tb) / min(len(ta), len(tb))
        na, nb = _numbers(a.content), _numbers(b.content)
        neg = bool(NEG.search(_norm(a.content))) != bool(NEG.search(_norm(b.content)))
        differs = (na != nb) or neg  # mismas palabras con otra cifra o negación: no es un duplicado
        ratio = difflib.SequenceMatcher(None, _norm(a.content), _norm(b.content)).ratio()
        if ratio >= 0.85 and not differs:
            dups.append({"a": a.id, "b": b.id, "a_text": a.content, "b_text": b.content, "similarity": round(ratio, 2)})
            continue
        if overlap >= 0.6:
            if (na and nb and na != nb) or neg:
                newer, older = (a, b) if a.updated_at >= b.updated_at else (b, a)
                contra.append({"newer": newer.id, "older": older.id, "newer_text": newer.content, "older_text": older.content,
                               "reason": "negación distinta" if neg else f"cifras distintas ({', '.join(sorted(_numbers(older.content)))} → {', '.join(sorted(_numbers(newer.content)))})",
                               "overlap": round(overlap, 2)})
    return {"duplicates": dups[:50], "contradictions": contra[:50], "checked": len(items),
            "note": "Detección por reglas: son candidatos. Tú decides si fusionar o qué versión es la vigente."}


def resolve(db: Session, keep: Memory, old: Memory, reason: str) -> None:
    """El recuerdo `old` queda como histórico (reemplazado por `keep`) y deja de usarse como contexto."""
    mem.update_memory(db, old, reason=reason, superseded_by=keep.id)


def merge(db: Session, keep: Memory, drop: Memory) -> None:
    """Fusión de duplicados: se conserva `keep` y se elimina `drop` (queda constancia en la auditoría)."""
    from atlas.services.activity import log_activity
    log_activity(db, "memory", "merge", f"Duplicado fusionado: «{drop.content[:60]}» → #{keep.id}")
    db.add(MemoryRevision(memory_id=keep.id, field="merge", before=drop.content[:4000], after=keep.content[:4000], reason="fusión de duplicado"))
    mem.forget(db, drop)


def history(db: Session, memory_id: int) -> list[dict]:
    return [{"id": r.id, "field": r.field, "before": r.before, "after": r.after, "reason": r.reason, "at": r.created_at.isoformat()}
            for r in db.scalars(select(MemoryRevision).where(MemoryRevision.memory_id == memory_id).order_by(MemoryRevision.id.desc()))]
