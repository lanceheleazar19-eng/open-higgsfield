"""Perfil personal: nombre, usuario, foto y preferencias.

La foto se guarda SOLO en la carpeta de datos local (data/avatar.webp). Se valida por su
contenido real (no por la extensión), se re-codifica (elimina EXIF/GPS y cualquier carga
oculta), se recorta cuadrada y se reduce a 512 px. Nunca se envía a la IA ni a terceros.
"""

import io
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator

from atlas.api.deps import DB
from atlas.config import get_settings
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs, set_prefs

router = APIRouter(prefix="/api/profile", tags=["profile"])

MAX_BYTES = 10 * 1024 * 1024
ALLOWED = {"JPEG", "PNG", "WEBP"}
SIZE = 512
Image.MAX_IMAGE_PIXELS = 40_000_000  # protección contra «bombas de descompresión»


def _avatar_path():
    d = get_settings().resolved_data_dir
    d.mkdir(parents=True, exist_ok=True)
    return d / "avatar.webp"


def _profile(db) -> dict:  # noqa: ANN001
    prefs = get_prefs(db)
    if not prefs.get("profile_created_at"):
        prefs = set_prefs(db, {"profile_created_at": datetime.now(timezone.utc).isoformat()})
        db.commit()
    p = _avatar_path()
    return {
        "display_name": prefs["user_name"],
        "username": prefs.get("username") or "",
        "preferences": prefs.get("personal_preferences") or "",
        "greeting": prefs.get("greeting") or "",
        "created_at": prefs["profile_created_at"],
        "has_avatar": p.exists(),
        "avatar_version": int(p.stat().st_mtime) if p.exists() else None,
    }


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    username: str | None = Field(default=None, pattern=r"^$|^[a-zA-Z0-9._-]{3,30}$")
    preferences: str | None = Field(default=None, max_length=2000)
    greeting: str | None = Field(default=None, max_length=120)

    @field_validator("display_name", "preferences", "greeting")
    @classmethod
    def strip(cls, v: str | None) -> str | None:
        return v.strip() if v is not None else v


@router.get("")
def read(db: DB) -> dict:
    return _profile(db)


@router.put("")
def update(body: ProfileIn, db: DB) -> dict:
    changes = {}
    if body.display_name is not None:
        changes["user_name"] = body.display_name
    if body.username is not None:
        changes["username"] = body.username.lower()
    if body.preferences is not None:
        changes["personal_preferences"] = body.preferences
    if body.greeting is not None:
        changes["greeting"] = body.greeting
    if changes:
        set_prefs(db, changes)
        log_activity(db, "settings", "profile", "Perfil actualizado")
        db.commit()
    return _profile(db)


@router.post("/avatar")
async def upload_avatar(db: DB, file: UploadFile = File(...)) -> dict:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "La imagen supera 10 MB")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()  # detecta archivos corruptos o manipulados
        if fmt not in ALLOWED:
            raise HTTPException(415, "Formato no permitido: usa JPG, PNG o WEBP")
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)  # respeta la orientación de la cámara
        img = img.convert("RGB")
        img = ImageOps.fit(img, (SIZE, SIZE), method=Image.Resampling.LANCZOS)  # recorte cuadrado centrado
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(415, "El archivo no es una imagen válida (JPG, PNG o WEBP)") from exc
    out = io.BytesIO()
    img.save(out, "WEBP", quality=90)  # re-codificada: sin EXIF ni metadatos
    p = _avatar_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(out.getvalue())
    tmp.replace(p)
    log_activity(db, "settings", "avatar", "Foto de perfil actualizada")
    db.commit()
    return _profile(db)


@router.get("/avatar")
def get_avatar() -> Response:
    p = _avatar_path()
    if not p.exists():
        raise HTTPException(404, "Sin foto de perfil")
    return FileResponse(p, media_type="image/webp", headers={"Cache-Control": "private, max-age=31536000, immutable"})


@router.delete("/avatar", status_code=204)
def delete_avatar(db: DB) -> None:
    p = _avatar_path()
    if p.exists():
        p.unlink()
        log_activity(db, "settings", "avatar", "Foto de perfil eliminada")
        db.commit()
