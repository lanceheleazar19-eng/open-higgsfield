"""Gmail por IMAP (solo lectura) con contraseña de aplicación. Descarga cabeceras y un extracto
de los correos recientes, y marca como importantes solo los que lo merecen:
1) señales fuertes: marca «Importante» de Gmail y remitentes/asuntos relevantes;
2) descarta boletines (List-Unsubscribe), no-reply masivos y promociones;
3) si hay IA, decide los casos dudosos y redacta el motivo."""

import email
import email.policy
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.integrations.secrets import get_secret
from atlas.models import EmailMessage
from atlas.services.activity import log_activity
from atlas.services.memory import normalize

IMAP_HOST = "imap.gmail.com"
KEYWORDS = re.compile(r"factura|pago|cobro|recibo|transferencia|banco|tarjeta|cita|reserva|examen|entrega|nota|matricula|"
                      r"clase|profesor|tutor|trabajo|contrato|nomina|urgente|importante|plazo|vencimiento|pedido|envio|"
                      r"seguridad|contrasena|verificacion|codigo|multa|hacienda|seguro|medico|hospital")
BULK = re.compile(r"no-?reply|noreply|newsletter|news@|marketing|promo|notifications?@|info@|mailer|bounce")


def _dec(v: str | None) -> str:
    if not v:
        return ""
    try:
        return str(make_header(decode_header(v)))
    except Exception:  # noqa: BLE001
        return v


def _snippet(msg: email.message.Message) -> str:
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_type() == "text/plain" and not part.get_filename():
            try:
                text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
            except Exception:  # noqa: BLE001
                continue
            return re.sub(r"\s+", " ", text).strip()[:400]
    return ""


def parse_message(raw: bytes, gmail_labels: str = "") -> dict:
    msg = email.message_from_bytes(raw, policy=email.policy.default)  # cabeceras UTF-8 y codificadas
    name, addr = parseaddr(_dec(msg.get("From")))
    try:
        dt = parsedate_to_datetime(msg.get("Date")).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:  # noqa: BLE001
        dt = datetime.utcnow()
    return {"message_id": (msg.get("Message-ID") or f"{addr}-{dt.isoformat()}")[:300],
            "sender": f"{name} <{addr}>" if name else addr, "sender_addr": addr.lower(), "subject": _dec(msg.get("Subject"))[:500],
            "received_at": dt, "snippet": _snippet(msg), "bulk_header": bool(msg.get("List-Unsubscribe") or msg.get("List-Id")),
            "gmail_important": "\\\\Important" in gmail_labels or "\\Important" in gmail_labels}


def rule_score(m: dict) -> tuple[bool | None, str]:
    """True/False si las reglas lo deciden; None si es dudoso (lo decide la IA si existe)."""
    text = normalize(m["subject"] + " " + m["snippet"][:200])
    bulk = m["bulk_header"] or bool(BULK.search(m["sender_addr"]))
    kw = KEYWORDS.search(text)
    if bulk and not kw:
        return False, "boletín o notificación automática"
    if m["gmail_important"] and kw and not bulk:
        return True, f"Gmail lo marca como importante y trata de «{kw.group(0)}»"
    if kw and not bulk:
        return None, f"menciona «{kw.group(0)}»"
    if m["gmail_important"] and not bulk:
        return None, "Gmail lo marca como importante"
    return False, "sin señales de importancia"


def fetch_recent(addr: str, password: str, since_days: int = 2, limit: int = 60) -> list[dict]:
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        imap.login(addr, password)
        imap.select("INBOX", readonly=True)  # solo lectura: no marca nada como leído
        since = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
        typ, data = imap.uid("search", None, f"(SINCE {since})")
        uids = (data[0] or b"").split()[-limit:]
        out = []
        for uid in uids:
            typ, parts = imap.uid("fetch", uid, "(X-GM-LABELS BODY.PEEK[HEADER] BODY.PEEK[TEXT]<0.4000>)")
            raw, labels = b"", ""
            for p in parts or []:
                if isinstance(p, tuple):
                    labels += p[0].decode(errors="replace")
                    raw += p[1]
            if raw:
                out.append(parse_message(raw, labels))
        return out
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass


AI_PROMPT = """Eres el asistente personal del usuario. Para cada correo decide si es IMPORTANTE para él hoy
(pagos, facturas, bancos, citas, estudios, trabajo, personas reales que esperan respuesta, seguridad de cuentas).
NO son importantes: publicidad, boletines, redes sociales, notificaciones automáticas sin acción.
Responde SOLO JSON: {"correos": [{"id": 0, "importante": true, "motivo": "frase breve en español"}]}"""


def classify(db: Session, prefs: dict, msgs: list[dict]) -> list[tuple[bool, str]]:
    from atlas.brain.base import ProviderError
    from atlas.brain.orchestrator import brain_status, get_provider
    decided = [rule_score(m) for m in msgs]
    doubtful = [i for i, (v, _) in enumerate(decided) if v is None]
    ai: dict[int, tuple[bool, str]] = {}
    if doubtful:
        provider = get_provider()
        st = brain_status(prefs, provider)
        if st["configured"]:
            import json
            payload = [{"id": i, "de": msgs[i]["sender"], "asunto": msgs[i]["subject"], "extracto": msgs[i]["snippet"][:300]} for i in doubtful]
            try:
                out = provider.complete_json(st["model"], [{"role": "system", "content": AI_PROMPT},
                                                           {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
                for c in out.get("correos", []) if isinstance(out, dict) else []:
                    if isinstance(c, dict) and c.get("id") in doubtful:
                        ai[c["id"]] = (bool(c.get("importante")), str(c.get("motivo") or "")[:300])
            except ProviderError:
                pass
    result = []
    for i, (v, reason) in enumerate(decided):
        if i in ai:
            result.append(ai[i])
        elif v is None:
            result.append((True, reason))  # sin IA: ante la duda con palabra clave, mejor avisar
        else:
            result.append((v, reason))
    return result


def sync(db: Session, prefs: dict, fetch=None) -> dict:
    fetch = fetch or fetch_recent
    addr = get_secret("gmail_address")
    pwd = get_secret("gmail_app_password")
    if not addr or not pwd:
        return {"configured": False, "new": 0, "important": 0}
    msgs = fetch(addr, pwd)
    known = set(db.scalars(select(EmailMessage.message_id)))
    fresh = [m for m in msgs if m["message_id"] not in known]
    verdicts = classify(db, prefs, fresh) if fresh else []
    n_imp = 0
    for m, (imp, reason) in zip(fresh, verdicts):
        db.add(EmailMessage(message_id=m["message_id"], sender=m["sender"][:300], subject=m["subject"], received_at=m["received_at"],
                            snippet=m["snippet"], important=imp, reason=reason))
        n_imp += imp
    if n_imp:
        log_activity(db, "email", "sync", f"{n_imp} correo(s) importante(s) nuevo(s)")
    db.commit()
    return {"configured": True, "new": len(fresh), "important": n_imp}


def important_today(db: Session, tz: str) -> list[EmailMessage]:
    from zoneinfo import ZoneInfo
    start = datetime.now(ZoneInfo(tz)).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
    return list(db.scalars(select(EmailMessage).where(EmailMessage.important.is_(True), EmailMessage.dismissed.is_(False),
                                                      EmailMessage.received_at >= start).order_by(EmailMessage.received_at.desc())))
