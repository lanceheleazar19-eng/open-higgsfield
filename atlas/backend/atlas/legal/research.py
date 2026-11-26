"""Legal Research Engine. Reutiliza el buscador y el lector web del Research Engine de VISTAN, pero solo admite fuentes
OFICIALES y produce un informe jurídico con cada afirmación rastreable hasta su fuente.

Pasos (reanudables): classify → plan → search → read → vigencia → analyze → synthesize → verify."""

from __future__ import annotations

import re
import threading
from datetime import datetime

from atlas.brain.base import ProviderError
from atlas.legal import ai, sources
from atlas.models import LgResearch
from atlas.security.policy import notify, sanitize_untrusted

STEPS = ["classify", "plan", "search", "read", "vigencia", "analyze", "synthesize", "verify"]
MAX_SOURCES = 8
_running: set[int] = set()
_lock = threading.Lock()


def to_dict(r: LgResearch, full: bool = False) -> dict:
    st = r.state or {}
    d = {"id": r.id, "case_id": r.case_id, "question": r.question, "jurisdiction": r.jurisdiction, "branch": r.branch, "status": r.status,
         "step": r.step, "progress": round(100 * len(st.get("done", [])) / len(STEPS)), "model": r.model, "error": r.error,
         "summary": (r.report or {}).get("resumen"), "sources_count": len(st.get("sources", [])),
         "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat() if r.updated_at else None}
    if full:
        d.update(facts=r.facts, report=r.report, verification=r.verification, classification=st.get("classification"),
                 issues=st.get("issues"), vigencia=st.get("vigencia"), search_errors=st.get("search_errors"),
                 sources=[{k: v for k, v in s.items() if k != "excerpt"} | {"excerpt": (s.get("excerpt") or "")[:500]} for s in st.get("sources", [])])
    return d


def _save(rid: int, **ch) -> None:  # noqa: ANN003
    from atlas.db import session_scope
    with session_scope() as db:
        r = db.get(LgResearch, rid)
        for k, v in ch.items():
            setattr(r, k, v)
        db.commit()


def start(rid: int) -> None:
    threading.Thread(target=run, args=(rid,), name=f"legal-research-{rid}", daemon=True).start()


def mark_interrupted() -> None:
    from sqlalchemy import select

    from atlas.db import session_scope
    with session_scope() as db:
        for r in db.scalars(select(LgResearch).where(LgResearch.status.in_(("queued", "running")))):
            r.status, r.error = "error", "Interrumpida por un reinicio. Puedes reanudarla."
        db.commit()


def run(rid: int, searcher=None, fetcher=None, http=None) -> None:  # noqa: ANN001, C901
    from atlas.db import session_scope
    from atlas.knowledge.web import fetch
    from atlas.metabrain.governance import killed
    from atlas.research.engine import WebSearcher
    from atlas.services.preferences import get_prefs
    with _lock:
        if rid in _running:
            return
        _running.add(rid)
    try:
        with session_scope() as db:
            r = db.get(LgResearch, rid)
            q, facts, st, prefs, juris = r.question, r.facts or "", dict(r.state or {}), get_prefs(db), r.jurisdiction
        if killed(prefs):
            _save(rid, status="error", error="Kill switch activo")
            return
        done = st.setdefault("done", [])
        searcher = searcher or WebSearcher()
        fetcher = fetcher or fetch
        _save(rid, status="running", error=None)

        def step(name: str) -> bool:
            if name in done:
                return False
            _save(rid, step=name, state=dict(st))
            return True

        def finish(name: str) -> None:
            done.append(name)
            _save(rid, state=dict(st))

        st["question"] = q
        if step("classify"):
            cl = sources.classify(q, facts)
            if juris and juris != "auto":
                cl["jurisdiction"], cl["jurisdiction_label"] = juris, sources.JURISDICTIONS.get(juris, juris)
            st["classification"] = cl
            _save(rid, jurisdiction=cl["jurisdiction"], branch=cl["branches"][0])
            finish("classify")
        cl = st["classification"]
        if step("plan"):
            res = ai.call(prefs, [{"role": "system", "content": ai.RULES + "\nDescompón la consulta en 2-4 cuestiones jurídicas concretas y "
                                   "propón términos de búsqueda en español jurídico. JSON: {\"problema\": str, \"cuestiones\": [str], "
                                   "\"busquedas\": [str], \"jurisprudencia_relevante\": bool}"},
                                  {"role": "user", "content": f"CONSULTA: {q}\nHECHOS: {facts or '-'}\nJURISDICCIÓN: {cl['jurisdiction_label']}\n"
                                   f"RAMAS: {', '.join(cl['branch_labels'])}"}], "plan")
            d = res["data"] or {}
            st["issues"] = {"problema": str(d.get("problema") or q)[:800], "cuestiones": [str(x) for x in (d.get("cuestiones") or [q])][:4],
                            "busquedas": [str(x) for x in (d.get("busquedas") or [q])][:4], "jurisprudencia": bool(d.get("jurisprudencia_relevante", True))}
            st["model"] = res["model"]
            finish("plan")
        iss = st["issues"]
        if step("search"):
            found, errors, seen = [], [], set()
            for kind, sites in sources.plan_sites(cl["jurisdiction"], cl["branches"], iss["jurisprudencia"]):
                for term in iss["busquedas"][:3]:
                    rs, errs = sources.search_official(searcher, term, sites, n=3)
                    errors += errs
                    for x in rs:
                        key = x["url"].split("#")[0]
                        if key not in seen:
                            seen.add(key)
                            found.append({**x, "query": term})
            boe = []
            if cl["jurisdiction"] in ("es", "es-ct"):
                try:
                    boe = sources.boe_search(" ".join(iss["busquedas"][:2]), client=http)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"API BOE: {type(exc).__name__}")
            for b in boe:
                if b.get("url") and b["url"] not in seen:
                    seen.add(b["url"])
                    found.append({"url": b["url"], "title": b.get("title") or b["id"], "snippet": "", "engine": "API BOE",
                                  "official": "BOE", "source_type": "legislacion", "boe_id": b["id"], "boe_status": b["status"]})
            st["search_errors"] = errors
            st["sources"] = [{**x, "id": i + 1} for i, x in enumerate(found[:MAX_SOURCES])]
            if not st["sources"]:
                raise RuntimeError("No encontré fuentes oficiales. " + ("; ".join(errors) if errors else "Reformula la consulta."))
            finish("search")
        if step("read"):
            for s in st["sources"]:
                if s.get("read") is not None:
                    continue
                try:
                    page = fetcher(s["url"])
                    text, flagged = sanitize_untrusted(page["text"])
                    s.update(read=True, excerpt=text[:9000], flagged=flagged, accessed_at=datetime.now().isoformat(timespec="minutes"))
                except Exception as exc:  # noqa: BLE001
                    s.update(read=False, error=f"{type(exc).__name__}")
                _save(rid, state=dict(st))
            if not any(s.get("read") for s in st["sources"]):
                raise RuntimeError("No se pudo leer ninguna fuente oficial (¿sin conexión?)")
            finish("read")
        if step("vigencia"):
            try:
                st["vigencia"] = sources.check_vigencia([(s["url"], s.get("excerpt") or "") for s in st["sources"] if s.get("read")], client=http)
            except Exception as exc:  # noqa: BLE001
                st["vigencia"] = {"_error": type(exc).__name__}
            finish("vigencia")
        if step("analyze"):
            for s in st["sources"]:
                if not s.get("read") or s.get("analysis") is not None:
                    continue
                try:
                    res = ai.call(prefs, [{"role": "system", "content": ai.RULES + "\nDel TEXTO de una fuente oficial extrae SOLO lo que dice "
                                           "y sea relevante. JSON: {\"relevante\": bool, \"tipo\": \"legislacion\"|\"jurisprudencia\"|\"criterio\", "
                                           "\"norma_o_resolucion\": str, \"articulos\": [str], \"afirmaciones\": [str], \"fecha\": str|null}"},
                                          {"role": "user", "content": f"CUESTIONES: {'; '.join(iss['cuestiones'])}\nFUENTE [{s['id']}] {s['official']}: "
                                           f"{s['title']}\nTEXTO:\n{s['excerpt'][:7000]}"}], "analyze")
                    s["analysis"] = res["data"] or {}
                except ProviderError as exc:
                    s["analysis"] = {"relevante": False, "error": str(exc)[:200]}
                _save(rid, state=dict(st))
            finish("analyze")
        if step("synthesize"):
            useful = [s for s in st["sources"] if (s.get("analysis") or {}).get("relevante")]
            if not useful:
                raise RuntimeError("Las fuentes oficiales leídas no contienen información relevante para la consulta")
            vig = st.get("vigencia") or {}
            brief = "\n\n".join(f"[{s['id']}] {s['official']} · {s['title']} · {s['url']}\n" + __import__("json").dumps(s["analysis"], ensure_ascii=False)[:1800]
                                for s in useful)
            res = ai.call(prefs, [{"role": "system", "content": ai.RULES + "\nRedacta un informe jurídico usando EXCLUSIVAMENTE las FUENTES "
                                   "(cítalas por id). JSON: {\"resumen\": str, \"problema\": str, \"legislacion\": [{\"norma\": str, \"articulos\": [str], "
                                   "\"fuente\": int, \"contenido\": str}], \"jurisprudencia\": [{\"resolucion\": str, \"fuente\": int, \"criterio\": str}], "
                                   "\"criterios_interpretativos\": [{\"texto\": str, \"fuente\": int}], \"interpretacion\": str, \"aplicacion\": str, "
                                   "\"riesgos\": [str], \"incertidumbres\": [str], \"conclusion\": str, \"requiere_abogado\": bool, \"plazos_mencionados\": [str]}"},
                                  {"role": "user", "content": f"CONSULTA: {q}\nHECHOS: {facts or '-'}\nJURISDICCIÓN: {cl['jurisdiction_label']}\n"
                                   f"PROBLEMA: {iss['problema']}\nCUESTIONES: {'; '.join(iss['cuestiones'])}\nVIGENCIA COMPROBADA: "
                                   f"{__import__('json').dumps(vig, ensure_ascii=False)[:1500]}\n\nFUENTES:\n{brief[:14000]}"}], "synth")
            st["draft"] = res["data"] or {}
            st["model"] = res["model"]
            finish("synthesize")
        if step("verify"):
            report, ver = verify(st)
            _save(rid, report=report, verification=ver, model=st.get("model"))
            finish("verify")
        _save(rid, status="done", step=None)
        with session_scope() as db:
            notify(db, "Investigación jurídica terminada", q[:140], link="/legal?s=research")
            db.commit()
    except Exception as exc:  # noqa: BLE001
        _save(rid, status="error", error=str(exc)[:500])
    finally:
        with _lock:
            _running.discard(rid)


