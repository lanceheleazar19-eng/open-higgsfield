"""Bóveda documental de VISTAN LEGAL.
- El original se guarda CIFRADO (Fernet/AES) en la carpeta de datos; la clave vive en el Llavero del sistema.
- El texto extraído se indexa en el gestor documental de VISTAN marcado como bóveda «legal»: fuera de la búsqueda general,
  del grafo y del chat; la búsqueda legal se filtra por expediente para que nada se cruce entre expedientes.
- Extracción: PDF, DOCX, TXT/MD (existente) + DOC (textutil de macOS), RTF, ODT y PDF escaneado (OCR con el modelo
  de visión LOCAL). Si no hay forma real de extraer el texto, se dice; nunca se inventa contenido."""

from __future__ import annotations

import hashlib
import io
import re
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.config import get_settings
from atlas.integrations.secrets import get_secret, set_secret
from atlas.models import DocChunk, Document, LgDocument
from atlas.security.policy import sanitize_untrusted

MAX_BYTES = 25 * 1024 * 1024
EXT = {".pdf": "pdf", ".docx": "docx", ".doc": "doc", ".txt": "txt", ".md": "md", ".rtf": "rtf", ".odt": "odt",
       ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image"}


# ───────── cifrado ─────────
def _fernet() -> Fernet:
    key = get_secret("legal_vault_key")
    if not key:
        key = Fernet.generate_key().decode()
        set_secret("legal_vault_key", key)
    return Fernet(key.encode())


def vault_dir() -> Path:
    p = Path(get_settings().data_dir) / "legal"
    p.mkdir(parents=True, exist_ok=True)
    return p


def store(data: bytes) -> str:
    name = f"{uuid.uuid4().hex}.bin"
    (vault_dir() / name).write_bytes(_fernet().encrypt(data))
    return name


def load(name: str) -> bytes:
    p = vault_dir() / Path(name).name  # nunca rutas fuera de la bóveda
    try:
        return _fernet().decrypt(p.read_bytes())
    except InvalidToken as exc:
        raise ValueError("No se puede descifrar el archivo (¿cambió la clave del Llavero?)") from exc


def erase(name: str | None) -> None:
    if name:
        p = vault_dir() / Path(name).name
        if p.exists():
            p.write_bytes(b"\0" * min(p.stat().st_size, 1 << 20))  # sobrescritura básica antes de borrar
            p.unlink()


# ───────── extracción ─────────
def _rtf(data: bytes) -> str:
    t = data.decode("latin-1", errors="replace")
    t = re.sub(r"\\'([0-9a-f]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", errors="replace"), t)
    t = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), t)
    t = re.sub(r"\{\\\*[^{}]*\}", "", t)
    t = re.sub(r"\\(par|line)\b ?", "\n", t)
    t = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", t)
    return re.sub(r"[{}]", "", t).strip()


