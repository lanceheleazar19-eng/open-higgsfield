"""Grafo de conocimiento construido con TUS datos: cada nodo es un elemento real (recuerdo, proyecto,
objetivo, tarea, documento, investigación, conversación o entidad) y cada arista una relación real
(pertenencia, enlace explícito o mención del nombre de una entidad)."""

import io
import re
import zipfile
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from atlas.models import (Conversation, DocChunk, Document, Entity, Goal, Memory, Project, Relation, Research, Task)

TYPES = {"project": "Proyecto", "memory": "Recuerdo", "decision": "Decisión", "idea": "Idea", "goal": "Objetivo",
         "task": "Tarea", "document": "Documento", "research": "Investigación", "conversation": "Conversación",
         "person": "Persona", "org": "Organización", "place": "Lugar", "concept": "Concepto"}
REL_TYPES = ("project", "memory", "goal", "task", "document", "research", "conversation", "entity")


def _nid(t: str, i: int) -> str:
    return f"{t}:{i}"


def build(db: Session, project_id: int | None = None) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(t: str, i: int, label: str, kind: str, **extra) -> None:  # noqa: ANN003
        nodes[_nid(t, i)] = {"id": _nid(t, i), "type": t, "kind": kind, "label": label[:90], **extra}

    def edge(a: str, b: str, label: str, origin: str) -> None:
        if a in nodes and b in nodes and a != b:
            edges.append({"source": a, "target": b, "label": label, "origin": origin})

    for p in db.scalars(select(Project)):
        node("project", p.id, p.name, "project", status=p.status)
    for m in db.scalars(select(Memory).limit(800)):
        kind = {"decision": "decision", "goal": "goal", "note": "memory"}.get(m.kind, "memory")
        if m.kind == "note" and re.match(r"(?i)idea\b|💡", m.content):
            kind = "idea"
        node("memory", m.id, m.content, kind, project_id=m.project_id, detail=m.content)
        if m.project_id:
            edge(_nid("memory", m.id), _nid("project", m.project_id), "pertenece a", "dato")
    for g in db.scalars(select(Goal).where(Goal.status != "abandoned")):
        node("goal", g.id, g.title, "goal", status=g.status)
    recent = datetime.utcnow() - timedelta(days=45)
    for t in db.scalars(select(Task).where(or_(Task.status == "pending", Task.completed_at >= recent)).limit(400)):
        node("task", t.id, t.title, "task", status=t.status, project_id=t.project_id)
        if t.goal_id:
            edge(_nid("task", t.id), _nid("goal", t.goal_id), "avanza", "dato")
        if t.project_id:
            edge(_nid("task", t.id), _nid("project", t.project_id), "pertenece a", "dato")
    for d in db.scalars(select(Document).where(Document.vault.is_(None))):
        node("document", d.id, d.title, "document", project_id=d.project_id, doc_kind=d.kind)
        if d.project_id:
            edge(_nid("document", d.id), _nid("project", d.project_id), "pertenece a", "dato")
    for r in db.scalars(select(Research)):
        node("research", r.id, r.question, "research", status=r.status, project_id=r.project_id)
        if r.project_id:
            edge(_nid("research", r.id), _nid("project", r.project_id), "pertenece a", "dato")
    for c in db.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(30)):
        node("conversation", c.id, c.title, "conversation")
    entities = list(db.scalars(select(Entity)))
    for e in entities:
        node("entity", e.id, e.name, e.kind if e.kind in TYPES else "concept", project_id=e.project_id, detail=e.notes)
        if e.project_id:
            edge(_nid("entity", e.id), _nid("project", e.project_id), "pertenece a", "dato")
    for rel in db.scalars(select(Relation)):
        edge(_nid(rel.src_type, rel.src_id), _nid(rel.dst_type, rel.dst_id), rel.label, f"manual:{rel.id}")
    # Menciones: el nombre de una entidad aparece en el texto de otro elemento
    for e in entities:
        if len(e.name) < 3:
            continue
        rx = re.compile(rf"(?<!\w){re.escape(e.name)}(?!\w)", re.I)
        for nid, n in nodes.items():
            if n["type"] != "entity" and rx.search(n.get("detail") or n["label"]):
                edge(nid, _nid("entity", e.id), "menciona", "mención")

    if project_id:  # vista por proyecto: el proyecto, lo que le pertenece y sus vecinos directos
        keep = {_nid("project", project_id)} | {k for k, n in nodes.items() if n.get("project_id") == project_id}
        keep |= {e["source"] for e in edges if e["target"] in keep} | {e["target"] for e in edges if e["source"] in keep}
        nodes = {k: v for k, v in nodes.items() if k in keep}
        edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
    deg: dict[str, int] = {}
    for e in edges:
        deg[e["source"]] = deg.get(e["source"], 0) + 1
        deg[e["target"]] = deg.get(e["target"], 0) + 1
    for k, n in nodes.items():
        n["degree"] = deg.get(k, 0)
        n.pop("detail", None)
    return {"nodes": list(nodes.values()), "edges": edges, "types": TYPES}