def _art_in(article: str, text_norm: str) -> bool:
    """¿Aparece «artículo N» (o «art. N») en el texto normalizado de la fuente?"""
    m = re.search(r"\d+(?:\s*(?:bis|ter|quater))?", sources.norm(article))
    if not m:
        return False
    num = re.sub(r"\s+", r"\\s*", m.group(0))
    return bool(re.search(rf"\bart(?:iculo|\.|s\.)?\s*{num}\b", text_norm))


def verify(st: dict) -> tuple[dict, dict]:
    """Cada norma, artículo y resolución debe rastrearse hasta una fuente LEÍDA. Lo no comprobable se marca."""
    d = st.get("draft") or {}
    srcs = {s["id"]: s for s in st.get("sources", []) if s.get("read")}
    vig = st.get("vigencia") or {}
    checks = []

    def src_text(i) -> str:  # noqa: ANN001
        s = srcs.get(i if isinstance(i, int) else int(i) if str(i).isdigit() else -1)
        return sources.norm(s.get("excerpt") or "") if s else ""

    leg = []
    for item in d.get("legislacion") or []:
        if not isinstance(item, dict):
            continue
        sid = item.get("fuente")
        txt = src_text(sid)
        arts = [str(a) for a in (item.get("articulos") or [])]
        found_arts = [a for a in arts if _art_in(a, txt)]
        s = srcs.get(sid if isinstance(sid, int) else -1) or {}
        ids = sources.BOE_ID.findall(s.get("url", "")) + sources.BOE_ID.findall((s.get("excerpt") or "")[:3000])
        celex = sources.CELEX.findall(s.get("url", ""))
        vs = (vig.get(ids[0]) if ids else None) or (vig.get(f"CELEX:{celex[0]}") if celex else None) or \
             ({"status": s.get("boe_status")} if s.get("boe_status") else None)
        status = (vs or {}).get("status") or "no_comprobada"
        ok_src = bool(txt)
        leg.append({**item, "verificada_en_fuente": ok_src, "articulos_encontrados": found_arts,
                    "articulos_no_encontrados": [a for a in arts if a not in found_arts], "vigencia": status,
                    "vigencia_via": (vs or {}).get("checked_via") or ("API BOE" if s.get("boe_status") else None),
                    "url": s.get("url"), "fuente_oficial": s.get("official")})
        checks.append(ok_src and not [a for a in arts if a not in found_arts])
    juris = []
    for item in d.get("jurisprudencia") or []:
        if not isinstance(item, dict):
            continue
        sid = item.get("fuente")
        s = srcs.get(sid if isinstance(sid, int) else -1) or {}
        ok_src = bool(s) and s.get("source_type") == "jurisprudencia"
        juris.append({**item, "verificada_en_fuente": ok_src, "url": s.get("url"), "fuente_oficial": s.get("official")})
        checks.append(ok_src)
    crit = [{**c, "url": (srcs.get(c.get("fuente")) or {}).get("url")} for c in (d.get("criterios_interpretativos") or []) if isinstance(c, dict)]
    warnings = []
    if any(x["vigencia"] == "no_comprobada" for x in leg):
        warnings.append("No se ha podido comprobar la vigencia de alguna norma: verifícala en la fuente oficial antes de aplicarla.")
    if any(x["vigencia"] == "derogada" for x in leg):
        warnings.append("Alguna norma citada figura como DEROGADA o con vigencia agotada: no debe aplicarse como vigente.")
    if any(not x["verificada_en_fuente"] or x["articulos_no_encontrados"] for x in leg) or any(not j["verificada_en_fuente"] for j in juris):
        warnings.append("Hay citas que no aparecen literalmente en las fuentes leídas: se marcan como no verificadas.")
    if d.get("plazos_mencionados"):
        warnings.append("Se mencionan plazos: requieren verificación prioritaria (reglas de cómputo, fechas relevantes, interrupciones o suspensiones).")
    report = {"pregunta": st.get("question"), "resumen": str(d.get("resumen") or ""), "problema": str(d.get("problema") or (st.get("issues") or {}).get("problema", "")),
              "jurisdiccion": (st.get("classification") or {}).get("jurisdiction_label"), "ramas": (st.get("classification") or {}).get("branch_labels"),
              "legislacion": leg, "jurisprudencia": juris, "criterios_interpretativos": crit, "interpretacion": str(d.get("interpretacion") or ""),
              "aplicacion": str(d.get("aplicacion") or ""), "riesgos": [str(x) for x in d.get("riesgos") or []],
              "incertidumbres": [str(x) for x in d.get("incertidumbres") or []] + warnings, "conclusion": str(d.get("conclusion") or ""),
              "requiere_abogado": bool(d.get("requiere_abogado")), "plazos_mencionados": [str(x) for x in d.get("plazos_mencionados") or []],
              "fuentes": [{"id": s["id"], "titulo": s["title"], "url": s["url"], "organismo": s["official"], "tipo": s["source_type"],
                           "consultada": s.get("accessed_at")} for s in srcs.values()], "aviso": ai.DISCLAIMER}
    ver = {"citas": len(checks), "verificadas": sum(1 for c in checks if c), "avisos": warnings,
           "nota": "Verificación literal: la norma/resolución está en una fuente oficial leída y los artículos citados aparecen en su texto."}
    return report, ver
