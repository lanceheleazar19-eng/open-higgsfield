"""Memoria persistente de VISTAN: recuerdos, búsqueda y contexto para el cerebro.

- Recuerdos permanentes (expires_at NULL) o temporales (con caducidad).
- Sin duplicados: huella normalizada + similitud con los candidatos más parecidos.
- Búsqueda de texto completo con SQLite FTS5 (sin tildes); LIKE como respaldo.
"""

import difflib
import hashlib
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from atlas.models import Conversation, ConversationMessage, Memory
from atlas.models.base import utcnow
from atlas.services.activity import log_activity
from atlas.services.clock import local_to_utc_naive, utc_naive_to_local

KIND_ES = {"preference": "preferencia", "goal": "objetivo", "decision": "decisión", "fact": "dato", "note": "nota"}
SIMILARITY_DUP = 0.9

STOPWORDS = set("""
a al algo algun alguna ante antes asi atlas aun bien cada como con contra cual cuales cuando cuanto de del desde
donde dos el ella ellas ellos en entre era es esa ese eso esta estas este esto estos fue fueron ha han hasta hay
la las le les lo los mas me mi mis mucho muy nada ni no nos nosotros o os otra otro para pero poco por porque que
quien se sea ser si sin sobre son su sus tambien te tengo ti tu tus un una uno unos y ya yo eres puedes dime
recuerdas sabes acuerdas semana pasada pasado ayer hoy manana mes dia dias vez algo
""".split())


# ----------------------------------------------------------------- utilidades

def normalize(text_: str) -> str:
    t = unicodedata.normalize("NFD", text_.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z0-9ñ]+", t))


def content_key(text_: str) -> str:
    return hashlib.sha256(normalize(text_).encode()).hexdigest()


def _terms(query: str) -> list[str]:
    words = [w for w in normalize(query).split() if len(w) >= 3 and w not in STOPWORDS]
    # «stemming» simple para el español, por prefijos: decidimos → decid*, ahorro → ahor*, mañanas → manan*
    out = []
    for w in words:
        t = w[:5] if len(w) >= 8 else (w[:max(4, len(w) - 2)] if len(w) >= 5 else w)
        if t not in out:
            out.append(t)
    return out[:12]


def _fts_query(query: str) -> str | None:
    terms = _terms(query)
    return " OR ".join(f'"{t}"*' for t in terms) if terms else None


def _has_fts(db: Session, table: str) -> bool:
    if db.get_bind().dialect.name != "sqlite":
        return False
    return bool(db.execute(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}).first())


def _active_clause(now: datetime):
    return or_(Memory.expires_at.is_(None), Memory.expires_at > now)


def to_dict(m: Memory, tz: str) -> dict:
    now = utcnow()
    return {
        "id": m.id,
        "content": m.content,
        "kind": m.kind,
        "permanent": m.expires_at is None,
        "expires_at": utc_naive_to_local(m.expires_at, tz).isoformat() if m.expires_at else None,
        "expired": bool(m.expires_at and m.expires_at <= now),
        "project_id": m.project_id,
        "source": m.source,
        "created_at": utc_naive_to_local(m.created_at, tz).isoformat(),
        "updated_at": utc_naive_to_local(m.updated_at, tz).isoformat(),
    }


# ----------------------------------------------------------------- búsqueda

def search_memories(db: Session, query: str, limit: int = 20, include_expired: bool = False,
                    project_id: int | None = None) -> list[Memory]:
    q = select(Memory)
    if not include_expired:
        q = q.where(_active_clause(utcnow()))
    if project_id is not None:
        q = q.where(or_(Memory.project_id.is_(None), Memory.project_id == project_id))
    match = _fts_query(query)
    if match is None:
        return []
    if _has_fts(db, "memory_fts"):
        ids = [r[0] for r in db.execute(
            text("SELECT rowid FROM memory_fts WHERE memory_fts MATCH :m ORDER BY bm25(memory_fts) LIMIT 200"),
            {"m": match})]
        if not ids:
            return []
        rows = {m.id: m for m in db.scalars(q.where(Memory.id.in_(ids)))}
        return [rows[i] for i in ids if i in rows][:limit]
    likes = [Memory.content.ilike(f"%{t}%") for t in _terms(query)]
    return list(db.scalars(q.where(or_(*likes)).order_by(Memory.updated_at.desc()).limit(limit)))


