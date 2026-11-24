"""Base de conocimiento (RAG): importar → extraer → trocear → indexar (FTS5 y, si hay modelo de
embeddings en Ollama, vectores) → recuperar fragmentos con su fuente."""

import base64
import io
import math
import re

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from atlas.config import get_settings
from atlas.knowledge.extract import extract
from atlas.models import DocChunk, Document
from atlas.security.policy import sanitize_untrusted
from atlas.services.memory import _fts_query, _has_fts

CHUNK = 1000
OVERLAP = 150


def chunk_text(t: str, size: int = CHUNK, overlap: int = OVERLAP) -> list[str]:
    """Trocea respetando párrafos y frases cuando es posible."""
    t = re.sub(r"\n{3,}", "\n\n", t.strip())
    if not t:
        return []
    paras = [p.strip() for p in t.split("\n\n") if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        while len(p) > size:  # párrafo enorme: corta por frases
            cut = max(p.rfind(". ", 0, size), p.rfind("\n", 0, size))
            cut = cut + 1 if cut > size // 2 else size
            pieces, p = p[:cut].strip(), p[cut:].strip()
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(pieces)
        if len(cur) + len(p) + 2 <= size:
            cur = f"{cur}\n\n{p}" if cur else p
        else:
            if cur:
                chunks.append(cur)
            cur = (chunks[-1][-overlap:] + "\n\n" if chunks and overlap else "") + p
    if cur:
        chunks.append(cur)
    return chunks


# ---------- Embeddings (opcionales, locales) ----------
def embed_model() -> str | None:
    try:
        r = httpx.get(f"{get_settings().ollama_url}/api/tags", timeout=2.0)
        names = [m["name"] for m in r.json().get("models", [])]
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    for pref in ("nomic-embed-text", "mxbai-embed", "bge-m3", "snowflake-arctic-embed"):
        for n in names:
            if n.startswith(pref):
                return n
    return next((n for n in names if "embed" in n), None)


def embed(texts: list[str], model: str) -> list[list[float]] | None:
    try:
        r = httpx.post(f"{get_settings().ollama_url}/api/embed", json={"model": model, "input": texts}, timeout=120.0)
        r.raise_for_status()
        return r.json()["embeddings"]
    except (httpx.HTTPError, ValueError, KeyError):
        return None


def _cos(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


# ---------- Ingesta ----------
def image_text(data: bytes, prefs: dict) -> str:
    """Describe/transcribe una imagen con el modelo de visión LOCAL. Sin él, no se inventa nada."""
    from PIL import Image, ImageOps

    from atlas.brain.orchestrator import get_provider
    from atlas.nutrition.service import pick_vision_model
    prov = get_provider()
    st = prov.status()
    model = pick_vision_model(st.models) if st.reachable else None
    if not model:
        raise ValueError("Para leer imágenes necesitas un modelo de visión local: ollama pull qwen2.5vl:7b")
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((1280, 1280))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    out = prov.complete_json(model, [{"role": "user", "content":
        "Transcribe todo el texto visible de la imagen y describe brevemente su contenido. "
        'Responde JSON: {"texto": "...", "descripcion": "..."}',
        "images": [base64.b64encode(buf.getvalue()).decode()]}])
    return f"{out.get('texto', '')}\n\n[Descripción] {out.get('descripcion', '')}".strip()


def ingest(db: Session, *, title: str, kind: str, text_: str | None = None, data: bytes | None = None,
           filename: str | None = None, url: str | None = None, project_id: int | None = None,
           prefs: dict | None = None) -> Document:
    doc = Document(title=title[:300], kind=kind, filename=filename, source_url=url, project_id=project_id,
                   size_bytes=len(data or (text_ or "").encode()))
    db.add(doc)
    db.flush()
    try:
        if text_ is None:
            text_ = image_text(data or b"", prefs or {}) if kind == "image" else extract(kind, data or b"")
        if not text_.strip():
            raise ValueError("No se ha podido extraer texto (¿PDF escaneado sin texto?)")
        pieces = chunk_text(text_)
        for i, c in enumerate(pieces):
            db.add(DocChunk(document_id=doc.id, idx=i, text=c))
        doc.chars, doc.chunks, doc.status = len(text_), len(pieces), "ready"
        db.flush()
        model = embed_model()
        if model and pieces:
            vecs = embed(pieces, model)
            if vecs and len(vecs) == len(pieces):
                for ch, v in zip(db.scalars(select(DocChunk).where(DocChunk.document_id == doc.id).order_by(DocChunk.idx)), vecs):
                    ch.embedding = v
                doc.embedded = True
    except Exception as exc:  # noqa: BLE001 - el documento queda registrado con su error
        doc.status, doc.error = "error", str(exc)[:500]
    db.flush()
    return doc


def doc_dict(d: Document) -> dict:
    return {"id": d.id, "title": d.title, "filename": d.filename, "kind": d.kind, "url": d.source_url,
            "project_id": d.project_id, "size_bytes": d.size_bytes, "chars": d.chars, "chunks": d.chunks,
            "embedded": d.embedded, "status": d.status, "error": d.error, "created_at": d.created_at.isoformat()}


# ---------- Recuperación ----------
def search(db: Session, query: str, k: int = 6, project_id: int | None = None) -> list[dict]:
    """Fragmentos más relevantes: texto completo (BM25) + similitud semántica si hay embeddings."""
    scored: dict[int, float] = {}
    match = _fts_query(query)
    if match and _has_fts(db, "chunk_fts"):
        rows = db.execute(text("SELECT rowid, bm25(chunk_fts) AS s FROM chunk_fts WHERE chunk_fts MATCH :q ORDER BY s LIMIT 40"),
                          {"q": match}).all()
        for i, (rid, s) in enumerate(rows):
            scored[rid] = scored.get(rid, 0) + 1.0 / (1 + i)  # fusión por rango
    if db.scalar(select(Document.id).where(Document.embedded.is_(True)).limit(1)):
        model = embed_model()
        qv = embed([query], model) if model else None
        if qv:
            cand = db.execute(select(DocChunk.id, DocChunk.embedding).where(DocChunk.embedding.is_not(None)).limit(8000)).all()
            sims = sorted(((cid, _cos(qv[0], e)) for cid, e in cand), key=lambda x: -x[1])[:40]
            for i, (cid, s) in enumerate(sims):
                if s > 0.35:
                    scored[cid] = scored.get(cid, 0) + 1.0 / (1 + i)
    if not scored:
        return []
    chunks = {c.id: c for c in db.scalars(select(DocChunk).where(DocChunk.id.in_(list(scored))))}
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.id.in_({c.document_id for c in chunks.values()})))}
    out = []
    for cid, s in sorted(scored.items(), key=lambda x: -x[1]):
        c = chunks.get(cid)
        if not c:
            continue
        d = docs[c.document_id]
        if project_id is not None and d.project_id != project_id:
            continue
        clean, flagged = sanitize_untrusted(c.text)
        out.append({"document_id": d.id, "title": d.title, "kind": d.kind, "url": d.source_url, "chunk": c.idx,
                    "text": clean, "score": round(s, 3), "flagged": flagged})
        if len(out) >= k:
            break
    return out
