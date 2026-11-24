"""Base de conocimiento (documentos/RAG), grafo y Markdown."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.knowledge import graph as kg
from atlas.knowledge.extract import KINDS, kind_for
from atlas.knowledge.service import doc_dict, ingest, search
from atlas.knowledge.web import fetch
from atlas.models import DocChunk, Document, Entity, Relation
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
MAX_FILE = 40 * 1024 * 1024


@router.get("/documents")
def list_docs(db: DB, project_id: int | None = None) -> list[dict]:
    q = select(Document).order_by(Document.created_at.desc())
    if project_id:
        q = q.where(Document.project_id == project_id)
    return [doc_dict(d) for d in db.scalars(q)]


@router.post("/documents", status_code=201)
async def upload(db: DB, files: list[UploadFile] = File(...), project_id: int | None = Form(None)) -> list[dict]:
    out = []
    for f in files[:20]:
        data = await f.read()
        if len(data) > MAX_FILE:
            raise HTTPException(413, f"{f.filename}: supera 40 MB")
        kind = kind_for(f.filename or "")
        if not kind:
            raise HTTPException(415, f"{f.filename}: formato no admitido (PDF, DOCX, TXT, MD, CSV, XLSX o imagen)")
        d = ingest(db, title=(f.filename or "documento").rsplit(".", 1)[0], kind=kind, data=data, filename=f.filename,
                   project_id=project_id, prefs=get_prefs(db))
        log_activity(db, "knowledge", "import", f"Documento «{d.title}» ({KINDS[kind]})")
        out.append(doc_dict(d))
    db.commit()
    return out


class UrlIn(BaseModel):
    url: str = Field(min_length=8, max_length=1000)
    project_id: int | None = None


@router.post("/documents/url", status_code=201)
def add_url(body: UrlIn, db: DB) -> dict:
    try:
        page = fetch(body.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    d = ingest(db, title=page["title"][:300], kind="url", text_=page["text"], url=page["url"], project_id=body.project_id)
    log_activity(db, "knowledge", "import", f"Web «{d.title}»")
    db.commit()
    return doc_dict(d)


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=200_000)
    project_id: int | None = None


@router.post("/documents/note", status_code=201)
def add_note(body: NoteIn, db: DB) -> dict:
    d = ingest(db, title=body.title, kind="note", text_=body.text, project_id=body.project_id)
    db.commit()
    return doc_dict(d)


@router.get("/documents/{doc_id}")
def get_doc(doc_id: int, db: DB) -> dict:
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Documento no encontrado")
    chunks = [c.text for c in db.scalars(select(DocChunk).where(DocChunk.document_id == d.id).order_by(DocChunk.idx).limit(6))]
    return doc_dict(d) | {"preview": "\n\n".join(chunks)[:6000]}


@router.patch("/documents/{doc_id}")
def patch_doc(doc_id: int, body: dict, db: DB) -> dict:
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Documento no encontrado")
    if "project_id" in body:
        d.project_id = body["project_id"]
    if body.get("title"):
        d.title = str(body["title"])[:300]
    db.commit()
    return doc_dict(d)


@router.delete("/documents/{doc_id}", status_code=204)
def delete_doc(doc_id: int, db: DB) -> None:
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Documento no encontrado")
    db.query(Relation).filter(((Relation.src_type == "document") & (Relation.src_id == doc_id)) |
                              ((Relation.dst_type == "document") & (Relation.dst_id == doc_id))).delete(synchronize_session=False)
    log_activity(db, "knowledge", "delete", f"Documento «{d.title}» eliminado")
    db.delete(d)
    db.commit()


@router.get("/search")
def do_search(q: str, db: DB, project_id: int | None = None, k: int = 8) -> list[dict]:
    return search(db, q, k=min(k, 20), project_id=project_id)


# ---------- Grafo ----------
@router.get("/graph")
def get_graph(db: DB, project_id: int | None = None) -> dict:
    return kg.build(db, project_id)


class EntityIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(default="concept", pattern="^(person|org|place|concept|idea)$")
    notes: str | None = Field(default=None, max_length=5000)
    project_id: int | None = None


@router.post("/entities", status_code=201)
def create_entity(body: EntityIn, db: DB) -> dict:
    e = Entity(**body.model_dump())
    db.add(e)
    db.commit()
    return {"id": e.id, "node": f"entity:{e.id}"}


@router.delete("/entities/{eid}", status_code=204)
def delete_entity(eid: int, db: DB) -> None:
    e = db.get(Entity, eid)
    if not e:
        raise HTTPException(404, "Entidad no encontrada")
    db.query(Relation).filter(((Relation.src_type == "entity") & (Relation.src_id == eid)) |
                              ((Relation.dst_type == "entity") & (Relation.dst_id == eid))).delete(synchronize_session=False)
    db.delete(e)
    db.commit()


class RelationIn(BaseModel):
    source: str = Field(pattern=r"^[a-z]+:\d+$")
    target: str = Field(pattern=r"^[a-z]+:\d+$")
    label: str = Field(default="relacionado", min_length=1, max_length=64)


@router.post("/relations", status_code=201)
def create_relation(body: RelationIn, db: DB) -> dict:
    (st, si), (dt, di) = [(x.split(":")[0], int(x.split(":")[1])) for x in (body.source, body.target)]
    if st not in kg.REL_TYPES or dt not in kg.REL_TYPES or not kg.exists(db, st, si) or not kg.exists(db, dt, di):
        raise HTTPException(422, "Alguno de los nodos no existe")
    if body.source == body.target:
        raise HTTPException(422, "Un nodo no puede relacionarse consigo mismo")
    r = Relation(src_type=st, src_id=si, dst_type=dt, dst_id=di, label=body.label)
    db.add(r)
    db.commit()
    return {"id": r.id}


@router.delete("/relations/{rid}", status_code=204)
def delete_relation(rid: int, db: DB) -> None:
    r = db.get(Relation, rid)
    if not r:
        raise HTTPException(404, "Relación no encontrada")
    db.delete(r)
    db.commit()


@router.get("/markdown/export")
def md_export(db: DB) -> Response:
    return Response(kg.export_markdown(db), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="atlas-segundo-cerebro.zip"'})


@router.post("/markdown/import")
async def md_import(db: DB, files: list[UploadFile] = File(...), project_id: int | None = Form(None)) -> dict:
    payload = [(f.filename or "nota.md", await f.read()) for f in files[:50]]
    r = kg.import_markdown(db, payload, project_id)
    log_activity(db, "knowledge", "import", f"Markdown: {r['documents']} notas, {r['links']} enlaces")
    db.commit()
    return r
