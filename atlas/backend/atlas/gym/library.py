"""Biblioteca de ejercicios en español (con alias para el registro por texto o voz).

Se sincroniza al arrancar: añade los que falten, sin tocar los creados o editados por el usuario.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.models import Exercise

# (nombre, músculo principal, secundarios, equipo, por_lado, alias)
LIBRARY: list[tuple[str, str, list[str], str, bool, list[str]]] = [
    # Pecho
    ("Press inclinado", "pecho", ["hombros", "triceps"], "barra", False, ["inclinado", "press inclinado", "press banca inclinado", "banca inclinada"]),
    ("Press banca", "pecho", ["triceps", "hombros"], "barra", False, ["banca", "press de banca", "press plano"]),
    ("Press banca con mancuernas", "pecho", ["triceps", "hombros"], "mancuernas", True, ["press mancuernas", "banca mancuernas"]),
    ("Press inclinado con mancuernas", "pecho", ["hombros", "triceps"], "mancuernas", True, ["inclinado mancuernas"]),
    ("Chest press", "pecho", ["triceps", "hombros"], "máquina", True, ["chest press", "press de pecho", "press pecho maquina"]),
    ("Aperturas en polea hacia el medio", "pecho", [], "polea", True, ["aperturas hacia el medio", "aperturas al medio", "aperturas medio", "cruces de polea", "cruce de poleas"]),
    ("Aperturas en polea hacia arriba", "pecho", ["hombros"], "polea", True, ["aperturas hacia arriba", "aperturas arriba", "cruces bajos"]),
    ("Aperturas con mancuernas", "pecho", [], "mancuernas", True, ["aperturas mancuernas", "flyes"]),
    ("Fondos en paralelas", "pecho", ["triceps", "hombros"], "peso corporal", False, ["fondos", "dips"]),
    ("Flexiones", "pecho", ["triceps", "hombros"], "peso corporal", False, ["flexiones", "push ups"]),
    # Espalda
    ("Jalón al pecho en máquina", "espalda", ["biceps"], "máquina", True, ["jalon al pecho", "jalon", "jalon maquina", "lat pulldown"]),
    ("Jalón al pecho en polea", "espalda", ["biceps"], "polea", False, ["jalon polea"]),
    ("Remo de densidad", "espalda", ["biceps", "deltoide_posterior", "trapecio"], "máquina", False, ["remo densidad", "remo de densidad"]),
    ("Remo con barra", "espalda", ["biceps", "deltoide_posterior"], "barra", False, ["remo barra"]),
    ("Remo con mancuerna", "espalda", ["biceps"], "mancuernas", True, ["remo mancuerna", "remo unilateral"]),
    ("Remo en polea baja", "espalda", ["biceps"], "polea", False, ["remo polea", "remo sentado"]),
    ("Pullover unilateral", "espalda", [], "polea", True, ["pullover", "pull over"]),
    ("Dominadas", "espalda", ["biceps"], "peso corporal", False, ["dominadas", "dominada", "pull ups", "pullups"]),
    ("Peso muerto", "espalda", ["isquios", "gluteos", "trapecio"], "barra", False, ["peso muerto", "deadlift"]),
    # Hombros
    ("Press militar en máquina", "hombros", ["triceps"], "máquina", True, ["militar", "press militar", "militar maquina"]),
    ("Press militar con barra", "hombros", ["triceps"], "barra", False, ["militar barra"]),
    ("Press de hombro con mancuernas", "hombros", ["triceps"], "mancuernas", True, ["press hombro", "press arnold"]),
    ("Elevaciones laterales en polea", "hombros", [], "polea", True, ["hombro laterales", "laterales", "laterales polea", "elevaciones laterales"]),
    ("Elevaciones laterales con mancuernas", "hombros", [], "mancuernas", True, ["laterales mancuernas"]),
    ("Deltoides posterior", "deltoide_posterior", ["trapecio"], "máquina", True, ["deltoides posterior", "deltoide posterior", "posterior", "pajaros", "reverse fly"]),
    ("Face pull", "deltoide_posterior", ["trapecio"], "polea", False, ["face pull", "facepull"]),
    # Trapecio
    ("Encogimientos (shrug)", "trapecio", [], "mancuernas", False, ["shrug", "shrugs", "encogimientos"]),
    # Bíceps / antebrazo
    ("Curl de bíceps", "biceps", ["antebrazo"], "barra", False, ["curl de bicep", "curl de biceps", "curl biceps", "curl bicep", "curl"]),
    ("Curl martillo", "biceps", ["antebrazo"], "mancuernas", True, ["martillo", "curl martillo", "hammer"]),
    ("Curl bayesiano", "biceps", [], "polea", True, ["bayesian", "bayesiano", "curl bayesian"]),
    ("Curl predicador", "biceps", [], "máquina", False, ["predicador", "scott"]),
    ("Curl concentrado", "biceps", [], "mancuernas", True, ["concentrado"]),
    ("Curl de muñeca", "antebrazo", [], "mancuernas", False, ["curl muneca", "antebrazo"]),
    ("Paseo del granjero", "antebrazo", ["trapecio"], "mancuernas", True, ["granjero", "farmer walk"]),
    # Tríceps
    ("Tríceps en V (polea)", "triceps", [], "polea", False, ["triceps v", "triceps en v", "tricep v", "pushdown", "jalon triceps"]),
    ("Extensión de tríceps por encima de la cabeza", "triceps", [], "polea", False, ["triceps hacia arriba", "tricep hacia arriba", "triceps arriba", "extension overhead", "triceps por encima"]),
    ("Tríceps unilateral en polea", "triceps", [], "polea", True, ["tricep unilateral", "triceps unilateral"]),
    ("Press francés", "triceps", [], "barra", False, ["press frances", "frances"]),
    # Pierna
    ("Sentadilla", "cuadriceps", ["gluteos", "isquios"], "barra", False, ["sentadilla", "squat"]),
    ("Prensa", "cuadriceps", ["gluteos"], "máquina", False, ["prensa", "leg press"]),
    ("Extensión de cuádriceps", "cuadriceps", [], "máquina", False, ["extension cuadriceps", "extensiones"]),
    ("Zancadas", "cuadriceps", ["gluteos"], "mancuernas", True, ["zancadas", "lunges"]),
    ("Peso muerto rumano", "isquios", ["gluteos", "espalda"], "barra", False, ["rumano", "peso muerto rumano"]),
    ("Curl femoral", "isquios", [], "máquina", False, ["femoral", "curl femoral"]),
    ("Hip thrust", "gluteos", ["isquios"], "barra", False, ["hip thrust", "empuje de cadera"]),
    ("Gemelos de pie", "gemelos", [], "máquina", False, ["gemelos", "pantorrilla"]),
    # Abdomen
    ("Plancha", "abdomen", [], "peso corporal", False, ["plancha", "plank"]),
    ("Crunch en polea", "abdomen", [], "polea", False, ["crunch", "abdominales"]),
    ("Elevaciones de piernas", "abdomen", [], "peso corporal", False, ["elevaciones de piernas", "elevacion de piernas"]),
]

MUSCLE_ES = {"pecho": "pecho", "espalda": "espalda", "hombros": "hombros", "deltoide_posterior": "deltoide posterior",
             "biceps": "bíceps", "triceps": "tríceps", "antebrazo": "antebrazo", "trapecio": "trapecio",
             "cuadriceps": "cuádriceps", "isquios": "isquiotibiales", "gluteos": "glúteos", "gemelos": "gemelos",
             "abdomen": "abdomen"}


def ensure_library(db: Session) -> int:
    existing = set(db.scalars(select(Exercise.name)))
    added = 0
    for name, muscle, sec, equip, per_side, aliases in LIBRARY:
        if name not in existing:
            db.add(Exercise(name=name, muscle=muscle, secondary=sec, equipment=equip, per_side=per_side, aliases=aliases))
            added += 1
    db.commit()
    return added
