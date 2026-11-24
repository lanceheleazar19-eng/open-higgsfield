"""Voz de VISTAN mediante VoiceStudio (local). El texto solo va a VoiceStudio en tu equipo."""

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

from atlas.voice import voicestudio as vs

router = APIRouter(prefix="/api/voicestudio", tags=["voice"])


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=vs.MAX_TEXT)
    voice: str | None = Field(default=None, max_length=200)
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    language: str | None = Field(default="es", max_length=12)


@router.get("/status")
async def status() -> dict:
    return await run_in_threadpool(vs.status)


@router.post("/speak")
async def speak(body: SpeakIn) -> Response:
    try:
        audio, ctype = await run_in_threadpool(vs.speak, body.text, body.voice, body.speed, "mp3", body.language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except vs.VoiceStudioError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=audio, media_type=ctype, headers={"Cache-Control": "no-store"})
