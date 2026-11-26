"""Fuentes jurídicas oficiales, detección de jurisdicción/rama y comprobación de vigencia.

- Solo se aceptan resultados de dominios OFICIALES (BOE, Portal Jurídic de Catalunya/DOGC, EUR-Lex, CURIA, Tribunal
  Constitucional, CGPJ/CENDOJ, AEPD, Agencia Tributaria, Seguridad Social y sedes .gob.es). Lo demás se descarta.
- BOE: API de datos abiertos de legislación consolidada (sin clave) para buscar normas y leer su estado de vigencia.
- EUR-Lex: se lee la página oficial del acto (CELEX) para su estado «en vigor».
- La búsqueda web usa el buscador de VISTAN (DuckDuckGo, sin clave) restringido con «site:».
Arquitectura extensible: añadir una jurisdicción = añadir sus dominios y reglas en JURISDICTIONS.
Nunca se afirma haber consultado una fuente que no se ha leído: cada fuente guarda URL y fecha de acceso."""

from __future__ import annotations

import json
import re
import unicodedata
from urllib.parse import urlparse

import httpx

UA = "VISTAN-Legal/1.0 (+uso personal)"
BRANCHES = {
    "civil": "Derecho civil", "mercantil": "Derecho mercantil", "laboral": "Derecho laboral", "penal": "Derecho penal",
    "administrativo": "Derecho administrativo", "fiscal": "Derecho fiscal y tributario", "constitucional": "Derecho constitucional",
    "inmobiliario": "Derecho inmobiliario", "contractual": "Derecho contractual", "consumo": "Derecho de consumo",
    "digital": "Derecho digital y tecnológico", "datos": "Protección de datos", "pi": "Propiedad intelectual",
    "ecommerce": "Comercio electrónico", "societario": "Derecho societario", "ue": "Normativa europea",
}
_BR_RX = {
    "laboral": r"despido|contrato de trabajo|salario|nomina|vacaciones|convenio|trabajador|empresario|baja laboral|finiquito|jornada|autonomo|seguridad social",
    "penal": r"delito|denuncia penal|querella|estafa|robo|hurto|lesiones|penal|condena|antecedentes",
    "fiscal": r"iva|irpf|impuesto|hacienda|tribut|factura|modelo 303|modelo 130|declaracion de la renta|agencia tributaria|retencion",
    "administrativo": r"multa|sancion administrativa|ayuntamiento|recurso de alzada|reposicion|licencia|silencio administrativo|administracion",
    "datos": r"datos personales|rgpd|gdpr|lopd|privacidad|aepd|consentimiento|cookies|tratamiento de datos",
    "ecommerce": r"tienda online|ecommerce|comercio electronico|shopify|venta online|lssi|desistimiento|envios",
    "consumo": r"consumidor|garantia|devolucion|reclamacion|clausula abusiva|desistimiento",
    "inmobiliario": r"alquiler|arrendamiento|inquilino|arrendador|fianza|hipoteca|compraventa de vivienda|comunidad de propietarios|desahucio",
    "societario": r"sociedad limitada|\bs\.?l\.?\b|socios|junta general|administrador|estatutos|ampliacion de capital|participaciones",
    "pi": r"propiedad intelectual|derechos de autor|marca|patente|copyright|licencia de uso|plagio",
    "digital": r"software|app|inteligencia artificial|plataforma|algoritmo|ciberseguridad|nube|saas",
    "contractual": r"contrato|clausula|incumplimiento|penalizacion|rescision|resolucion del contrato",
    "mercantil": r"empresa|mercantil|proveedor|distribucion|agencia comercial|competencia desleal|concurso de acreedores",
    "constitucional": r"derecho fundamental|constitucion|amparo|libertad de expresion|igualdad",
    "civil": r"herencia|testamento|sucesion|divorcio|custodia|vecino|responsabilidad civil|deuda|prestamo",
    "ue": r"directiva|reglamento \(ue\)|reglamento europeo|union europea|tjue|eur-lex",
}
CAT_RX = r"catalu|catalunya|barcelona|girona|lleida|tarragona|generalitat|codi civil de catalunya|codigo civil de cataluna|\bcccat\b|dogc"
EU_RX = r"\brgpd\b|\bgdpr\b|directiva|reglamento \(ue\)|union europea|tjue|\bue\b|europe"
# Materias en las que el derecho civil catalán puede desplazar al estatal: si no se sabe dónde, hay que preguntarlo
TERRITORIAL = ("inmobiliario", "civil")

