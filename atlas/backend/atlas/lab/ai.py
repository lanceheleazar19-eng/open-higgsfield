"""IA del INNOVATION LAB. Todo lo generado se etiqueta como propuesta/hipótesis; los hechos solo salen de fuentes
citadas o de tus registros. El contenido externo (investigaciones, documentos) se trata como DATOS."""

from __future__ import annotations

import json

from atlas.brain import router
from atlas.security.policy import sanitize_untrusted

BASE = ("Eres el INNOVATION AGENT de VISTAN, un laboratorio privado de investigación. Responde en español, con rigor "
        "científico. Distingue siempre HECHOS (con fuente), HIPÓTESIS y PREDICCIONES. No inventes artículos, autores, "
        "experimentos, patentes ni resultados. Si no hay información suficiente, dilo. Nunca afirmes que algo es "
        "patentable o está libre de derechos: eso requiere un análisis jurídico profesional.")


def _safe(d: object) -> str:
    txt, _ = sanitize_untrusted(json.dumps(d, ensure_ascii=False, default=str)[:12000])
    return txt


def _json(prefs: dict, system: str, payload: object) -> tuple[dict, str]:
    return router.complete_json("json", prefs, [{"role": "system", "content": BASE + "\n" + system},
                                                {"role": "user", "content": _safe(payload)}])


def ideas(prefs: dict, source_kind: str, source_text: str, context: dict, n: int = 3) -> tuple[list[dict], str]:
    sys = (f"Genera {n} ideas de innovación a partir de la entrada ({source_kind}). JSON: "
           '{"ideas": [{"name": str, "concept": str, "problem": str, "solution": str, "tech": str, '
           '"feasibility": str (viabilidad PRELIMINAR y por qué), "difficulty": "baja"|"media"|"alta", "cost": str (rango aproximado y supuestos), '
           '"applications": str, "risks": str, "customers": str, "next_experiment": str (experimento barato y concreto para validar)}]}. '
           "Son propuestas sin validar: nunca las presentes como inventos demostrados.")
    data, model = _json(prefs, sys, {"entrada": source_text, "contexto_del_laboratorio": context})
    keys = ("name", "concept", "problem", "solution", "tech", "feasibility", "difficulty", "cost", "applications", "risks", "customers", "next_experiment")
    out = []
    for i in data.get("ideas", [])[:n]:
        if i.get("name"):
            d = {k: (str(i.get(k))[:4000] if i.get(k) is not None else None) for k in keys}
            if d["difficulty"] not in ("baja", "media", "alta"):
                d["difficulty"] = None
            out.append(d)
    return out, model


def design_experiment(prefs: dict, exp: dict) -> tuple[dict, str]:
    sys = ('Propón una metodología para comprobar la hipótesis. JSON: {"metodologia": str, "variables": {"independientes": [str], '
           '"dependientes": [str], "controladas": [str]}, "metricas": [str], "criterio_exito": str, "criterio_fracaso": str, '
           '"recursos": [str], "riesgos": [str], "seguridad": str}. El criterio de éxito debe ser medible.')
    return _json(prefs, sys, exp)


def evaluate_experiment(prefs: dict, exp: dict, trials: list[dict]) -> tuple[dict, str]:
    sys = ('Compara resultados esperados y observados con las pruebas registradas. JSON: {"comparacion": str, '
           '"veredicto_sugerido": "supported"|"refuted"|"inconclusive", "por_que": str, "evidencia_que_falta": [str], '
           '"siguiente_experimento": str}. Si no hay resultados medidos, el veredicto debe ser "inconclusive".')
    return _json(prefs, sys, {"experimento": exp, "pruebas": trials})


def scenario(prefs: dict, question: str, horizon: str, research: dict | None) -> tuple[dict, str]:
    sys = ('Analiza un escenario tecnológico futuro. JSON: {"hechos": [{"texto": str, "fuente": str}], "hipotesis": [str], '
           '"variables": [str], "escenarios": [{"nombre": str, "descripcion": str, "probabilidad_cualitativa": "baja"|"media"|"alta", '
           '"senales_tempranas": [str]}], "factores": [str], "oportunidades": [str], "riesgos": [str], "incertidumbres": [str], '
           '"predicciones": [str], "fuentes": [str]}. Los "hechos" SOLO si vienen en la investigación adjunta (cita su URL); '
           "si no hay investigación, deja hechos vacío. Las predicciones nunca son certezas.")
    return _json(prefs, sys, {"pregunta": question, "horizonte": horizon, "investigacion": research})


def extract(prefs: dict, item: dict, text: str) -> tuple[dict, str]:
    sys = ('Resume y extrae conceptos del documento. JSON: {"resumen": str (5-8 frases), "conceptos": [str] (máx. 12), '
           '"metodos": [str], "hallazgos": [str], "limitaciones": [str]}. Solo lo que dice el texto.')
    return _json(prefs, sys, {"documento": item, "texto": text[:10000]})


def compare(prefs: dict, techs: list[dict]) -> tuple[dict, str]:
    sys = ('Compara estas tecnologías usando SOLO los descubrimientos registrados. JSON: {"tabla": [{"tecnologia": str, '
           '"madurez": str, "evidencia": str, "ventajas": [str], "limitaciones": [str]}], "conclusion": str, "datos_que_faltan": [str]}.')
    return _json(prefs, sys, techs)


def agent(prefs: dict, question: str, context: dict, history: list[dict]) -> tuple[str, str]:
    msgs = [{"role": "system", "content": BASE + " Justifica tus conclusiones con los datos del contexto. Propón experimentos "
             "concretos con criterio de éxito medible. Si necesitas más información, di qué investigación (Research Agent), "
             "qué código (Coding Agent), qué análisis de negocio (Business Agent) o qué plan (Planning Agent) haría falta. Máx. ~400 palabras."},
            {"role": "system", "content": "CONTEXTO DEL LABORATORIO (datos registrados):\n" + _safe(context)}]
    msgs += [{"role": h["role"], "content": str(h["content"])[:2000]} for h in history[-6:] if h.get("role") in ("user", "assistant")]
    msgs.append({"role": "user", "content": question})
    out, model = router.complete_text("chat", prefs, msgs)
    return out.strip(), model
