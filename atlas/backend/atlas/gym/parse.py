"""Interpreta entrenamientos escritos en español.

Acepta la forma en que la gente apunta sus series:
  «Inclinado 2 calentamiento 2x8 40kg»
  «Triceps v 40kg x 8-10 2 series»
  «Militar 25kg 2 series x 10 reps cada lado maquina»
  «press inclinado 3x8 con 42,5 kg rir 2»
  «dominadas 6, 5 y 5»
Varias líneas (o separadas por «;») = varios ejercicios.
"""

import re
from dataclasses import dataclass, field

from atlas.models import Exercise
from atlas.services.memory import normalize


@dataclass
class ParsedExercise:
    exercise_id: int
    exercise_name: str
    reps: list[int]  # una entrada por serie efectiva
    weight: float | None
    rir: int | None = None
    warmup_sets: int = 0
    per_side: bool = False
    reps_max: int | None = None
    notes: list[str] = field(default_factory=list)


def _alias_index(exercises: list[Exercise]) -> list[tuple[str, Exercise]]:
    idx = []
    for e in exercises:
        for a in [e.name, *(e.aliases or [])]:
            idx.append((normalize(a), e))
    # Los alias más largos primero («curl martillo» antes que «curl»)
    idx.sort(key=lambda x: -len(x[0]))
    return idx


def match_exercise(text: str, exercises: list[Exercise]) -> tuple[Exercise, str] | None:
    """Devuelve (ejercicio, texto restante) si el segmento menciona un ejercicio conocido."""
    n = " " + normalize(text) + " "
    for alias, e in _alias_index(exercises):
        if alias and f" {alias} " in n:
            rest = n.replace(f" {alias} ", " ", 1)
            return e, rest
    return None


NUM = r"\d+(?:[.,]\d+)?"


def _f(s: str) -> float:
    return float(s.replace(",", "."))


def parse_segment(text: str, exercises: list[Exercise]) -> ParsedExercise | None:
    m = match_exercise(text, exercises)
    if not m:
        return None
    ex, rest = m
    # normalize() quitó puntos y comas: recuperamos números decimales del texto original
    raw = " " + text.lower().replace("×", "x") + " "
    t = " " + rest + " "
    notes: list[str] = []

    per_side = bool(re.search(r"\b(por lado|cada lado|por mano|cada mano|por brazo)\b", t)) or ex.per_side
    rir = None
    if (mm := re.search(r"\brir\s*(\d+)", t)):
        rir = int(mm.group(1))
        t = t.replace(mm.group(0), " ")

    weight = None
    if (mm := re.search(rf"({NUM})\s*(?:kg|kilos?|k)\b", raw)):
        weight = _f(mm.group(1))
        t = re.sub(rf"\b{re.escape(normalize(mm.group(1)))}\s*(?:kg|kilos?|k)\b", " ", t, count=1)
    elif (mm := re.search(rf"\b({NUM})\s*(?:por|cada)\s+(?:lado|mano|brazo)\b", raw)):
        weight = _f(mm.group(1))
        t = re.sub(rf"\b{re.escape(normalize(mm.group(1)))}\b", " ", t, count=1)
    elif (mm := re.search(rf"\bcon\s+({NUM})\b", raw)):
        weight = _f(mm.group(1))
        t = re.sub(rf"\bcon\s+{re.escape(normalize(mm.group(1)))}\b", " ", t, count=1)

    warm = 0
    if (mm := re.search(r"\b(\d+)\s*(?:series?\s+(?:de\s+)?)?calentamientos?\b", t)):
        warm = int(mm.group(1))
        t = t.replace(mm.group(0), " ")

    sets = reps = reps_max = None
    reps_list: list[int] = []
    # 3x8, 3 x 8-10
    if (mm := re.search(r"\b(\d+)\s*x\s*(\d+)(?:\s*-\s*(\d+))?\b", t)):
        sets, reps = int(mm.group(1)), int(mm.group(2))
        reps_max = int(mm.group(3)) if mm.group(3) else None
        t = t.replace(mm.group(0), " ")
    # «x 8-10» (sin número de series delante)
    elif (mm := re.search(r"\bx\s*(\d+)(?:\s*-\s*(\d+))?\b", t)):
        reps = int(mm.group(1))
        reps_max = int(mm.group(2)) if mm.group(2) else None
        t = t.replace(mm.group(0), " ")
    # «2 series x 10 reps», «3 series de 8»
    if (mm := re.search(r"\b(\d+)\s*series?\b(?:\s*(?:x|de)\s*(\d+)(?:\s*-\s*(\d+))?)?", t)):
        sets = int(mm.group(1))
        if mm.group(2):
            reps = int(mm.group(2))
            reps_max = int(mm.group(3)) if mm.group(3) else reps_max
        t = t.replace(mm.group(0), " ")
    if reps is None and (mm := re.search(r"\b(\d+)\s*(?:reps?|repeticiones)\b", t)):
        reps = int(mm.group(1))
        t = t.replace(mm.group(0), " ")
    # Lista de repeticiones: «6 5 y 5» (normalize ya quitó las comas)
    if reps is None:
        nums = [int(x) for x in re.findall(r"\b(\d{1,2})\b", t)]
        if nums and all(1 <= n <= 30 for n in nums):  # números grandes son pesos, no repeticiones
            reps_list = nums
    # Rango «8-10» (normalize quitó el guion: se lee del texto original)
    if reps is not None and reps_max is None and (mm := re.search(r"x\s*(\d+)\s*-\s*(\d+)", raw)):
        reps_max = int(mm.group(2))
    if reps is not None:
        reps_list = [reps] * (sets or 1)
    if not reps_list:
        return None  # sin series no hay nada que registrar
    if reps_max and reps_max != reps:
        notes.append(f"rango {reps}-{reps_max}")
    return ParsedExercise(ex.id, ex.name, reps_list, weight, rir, warm, per_side, reps_max, notes)


def split_segments(text: str) -> list[str]:
    parts = re.split(r"[\n;]+|\s+y\s+luego\s+|\.\s+(?=[A-Za-zÁÉÍÓÚáéíóúñ])", text)
    return [p.strip(" .,-") for p in parts if p.strip(" .,-")]


def parse_workout(text: str, exercises: list[Exercise]) -> list[ParsedExercise]:
    out = []
    for seg in split_segments(text):
        p = parse_segment(seg, exercises)
        if p:
            out.append(p)
    return out


LOG_TRIGGER = re.compile(
    r"^(?:atlas[,:\s]+)?(?:hoy\s+)?(?:he\s+hecho|acabo\s+de\s+hacer|registra(?:r)?|apunta\s+(?:el\s+)?entreno|entreno\s*:|"
    r"he\s+entrenado|hice)\b", re.IGNORECASE)


def looks_like_log(text: str) -> bool:
    """¿El mensaje registra series? (trigger explícito o formato NxM/«series» sin ser pregunta)."""
    if "?" in text or "¿" in text:
        return False
    if LOG_TRIGGER.search(text.strip()):
        return True
    return bool(re.search(r"\d+\s*[x×]\s*\d+|\d+\s*series?\b", text, re.IGNORECASE))
