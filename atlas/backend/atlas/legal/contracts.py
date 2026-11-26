"""Contract Analyzer y comparación de versiones.

Dos capas: (1) reglas deterministas y explicables (tipo, partes, fechas, importes, plazos, cláusulas, penalizaciones,
renovación, terminación, ambigüedad, contradicciones numéricas, información ausente por tipo de contrato) y (2) análisis
con IA LOCAL que debe citar el fragmento ORIGINAL: un riesgo cuyo fragmento no aparece en el contrato se descarta.
Nunca se declara un contrato legal, ilegal, válido o nulo."""

from __future__ import annotations

import difflib
import re
import unicodedata

LEVELS = ("critico", "alto", "medio", "bajo")
TYPES = {
    "arrendamiento": (r"arrendamiento|arrendador|arrendatari|inquilin|renta mensual|fianza", "Arrendamiento",
                      ["duración", "renta", "fianza", "actualización de la renta", "estado del inmueble", "gastos y suministros"]),
    "laboral": (r"contrato de trabajo|trabajador|empleador|jornada laboral|periodo de prueba|convenio colectivo|salario bruto", "Contrato laboral",
                ["jornada", "salario", "categoría profesional", "periodo de prueba", "convenio aplicable", "vacaciones"]),
    "nda": (r"confidencialidad|informaci[oó]n confidencial|non-disclosure|\bnda\b", "Acuerdo de confidencialidad (NDA)",
            ["definición de información confidencial", "duración de la obligación", "excepciones", "devolución o destrucción de la información"]),
    "compraventa": (r"compraventa|vendedor|comprador|precio de venta", "Compraventa", ["objeto", "precio", "forma de pago", "entrega", "garantías"]),
    "servicios": (r"prestaci[oó]n de servicios|proveedor del servicio|el prestador|honorarios|entregables", "Prestación de servicios",
                  ["objeto y alcance", "precio", "plazos de entrega", "propiedad de los resultados", "confidencialidad", "terminación"]),
    "distribucion": (r"distribuci[oó]n|distribuidor|territorio exclusivo", "Distribución", ["territorio", "exclusividad", "precios", "objetivos", "duración"]),
    "licencia": (r"licencia de uso|licenciante|licenciatario|software", "Licencia", ["alcance de la licencia", "precio", "duración", "propiedad intelectual"]),
    "privacidad": (r"pol[ií]tica de privacidad|responsable del tratamiento|datos personales|derechos de acceso", "Política de privacidad",
                   ["identidad del responsable", "finalidades", "base jurídica", "plazo de conservación", "destinatarios", "derechos y cómo ejercerlos"]),
    "terminos": (r"t[eé]rminos y condiciones|condiciones generales de (uso|contrataci[oó]n)", "Términos y condiciones",
                 ["identificación del titular", "proceso de contratación", "precios e impuestos", "derecho de desistimiento", "ley aplicable"]),
    "societario": (r"pacto de socios|socios|participaciones sociales|junta general", "Acuerdo societario",
                   ["participaciones", "aportaciones", "gobierno", "transmisión de participaciones", "salida de socios"]),
    "mercantil": (r"suministro|proveedor|colaboraci[oó]n|agencia comercial", "Contrato mercantil", ["objeto", "precio", "duración", "responsabilidad"]),
}
MISSING_RX = {
    "duración": r"duraci[oó]n|vigencia|plazo de \d+|por un periodo", "renta": r"renta|precio del alquiler", "fianza": r"fianza|garant[ií]a adicional",
    "actualización de la renta": r"actualiza|ipc|[ií]ndice", "estado del inmueble": r"estado|inventario", "gastos y suministros": r"gastos|suministros",
    "jornada": r"jornada|horas semanales", "salario": r"salario|retribuci[oó]n", "categoría profesional": r"categor[ií]a|grupo profesional",
    "periodo de prueba": r"periodo de prueba|per[ií]odo de prueba", "convenio aplicable": r"convenio", "vacaciones": r"vacaciones",
    "definición de información confidencial": r"se entender[aá] por informaci[oó]n confidencial|informaci[oó]n confidencial (significa|incluye|comprende)",
    "duración de la obligación": r"duraci[oó]n|a[nñ]os desde|vigencia", "excepciones": r"excepci[oó]n|no se considerar[aá]",
    "devolución o destrucción de la información": r"devoluci[oó]n|destrucci[oó]n|devolver", "objeto": r"objeto", "precio": r"precio|importe|honorarios",
    "forma de pago": r"pago|transferencia|abonar", "entrega": r"entrega", "garantías": r"garant[ií]a", "objeto y alcance": r"objeto|alcance",
    "plazos de entrega": r"plazo|entrega", "propiedad de los resultados": r"propiedad intelectual|titularidad", "confidencialidad": r"confidencial",
    "terminación": r"resoluci[oó]n|terminaci[oó]n|rescisi[oó]n|extinci[oó]n", "territorio": r"territorio", "exclusividad": r"exclusiv",
    "precios": r"precio", "objetivos": r"objetivo|m[ií]nimo de compra", "alcance de la licencia": r"licencia", "propiedad intelectual": r"propiedad intelectual",
    "identidad del responsable": r"responsable", "finalidades": r"finalidad", "base jurídica": r"base (jur[ií]dica|legal|de legitimaci[oó]n)|legitimaci[oó]n",
    "plazo de conservación": r"conserva", "destinatarios": r"destinatari|ced", "derechos y cómo ejercerlos": r"acceso|rectificaci[oó]n|supresi[oó]n",
    "identificación del titular": r"\bnif\b|\bcif\b|domicilio|titular", "proceso de contratación": r"pedido|contrataci[oó]n|compra",
    "precios e impuestos": r"iva|impuesto", "derecho de desistimiento": r"desistimiento", "ley aplicable": r"ley aplicable|legislaci[oó]n aplicable|jurisdicci[oó]n",
    "participaciones": r"participaci[oó]n", "aportaciones": r"aportaci[oó]n", "gobierno": r"junta|administrador|consejo", "transmisión de participaciones": r"transmisi[oó]n",
    "salida de socios": r"salida|separaci[oó]n|exclusi[oó]n", "responsabilidad": r"responsabilidad",
}
RULES: list[tuple[str, str, str, str, str]] = [  # (regex, nivel, tema, problema, recomendación)
    (r"renovar[aá]n? (autom[aá]tica|t[aá]citamente)|pr[oó]rroga(s)? (autom[aá]tica|t[aá]cita)|se prorrogar[aá]", "medio", "renovación",
     "Renovación o prórroga automática: puede obligarte por otro periodo si no avisas a tiempo.", "Comprueba el preaviso y anótalo como plazo verificado."),
    (r"penalizaci[oó]n|penalidad|cl[aá]usula penal|indemnizaci[oó]n de \d", "alto", "penalización",
     "Penalización económica: revisa su cuantía y si es proporcionada al daño.", "Limita la penalización a un importe razonable y vincúlala a un incumplimiento concreto."),
    (r"unilateralmente|a su (sola|exclusiva) discreci[oó]n|en cualquier momento y sin|sin previo aviso", "alto", "desequilibrio",
     "Facultad unilateral de una parte: posible desequilibrio entre las partes.", "Pide que la facultad sea recíproca o sujeta a causa y preaviso."),
    (r"en ning[uú]n caso (ser[aá]|responder[aá])|exclu(ye|sión) (de )?(toda|cualquier) responsabilidad|no se hace responsable", "alto", "responsabilidad",
     "Exclusión amplia de responsabilidad.", "Acota la exclusión; las exclusiones por dolo o culpa grave suelen ser problemáticas."),
    (r"no competencia|no competir|pacto de no competencia", "medio", "no competencia",
     "Pacto de no competencia: revisa duración, ámbito y compensación.", "Limita duración y territorio; en lo laboral suele exigirse compensación."),
    (r"exclusiv", "medio", "exclusividad", "Cláusula de exclusividad.", "Valora si compensa económicamente y fija su duración."),
    (r"renuncia(n)? (expresa(mente)? )?a|con renuncia (expresa )?a", "alto", "renuncia de derechos", "Renuncia a derechos: algunas renuncias no son admisibles o son desfavorables.",
     "Revisa qué derecho se renuncia; consulta con un profesional si afecta a derechos de consumidor o trabajador."),
    (r"intereses? de demora|recargo", "medio", "intereses de demora", "Intereses o recargos por retraso.", "Comprueba el tipo aplicado y desde cuándo se devenga."),
    (r"tribunales de|sumisi[oó]n (expresa)?|fuero", "bajo", "jurisdicción", "Cláusula de sumisión a tribunales concretos.",
     "Comprueba que el fuero no sea gravoso para ti (en consumo puede no ser oponible)."),
    (r"ced(e|er[aá]|i[oó]n) (todos )?los derechos|cesi[oó]n de (los )?derechos de (propiedad|explotaci[oó]n)", "alto", "propiedad intelectual",
     "Cesión de derechos de propiedad intelectual.", "Define alcance, territorio, duración y si es exclusiva; valora la contraprestación."),
    (r"ced(er|e) (los )?datos|comunicar (sus|los) datos a terceros", "alto", "datos personales",
     "Comunicación de datos personales a terceros.", "Debe existir base jurídica e información al interesado (RGPD)."),
    (r"resolver el contrato|rescindir|desistir", "bajo", "terminación", "Condiciones de terminación del contrato.", "Comprueba causas, preaviso y consecuencias económicas."),
]
AMBIGUOUS = r"\b(razonable(s|mente)?|en su caso|aproximadamente|cuanto antes|a la mayor brevedad|en breve|etc\.?|o similar(es)?|cuando proceda|adecuad[oa]s?)\b"
CATEGORICAL = re.compile(r"\b(es|ser[ií]a|resulta) (nulo|nula|ilegal|legal|v[aá]lido|v[aá]lida|inv[aá]lid[oa])\b", re.I)
MONTHS = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre"