def search_messages(db: Session, query: str, limit: int = 8, exclude_conversation: int | None = None,
                    since: datetime | None = None, until: datetime | None = None) -> list[ConversationMessage]:
    q = select(ConversationMessage)
    if exclude_conversation:
        q = q.where(ConversationMessage.conversation_id != exclude_conversation)
    if since:
        q = q.where(ConversationMessage.created_at >= since)
    if until:
        q = q.where(ConversationMessage.created_at < until)
    match = _fts_query(query)
    if match and _has_fts(db, "message_fts"):
        ids = [r[0] for r in db.execute(
            text("SELECT rowid FROM message_fts WHERE message_fts MATCH :m ORDER BY bm25(message_fts) LIMIT 300"),
            {"m": match})]
        rows = {m.id: m for m in db.scalars(q.where(ConversationMessage.id.in_(ids)))} if ids else {}
        found = [rows[i] for i in ids if i in rows][:limit]
    elif match:
        likes = [ConversationMessage.content.ilike(f"%{t}%") for t in _terms(query)]
        found = list(db.scalars(q.where(or_(*likes)).order_by(ConversationMessage.created_at.desc()).limit(limit)))
    else:
        found = []
    # Si la pregunta se refiere a un periodo y no hay coincidencias, devuelve lo más reciente de ese periodo
    if not found and since:
        found = list(db.scalars(q.order_by(ConversationMessage.created_at.desc()).limit(limit)))
    return found


# ----------------------------------------------------------------- escritura

def find_duplicate(db: Session, content: str, project_id: int | None = None) -> Memory | None:
    key = content_key(content)
    exact = db.scalars(select(Memory).where(Memory.content_key == key, _active_clause(utcnow()))).first()
    if exact:
        return exact
    norm = normalize(content)
    for cand in search_memories(db, content, limit=8, project_id=project_id):
        if cand.project_id == project_id and difflib.SequenceMatcher(None, norm, normalize(cand.content)).ratio() >= SIMILARITY_DUP:
            return cand
    return None


def remember(db: Session, content: str, kind: str = "fact", expires_at: datetime | None = None,
             source: str = "manual", project_id: int | None = None) -> tuple[Memory, bool]:
    """Guarda un recuerdo. Devuelve (recuerdo, creado). Si ya existía, lo refresca en lugar de duplicarlo."""
    content = content.strip()
    dup = find_duplicate(db, content, project_id)
    if dup:
        dup.updated_at = utcnow()
        if expires_at and dup.expires_at:
            dup.expires_at = max(dup.expires_at, expires_at)
        db.flush()
        return dup, False
    m = Memory(content=content, kind=kind, expires_at=expires_at, source=source,
               project_id=project_id, content_key=content_key(content))
    db.add(m)
    db.flush()
    log_activity(db, "memory", "create", f"Memoria guardada: {content[:80]}")
    return m, True


def update_memory(db: Session, m: Memory, **changes) -> Memory:
    for k, v in changes.items():
        setattr(m, k, v)
    if "content" in changes:
        m.content_key = content_key(m.content)
    db.flush()
    log_activity(db, "memory", "update", f"Memoria editada: {m.content[:80]}")
    return m


def forget(db: Session, m: Memory) -> None:
    log_activity(db, "memory", "delete", f"Memoria eliminada: {m.content[:80]}")
    db.delete(m)
    db.flush()


def purge_expired(db: Session) -> int:
    expired = list(db.scalars(select(Memory).where(Memory.expires_at.is_not(None), Memory.expires_at <= utcnow())))
    for m in expired:
        db.delete(m)
    if expired:
        log_activity(db, "memory", "purge", f"{len(expired)} recuerdos caducados eliminados")
    db.flush()
    return len(expired)


# ----------------------------------------------------------------- lenguaje natural

_REMEMBER = re.compile(
    r"^(?:oye\s+)?(?:(?:atlas|vistan|bistan)[,:\s]+)?(?:por favor\s+)?"
    r"(?:recuerda(?:\s+siempre)?|no olvides|memoriza|apunta que|anota que|guarda en (?:la |tu )?memoria)"
    r"(?:\s+que|\s+esto|:)?[\s:,]+(?P<body>.{3,})$",
    re.IGNORECASE | re.DOTALL,
)
_FORGET = re.compile(
    r"^(?:oye\s+)?(?:(?:atlas|vistan|bistan)[,:\s]+)?(?:por favor\s+)?(?:olvida|borra de (?:la |tu )?memoria)(?:\s+que|:)?[\s:,]+(?P<body>.{3,})$",
    re.IGNORECASE | re.DOTALL,
)


def parse_command(text_: str) -> tuple[str, str] | None:
    """Detecta «recuerda que …» / «olvida que …». Devuelve (acción, contenido) o None."""
    t = text_.strip().rstrip(".!")
    for action, rx in (("remember", _REMEMBER), ("forget", _FORGET)):
        m = rx.match(t)
        if m:
            body = m.group("body").strip()
            return action, body[0].upper() + body[1:]
    return None


