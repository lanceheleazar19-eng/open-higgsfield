"""Capa de seguridad: niveles de permiso de cada herramienta, política configurable, aprobaciones
y protección frente a instrucciones maliciosas dentro de documentos o webs."""

import re
from datetime import datetime

from sqlalchemy.orm import Session

from atlas.models import Approval, Notification
from atlas.services.activity import log_activity

LEVELS = {
    "READ": "Consultar información",
    "WRITE": "Crear o modificar información",
    "EXECUTE": "Ejecutar acciones (internet, copias, procesos)",
    "ADMIN": "Cambiar configuraciones críticas",
}
DEFAULT_POLICY = {"READ": "auto", "WRITE": "auto", "EXECUTE": "confirm", "ADMIN": "confirm"}
# Lo que VISTAN nunca hace, se pida como se pida
NEVER = [
    "Ejecutar operaciones financieras reales (pagos, transferencias, órdenes de bolsa).",
    "Borrar información importante sin tu confirmación.",
    "Enviar mensajes o correos externos sin tu autorización.",
    "Mostrar o enviar tus credenciales (las API keys nunca salen del Llavero).",
    "Ejecutar comandos del sistema peligrosos.",
]


def policy(prefs: dict) -> dict:
    p = {**DEFAULT_POLICY, **(prefs.get("security_policy") or {})}
    p["READ"] = "auto"
    p["ADMIN"] = "confirm"  # lo crítico siempre se confirma
    return p


def needs_approval(level: str, prefs: dict) -> bool:
    return policy(prefs).get(level, "confirm") != "auto"


def request_approval(db: Session, action: str, level: str, summary: str, payload: dict,
                     workflow_run_id: int | None = None) -> Approval:
    a = Approval(action=action, level=level, summary=summary, payload=payload, workflow_run_id=workflow_run_id)
    db.add(a)
    db.flush()
    notify(db, "Necesito tu autorización", summary, level="warning", link="/agents?tab=approvals")
    log_activity(db, "security", "approval_requested", f"[{level}] {summary}")
    return a


def decide(db: Session, a: Approval, approve: bool) -> Approval:
    a.status = "approved" if approve else "rejected"
    a.decided_at = datetime.utcnow()
    log_activity(db, "security", "approved" if approve else "rejected", f"[{a.level}] {a.summary}")
    return a


def notify(db: Session, title: str, body: str = "", level: str = "info", link: str | None = None) -> Notification:
    n = Notification(title=title[:200], body=body, level=level, link=link)
    db.add(n)
    return n


INJECTION = re.compile(
    r"(ignore|ignora|olvida|disregard)\s+(all\s+|todas?\s+|the\s+|las\s+)?(previous|prior|anteriores|above|instrucciones)"
    r"|system\s*prompt|you are now|ahora eres|act[uú]a como|developer mode|jailbreak"
    r"|(send|env[ií]a|reveal|revela|muestra).{0,40}(api[\s_-]?key|password|contraseña|token|credencial)",
    re.I)


def sanitize_untrusted(text_: str) -> tuple[str, bool]:
    """Neutraliza líneas con aspecto de instrucción para el modelo dentro de contenido externo.
    Devuelve (texto, ¿se detectó algo?). El contenido sigue siendo consultable, pero marcado."""
    flagged = False
    out = []
    for line in text_.splitlines():
        if INJECTION.search(line):
            flagged = True
            out.append(f"[línea omitida por seguridad: parecía una instrucción para la IA]")
        else:
            out.append(line)
    return "\n".join(out), flagged
