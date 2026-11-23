"""Calendario de iCloud por CalDAV (contraseña de aplicación de Apple).
Importa eventos (−1 a +60 días, recurrentes expandidos) a calendar_events con source="icloud"."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.integrations.secrets import get_secret
from atlas.models import CalendarEvent
from atlas.services.activity import log_activity

CALDAV_URL = "https://caldav.icloud.com"


def _utc(v) -> tuple[datetime, bool]:  # noqa: ANN001
    if isinstance(v, datetime):
        if v.tzinfo is None:
            return v, False
        return v.astimezone(timezone.utc).replace(tzinfo=None), False
    return datetime.combine(v, datetime.min.time()), True  # día completo


def fetch_events(user: str, password: str, start: datetime, end: datetime) -> list[dict]:
    import caldav
    client = caldav.DAVClient(url=CALDAV_URL, username=user, password=password)
    out = []
    for cal in client.principal().calendars():
        for ev in cal.search(start=start, end=end, event=True, expand=True):
            comp = ev.icalendar_component
            s, all_day = _utc(comp.get("dtstart").dt)
            e_raw = comp.get("dtend")
            e = _utc(e_raw.dt)[0] if e_raw else None
            uid = str(comp.get("uid"))
            out.append({"external_id": f"{uid}@{s.isoformat()}", "title": str(comp.get("summary") or "(sin título)"),
                        "location": str(comp.get("location")) if comp.get("location") else None,
                        "start_at": s, "end_at": e, "all_day": all_day, "calendar": str(cal.name or "")})
    return out


def sync(db: Session, fetch=None) -> dict:
    fetch = fetch or fetch_events
    user, pwd = get_secret("icloud_user"), get_secret("icloud_app_password")
    if not user or not pwd:
        return {"configured": False}
    start = datetime.utcnow() - timedelta(days=1)
    end = datetime.utcnow() + timedelta(days=60)
    events = fetch(user, pwd, start, end)
    existing = {e.external_id: e for e in db.scalars(select(CalendarEvent).where(CalendarEvent.source == "icloud"))}
    seen = set()
    added = 0
    for ev in events:
        seen.add(ev["external_id"])
        row = existing.get(ev["external_id"])
        if row is None:
            db.add(CalendarEvent(title=ev["title"], location=ev["location"], start_at=ev["start_at"], end_at=ev["end_at"],
                                 source="icloud", external_id=ev["external_id"], description=ev.get("calendar")))
            added += 1
        else:
            row.title, row.location, row.start_at, row.end_at = ev["title"], ev["location"], ev["start_at"], ev["end_at"]
    # eventos borrados en iCloud dentro de la ventana sincronizada
    removed = 0
    for ext, row in existing.items():
        if ext not in seen and start <= row.start_at <= end:
            db.delete(row)
            removed += 1
    if added or removed:
        log_activity(db, "calendar", "sync", f"Calendario de iCloud: {added} nuevos, {removed} eliminados")
    db.commit()
    return {"configured": True, "events": len(events), "added": added, "removed": removed}


def create_icloud_event(title: str, start: datetime, end: datetime, location: str | None) -> None:
    """Crea el evento en el primer calendario de iCloud (fechas en UTC)."""
    import caldav
    client = caldav.DAVClient(url=CALDAV_URL, username=get_secret("icloud_user"), password=get_secret("icloud_app_password"))
    cal = client.principal().calendars()[0]
    cal.save_event(dtstart=start.replace(tzinfo=timezone.utc), dtend=end.replace(tzinfo=timezone.utc), summary=title,
                   location=location or "")


def conflicts(events: list[CalendarEvent]) -> list[tuple[int, int]]:
    """Pares de eventos que se solapan."""
    out = []
    evs = sorted((e for e in events if e.end_at), key=lambda e: e.start_at)
    for i, a in enumerate(evs):
        for b in evs[i + 1:]:
            if b.start_at >= a.end_at:
                break
            out.append((a.id, b.id))
    return out