def _odt(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ElementTree.fromstring(z.read("content.xml"))
    ns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    out = []
    for el in root.iter():
        if el.tag in (f"{ns}p", f"{ns}h"):
            out.append("".join(el.itertext()))
    return "\n".join(out).strip()


def _doc(data: bytes) -> str:
    """Word 97-2003: con la herramienta de macOS (textutil) o antiword si existen. Si no, se pide convertir a DOCX."""
    tool = shutil.which("textutil") or shutil.which("antiword")
    if not tool:
        raise ValueError("Formato .doc antiguo: en este equipo no hay conversor (textutil/antiword). Guárdalo como .docx o PDF.")
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "in.doc"
        src.write_bytes(data)
        cmd = [tool, "-convert", "txt", "-stdout", str(src)] if tool.endswith("textutil") else [tool, str(src)]
        r = subprocess.run(cmd, capture_output=True, timeout=60, check=False)  # noqa: S603 - binario del sistema, sin shell
        if r.returncode != 0:
            raise ValueError("No se pudo convertir el .doc")
        return r.stdout.decode("utf-8", errors="replace").strip()


def _pdf_ocr(data: bytes, prefs: dict) -> str:
    """PDF escaneado: las páginas son imágenes; se transcriben con el modelo de visión LOCAL (nada sale del equipo)."""
    from pypdf import PdfReader

    from atlas.knowledge.service import image_text
    pages = []
    for i, page in enumerate(PdfReader(io.BytesIO(data)).pages[:30]):
        for img in page.images[:2]:
            txt = image_text(img.data, prefs)
            if txt.strip():
                pages.append(f"[Página {i + 1}]\n{txt}")
    return "\n\n".join(pages)


def extract(kind: str, data: bytes, prefs: dict) -> tuple[str, str]:
    """(texto, método). Lanza ValueError con un mensaje claro si no se puede."""
    from atlas.knowledge.extract import extract as base_extract
    from atlas.knowledge.service import image_text
    if kind in ("pdf", "docx", "txt", "md"):
        text = base_extract(kind, data)
        if kind == "pdf" and len(text.strip()) < 40:
            ocr = _pdf_ocr(data, prefs)
            if not ocr.strip():
                raise ValueError("PDF escaneado sin texto y sin modelo de visión local para OCR (ollama pull qwen2.5vl:7b)")
            return ocr, "ocr-vision-local"
        return text, kind
    if kind == "rtf":
        return _rtf(data), "rtf"
    if kind == "odt":
        return _odt(data), "odt"
    if kind == "doc":
        return _doc(data), "doc"
    if kind == "image":
        t = image_text(data, prefs)
        if not t.strip():
            raise ValueError("Imagen sin texto legible o sin modelo de visión local (ollama pull qwen2.5vl:7b)")
        return t, "ocr-vision-local"
    raise ValueError("Formato no admitido")


def kind_for(filename: str) -> str | None:
    return EXT.get(Path(filename).suffix.lower())


def _hash(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def add(db: Session, *, title: str, kind: str, case_id: int | None, prefs: dict, data: bytes | None = None,
        filename: str | None = None, text: str | None = None, origin: str = "original", meta: dict | None = None,
        parent_id: int | None = None, version: int = 1) -> tuple[LgDocument, bool]:
    """Guarda un documento en la bóveda. Devuelve (documento, creado). Evita duplicados dentro del mismo expediente."""
    if data is not None and len(data) > MAX_BYTES:
        raise ValueError("Archivo demasiado grande (máx. 25 MB)")
    sha = _hash(data) if data is not None else None
    if sha:
        dup = db.scalar(select(LgDocument).where(LgDocument.sha256 == sha, LgDocument.case_id.is_(case_id) if case_id is None
                                                 else LgDocument.case_id == case_id))
        if dup:
            return dup, False
    method = "texto"
    if text is None:
        fkind = kind_for(filename or "") if filename else None
        if not fkind:
            raise ValueError("Formato no admitido: PDF, DOCX, DOC, TXT, RTF, ODT o imagen")
        text, method = extract(fkind, data or b"", prefs)
    text = text.strip()
    if not text:
        raise ValueError("El documento no contiene texto extraíble")
    th = _hash(text.encode())
    if data is None:
        dup = db.scalar(select(LgDocument).where(LgDocument.text_hash == th, LgDocument.case_id == case_id) if case_id is not None
                        else select(LgDocument).where(LgDocument.text_hash == th, LgDocument.case_id.is_(None)))
        if dup:
            return dup, False
    from atlas.knowledge.service import ingest
    d = ingest(db, title=f"[Legal] {title}"[:300], kind="txt" if kind != "note" else "note", text_=text, filename=filename,
               prefs=prefs, vault="legal")
    lg = LgDocument(case_id=case_id, document_id=d.id, title=title[:300], kind=kind, origin=origin, filename=filename,
                    size_bytes=len(data) if data is not None else len(text.encode()), sha256=sha, text_hash=th,
                    stored_path=store(data) if data is not None else None, extraction=method, chars=len(text),
                    meta=meta or {}, parent_id=parent_id, version=version, status=d.status, error=d.error)
    db.add(lg)
    db.flush()
    return lg, True


def text_of(db: Session, lg: LgDocument) -> str:
    if not lg.document_id:
        return ""
    return "\n".join(c.text for c in db.scalars(select(DocChunk).where(DocChunk.document_id == lg.document_id).order_by(DocChunk.idx)))


def clean_text(db: Session, lg: LgDocument) -> tuple[str, bool]:
    """Texto para la IA: el contenido es DATO, no instrucciones (se neutraliza lo que parezca una orden)."""
    return sanitize_untrusted(text_of(db, lg))


def search(db: Session, query: str, case_id: int | None = None, k: int = 6, all_cases: bool = False) -> list[dict]:
    """Búsqueda semántica + texto en la bóveda legal. Por defecto, SOLO en el expediente indicado."""
    from atlas.knowledge.service import search as kb_search
    q = select(LgDocument.document_id, LgDocument.id)
    if not all_cases:
        q = q.where(LgDocument.case_id == case_id) if case_id is not None else q.where(LgDocument.case_id.is_(None))
    pairs = [(d, l) for d, l in db.execute(q).all() if d]
    by_doc = {d: l for d, l in pairs}
    hits = kb_search(db, query, k=k, vault="legal", doc_ids=set(by_doc))
    for h in hits:
        lg = db.get(LgDocument, by_doc[h["document_id"]])
        h.update(legal_doc_id=lg.id, case_id=lg.case_id, origin=lg.origin, title=lg.title, kind=lg.kind, version=lg.version,
                 created_at=lg.created_at.isoformat())
    return hits


def delete(db: Session, lg: LgDocument) -> None:
    erase(lg.stored_path)
    if lg.document_id:
        d = db.get(Document, lg.document_id)
        if d:
            db.delete(d)
    db.delete(lg)
    db.flush()