OFFICIAL = {
    "boe.es": ("BOE", "legislacion"), "portaljuridic.gencat.cat": ("Portal Jurídic de Catalunya", "legislacion"),
    "dogc.gencat.cat": ("DOGC", "legislacion"), "eur-lex.europa.eu": ("EUR-Lex", "legislacion"),
    "curia.europa.eu": ("CURIA (TJUE)", "jurisprudencia"), "tribunalconstitucional.es": ("Tribunal Constitucional", "jurisprudencia"),
    "hj.tribunalconstitucional.es": ("Tribunal Constitucional", "jurisprudencia"), "poderjudicial.es": ("CGPJ / CENDOJ", "jurisprudencia"),
    "aepd.es": ("AEPD", "criterio"), "agenciatributaria.es": ("Agencia Tributaria", "criterio"),
    "sede.agenciatributaria.gob.es": ("Agencia Tributaria (sede)", "criterio"), "seg-social.es": ("Seguridad Social", "criterio"),
    "gencat.cat": ("Generalitat de Catalunya", "criterio"), "gob.es": ("Administración General del Estado", "criterio"),
    "europa.eu": ("Unión Europea", "criterio"),
}
GROUPS = {
    "legislacion": {"es": ["boe.es"], "es-ct": ["portaljuridic.gencat.cat", "boe.es"], "eu": ["eur-lex.europa.eu"]},
    "jurisprudencia": {"es": ["poderjudicial.es", "tribunalconstitucional.es"], "es-ct": ["poderjudicial.es"], "eu": ["curia.europa.eu"]},
    "criterio": {"datos": ["aepd.es"], "fiscal": ["agenciatributaria.es"], "laboral": ["seg-social.es"]},
}
JURISDICTIONS = {"es": "España", "es-ct": "Cataluña (y estatal supletorio)", "eu": "Unión Europea"}


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def official(url: str) -> tuple[str, str] | None:
    host = (urlparse(url).hostname or "").lower()
    for dom in sorted(OFFICIAL, key=len, reverse=True):
        if host == dom or host.endswith("." + dom):
            return OFFICIAL[dom]
    return None


def classify(question: str, facts: str = "") -> dict:
    """Jurisdicción y rama por reglas explicables + preguntas si falta información esencial."""
    t = norm(f"{question} {facts}")
    branches = [b for b, rx in _BR_RX.items() if re.search(rx, t)]
    juris = "es-ct" if re.search(CAT_RX, t) else "eu" if re.search(EU_RX, t) and not re.search(r"espan|boe|ley \d+/\d{4}", t) else "es"
    questions = []
    if juris != "es-ct" and any(b in TERRITORIAL for b in branches) and not re.search(r"madrid|valencia|sevilla|espan|bilbao|zaragoza|malaga", t):
        questions.append("¿En qué comunidad autónoma está el inmueble o residen las partes? (En Cataluña puede aplicarse el Código civil catalán.)")
    if re.search(r"plazo|cuanto tiempo tengo|fecha limite|caduca|prescrib", t) and not re.search(r"\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2} de [a-z]+", t):
        questions.append("¿Qué fecha exacta tiene el hecho o la notificación de la que parte el plazo? (Sin ella no se puede orientar ningún plazo.)")
    if "laboral" in branches and not re.search(r"convenio|sector|categoria", t):
        questions.append("¿Qué convenio colectivo o sector se aplica a la relación laboral?")
    return {"jurisdiction": juris, "jurisdiction_label": JURISDICTIONS[juris], "branches": branches[:4] or ["civil"],
            "branch_labels": [BRANCHES[b] for b in (branches[:4] or ["civil"])], "questions": questions}


def plan_sites(jurisdiction: str, branches: list[str], want_case_law: bool) -> list[tuple[str, list[str]]]:
    out = [("legislacion", GROUPS["legislacion"].get(jurisdiction, ["boe.es"]) + (["eur-lex.europa.eu"] if "ue" in branches or "datos" in branches else []))]
    if want_case_law:
        out.append(("jurisprudencia", GROUPS["jurisprudencia"].get(jurisdiction, ["poderjudicial.es"])))
    crit = sorted({d for b in branches for d in GROUPS["criterio"].get(b, [])})
    if crit:
        out.append(("criterio", crit))
    return out


def search_official(searcher, query: str, sites: list[str], n: int = 4) -> tuple[list[dict], list[str]]:  # noqa: ANN001
    """Búsqueda web restringida a dominios oficiales. Descarta cualquier resultado no oficial."""
    results, errors = [], []
    for site in sites[:3]:
        try:
            for r in searcher.duckduckgo(f"{query} site:{site}", n=n):
                off = official(r["url"])
                if off:
                    results.append({**r, "official": off[0], "source_type": off[1]})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{site}: {type(exc).__name__}")
    return results, errors


# ───────── BOE (datos abiertos, sin clave) ─────────
BOE_API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
BOE_ID = re.compile(r"BOE-[A-Z]-\d{4}-\d{1,6}")
CELEX = re.compile(r"CELEX[:%3A]+(\d{5}[A-Z]\d{4})", re.I)


