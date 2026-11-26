"""Academy Agents: profesores especializados (personas del Learning Agent de VISTAN, no agentes nuevos en el registro) y el
Academy Coordinator, que elige el profesor por categoría y contenido y añade un colaborador si la pregunta combina disciplinas."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class Teacher:
    id: str
    name: str
    specialty: str
    categories: list[str]
    instructions: str
    tools: list[str] = field(default_factory=list)  # sandbox | research | knowledge | labs
    rx: str = ""


TEACHERS = {t.id: t for t in [
    Teacher("economics", "Economics Teacher", "Economía, micro y macro", ["economia"], "Usa gráficos de oferta/demanda descritos en tablas y ejemplos cotidianos.",
            ["research", "knowledge"], r"econom|inflaci|pib|oferta|demanda|mercado|macro|micro"),
    Teacher("finance", "Finance Teacher", "Finanzas, inversión, trading y contabilidad", ["economia"], "Usa números concretos y dinero virtual; recuerda siempre el riesgo.",
            ["labs", "research"], r"finanz|invers|bolsa|trading|interes|contab|balance|presupuest|cripto|riesgo"),
    Teacher("business", "Business Teacher", "Emprendimiento, marketing, ventas y estrategia", ["negocios"], "Aterriza todo en decisiones de negocio reales y medibles.",
            ["labs", "research"], r"negocio|empresa|marketing|venta|shopify|ecommerce|marca|cliente|estrategi|startup|lideraz"),
    Teacher("ai", "AI Teacher", "Inteligencia artificial, ML, LLMs y agentes", ["tecnologia"], "Explica la intuición antes de las fórmulas; usa ejemplos de VISTAN.",
            ["sandbox", "research"], r"inteligencia artificial|\bia\b|machine learning|red neuronal|llm|agente|prompt|modelo"),
    Teacher("programming", "Programming Teacher", "Programación y desarrollo de software", ["programacion"], "Enseña con código ejecutable, corto y comentado; corrige con tests.",
            ["sandbox"], r"python|javascript|typescript|react|codigo|programa|funcion|api|git|base de datos|sql|backend"),
    Teacher("legal", "Legal Teacher", "Derecho y conocimiento jurídico", ["derecho"], "Distingue norma, interpretación y caso; cita normas solo si estás seguro y recuerda verificar vigencia.",
            ["research"], r"derecho|ley|contrato|juridic|tribunal|rgpd|legal"),
    Teacher("psychology", "Psychology Teacher", "Psicología y desarrollo personal", ["psicologia"], "Basado en evidencia; distingue estudios sólidos de divulgación popular.",
            ["research"], r"psicolog|emoci|habito|productividad|motivaci|decisi|sesgo|disciplina"),
    Teacher("history", "History Teacher", "Historia y geopolítica", ["historia"], "Contextualiza con fechas y causas; presenta las interpretaciones historiográficas como tales.",
            ["research"], r"historia|guerra|imperio|siglo|geopolit|civilizaci|revoluci"),
    Teacher("science", "Science Teacher", "Física, química, biología y ciencia", ["ciencia"], "Usa experimentos mentales y unidades; separa consenso científico de hipótesis.",
            ["research", "sandbox"], r"fisica|quimica|biolog|astronom|energia|celula|atomo|neuro"),
    Teacher("language", "Language Teacher", "Idiomas y comunicación", ["idiomas"], "Practica con frases reales; corrige con amabilidad y explica la regla.",
            [], r"ingles|frances|aleman|japones|chino|catalan|gramatica|vocabulario|pronunci|idioma|oratoria|escritura"),
    Teacher("math", "Mathematics Teacher", "Matemáticas", ["ciencia"], "Resuelve paso a paso, verifica los cálculos y propone problemas graduados.",
            ["sandbox"], r"matemat|ecuaci|algebra|calculo|derivad|integral|probabilid|estadistic|geometr"),
    Teacher("critical", "Critical Thinking Teacher", "Pensamiento crítico y resolución de problemas", ["psicologia"], "Usa preguntas socráticas, falacias y análisis de datos.",
            [], r"logica|falacia|argument|razonamiento|pensamiento critico|problema"),
]}
COORDINATOR = "Academy Coordinator"
_BY_CAT = {"economia": "economics", "negocios": "business", "tecnologia": "ai", "programacion": "programming", "derecho": "legal",
           "psicologia": "psychology", "historia": "history", "ciencia": "science", "idiomas": "language"}
_BY_NAME = {"matematicas": "math", "pensamiento critico": "critical", "resolucion de problemas": "critical", "finanzas personales": "finance",
            "trading": "finance", "inversion": "finance", "bolsa": "finance", "contabilidad": "finance", "fiscalidad": "finance",
            "gestion patrimonial": "finance", "finanzas empresariales": "finance", "criptomonedas y blockchain": "finance"}


def _n(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def choose(category: str | None, subject_name: str | None, text: str = "") -> list[Teacher]:
    """Profesor principal según la asignatura y, si el texto toca otra disciplina, un colaborador."""
    main = _BY_NAME.get(_n(subject_name or "")) or _BY_CAT.get(category or "") or None
    t = _n(text)
    hits = sorted(((len(re.findall(x.rx, t)), x.id) for x in TEACHERS.values() if x.rx), reverse=True)
    if not main:
        main = hits[0][1] if hits and hits[0][0] else "critical"
    team = [TEACHERS[main]]
    other = next((tid for n, tid in hits if n and tid != main), None)
    if other:
        team.append(TEACHERS[other])
    return team
