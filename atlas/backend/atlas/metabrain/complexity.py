"""Interpretación de la petición: complejidad, modo de resolución, agentes y si contiene datos personales.
Reglas deterministas y explicables (cada punto de complejidad tiene su motivo)."""

from __future__ import annotations

import re

from atlas.agents import core as agents_core

SIGNALS = [
    (r"\?[^?]+\?", 12, "varias preguntas"),
    (r"compar|versus|\bvs\.?\b|diferencia entre|mejor opci|ventajas|desventajas|pros y contras", 15, "comparación"),
    (r"analiz|evalua|estrategi|planifica|\bplan\b|disen|arquitectur|por que|causas|implicaciones|riesgos|optimiz", 15, "análisis o planificación"),
    (r"\d+[.,]?\d*\s*(%|€|eur|\$|x|\*|/|\+)\s*\d|calcula|cuanto (me )?(cuesta|sale|gano|necesito)|rentab|interes compuesto", 10, "cálculos"),
    (r"investig|fuentes|estudios|evidencia|papers?|cientific|ultimas? noticias|actualidad|segun la ciencia|demostrad", 18, "necesita información externa verificable"),
    (r"deberia|me conviene|que hago|decid|elegir|recomiend|vale la pena", 10, "decisión"),
    (r"paso a paso|detallad|en profundidad|a fondo|exhaustiv|completo", 10, "pide profundidad"),
]
PERSONAL = re.compile(r"\bmi(s)? (salud|peso|dinero|sueldo|nomina|deuda|cuenta|familia|pareja|medic|ansiedad|estado de animo)|"
                      r"mis gastos|mi patrimonio|estoy (triste|enfermo|deprimid)|mi cuerpo|mis analisis")
DEEP_CMD = re.compile(r"^(?:(?:vistan|atlas)[, ]+)?(?:piensa a fondo|consejo|council|meta[- ]?brain|/meta|/council)[:,]?\s+(.{4,})", re.I)


def deep_command(text: str) -> str | None:
    m = DEEP_CMD.match(text.strip())
    return m.group(1).strip() if m else None


def analyze(text: str, prefs: dict | None = None) -> dict:
    from atlas.metabrain.governance import allowed_agents
    t = agents_core.norm(text)
    score, reasons = 0, []
    words = len(t.split())
    if words > 60:
        score, reasons = score + 15, reasons + [f"petición larga ({words} palabras)"]
    elif words > 25:
        score, reasons = score + 8, reasons + [f"petición media ({words} palabras)"]
    flags = set()
    for rx, pts, why in SIGNALS:
        if re.search(rx, t):
            score += pts
            reasons.append(why)
            flags.add(why)
    agents = allowed_agents(prefs or {}, agents_core.plan(text))
    if len(agents) > 1:
        score += 8 * (len(agents) - 1)
        reasons.append(f"{len(agents)} áreas implicadas")
    score = min(100, score)
    label = "simple" if score < 25 else "moderada" if score < 50 else "compleja"
    research = bool(agents_core.research_command(text)) or ("necesita información externa verificable" in flags and score >= 35)
    if research:
        mode = "research"
    elif label == "compleja":
        mode = "council"
    elif agents:
        mode = "agents"
    else:
        mode = "direct"
    return {"score": score, "label": label, "reasons": reasons, "agents": agents, "mode": mode,
            "personal": bool(PERSONAL.search(t)), "words": words}