def _client() -> httpx.Client:
    return httpx.Client(timeout=12.0, follow_redirects=True, headers={"User-Agent": UA, "Accept": "application/json"})


def boe_search(words: str, limit: int = 5, client: httpx.Client | None = None) -> list[dict]:
    """Busca normas consolidadas por palabras del título. Devuelve lo que diga el BOE, con su estado si lo informa."""
    terms = " AND ".join(f"titulo:{w}" for w in re.findall(r"[a-záéíóúñü]{4,}", words.lower())[:4]) or "titulo:ley"
    q = json.dumps({"query": {"query_string": {"query": terms}}, "sort": [{"fecha_actualizacion": "desc"}]})
    c = client or _client()
    r = c.get(BOE_API, params={"query": q, "limit": limit})
    r.raise_for_status()
    data = r.json().get("data") or []
    return [_boe_item(x) for x in (data if isinstance(data, list) else [data])]


def _boe_item(x: dict) -> dict:
    ident = x.get("identificador") or x.get("id")
    agot = str(x.get("vigencia_agotada") or "").upper()
    derog = str(x.get("estatus_derogacion") or "").upper()
    status = "derogada" if derog == "S" or agot == "S" else "vigente" if agot == "N" or derog == "N" else "no_comprobada"
    return {"id": ident, "title": x.get("titulo"), "status": status, "updated": x.get("fecha_actualizacion"),
            "url": x.get("url_html_consolidada") or (f"https://www.boe.es/buscar/act.php?id={ident}" if ident else None),
            "eli": x.get("url_eli"), "raw_status": {k: x.get(k) for k in ("vigencia_agotada", "estatus_derogacion", "estado_consolidacion") if k in x}}


def boe_status(ident: str, client: httpx.Client | None = None) -> dict:
    c = client or _client()
    r = c.get(f"{BOE_API}/id/{ident}/metadatos")
    r.raise_for_status()
    d = r.json().get("data") or {}
    d = d[0] if isinstance(d, list) and d else d
    return _boe_item({**d, "identificador": d.get("identificador") or ident})


def eurlex_status(celex: str, client: httpx.Client | None = None) -> dict:
    c = client or _client()
    url = f"https://eur-lex.europa.eu/legal-content/ES/ALL/?uri=CELEX:{celex}"
    r = c.get(url, headers={"Accept": "text/html"})
    r.raise_for_status()
    t = norm(r.text)
    status = "derogada" if re.search(r"ya no esta en vigor|derogad", t) else "vigente" if re.search(r"en vigor", t) else "no_comprobada"
    return {"id": f"CELEX:{celex}", "status": status, "url": url}


def check_vigencia(urls_texts: list[tuple[str, str]], client: httpx.Client | None = None) -> dict[str, dict]:
    """Estado de vigencia de las normas identificables (BOE-A-… y CELEX) en las fuentes leídas."""
    out: dict[str, dict] = {}
    ids_boe, ids_celex = set(), set()
    for url, text in urls_texts:
        ids_boe |= set(BOE_ID.findall(url)) | set(BOE_ID.findall(text[:20000]))
        ids_celex |= set(CELEX.findall(url))
    for i in list(ids_boe)[:8]:
        try:
            out[i] = {**boe_status(i, client), "checked_via": "API BOE"}
        except Exception as exc:  # noqa: BLE001
            out[i] = {"id": i, "status": "no_comprobada", "error": type(exc).__name__}
    for c in list(ids_celex)[:4]:
        try:
            out[f"CELEX:{c}"] = {**eurlex_status(c, client), "checked_via": "página EUR-Lex"}
        except Exception as exc:  # noqa: BLE001
            out[f"CELEX:{c}"] = {"id": f"CELEX:{c}", "status": "no_comprobada", "error": type(exc).__name__}
    return out


def status() -> list[dict]:
    return [
        {"id": "boe_api", "name": "BOE · API de legislación consolidada", "needs_key": False, "covers": "Normas estatales y su vigencia"},
        {"id": "eurlex", "name": "EUR-Lex (páginas oficiales)", "needs_key": False, "covers": "Derecho de la UE y su estado"},
        {"id": "web_official", "name": "Búsqueda web restringida a dominios oficiales", "needs_key": False,
         "covers": ", ".join(sorted({v[0] for v in OFFICIAL.values()}))},
        {"id": "cendoj", "name": "CENDOJ (jurisprudencia)", "needs_key": False,
         "covers": "Se localizan resoluciones vía poderjudicial.es; el buscador de CENDOJ no tiene API pública, se enlaza"},
        {"id": "private_db", "name": "Bases privadas (Aranzadi, vLex, Tirant…)", "needs_key": True,
         "covers": "No integradas: requieren suscripción. VISTAN no simula su consulta."},
    ]