def exists(db: Session, t: str, i: int) -> bool:
    model = {"project": Project, "memory": Memory, "goal": Goal, "task": Task, "document": Document,
             "research": Research, "conversation": Conversation, "entity": Entity}.get(t)
    return bool(model and db.get(model, i))


# ---------- Markdown (compatible con Obsidian) ----------
def _slug(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|#^\[\]]", " ", s).strip()
    return re.sub(r"\s+", " ", s)[:80] or "sin título"


def export_markdown(db: Session) -> bytes:
    g = build(db)
    names = {n["id"]: _slug(n["label"]) for n in g["nodes"]}
    links: dict[str, list[str]] = {}
    for e in g["edges"]:
        links.setdefault(e["source"], []).append(f"- {e['label']}: [[{names[e['target']]}]]")
        links.setdefault(e["target"], []).append(f"- {e['label']} (desde): [[{names[e['source']]}]]")
    folder = {"project": "Proyectos", "memory": "Memoria", "goal": "Objetivos", "task": "Tareas", "document": "Documentos",
              "research": "Investigaciones", "conversation": "Conversaciones", "entity": "Entidades"}
    full = {m.id: m.content for m in db.scalars(select(Memory))}
    reports = {r.id: r for r in db.scalars(select(Research))}
    buf = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n in g["nodes"]:
            t, i = n["type"], int(n["id"].split(":")[1])
            body = n["label"]
            if t == "memory":
                body = full.get(i, body)
            elif t == "research" and reports.get(i) and reports[i].report:
                rep = reports[i].report
                body = f"# {reports[i].question}\n\n{rep.get('summary', '')}\n\n" + "\n".join(
                    f"- {c['text']} (confianza {c.get('confidence')})" for c in rep.get("conclusions", []))
            elif t == "document":
                body = "\n\n".join(c.text for c in db.scalars(select(DocChunk).where(DocChunk.document_id == i).order_by(DocChunk.idx).limit(40)))
            path = f"{folder[t]}/{names[n['id']]}.md"
            k = 2
            while path in used:
                path = f"{folder[t]}/{names[n['id']]} ({k}).md"
                k += 1
            used.add(path)
            front = f"---\natlas_id: {n['id']}\ntipo: {TYPES.get(n['kind'], n['kind'])}\n---\n\n"
            rel = "\n\n## Relaciones\n" + "\n".join(links[n["id"]]) if n["id"] in links else ""
            z.writestr(path, front + body + rel + "\n")
    return buf.getvalue()


WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")


def import_markdown(db: Session, files: list[tuple[str, bytes]], project_id: int | None = None) -> dict:
    """Cada nota .md se importa como documento consultable; cada [[enlace]] crea (o reutiliza) una entidad
    y una relación real documento → entidad."""
    from atlas.knowledge.service import ingest
    expanded: list[tuple[str, bytes]] = []
    for name, data in files:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                expanded += [(n, z.read(n)) for n in z.namelist() if n.lower().endswith(".md") and not n.startswith("__MACOSX")]
        elif name.lower().endswith((".md", ".markdown")):
            expanded.append((name, data))
    docs = links = 0
    for name, data in expanded[:500]:
        text_ = data.decode("utf-8", errors="replace")
        title = re.sub(r"\.(md|markdown)$", "", name.rsplit("/", 1)[-1], flags=re.I)
        d = ingest(db, title=title, kind="md", text_=text_, filename=name, project_id=project_id)
        docs += 1
        for target in {m.strip() for m in WIKILINK.findall(text_) if m.strip()}:
            e = db.scalar(select(Entity).where(Entity.name == target[:200]))
            if not e:
                e = Entity(name=target[:200], kind="concept", project_id=project_id)
                db.add(e)
                db.flush()
            db.add(Relation(src_type="document", src_id=d.id, dst_type="entity", dst_id=e.id, label="enlaza"))
            links += 1
    db.flush()
    return {"documents": docs, "links": links}
