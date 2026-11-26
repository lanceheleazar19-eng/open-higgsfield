"""Autonomous Execution Engine: convierte un objetivo en un plan de pasos REALES del motor de Automatizaciones de VISTAN
(mismos tipos de paso, permisos por nivel, autorizaciones, historial, reintentos, cancelación y checkpoints). El plan se
te muestra antes de ejecutar: nada se ejecuta sin que lo lances, y los pasos de escritura/ejecución piden tu permiso
según tu política. Ningún paso puede pagar, comprar, publicar ni enviar mensajes externos: esos tipos no existen."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from atlas.brain.base import ProviderError
from atlas.metabrain import llm
from atlas.metabrain.governance import meta_conf
from atlas.models import Workflow
from atlas.security.policy import needs_approval
from atlas.workflows.engine import STEP_TYPES

MAX_STEPS = 12
FORBIDDEN = ("backup",)  # disponible en Automatizaciones, pero no en planes generados


def step_catalog() -> list[dict]:
    return [{"type": k, "level": v[0], "label": v[1], "params": v[2]} for k, v in STEP_TYPES.items() if k not in FORBIDDEN]


def validate(steps: list, prefs: dict) -> tuple[list[dict], list[str]]:
    out, problems = [], []
    for i, s in enumerate(steps[:MAX_STEPS]):
        if not isinstance(s, dict) or s.get("type") not in STEP_TYPES or s.get("type") in FORBIDDEN:
            problems.append(f"Paso {i + 1}: tipo «{s.get('type') if isinstance(s, dict) else s}» no existe; descartado")
            continue
        level, label, allowed = STEP_TYPES[s["type"]]
        params = {k: v for k, v in (s.get("params") or {}).items() if k in allowed and v not in (None, "")}
        miss = [p for p in allowed if p not in params and p not in ("agents", "project_id", "suite_id")]
        if miss:
            problems.append(f"Paso {i + 1} ({label}): falta {', '.join(miss)}; descartado")
            continue
        out.append({"type": s["type"], "params": params, "why": str(s.get("why") or s.get("porque") or "")[:300], "level": level, "label": label,
                    "needs_approval": level != "READ" and needs_approval(level, prefs)})
    if len(steps) > MAX_STEPS:
        problems.append(f"El plan tenía {len(steps)} pasos; se limita a {MAX_STEPS}")
    return out, problems


def plan(prefs: dict, goal: str) -> dict:
    cat = "\n".join(f"- {c['type']} [{c['level']}] {c['label']} · parámetros: {', '.join(c['params']) or 'ninguno'}" for c in step_catalog())
    conf = meta_conf(prefs)
    budget = llm.Budget(max_calls=2, max_seconds=int(conf["limits"]["max_seconds"]))
    res = llm.call("json", prefs, [
        {"role": "system", "content": "Eres el Execution Planner de VISTAN. Convierte el objetivo en un plan ejecutable usando SOLO estos "
         "tipos de paso (no inventes otros; si algo no se puede hacer con ellos, dilo en «limitaciones»):\n" + cat +
         '\nDevuelve JSON: {"nombre": str, "comprension": str, "recursos": [str], "pasos": [{"type": str, "params": {}, "why": str}], '
         '"verificacion": str, "limitaciones": [str]}. Máximo 8 pasos. Nada de pagos, compras, publicaciones ni mensajes externos.'},
        {"role": "user", "content": goal}], json_mode=True, budget=budget, tag="meta_exec_plan")
    d = res["data"] if isinstance(res["data"], dict) else {}
    steps, problems = validate(d.get("pasos") or [], prefs)
    if not steps:
        raise ProviderError("El modelo no propuso ningún paso válido. Reformula el objetivo o crea la automatización a mano.")
    return {"name": str(d.get("nombre") or goal)[:110], "understanding": str(d.get("comprension") or "")[:1000],
            "resources": [str(x) for x in (d.get("recursos") or [])][:10], "steps": steps,
            "verification": str(d.get("verificacion") or "")[:600], "limitations": [str(x) for x in (d.get("limitaciones") or [])][:10],
            "problems": problems, "model": res["model"]}


def create(db: Session, name: str, goal: str, steps: list[dict], prefs: dict) -> Workflow:
    clean, _ = validate(steps, prefs)
    if not clean:
        raise ValueError("El plan no tiene pasos válidos")
    wf = Workflow(key=f"meta-{uuid.uuid4().hex[:10]}", name=name[:120], enabled=False, builtin=False, schedule=None,
                  description=f"[META-BRAIN] Objetivo: {goal[:900]}",
                  steps=[{"type": s["type"], "params": s["params"], **({"retries": 1} if s["level"] == "EXECUTE" else {})} for s in clean])
    db.add(wf)
    db.flush()
    return wf


def plan_json(p: dict) -> str:
    return json.dumps(p, ensure_ascii=False)
