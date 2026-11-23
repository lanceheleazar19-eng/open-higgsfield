from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from atlas.api.deps import DB
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs, list_timezones, set_prefs, validate_timezone

router = APIRouter(prefix="/api/settings", tags=["settings"])


class PrefsUpdate(BaseModel):
    user_name: str | None = Field(default=None, max_length=80)
    timezone: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    ai_model: str | None = Field(default=None, max_length=200)  # "" = automático

    @field_validator("user_name")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if v is not None else v

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


PUBLIC = ("user_name", "timezone", "currency", "ai_model")


def _public(prefs: dict) -> dict:
    return {k: prefs[k] for k in PUBLIC}


@router.get("")
def read_prefs(db: DB) -> dict:
    return _public(get_prefs(db))


@router.put("")
def update_prefs(body: PrefsUpdate, db: DB) -> dict:
    changes = body.model_dump(exclude_none=True)
    if "timezone" in changes:
        try:
            validate_timezone(changes["timezone"])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not changes:
        return _public(get_prefs(db))
    prefs = _public(set_prefs(db, changes))
    log_activity(db, "settings", "update", "Preferencias actualizadas: " + ", ".join(sorted(changes)))
    db.commit()
    return prefs


@router.get("/timezones")
def timezones() -> list[str]:
    return list_timezones()
