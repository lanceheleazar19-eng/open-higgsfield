from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.integrations import calendar_sync, email_sync
from atlas.integrations.secrets import delete_secret, get_secret, set_secret
from atlas.models import CalendarEvent, EmailMessage
from atlas.services.activity import log_activity
from atlas.services.clock import utc_naive_to_local
from atlas.services.preferences import get_prefs, set_prefs

router = APIRouter(tags=["integrations"])


def _tz(db) -> str:  # noqa: ANN001
    return str(get_prefs(db)["timezone"])


def _status(db) -> dict:  # noqa: ANN001
    prefs = get_prefs(db)
    return {
        "gmail": {"connected": bool(get_secret("gmail_address") and get_secret("gmail_app_password")),
                  "address": get_secret("gmail_address"), "last_sync": prefs.get("gmail_last_sync")},
        "icloud": {"connected": bool(get_secret("icloud_user") and get_secret("icloud_app_password")),
                   "user": get_secret("icloud_user"), "last_sync": prefs.get("icloud_last_sync")},
    }


@router.get("/api/integrations")
def status(db: DB) -> dict:
    return _status(db)


class Creds(BaseModel):
    user: str = Field(min_length=3, max_length=200)
    app_password: str = Field(min_length=8, max_length=64)

    @field_validator("app_password")
    @classmethod
    def strip_spaces(cls, v: str) -> str:
        return v.replace(" ", "")  # Google y Apple muestran la contraseña en bloques con espacios


def _stamp(db, key: str) -> None:  # noqa: ANN001
    set_prefs(db, {key: datetime.now(timezone.utc).isoformat()})


def sync_all(db) -> dict:  # noqa: ANN001
    """Sincroniza lo conectado. Usado por el botón y por la tarea periódica."""
    out = {}
    prefs = get_prefs(db)
    try:
        r = email_sync.sync(db, prefs)
        if r["configured"]:
            _stamp(db, "gmail_last_sync")
        out["gmail"] = r
    except Exception as exc:  # noqa: BLE001
        out["gmail"] = {"error": str(exc)[:200]}
    try:
        r = calendar_sync.sync(db)
        if r["configured"]:
            _stamp(db, "icloud_last_sync")
        out["icloud"] = r
    except Exception as exc:  # noqa: BLE001
        out["icloud"] = {"error": str(exc)[:200]}
    db.commit()
    return out


@router.post("/api/integrations/gmail")
def connect_gmail(body: Creds, db: DB) -> dict:
    try:
        email_sync.fetch_recent(body.user, body.app_password, since_days=1, limit=1)  # prueba de acceso
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "No se pudo acceder a Gmail. Revisa el correo y la contraseña de aplicación "
                                 "(y que IMAP esté activado en Gmail).") from exc
    set_secret("gmail_address", body.user.strip().lower())
    set_secret("gmail_app_password", body.app_password)
    log_activity(db, "email", "connect", "Gmail conectado (solo lectura)")
    db.commit()
    sync_all(db)
    return _status(db)


@router.post("/api/integrations/icloud")
def connect_icloud(body: Creds, db: DB) -> dict:
    now = datetime.utcnow()
    try:
        calendar_sync.fetch_events(body.user, body.app_password, now, now + timedelta(days=1))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "No se pudo acceder al calendario de iCloud. Revisa el Apple ID y la contraseña de aplicación.") from exc
    set_secret("icloud_user", body.user.strip())
    set_secret("icloud_app_password", body.app_password)
    log_activity(db, "calendar", "connect", "Calendario de iCloud conectado")
    db.commit()
    sync_all(db)
    return _status(db)


@router.delete("/api/integrations/{name}", status_code=204)
def disconnect(name: str, db: DB) -> None:
    keys = {"gmail": ("gmail_address", "gmail_app_password"), "icloud": ("icloud_user", "icloud_app_password")}.get(name)
    if not keys:
        raise HTTPException(404, "Integración desconocida")
    for k in keys:
        delete_secret(k)
    log_activity(db, "settings", "disconnect", f"{'Gmail' if name == 'gmail' else 'iCloud'} desconectado")
    db.commit()


