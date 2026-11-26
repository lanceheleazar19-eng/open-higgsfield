"""Intelligence Benchmark Center. Reutiliza el Model Testing Arena del Innovation Lab (mismas tablas y ejecución) con una
batería propia de VISTAN: las mismas pruebas, en el mismo orden y con la misma comprobación automática para cada
concursante (cada modelo configurado y el propio META-BRAIN). Todas las puntuaciones salen de comprobaciones
deterministas (número exacto, regex, contiene, tests de Python en el sandbox, consistencia entre repeticiones o datos
reales de VISTAN). No hay puntuaciones inventadas ni «ganadores» declarados sin resultados."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.models import IxArenaSuite

SUITE_NAME = "VISTAN Benchmark v1"
CATEGORIES = {"reasoning": "Razonamiento", "coding": "Programación", "research": "Investigación (no inventar)", "documents": "Comprensión documental",
              "memory": "Memoria en contexto", "math": "Matemáticas", "planning": "Planificación", "tools": "Ejecución de herramientas",
              "consistency": "Consistencia"}
DOC = ("Lumetra es una empresa fundada en 2019 en Valencia. Fabrica sensores de humedad para invernaderos y cuenta con 42 empleados. "
       "En 2023 abrió una oficina en Oporto. Su fundadora, Irene Sáez, es ingeniera agrónoma.")
FILLER = ("Durante la reunión se habló del calendario de entregas, del presupuesto de marketing, de la renovación de las licencias "
          "de software, del plan de formación del equipo y de la posibilidad de cambiar de proveedor de mensajería. ") * 3

TESTS: list[dict] = [
    {"category": "reasoning", "prompt": "Si todos los zorbos son flins y ningún flin es azul, ¿puede un zorbo ser azul? Responde solo «sí» o «no».",
     "check": "regex", "expected": r"^\W*no\b"},
    {"category": "reasoning", "prompt": "Ana es más alta que Bea. Bea es más alta que Carla. ¿Quién es la más baja? Responde solo con el nombre.",
     "check": "contains", "expected": "Carla"},
    {"category": "math", "prompt": "¿Cuánto es 17 × 23? Responde solo con el número.", "check": "number", "expected": "391"},
    {"category": "math", "prompt": "Un producto cuesta 80 €. Sube un 25 % y después baja un 20 %. ¿Cuál es el precio final en euros? Responde solo con el número.",
     "check": "number", "expected": "80"},
    {"category": "math", "prompt": "Resuelve 3x + 7 = 31. Responde solo con el valor de x.", "check": "number", "expected": "8"},
    {"category": "coding", "prompt": "Escribe una función de Python llamada es_primo(n) que devuelva True si n es primo y False si no. Devuelve solo el código.",
     "check": "python", "expected": "assert es_primo(2) and es_primo(97) and not es_primo(1) and not es_primo(91) and not es_primo(0)\nprint('ok')"},
    {"category": "coding", "prompt": "Escribe una función de Python llamada invertir_palabras(s) que invierta el orden de las palabras de una frase separada por espacios. Devuelve solo el código.",
     "check": "python", "expected": "assert invertir_palabras('hola mundo feliz') == 'feliz mundo hola'\nassert invertir_palabras('uno') == 'uno'\nprint('ok')"},
    {"category": "documents", "prompt": f"Texto: «{DOC}»\n¿En qué ciudad se fundó Lumetra y cuántos empleados tiene? Responde con el formato «ciudad, número».",
     "check": "regex", "expected": r"Valencia.{0,20}42"},
    {"category": "documents", "prompt": f"Texto: «{DOC}»\n¿Cuánto facturó Lumetra en 2023? Si el texto no lo dice, responde exactamente «no consta».",
     "check": "contains", "expected": "no consta"},
    {"category": "memory", "prompt": f"Dato para recordar: el código del proyecto es KESTREL-58.\n\n{FILLER}\n\n¿Cuál era el código del proyecto? Responde solo con el código.",
     "check": "contains", "expected": "KESTREL-58"},
    {"category": "planning", "prompt": "Ordena las tareas A, B, C y D respetando: C depende de A; B depende de C; D debe ir al final. Responde solo con las letras separadas por comas.",
     "check": "regex", "expected": r"A\s*,\s*C\s*,\s*B\s*,\s*D"},
    {"category": "planning", "prompt": "Tengo exactamente 3 horas. Tareas: estudiar (90 min), gimnasio (60 min), compra (30 min), llamada (20 min). "
     "¿Qué combinación de tareas ocupa exactamente las 3 horas? Responde solo con los nombres de las tareas.",
     "check": "regex", "expected": r"^(?!.*llamada)(?=.*estudiar)(?=.*gimnasio)(?=.*compra)"},
    {"category": "research", "prompt": "Dame el DOI exacto del artículo «Quantum Banana Teleportation in Ferrets» (2023). Si no puedes verificar que existe, responde exactamente «no puedo verificarlo».",
     "check": "contains", "expected": "no puedo verificarlo"},
    {"category": "research", "prompt": "¿Qué organismo publica el Índice de Precios de Consumo (IPC) en España? Responde solo con su nombre o sus siglas.",
     "check": "regex", "expected": r"\bINE\b|Instituto Nacional de Estad"},
    {"category": "tools", "prompt": "¿Cuántas tareas pendientes tengo ahora mismo en VISTAN? Responde solo con el número.", "check": "live", "expected": "tasks_open"},
    {"category": "tools", "prompt": "¿Cuántos recuerdos tengo guardados en la memoria de VISTAN? Responde solo con el número.", "check": "live", "expected": "memories"},
    {"category": "consistency", "prompt": "Responde con una sola palabra: ¿cuál es la capital de Australia?", "check": "consistency", "expected": "Canberra", "repeat": 3},
]


def live_value(db: Session, key: str) -> str | None:
    """Respuesta correcta calculada en el momento con tus datos reales (para la categoría de herramientas)."""
    from sqlalchemy import func

    from atlas.models import Memory, Task
    if key == "tasks_open":
        return str(db.scalar(select(func.count(Task.id)).where(Task.status.in_(("pending", "in_progress")))) or 0)
    if key == "memories":
        from atlas.services.memory import counts
        return str(counts(db)["memories"])
    return None


def install(db: Session) -> IxArenaSuite:
    s = db.scalar(select(IxArenaSuite).where(IxArenaSuite.name == SUITE_NAME))
    if s:
        s.tests = TESTS  # se actualiza a la versión del código
    else:
        s = IxArenaSuite(name=SUITE_NAME, description="Batería oficial de VISTAN: 9 categorías, comprobación automática. "
                         "«Herramientas» mide el acceso a tus datos: un modelo sin herramientas no puede conocerlos.", tests=TESTS)
        db.add(s)
    db.flush()
    return s


def compare(runs: list[dict], suite_tests: list[dict]) -> dict:
    """Tabla comparativa por categoría con resultados medidos. Solo señala al mejor si hay datos puntuados de todos."""
    table = []
    for r in runs:
        cats: dict[str, list[float]] = {}
        for res in r.get("results") or []:
            t = suite_tests[res["i"]] if res["i"] < len(suite_tests) else {}
            if res.get("score") is not None:
                cats.setdefault(t.get("category", "otros"), []).append(res["score"])
        table.append({"model": r["model"], "run_id": r["id"], "status": r["status"], "summary": r.get("summary") or {},
                      "by_category": {k: round(sum(v) / len(v), 1) for k, v in cats.items()}})
    done = [t for t in table if t["status"] == "done" and t["summary"].get("avg_score") is not None]
    best = None
    if len(done) >= 2:
        top = sorted(done, key=lambda t: -t["summary"]["avg_score"])
        if top[0]["summary"]["avg_score"] > top[1]["summary"]["avg_score"]:
            best = {"model": top[0]["model"], "avg_score": top[0]["summary"]["avg_score"], "tests": top[0]["summary"].get("scored"),
                    "note": "Mejor puntuación media medida en ESTA batería y en estas condiciones; no es una afirmación general."}
    return {"table": table, "best": best, "categories": CATEGORIES}
