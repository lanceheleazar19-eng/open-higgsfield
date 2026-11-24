"""Almacenamiento PRIVADO de fotos: fuera de la carpeta web, nombres aleatorios, permisos solo para tu usuario,
sin metadatos EXIF (ubicación, móvil…), redimensionadas y en WEBP. Se sirven solo a través de la API."""

import io
import os
import secrets
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from atlas.config import get_settings

CATEGORIES = ("physique", "meal")
ALLOWED = {"JPEG", "PNG", "WEBP", "HEIF", "MPO"}
MAX_BYTES = 25 * 1024 * 1024


class BadImage(ValueError):
    pass


def folder(category: str) -> Path:
    assert category in CATEGORIES
    d = get_settings().resolved_data_dir / "private" / "photos" / category
    d.mkdir(parents=True, exist_ok=True)
    for p in (d, d.parent, d.parent.parent):
        try:
            os.chmod(p, 0o700)
        except OSError:
            pass
    return d


def save(category: str, data: bytes, max_side: int = 1600) -> tuple[str, int, int]:
    """Valida por contenido (no por extensión), corrige la orientación, quita metadatos y guarda foto + miniatura."""
    if len(data) > MAX_BYTES:
        raise BadImage("La foto supera 25 MB")
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        pass
    try:
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or "").upper()
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise BadImage("El archivo no es una imagen válida (JPG, PNG o WEBP)") from exc
    if fmt not in ALLOWED:
        raise BadImage("Formato no admitido: usa JPG, PNG o WEBP")
    img.thumbnail((max_side, max_side))
    name = secrets.token_hex(16)
    d = folder(category)
    img.save(d / f"{name}.webp", "WEBP", quality=86, method=4)
    th = img.copy()
    th.thumbnail((420, 420))
    th.save(d / f"{name}_t.webp", "WEBP", quality=80)
    for f in (d / f"{name}.webp", d / f"{name}_t.webp"):
        os.chmod(f, 0o600)
    return name, img.width, img.height


def path(category: str, name: str, thumb: bool = False) -> Path:
    if not name.isalnum():
        raise FileNotFoundError(name)
    return folder(category) / f"{name}{'_t' if thumb else ''}.webp"


def delete(category: str, name: str) -> None:
    for t in (False, True):
        try:
            path(category, name, t).unlink(missing_ok=True)
        except FileNotFoundError:
            pass
