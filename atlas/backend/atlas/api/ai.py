import json
import re

from sqlalchemy import select
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from atlas.api.deps import DB
from atlas.brain.orchestrator import brain_status, chat_events
from atlas.db import session_scope
from atlas.services import conversations as convs
from atlas.gym import service as gym_svc
from atlas.gym.parse import looks_like_log, parse_workout
from atlas.models import Exercise, Goal
from atlas.services import goals as goals_svc
from atlas.services import memory as mem
from atlas.services import tasks as tasks_svc
from atlas.services.clock import local_to_utc_naive
from atlas.services.nlp import TASK_TRIGGER, parse_complete_command, parse_task_command
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


GYM_Q = re.compile(r"entren|gimnasio|gym|rutina|toca hoy|musculo|volumen|series|progres|mejorando|fuerza|press|curl|"
                   r"dominad|jalon|remo|triceps|biceps|pecho|espalda|hombro|pierna|1rm|estanc|peso|kilos|kg")
PLAN_Q = re.compile(r"organiza|planifica|plan de la semana|mi semana|esta semana|que hago (esta|la) semana")
DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
PRIO_ES = {"low": "baja", "medium": "media", "high": "alta", "critical": "crítica"}


def _when(dt: datetime, all_day: bool) -> str:
    s = f"el {DAYS[dt.weekday()]} {dt.day}/{dt.month}"
    return s if all_day else f"{s} a las {dt:%H:%M}"


def _es(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def _gym_log(db, text: str, tz: str):  # noqa: ANN001
    """Registra series si el mensaje es un entrenamiento. Devuelve (evento, respuesta) o None."""
    if not looks_like_log(text) or TASK_TRIGGER.match(text.strip()) or mem.parse_command(text):
        return None  # «apúntame…» es una tarea y «recuerda que…» es memoria, aunque mencionen series
    parsed = parse_workout(text, list(db.scalars(select(Exercise))))
    if not parsed:
        return None
    today = datetime.now(ZoneInfo(tz)).date()
    before = {g.id: g.current_value for g in goals_svc.active_goals(db)}
    s, _ = gym_svc.log_parsed(db, parsed, today)
    db.commit()
    lines = []
    for p in parsed:
        reps = "/".join(str(r) for r in p.reps)
        w = f" con {_es(p.weight)} kg{' por lado' if p.per_side else ''}" if p.weight else ""
        rir = f", RIR {p.rir}" if p.rir is not None else ""
        lines.append(f"{p.exercise_name}: {len(p.reps)}×({reps}){w}{rir}")
    reply = "Registrado en tu sesión de hoy: " + "; ".join(lines) + "."
    for g in goals_svc.active_goals(db):
        if g.auto_metric and before.get(g.id) != g.current_value:
            reply += f" Objetivo «{g.title}» actualizado: {_es(g.current_value)}{(' ' + g.unit) if g.unit else ''}."
    achieved = [g for g in db.scalars(select(Goal).where(Goal.status == "achieved", Goal.id.in_(list(before))))]
    for g in achieved:
        reply += f" 🎯 ¡Has conseguido «{g.title}»!"
    return {"type": "gym", "action": "logged", "session": gym_svc.session_dict(db, s)}, reply


def _task_command(db, text: str, tz: str):  # noqa: ANN001
    """Crea una tarea o propone completarla. Devuelve (evento, respuesta) o None."""
    now_local = datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
    p = parse_task_command(text, now_local)
    if p:
        due = local_to_utc_naive(p.due.replace(tzinfo=ZoneInfo(tz))) if p.due else None
        reminder = due if (p.reminder and due) else None
        if p.reminder and p.all_day and due:  # recordatorio de día completo → a las 9:00 de ese día
            reminder = local_to_utc_naive(p.due.replace(hour=9, minute=0, second=0, tzinfo=ZoneInfo(tz)))
        t = tasks_svc.create_task(db, title=p.title, priority=p.priority, category=p.category,
                                  due_at=due, all_day=p.all_day, reminder_at=reminder)
        db.commit()
        reply = f"Apuntado: «{t.title}»"
        if p.due:
            reply += " para " + _when(p.due, p.all_day)
        if p.priority != "medium":
            reply += f", prioridad {PRIO_ES[p.priority]}"
        reply += "."
        if reminder:
            reply += " Te avisaré a su hora mientras ATLAS esté abierto."
        return {"type": "task", "action": "created", "task": tasks_svc.to_dict(t, tz)}, reply
    target = parse_complete_command(text)
    if target:
        t = tasks_svc.find_open_task(db, target)
        if not t:
            return {"type": "task", "action": "not_found", "task": None}, "No encuentro ninguna tarea abierta parecida."
        return ({"type": "task", "action": "complete_candidate", "task": tasks_svc.to_dict(t, tz)},
                f"¿Marco como hecha «{t.title}»? Confírmalo con el botón.")
    return None


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

            # Registro de entrenamiento: «press inclinado 3x8 40kg rir 2»
            gym_ev = _gym_log(db, body.text, tz)
            if gym_ev:
                ev, reply = gym_ev
                yield _line(ev)
                yield _line({"type": "delta", "text": reply})
                yield _line({"type": "done", "mode": "gym", "model": None})
                convs.add_message(db, conv, "assistant", reply, mode="local")
                db.commit()
                return

            # Órdenes de tareas: «apúntame…», «recuérdame…», «he terminado…»
            task_ev = _task_command(db, body.text, tz)
            if task_ev:
                ev, reply = task_ev
                yield _line(ev)
                yield _line({"type": "delta", "text": reply})
                yield _line({"type": "done", "mode": "tasks", "model": None})
                convs.add_message(db, conv, "assistant", reply, mode="local")
                db.commit()
                return

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
            d["goal_snapshot"] = goals_svc.snapshot(db, date.fromisoformat(d["generated_at"][:10]))
            if GYM_Q.search(mem.normalize(body.text)) or not brain_status(prefs)["configured"]:
                d["gym"] = gym_svc.snapshot(db, date.fromisoformat(d["generated_at"][:10]))
            if PLAN_Q.search(mem.normalize(body.text)) or not brain_status(prefs)["configured"]:
                d["week_plan"] = tasks_svc.plan_week(db, tz)
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
