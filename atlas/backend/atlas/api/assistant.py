from fastapi import APIRouter
from pydantic import BaseModel, Field

from atlas.api.deps import DB
from atlas.services.alerts import build_alerts
from atlas.services.assistant import answer, briefing, welcome
from atlas.services.dashboard import build_dashboard
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class Query(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def _data(db) -> dict:  # noqa: ANN001
    d = build_dashboard(db, get_prefs(db))
    d["alerts"] = build_alerts(d)
    return d


@router.post("/query")
def query(body: Query, db: DB) -> dict:
    return answer(body.text, _data(db))


@router.get("/briefing")
def get_briefing(db: DB) -> dict:
    return {"reply": briefing(_data(db)), "intent": "briefing", "mode": "local"}


@router.get("/welcome")
def get_welcome(db: DB) -> dict:
    return {"reply": welcome(_data(db)), "intent": "welcome", "mode": "local"}
