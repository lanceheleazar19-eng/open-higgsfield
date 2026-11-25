"""Fuentes externas del laboratorio (solo lectura):
- arXiv (sin clave): preprints científicos. Atom XML.
- OpenAlex (sin clave): publicaciones académicas con revista, citas y DOI.
- EPO Open Patent Services (Espacenet) con clave gratuita (consumer key + secret): patentes oficiales.
- Google Patents: no tiene API pública oficial → solo enlaces de búsqueda para abrir en el navegador.
Nunca se inventan artículos ni patentes: si la fuente falla, se devuelve el error."""

from __future__ import annotations

import base64
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime
from urllib.parse import quote_plus

import httpx

from atlas.integrations.secrets import get_secret


class SourceError(RuntimeError):
    pass


UA = {"User-Agent": "VISTAN-InnovationLab/1.0 (uso personal)"}
_stats: dict[str, dict] = {k: {"ok": 0, "errors": 0, "last_error": None, "last_ms": None} for k in ("arxiv", "openalex", "epo")}


def _get(src: str, url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 20.0) -> httpx.Response:
    t0 = time.perf_counter()
    st = _stats[src]
    try:
        r = httpx.get(url, params=params, headers={**UA, **(headers or {})}, timeout=timeout)
    except httpx.HTTPError as exc:
        st.update(errors=st["errors"] + 1, last_error=f"sin conexión ({type(exc).__name__})")
        raise SourceError(f"{src}: sin conexión") from exc
    st["last_ms"] = round((time.perf_counter() - t0) * 1000)
    if r.status_code >= 400:
        st.update(errors=st["errors"] + 1, last_error=f"HTTP {r.status_code}")
        raise SourceError(f"{src}: error {r.status_code}" + (" (clave no válida o sin permiso)" if r.status_code in (401, 403) else ""))
    st.update(ok=st["ok"] + 1, last_error=None)
    return r


def _d(s: str | None) -> str | None:
    return s[:10] if s else None


# ───────── arXiv ─────────
NS = {"a": "http://www.w3.org/2005/Atom"}


def arxiv(query: str, limit: int = 10) -> list[dict]:
    r = _get("arxiv", "https://export.arxiv.org/api/query", {"search_query": f"all:{query}", "start": 0, "max_results": min(limit, 30),
                                                             "sortBy": "submittedDate", "sortOrder": "descending"})
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as exc:
        raise SourceError("arXiv: respuesta no válida") from exc
    out = []
    for e in root.findall("a:entry", NS):
        link = e.findtext("a:id", default="", namespaces=NS).strip()
        out.append({"title": " ".join((e.findtext("a:title", default="", namespaces=NS) or "").split()),
                    "summary": " ".join((e.findtext("a:summary", default="", namespaces=NS) or "").split())[:1500],
                    "authors": [a.findtext("a:name", default="", namespaces=NS) for a in e.findall("a:author", NS)][:8],
                    "published": _d(e.findtext("a:published", default=None, namespaces=NS)), "url": link,
                    "external_id": link.rsplit("/", 1)[-1], "source": "arXiv", "kind": "paper",
                    "maturity": "academic", "reliability": "media",
                    "note": "Preprint: puede no estar revisado por pares"})
    return out


# ───────── OpenAlex ─────────
def openalex(query: str, limit: int = 10) -> list[dict]:
    r = _get("openalex", "https://api.openalex.org/works", {"search": query, "per-page": min(limit, 25), "sort": "publication_date:desc"})
    out = []
    for w in r.json().get("results", []):
        inv = w.get("abstract_inverted_index") or {}
        abstract = ""
        if inv:
            pos = sorted((p, word) for word, ps in inv.items() for p in ps)
            abstract = " ".join(word for _, word in pos)[:1500]
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        peer = (w.get("type") in ("article", "review")) and bool(venue)
        out.append({"title": w.get("display_name") or w.get("title") or "(sin título)", "summary": abstract,
                    "authors": [a["author"]["display_name"] for a in (w.get("authorships") or [])[:8] if a.get("author")],
                    "published": w.get("publication_date"), "url": w.get("doi") or w.get("id"), "external_id": w.get("id"),
                    "source": f"OpenAlex · {venue}" if venue else "OpenAlex", "kind": "paper", "maturity": "academic",
                    "reliability": "alta" if peer else "media", "citations": w.get("cited_by_count"),
                    "note": "Publicada en revista/actas" if peer else "Tipo de publicación sin revisión confirmada"})
    return out


# ───────── EPO OPS (Espacenet) ─────────
_token: dict = {"value": None, "exp": 0.0}


def epo_configured() -> bool:
    return bool(get_secret("epo_ops_key") and get_secret("epo_ops_secret"))