def _n(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def detect_type(text: str) -> tuple[str, str]:
    t = _n(text[:20000])
    scores = {k: len(re.findall(_n(rx), t)) for k, (rx, _, _) in TYPES.items()}
    best = max(scores, key=scores.get)
    return (best, TYPES[best][1]) if scores[best] else ("otro", "Documento jurídico (tipo no identificado)")


HEAD = re.compile(r"^\s*((?:CL[ÁA]USULA|ESTIPULACI[ÓO]N|ART[ÍI]CULO)\s+[\wÁÉÍÓÚ]+[\.\-:]?.*|(?:PRIMER[AO]|SEGUND[AO]|TERCER[AO]|CUART[AO]|QUINT[AO]|SEXT[AO]|S[ÉE]PTIM[AO]|OCTAV[AO]|NOVEN[AO]|D[ÉE]CIM[AO])[\w\s]*[\.\-:].*|\d{1,2}[\.\)]\s+[A-ZÁÉÍÓÚ].{0,80})$", re.M)


def clauses(text: str) -> list[dict]:
    """Segmenta en cláusulas por encabezados habituales (CLÁUSULA, PRIMERA., 1., Artículo…)."""
    marks = [m for m in HEAD.finditer(text)]
    if not marks:
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return [{"n": i + 1, "title": p.split("\n")[0][:80], "text": p} for i, p in enumerate(paras)]
    out = []
    if marks[0].start() > 0 and text[:marks[0].start()].strip():
        out.append({"n": 0, "title": "Encabezamiento / partes", "text": text[:marks[0].start()].strip()})
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append({"n": len(out) + (0 if out and out[0]["n"] == 0 else 1), "title": m.group(1).strip()[:120], "text": text[m.start():end].strip()})
    return out


def entities(text: str) -> dict:
    parties = []
    for m in re.finditer(r"(?:De una parte|De otra parte|Y de otra)[,:\s]+(?:D\.|Dña\.|Don|Doña|la entidad|la sociedad|el Sr\.|la Sra\.)?\s*([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\.\s,]{2,80}?)(?:,|\s+con\s|\s+mayor|\s+en\s)", text):
        p = m.group(1).strip(" ,.")
        if p and p not in parties:
            parties.append(p)
    roles = sorted(set(re.findall(r"\b(?:el|la) (ARRENDADOR[A]?|ARRENDATARI[OA]|VENDEDOR[A]?|COMPRADOR[A]?|PRESTADOR[A]?|CLIENTE|PROVEEDOR|"
                                   r"TRABAJADOR[A]?|EMPRESA|LICENCIANTE|LICENCIATARI[OA]|DISTRIBUIDOR[A]?|PARTE REVELADORA|PARTE RECEPTORA)\b", text)))
    dates = sorted(set(re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", text)) | set(re.findall(rf"\b\d{{1,2}} de (?:{MONTHS}) de \d{{4}}\b", text, re.I)))
    amounts = sorted(set(m.group(0).strip() for m in re.finditer(r"\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?\s?(?:€|euros|EUR)", text)))
    periods = sorted(set(m.group(0) for m in re.finditer(r"\b\d+\s*(?:d[ií]as?|meses|mes|a[nñ]os?|semanas?)(?:\s+(?:naturales|h[aá]biles))?\b", text, re.I)))
    return {"parties": parties[:8], "roles": roles, "dates": dates[:30], "amounts": amounts[:30], "periods": periods[:30]}


def _fragment(text: str, m: re.Match, width: int = 220) -> str:
    a = text.rfind("\n", 0, m.start())
    a = max(a + 1, m.start() - width // 2)
    b = text.find("\n", m.end())
    b = min(b if b != -1 else len(text), m.end() + width // 2)
    return text[a:b].strip()


def rule_risks(cls: list[dict]) -> list[dict]:
    out = []
    for c in cls:
        body = c["text"][len(c["title"]):] if c["text"].startswith(c["title"]) else c["text"]
        for rx, lvl, topic, prob, rec in RULES:
            m = re.search(rx, body, re.I)
            if m:
                out.append({"nivel": lvl, "clausula": c["title"], "fragmento": _fragment(body, m), "problema": prob, "tema": topic,
                            "consecuencia": None, "norma": None, "recomendacion": rec, "redaccion_alternativa": None, "origen": "regla"})
        amb = sorted(set(x.lower() for x in re.findall(AMBIGUOUS, c["text"], re.I) if isinstance(x, str)))
        hits = [m for m in re.finditer(AMBIGUOUS, c["text"], re.I)]
        if hits:
            out.append({"nivel": "bajo", "clausula": c["title"], "fragmento": _fragment(c["text"], hits[0]), "tema": "ambigüedad",
                        "problema": f"Términos imprecisos ({', '.join(sorted({h.group(0).lower() for h in hits}))[:120]}) que pueden interpretarse de forma distinta.",
                        "consecuencia": "Discusiones sobre qué se pactó exactamente.", "norma": None,
                        "recomendacion": "Sustituye por plazos, cantidades o criterios concretos.", "redaccion_alternativa": None, "origen": "regla"})
    return out


def contradictions(cls: list[dict]) -> list[dict]:
    """Mismo concepto con cifras distintas en cláusulas diferentes (p. ej. preaviso de 30 y de 15 días)."""
    topics = {"preaviso": r"preaviso", "pago": r"\bpago|abon", "duración": r"duraci[oó]n|vigencia", "plazo de entrega": r"entrega",
              "penalización": r"penaliza", "fianza": r"fianza"}
    out = []
    for name, rx in topics.items():
        found = {}
        for c in cls:
            for sent in re.split(r"(?<=[.;])\s+", c["text"]):
                if re.search(rx, sent, re.I):
                    for m in re.finditer(r"\b(\d+)\s*(d[ií]as|meses|a[nñ]os|%|€|euros)", sent, re.I):
                        found.setdefault(_n(m.group(2)).replace("dias", "días"), {}).setdefault(m.group(1), (c["title"], sent.strip()[:220]))
        for unit, vals in found.items():
            if len(vals) > 1:
                items = list(vals.items())[:3]
                out.append({"tema": name, "detalle": " vs ".join(f"{v} {unit} ({t})" for v, (t, _) in items),
                            "fragmentos": [s for _, (_, s) in items]})
    return out


def missing(ctype: str, text: str) -> list[str]:
    if ctype not in TYPES:
        return []
    t = _n(text)
    return [item for item in TYPES[ctype][2] if not re.search(_n(MISSING_RX.get(item, item)), t)]


def fragment_ok(fragment: str, text: str) -> bool:
    """¿El fragmento citado por la IA existe realmente en el contrato? (tolera espacios y pequeñas diferencias)."""
    f, t = re.sub(r"\s+", " ", _n(fragment)).strip(), re.sub(r"\s+", " ", _n(text))
    if len(f) < 12:
        return False
    if f in t:
        return True
    probe = f[:80]
    sm = difflib.SequenceMatcher(None, t, probe, autojunk=False)
    m = sm.find_longest_match(0, len(t), 0, len(probe))
    return m.size >= min(60, int(len(probe) * 0.8))


def analyze(text: str, prefs: dict) -> dict:
    from atlas.brain.base import ProviderError
    from atlas.legal import ai
    from atlas.security.policy import sanitize_untrusted
    clean, flagged = sanitize_untrusted(text)
    ctype, label = detect_type(clean)
    cls = clauses(clean)
    ents = entities(clean)
    risks = rule_risks(cls)
    contra = contradictions(cls)
    miss = missing(ctype, clean)
    ai_part, model, discarded, ai_error = {}, None, [], None
    try:
        res = ai.call(prefs, [
            {"role": "system", "content": ai.RULES + "\nAnaliza el CONTRATO. Cada riesgo debe citar un fragmento LITERAL del contrato. "
             "Niveles: critico, alto, medio, bajo. No cites normas que no conozcas con certeza (deja «norma» vacía si dudas). JSON: "
             "{\"resumen\": str, \"partes\": [str], \"obligaciones\": [{\"parte\": str, \"obligacion\": str, \"plazo\": str}], "
             "\"riesgos\": [{\"nivel\": str, \"clausula\": str, \"fragmento\": str, \"problema\": str, \"consecuencia\": str, \"norma\": str, "
             "\"recomendacion\": str, \"redaccion_alternativa\": str}], \"terminacion_y_renovacion\": str, \"riesgos_economicos\": [str], "
             "\"informacion_ausente\": [str]}"},
            {"role": "user", "content": f"TIPO DETECTADO: {label}\nCONTRATO:\n{clean[:14000]}"}], "contract", max_calls=2)
        ai_part, model = res["data"] or {}, res["model"]
    except ProviderError as exc:
        ai_error = str(exc)[:300]
    for r in ai_part.get("riesgos") or []:
        if not isinstance(r, dict):
            continue
        lvl = _n(str(r.get("nivel") or "medio")).strip()
        r["nivel"] = lvl if lvl in LEVELS else "medio"
        r["origen"] = "ia"
        if r.get("norma"):
            r["norma_verificada"] = False  # una norma propuesta por la IA no está verificada hasta investigarla
        for k in ("problema", "consecuencia", "recomendacion"):
            if r.get(k) and CATEGORICAL.search(str(r[k])):
                r[k] = CATEGORICAL.sub("podría plantear dudas de validez", str(r[k]))
        (risks if fragment_ok(str(r.get("fragmento") or ""), clean) else discarded).append(r)
    order = {lvl: i for i, lvl in enumerate(LEVELS)}
    risks.sort(key=lambda r: order.get(r["nivel"], 9))
    counts = {lvl: sum(1 for r in risks if r["nivel"] == lvl) for lvl in LEVELS}
    return {"type": ctype, "type_label": label, "chars": len(clean), "injection_flags": flagged, "entities": ents,
            "parties_ai": [str(x) for x in ai_part.get("partes") or []][:8], "clauses": [{"n": c["n"], "title": c["title"], "chars": len(c["text"])} for c in cls],
            "obligations": [o for o in ai_part.get("obligaciones") or [] if isinstance(o, dict)][:25],
            "termination": str(ai_part.get("terminacion_y_renovacion") or ""), "economic": [str(x) for x in ai_part.get("riesgos_economicos") or []][:10],
            "risks": risks, "counts": counts, "contradictions": contra,
            "missing": sorted(set(miss) | {str(x) for x in ai_part.get("informacion_ausente") or []})[:20],
            "summary": str(ai_part.get("resumen") or ""), "discarded_ai_risks": len(discarded), "ai_error": ai_error, "model": model,
            "note": ("Análisis orientativo: no declara el contrato legal, ilegal, válido ni nulo. Las normas citadas por la IA no están "
                     "verificadas hasta que se investiguen en fuentes oficiales." + (f" {len(discarded)} riesgo(s) de la IA descartado(s) por citar texto "
                                                                                    "que no existe en el contrato." if discarded else ""))}


# ───────── comparación de versiones ─────────
CHANGE_RX = {"económico": r"\d[\d.,]*\s*(€|euros|%)|precio|importe|renta|honorarios", "fechas y plazos": r"\d+\s*(d[ií]as|meses|a[nñ]os)|\d{1,2}/\d{1,2}/\d{2,4}|plazo|fecha",
             "obligaciones": r"deber[aá]|se obliga|obligaci[oó]n|tendr[aá] que", "penalizaciones": r"penaliz|indemniz|cl[aá]usula penal",
             "responsabilidades": r"responsab", "derechos": r"derecho|podr[aá]|facultad"}


def _key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _n(title))[:40]


def compare(a: str, b: str) -> dict:
    ca, cb = clauses(a), clauses(b)
    ka, kb = {_key(c["title"]): c for c in ca}, {_key(c["title"]): c for c in cb}
    changes = []
    for k, c in ka.items():
        if k not in kb:
            changes.append({"kind": "eliminada", "clause": c["title"], "before": c["text"], "after": None, "categories": _cats(c["text"]), "diff": []})
    for k, c in kb.items():
        if k not in ka:
            changes.append({"kind": "añadida", "clause": c["title"], "before": None, "after": c["text"], "categories": _cats(c["text"]), "diff": []})
        elif ka[k]["text"] != c["text"]:
            wa, wb = ka[k]["text"].split(), c["text"].split()
            ops = []
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb).get_opcodes():
                ops.append({"op": tag, "a": " ".join(wa[i1:i2]), "b": " ".join(wb[j1:j2])})
            changed = " ".join(o["a"] + " " + o["b"] for o in ops if o["op"] != "equal")
            changes.append({"kind": "modificada", "clause": c["title"], "before": ka[k]["text"], "after": c["text"],
                            "categories": _cats(f"{c['title']} {changed}"), "diff": ops,
                            "numbers": {"antes": sorted(set(re.findall(r"\d[\d.,]*", " ".join(o["a"] for o in ops if o["op"] != "equal")))),
                                        "despues": sorted(set(re.findall(r"\d[\d.,]*", " ".join(o["b"] for o in ops if o["op"] != "equal"))))}})
    summary = {cat: sum(1 for c in changes if cat in c["categories"]) for cat in CHANGE_RX}
    return {"changes": changes, "summary": summary, "counts": {k: sum(1 for c in changes if c["kind"] == k) for k in ("añadida", "eliminada", "modificada")},
            "similarity": round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() * 100, 1) if len(a) + len(b) < 400000 else None}


def _cats(t: str) -> list[str]:
    return [k for k, rx in CHANGE_RX.items() if re.search(rx, t, re.I)]
