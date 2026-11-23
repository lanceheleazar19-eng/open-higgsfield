import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from atlas.api.deps import DB
from atlas.brain.orchestrator import brain_status, chat_events
from atlas.services.alerts import build_alerts
from atlas.services.dashboard import build_dashboard
from atlas.services.preferences import get_prefs

router = APIRouter(tags=["ai"])


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    history: list[Message] = Field(default_factory=list, max_length=40)


@router.get("/api/ai/status")
def ai_status(db: DB) -> dict:
    return brain_status(get_prefs(db))


@router.post("/api/assistant/chat")
def chat(body: ChatIn, db: DB) -> StreamingResponse:
    """Respuesta en streaming, una línea JSON por evento (NDJSON)."""
    prefs = get_prefs(db)
    d = build_dashboard(db, prefs)
    d["alerts"] = build_alerts(d)
    history = [m.model_dump() for m in body.history]

    def gen():
        for ev in chat_events(d, prefs, body.text, history):
            yield json.dumps(ev, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})