@router.post("/api/integrations/sync")
def sync_now(db: DB) -> dict:
    return sync_all(db)


# ---------------------------------------------------------------- correo

def _mail(m: EmailMessage, tz: str) -> dict:
    return {"id": m.id, "sender": m.sender, "subject": m.subject, "snippet": m.snippet[:200], "reason": m.reason,
            "received_at": utc_naive_to_local(m.received_at, tz).isoformat()}


@router.get("/api/email/important")
def important(db: DB) -> dict:
    tz = _tz(db)
    return {"items": [_mail(m, tz) for m in email_sync.important_today(db, tz)], **_status(db)["gmail"]}


@router.post("/api/email/{mail_id}/dismiss", status_code=204)
def dismiss(mail_id: int, db: DB) -> None:
    m = db.get(EmailMessage, mail_id)
    if not m:
        raise HTTPException(404, "Correo no encontrado")
    m.dismissed = True
    db.commit()


# ---------------------------------------------------------------- calendario

def _event(e: CalendarEvent, tz: str) -> dict:
    return {"id": e.id, "title": e.title, "location": e.location, "source": e.source,
            "start_at": utc_naive_to_local(e.start_at, tz).isoformat(),
            "end_at": utc_naive_to_local(e.end_at, tz).isoformat() if e.end_at else None}


@router.get("/api/calendar")
def calendar(db: DB, days: int = 30) -> dict:
    tz = _tz(db)
    now = datetime.utcnow()
    rows = list(db.scalars(select(CalendarEvent).where(CalendarEvent.start_at >= now - timedelta(hours=12),
                                                       CalendarEvent.start_at <= now + timedelta(days=min(days, 120)))
                           .order_by(CalendarEvent.start_at)))
    return {"items": [_event(e, tz) for e in rows], "conflicts": calendar_sync.conflicts(rows), **_status(db)["icloud"]}


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start_at: datetime
    end_at: datetime
    location: str | None = Field(default=None, max_length=300)
    to_icloud: bool = False  # el usuario lo confirma explícitamente en la interfaz


@router.post("/api/calendar", status_code=201)
def create_event(body: EventIn, db: DB) -> dict:
    if body.start_at.tzinfo is None or body.end_at.tzinfo is None:
        raise HTTPException(422, "Las fechas deben incluir zona horaria")
    s = body.start_at.astimezone(timezone.utc).replace(tzinfo=None)
    e = body.end_at.astimezone(timezone.utc).replace(tzinfo=None)
    if e <= s:
        raise HTTPException(422, "El final debe ser posterior al inicio")
    if body.to_icloud:
        if not _status(db)["icloud"]["connected"]:
            raise HTTPException(400, "iCloud no está conectado")
        try:
            calendar_sync.create_icloud_event(body.title, s, e, body.location)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"No se pudo crear en iCloud: {str(exc)[:120]}") from exc
        sync_all(db)
        log_activity(db, "calendar", "create", f"Evento creado en iCloud: {body.title[:80]}")
        db.commit()
        ev = db.scalars(select(CalendarEvent).where(CalendarEvent.title == body.title, CalendarEvent.start_at == s)).first()
        return _event(ev, _tz(db)) if ev else {"title": body.title, "source": "icloud"}
    ev = CalendarEvent(title=body.title, start_at=s, end_at=e, location=body.location, source="local")
    db.add(ev)
    log_activity(db, "calendar", "create", f"Evento creado: {body.title[:80]}")
    db.commit()
    return _event(ev, _tz(db))


@router.delete("/api/calendar/{event_id}", status_code=204)
def delete_event(event_id: int, db: DB) -> None:
    ev = db.get(CalendarEvent, event_id)
    if not ev:
        raise HTTPException(404, "Evento no encontrado")
    if ev.source != "local":
        raise HTTPException(400, "Los eventos de iCloud se borran desde el calendario de Apple")
    db.delete(ev)
    db.commit()
