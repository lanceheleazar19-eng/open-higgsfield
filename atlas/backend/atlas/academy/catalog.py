"""Academy Library: biblioteca ampliable de disciplinas. Reutiliza las asignaturas de LIFE OS (lf_subjects) y añade el
resto; el usuario puede incorporar disciplinas propias (custom)."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.models import LfSubject

CATEGORIES = {
    "economia": "Economía y finanzas", "negocios": "Emprendimiento y negocios", "tecnologia": "Tecnología e inteligencia artificial",
    "programacion": "Programación y desarrollo", "derecho": "Derecho y conocimiento jurídico", "psicologia": "Psicología y desarrollo personal",
    "historia": "Historia y geopolítica", "ciencia": "Ciencia y tecnología", "idiomas": "Idiomas y comunicación",
}
LIBRARY = {
    "economia": ["Economía básica", "Macroeconomía", "Microeconomía", "Mercados financieros", "Bolsa", "Trading", "Inversión", "Gestión patrimonial",
                 "Contabilidad", "Fiscalidad", "Finanzas empresariales", "Gestión de riesgos", "Finanzas personales", "Criptomonedas y blockchain"],
    "negocios": ["Creación de empresas", "Modelos de negocio", "E-commerce", "Shopify", "Dropshipping", "Marketing digital", "Branding", "Ventas",
                 "Negociación", "Gestión empresarial", "Estrategia empresarial", "Liderazgo", "Gestión de equipos", "Análisis de competencia",
                 "Escalabilidad", "Emprendimiento tecnológico"],
    "tecnologia": ["Inteligencia artificial", "Machine Learning", "Deep Learning", "Agentes autónomos", "Sistemas multiagente", "LLMs", "Prompt Engineering",
                   "Automatización", "Robótica", "Ciencia de datos", "Ciberseguridad", "Computación en la nube", "APIs", "Blockchain", "Computación cuántica"],
    "programacion": ["Python", "JavaScript", "TypeScript", "HTML y CSS", "React", "Backend", "Bases de datos", "Git", "Arquitectura de software",
                     "Desarrollo de aplicaciones", "Desarrollo web", "Desarrollo de IA", "Ingeniería de software"],
    "derecho": ["Derecho civil", "Derecho mercantil", "Derecho laboral", "Derecho penal", "Derecho administrativo", "Derecho fiscal", "Derecho digital",
                "Protección de datos", "Derecho europeo", "Contratos", "Legislación empresarial"],
    "psicologia": ["Psicología general", "Psicología cognitiva", "Inteligencia emocional", "Comunicación", "Toma de decisiones", "Disciplina", "Productividad",
                   "Pensamiento crítico", "Resolución de problemas", "Gestión del tiempo", "Liderazgo personal", "Filosofía"],
    "historia": ["Historia antigua", "Historia medieval", "Historia moderna", "Historia contemporánea", "Historia económica", "Geopolítica",
                 "Relaciones internacionales", "Historia militar", "Civilizaciones", "Sistemas políticos"],
    "ciencia": ["Física", "Química", "Matemáticas", "Biología", "Astronomía", "Neurociencia", "Biotecnología", "Nanotecnología", "Energía",
                "Investigación científica", "Tecnología"],
    "idiomas": ["Inglés", "Catalán", "Español", "Francés", "Alemán", "Japonés", "Chino", "Escritura", "Oratoria", "Comunicación profesional", "Idiomas"],
}
# Asignaturas que ya existían en LIFE OS (se conservan con su clave y su historial)
LEGACY = {"economia": ("economia", "Economía básica"), "finanzas": ("economia", "Finanzas personales"), "emprendimiento": ("negocios", "Creación de empresas"),
          "marketing": ("negocios", "Marketing digital"), "ventas": ("negocios", "Ventas"), "negociacion": ("negocios", "Negociación"),
          "psicologia": ("psicologia", "Psicología general"), "filosofia": ("psicologia", "Filosofía"), "historia": ("historia", "Historia contemporánea"),
          "geopolitica": ("historia", "Geopolítica"), "ia": ("tecnologia", "Inteligencia artificial"), "programacion": ("programacion", "Python"),
          "tecnologia": ("ciencia", "Tecnología"), "liderazgo": ("negocios", "Liderazgo"), "comunicacion": ("psicologia", "Comunicación"), "idiomas": ("idiomas", "Idiomas")}
HIGH_IMPACT = {"derecho": "derecho", "economia": "finanzas"}
HIGH_IMPACT_NAMES = {"Neurociencia", "Psicología general", "Psicología cognitiva", "Biología", "Biotecnología"}


def slug(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:32]


def ensure(db: Session) -> None:
    from atlas.life.service import ensure_subjects
    ensure_subjects(db)
    have = {s.key: s for s in db.scalars(select(LfSubject))}
    legacy_names = set()
    for key, (cat, same_as) in LEGACY.items():
        s = have.get(key)
        if s and not s.category:
            s.category = cat
        legacy_names.add((cat, same_as))
    taken = {(s.category, s.name) for s in have.values()}
    for cat, names in LIBRARY.items():
        for n in names:
            k = slug(n)
            if k in have or (cat, n) in taken:
                continue
            if any(lk for lk, (lc, ln) in LEGACY.items() if lc == cat and ln == n and lk in have):
                continue  # ya cubierta por una asignatura de LIFE OS
            s = LfSubject(key=k, name=n, syllabus=[], category=cat)
            db.add(s)
            have[k] = s
    db.flush()


def high_impact(s: LfSubject) -> str | None:
    if s.category == "derecho":
        return "derecho"
    if s.category == "economia" and any(w in s.name.lower() for w in ("trading", "inversi", "bolsa", "fiscal", "patrimon", "cripto", "finanzas", "riesgo", "mercados")):
        return "finanzas"
    if s.name in HIGH_IMPACT_NAMES:
        return "salud"
    return None


DISCLAIMERS = {
    "derecho": "Contenido educativo, no asesoramiento jurídico. La normativa cambia: comprueba la fuente oficial (BOE, EUR-Lex) y consulta a un abogado para casos concretos.",
    "finanzas": "Contenido educativo, no asesoramiento financiero. Invertir implica riesgo de pérdida. Los ejercicios usan dinero virtual.",
    "salud": "Contenido educativo, no consejo médico ni psicológico. Ante un problema de salud, consulta a un profesional sanitario.",
}
