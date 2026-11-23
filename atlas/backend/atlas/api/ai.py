import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from atlas.api.deps import DB
from atlas.brain.orchestrator import brain_status, chat_events
from atlas.db import session_scope
from atlas.services import conversations as convs
from atlas.services import memory as mem
from atlas.services.alerts import build_alerts
from atlas.services.dashboard import build_dashboard
from atlas.services.preferences import get_prefs

router = APIRouter(tags=["ai"])


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    # Solo se usa si no hay conversation_id (compatibilidad); si lo hay, el historial sale de la base de datos
    history: list[Message] = Field(default_factory=list, max_length=40)


@router.get("/api/ai/status")
def ai_status(db: DB) -> dict:
    return brain_status(get_prefs(db))


def _line(ev: dict) -> str:
    return json.dumps(ev, ensure_ascii=False) + "\n"


@router.post("/api/assistant/chat")
def chat(body: ChatIn) -> StreamingResponse:
    """Conversación en streaming (NDJSON). Guarda la conversación y usa la memoria de ATLAS."""

    def gen():
        with session_scope() as db:
            prefs = get_prefs(db)
            tz = str(prefs["timezone"])
            conv = convs.get_or_create(db, body.conversation_id, body.text)
            hist = convs.history(db, conv) if body.conversation_id else [m.model_dump() for m in body.history]
            convs.add_message(db, conv, "user", body.text)
            db.commit()
            yield _line({"type": "meta", "conversation_id": conv.id})

            # Órdenes explícitas de memoria: «recuerda que…» / «olvida que…»
            cmd = mem.parse_command(body.text)
            if cmd:
                action, content = cmd
                if action == "remember":
                    m, created = mem.remember(db, content, kind=mem.guess_kind(content),
                                              expires_at=mem.guess_expiry(content, tz), source="chat")
                    item = mem.to_dict(m, tz)
                    yield _line({"type": "memory", "action": "saved" if created else "duplicate", "memory": item})
                    if created:
                        reply = f"Hecho. Lo recordaré: «{m.content}»."
                        if m.expires_at:
                            reply += f" Es temporal: lo tendré en cuenta hasta el {item['expires_at'][8:10]}/{item['expires_at'][5:7]}."
                    else:
                        reply = f"Eso ya lo tenía guardado: «{m.content}». He actualizado la fecha."
                else:
                    found = mem.search_memories(db, content, limit=1)
                    if found:
                        yield _line({"type": "memory", "action": "forget_candidate", "memory": mem.to_dict(found[0], tz)})
                        reply = f"¿Quieres que olvide esto?: «{found[0].content}». Confírmalo con el botón."
                    else:
                        reply = "No encuentro nada parecido en mi memoria."
                yield _line({"type": "delta", "text": reply})
                yield _line({"type": "done", "mode": "memory", "model": None})
                convs.add_message(db, conv, "assistant", reply, mode="local")
                db.commit()
                return

            d = build_dashboard(db, prefs)
            d["alerts"] = build_alerts(d)
            memory_ctx = mem.memory_context(db, body.text, tz, conversation_id=conv.id)
            db.commit()
            text, final = "", None
            for ev in chat_events(d, prefs, body.text, hist, memory=memory_ctx):
                if ev["type"] == "delta":
                    text += ev["text"]
                elif ev["type"] in ("done", "error"):
                    final = ev
                yield _line(ev)
            if text:
                mode = final.get("mode") if final and final["type"] == "done" else None
                convs.add_message(db, conv, "assistant", text, mode=mode, model=(final or {}).get("model"))
                db.commit()

    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})
