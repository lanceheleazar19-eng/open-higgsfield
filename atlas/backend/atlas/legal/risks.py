"""Legal Risk Detection: genera alertas (sin duplicados) a partir de datos reales: análisis de contratos, plazos
(registrados por ti, nunca calculados), cumplimiento y expedientes. Siempre «posible riesgo», nunca «infracción»."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.models import LgAlert, LgAnalysis, LgCompliance, LgDeadline, LgDocument
from atlas.security.policy import notify

LV = {"critico": "CRÍTICO", "alto": "ALTO", "medio": "MEDIO", "bajo": "BAJO"}


def _upsert(db: Session, key: str, **f) -> LgAlert | None:  # noqa: ANN003
    a = db.scalar(select(LgAlert).where(LgAlert.key == key))
    if a:
        return None
    a = LgAlert(key=key[:80], **f)
    db.add(a)
    return a


def scan(db: Session, today: date | None = None) -> int:
    today = today or date.today()
    new = 0
    for an in db.scalars(select(LgAnalysis).where(LgAnalysis.status == "done")):
        lg = db.get(LgDocument, an.legal_doc_id)
        for i, r in enumerate((an.result or {}).get("risks", [])):
            if r.get("nivel") not in ("critico", "alto"):
                continue
            a = _upsert(db, f"an{an.id}-{i}", case_id=lg.case_id if lg else None, legal_doc_id=an.legal_doc_id, level=r["nivel"],
                        title=f"Posible riesgo {LV[r['nivel']]} en «{(lg.title if lg else 'contrato')[:80]}»",
                        description=r.get("problema") or "", evidence=r.get("fragmento"), source=f"Análisis #{an.id} · {r.get('clausula') or ''}"[:300],
                        consequence=r.get("consecuencia"), action=r.get("recomendacion"))
            new += a is not None
        for j, c in enumerate((an.result or {}).get("contradictions", [])):
            a = _upsert(db, f"an{an.id}-c{j}", case_id=lg.case_id if lg else None, legal_doc_id=an.legal_doc_id, level="medio",
                        title=f"Posible contradicción ({c['tema']}) en «{(lg.title if lg else 'contrato')[:80]}»", description=c["detalle"],
                        evidence=" | ".join(c.get("fragmentos") or [])[:1500], source=f"Análisis #{an.id}",
                        consequence="Interpretaciones distintas del mismo punto.", action="Unifica la cifra en todas las cláusulas.")
            new += a is not None
    for d in db.scalars(select(LgDeadline).where(LgDeadline.status == "pendiente")):
        days = (d.due_on - today).days
        if days < 0:
            lvl, why = "critico", f"venció hace {-days} día(s)"
        elif days <= 7:
            lvl, why = "alto", f"vence en {days} día(s)"
        elif days <= 21:
            lvl, why = "medio", f"vence en {days} día(s)"
        else:
            continue
        a = _upsert(db, f"dl{d.id}-{lvl}", case_id=d.case_id, level=lvl, title=f"Plazo «{d.title[:80]}»: {why}",
                    description=("Plazo VERIFICADO por ti." if d.verified else "Plazo NO verificado: confirma reglas de cómputo, "
                                 "fecha inicial e interrupciones o suspensiones antes de confiar en él."),
                    evidence=d.basis, source="Plazos registrados", consequence="Posible pérdida de derechos o recargos si se supera.",
                    action="Revisa el plazo con prioridad" + ("" if d.verified else " y verifícalo con un profesional"))
        if a:
            new += 1
            notify(db, a.title, a.description, level="warning", link="/legal?s=risks")
    for c in db.scalars(select(LgCompliance).where(LgCompliance.status.in_(("pendiente", "en_curso")), LgCompliance.due_on.is_not(None))):
        if c.due_on < today:
            new += _upsert(db, f"cp{c.id}", case_id=c.case_id, level="alto", title=f"Obligación pendiente vencida: {c.obligation[:120]}",
                           description=f"{c.norm or ''} {c.article or ''}".strip(), source=c.source_url, consequence="Posible incumplimiento normativo.",
                           action="Completa la obligación o revisa si aplica.") is not None
    db.flush()
    return new


def alert_dict(a: LgAlert) -> dict:
    return {"id": a.id, "case_id": a.case_id, "legal_doc_id": a.legal_doc_id, "level": a.level, "level_label": LV.get(a.level, a.level),
            "title": a.title, "description": a.description, "evidence": a.evidence, "source": a.source, "consequence": a.consequence,
            "action": a.action, "status": a.status, "detected_at": a.detected_at.isoformat()}


def stale(db: Session, days: int = 180) -> list[LgDocument]:
    """Conclusiones de IA antiguas que conviene revisar por si la normativa cambió."""
    cut = datetime.utcnow() - timedelta(days=days)
    return list(db.scalars(select(LgDocument).where(LgDocument.origin == "ia", LgDocument.created_at < cut)))