def _epo_token() -> str:
    if _token["value"] and _token["exp"] > time.time() + 30:
        return _token["value"]
    key, secret = get_secret("epo_ops_key"), get_secret("epo_ops_secret")
    if not (key and secret):
        raise SourceError("Espacenet (EPO OPS): faltan las credenciales gratuitas (consumer key y secret)")
    try:
        r = httpx.post("https://ops.epo.org/3.2/auth/accesstoken", data={"grant_type": "client_credentials"}, timeout=15,
                       headers={**UA, "Authorization": "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode()})
    except httpx.HTTPError as exc:
        raise SourceError("Espacenet: sin conexión") from exc
    if r.status_code >= 400:
        _stats["epo"].update(errors=_stats["epo"]["errors"] + 1, last_error=f"autenticación HTTP {r.status_code}")
        raise SourceError("Espacenet: credenciales no válidas")
    j = r.json()
    _token.update(value=j["access_token"], exp=time.time() + int(j.get("expires_in", 1200)))
    return _token["value"]


def _txt(x) -> str:  # noqa: ANN001
    if isinstance(x, dict):
        return str(x.get("$", ""))
    if isinstance(x, list):
        return _txt(x[0]) if x else ""
    return str(x or "")


def _as_list(x) -> list:  # noqa: ANN001
    return x if isinstance(x, list) else [x] if x else []


def epo_search(query: str, limit: int = 10) -> list[dict]:
    tok = _epo_token()
    cql = f'ti all "{query}" or ab all "{query}"'
    r = _get("epo", "https://ops.epo.org/3.2/rest-services/published-data/search/biblio", {"q": cql, "Range": f"1-{min(limit, 25)}"},
             headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"})
    root = r.json().get("ops:world-patent-data", {})
    docs = _as_list(((root.get("ops:biblio-search") or {}).get("ops:search-result") or {}).get("exchange-documents"))
    out = []
    for d in docs:
        ex = d.get("exchange-document", d)
        bib = ex.get("bibliographic-data", {})
        titles = _as_list(bib.get("invention-title"))
        title = next((_txt(t) for t in titles if isinstance(t, dict) and t.get("@lang") in ("es", "en")), _txt(titles))
        abstracts = _as_list(ex.get("abstract"))
        ab = next((a for a in abstracts if isinstance(a, dict) and a.get("@lang") == "en"), abstracts[0] if abstracts else {})
        ab_text = " ".join(_txt(p) for p in _as_list(ab.get("p"))) if isinstance(ab, dict) else ""
        apps = [_txt(a.get("applicant-name", {}).get("name")) for a in _as_list((bib.get("parties") or {}).get("applicants", {}).get("applicant"))
                if isinstance(a, dict) and a.get("@data-format") == "epodoc"]
        pub = next((x for x in _as_list((bib.get("publication-reference") or {}).get("document-id")) if isinstance(x, dict) and x.get("@document-id-type") == "docdb"), {})
        country, num, kind, dt = _txt(pub.get("country")), _txt(pub.get("doc-number")), _txt(pub.get("kind")), _txt(pub.get("date"))
        number = f"{country}{num}{kind}"
        out.append({"title": title or "(sin título)", "number": number, "office": country, "applicants": apps[:5], "abstract": ab_text[:1500],
                    "published": f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}" if len(dt) == 8 else None,
                    "url": f"https://worldwide.espacenet.com/patent/search?q=pn%3D{country}{num}", "source": "EPO OPS (Espacenet)"})
    return out


def patent_links(query: str) -> dict:
    """Búsquedas oficiales para abrir en el navegador (no se scrapean)."""
    q = quote_plus(query)
    return {"google_patents": f"https://patents.google.com/?q={q}", "espacenet": f"https://worldwide.espacenet.com/patent/search?q={q}",
            "oepm": "https://consultas2.oepm.es/InvenesWeb/faces/busquedaInternet.jsp"}


def status() -> list[dict]:
    return [{"id": "arxiv", "name": "arXiv", "needs_key": False, "configured": True, "covers": "Preprints científicos (física, IA, informática…)"} | _stats["arxiv"],
            {"id": "openalex", "name": "OpenAlex", "needs_key": False, "configured": True, "covers": "Publicaciones académicas con revista, citas y DOI"} | _stats["openalex"],
            {"id": "epo", "name": "Espacenet (EPO OPS)", "needs_key": True, "configured": epo_configured(),
             "covers": "Patentes oficiales (búsqueda bibliográfica)", "how": "Registro gratuito en developers.epo.org → crea una app → consumer key y secret"} | _stats["epo"],
            {"id": "google_patents", "name": "Google Patents", "needs_key": False, "configured": True, "covers": "Sin API pública: enlaces de búsqueda",
             "ok": 0, "errors": 0, "last_error": None, "last_ms": None}]


def parse_date(s: str | None) -> date | None:
    try:
        return datetime.fromisoformat(s[:10]).date() if s else None
    except ValueError:
        return None