def guess_kind(content: str) -> str:
    n = normalize(content)
    if re.search(r"\b(prefiero|me gusta|no me gusta|me encanta|odio|detesto|mi favorit|suelo)\b", n):
        return "preference"
    if re.search(r"\b(objetivo|meta|quiero (conseguir|lograr|llegar|ahorrar|bajar|subir|ganar|aprender|correr))\b", n):
        return "goal"
    if re.search(r"\b(decid|acordamos|hemos acordado|vamos a|he elegido|elegimos)", n):
        return "decision"
    return "fact"


def guess_expiry(content: str, tz: str, today: date | None = None) -> datetime | None:
    """Recuerdos con referencia temporal caducan solos (hoy, mañana, esta semana, este mes)."""
    n = normalize(content)
    z = ZoneInfo(tz)
    today = today or datetime.now(z).date()

    def end_of(d: date) -> datetime:
        return local_to_utc_naive(datetime.combine(d + timedelta(days=1), time.min, tzinfo=z))

    if re.search(r"\b(hoy|esta (tarde|noche|manana))\b", n):
        return end_of(today)
    if re.search(r"\bmanana\b", n):
        return end_of(today + timedelta(days=1))
    if re.search(r"\b(esta semana|estos dias)\b", n):
        return end_of(today + timedelta(days=6 - today.weekday()))
    if re.search(r"\beste mes\b", n):
        nxt = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        return end_of(nxt - timedelta(days=1))
    return None


def time_window(query: str, tz: str, today: date | None = None) -> tuple[datetime, datetime] | None:
    """Periodo al que se refiere una pregunta («ayer», «la semana pasada», «el mes pasado»), en UTC."""
    n = normalize(query)
    z = ZoneInfo(tz)
    today = today or datetime.now(z).date()

    def utc(d: date) -> datetime:
        return local_to_utc_naive(datetime.combine(d, time.min, tzinfo=z))

    if re.search(r"\bayer\b", n):
        return utc(today - timedelta(days=1)), utc(today)
    if re.search(r"\bsemana pasada\b", n):
        start = today - timedelta(days=today.weekday() + 7)
        return utc(start), utc(start + timedelta(days=7))
    if re.search(r"\b(esta semana)\b", n):
        start = today - timedelta(days=today.weekday())
        return utc(start), utc(today + timedelta(days=1))
    if re.search(r"\bmes pasado\b", n):
        first = today.replace(day=1)
        prev = (first - timedelta(days=1)).replace(day=1)
        return utc(prev), utc(first)
    return None


# ----------------------------------------------------------------- contexto para el cerebro

def memory_context(db: Session, query: str, tz: str, conversation_id: int | None = None) -> dict:
    """Recuerdos y fragmentos de conversaciones anteriores relevantes para `query`."""
    now = utcnow()
    profile = list(db.scalars(
        select(Memory).where(Memory.expires_at.is_(None), Memory.kind.in_(("preference", "goal")),
                             Memory.project_id.is_(None))
        .order_by(Memory.updated_at.desc()).limit(12)))
    temporary = list(db.scalars(select(Memory).where(Memory.expires_at > now).order_by(Memory.expires_at).limit(8)))
    seen = {m.id for m in profile + temporary}
    relevant = [m for m in search_memories(db, query, limit=8) if m.id not in seen]
    window = time_window(query, tz)
    msgs = search_messages(db, query, limit=6, exclude_conversation=conversation_id,
                           since=window[0] if window else None, until=window[1] if window else None)
    for m in profile + temporary + relevant:
        m.last_used_at = now
    db.flush()

    def fmt(m: Memory) -> dict:
        d = {"tipo": KIND_ES[m.kind], "contenido": m.content,
             "guardado": utc_naive_to_local(m.created_at, tz).strftime("%d/%m/%Y")}
        if m.expires_at:
            d["valido_hasta"] = utc_naive_to_local(m.expires_at, tz).strftime("%d/%m/%Y %H:%M")
        return d

    return {
        "perfil": [fmt(m) for m in profile],
        "temporal": [fmt(m) for m in temporary],
        "relevante": [fmt(m) for m in relevant],
        "conversaciones": [
            {"fecha": utc_naive_to_local(m.created_at, tz).strftime("%d/%m/%Y %H:%M"),
             "quien": "usuario" if m.role == "user" else "VISTAN", "texto": m.content[:400]}
            for m in msgs
        ],
    }


def counts(db: Session) -> dict:
    now = utcnow()
    return {
        "memories": db.scalar(select(func.count()).select_from(Memory).where(_active_clause(now))) or 0,
        "conversations": db.scalar(select(func.count()).select_from(Conversation)) or 0,
    }
