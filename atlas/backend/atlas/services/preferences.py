"""Preferencias del usuario guardadas en la tabla `settings`."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from sqlalchemy.orm import Session

from atlas.config import get_settings
from atlas.models import Setting

DEFAULTS: dict[str, object] = {
    "user_name": "",
    "timezone": None,  # None => ATLAS_TIMEZONE del entorno
    "currency": "EUR",
    "ai_model": "",  # "" => elección automática
    "username": "",
    "personal_preferences": "",
    "profile_created_at": None,
    "nutrition_profile": None,
    "gmail_last_sync": None,
    "icloud_last_sync": None,
    "paper_capital": None,
    "model_router": None,  # configuración del Model Router (ver atlas/brain/router.py)
    "security_policy": None,  # niveles WRITE/EXECUTE/ADMIN: auto | confirm
    "proactive": None,  # reglas de inteligencia proactiva activadas
    "insights_dismissed": None,
    "greeting": "",  # saludo personalizado  # capital VIRTUAL inicial del paper trading (no es dinero real)
}


def get_prefs(db: Session) -> dict[str, object]:
    prefs = dict(DEFAULTS)
    for row in db.query(Setting).filter(Setting.key.in_(DEFAULTS.keys())):
        prefs[row.key] = row.value
    if not prefs["timezone"]:
        prefs["timezone"] = get_settings().timezone
    return prefs


def set_prefs(db: Session, changes: dict[str, object]) -> dict[str, object]:
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise KeyError(key)
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
    db.flush()
    return get_prefs(db)


def validate_timezone(tz: str) -> str:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Zona horaria desconocida: {tz}") from exc
    return tz


def list_timezones() -> list[str]:
    return sorted(available_timezones())
