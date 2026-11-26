"""Corrección con criterios DEFINIDOS (no valoraciones arbitrarias):
- test, verdadero/falso: respuesta exacta · numérica: tolerancia declarada · código: tests ejecutados en el sandbox aislado
- abiertas/casos: rúbrica con puntos por criterio; la IA solo decide si cada criterio se cumple (sí/no) y lo justifica.
Nota = puntos obtenidos / puntos posibles (cada tipo de pregunta pesa sus puntos)."""

from __future__ import annotations

import re

from atlas.academy import ai
from atlas.brain.base import ProviderError

CRITERIA_NOTE = ("Tipo test y V/F: 1 punto, respuesta exacta. Numéricas: 2 puntos, dentro de la tolerancia indicada. Abiertas: 3 puntos y casos: 4 "
                 "puntos, repartidos según los criterios de la rúbrica. Código: 4 puntos, proporcional a los tests superados en el sandbox.")


def _num(v: object) -> float | None:
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v or ""))
    return float(m.group().replace(",", ".")) if m else None


def _code(ans: str, tests: str) -> tuple[float, str]:
    from atlas.lab.sandbox import run_python
    lines = [ln for ln in tests.splitlines() if ln.strip().startswith("assert")]
    if not ans.strip():
        return 0.0, "Sin código"
    body = "\n".join(f"try:\n    {ln.strip()}\n    __p += 1\nexcept Exception as __e:\n    __f.append({ln.strip()!r})" for ln in lines)
    res = run_python(f"{ans}\n\n__p = 0\n__f = []\n{body}\nprint('__RESULT__', __p, len(__f))\nfor x in __f: print('FALLA:', x)")
    m = re.search(r"__RESULT__ (\d+) (\d+)", res.get("stdout", ""))
    if not m:
        return 0.0, f"El código no se pudo ejecutar ({res.get('status')}): {(res.get('stderr') or '')[-400:]}"
    ok, bad = int(m.group(1)), int(m.group(2))
    fails = [ln for ln in res["stdout"].splitlines() if ln.startswith("FALLA:")]
    return (ok / (ok + bad) * 100 if ok + bad else 0.0), f"{ok}/{ok + bad} tests superados" + (f". {'; '.join(fails[:3])}" if fails else "")


def grade(prefs: dict, subject: str, questions: list[dict], answers: list) -> dict:
    results: list[dict] = [{} for _ in questions]
    opens = []
    for i, (q, a) in enumerate(zip(questions, answers)):
        t = q["type"]
        base = {"type": t, "topic": q.get("topic"), "points": q.get("points", 1), "explanation": q.get("explanation")}
        if t == "mcq":
            ok = isinstance(a, int) and a == q["answer"]
            results[i] = {**base, "score": 100.0 if ok else 0.0, "correct": ok, "answer": q["answer"]}
        elif t == "tf":
            ok = isinstance(a, bool) and a == q["answer"]
            results[i] = {**base, "score": 100.0 if ok else 0.0, "correct": ok, "answer": q["answer"]}
        elif t == "numeric":
            v = _num(a)
            ok = v is not None and abs(v - q["answer"]) <= q["tolerance"]
            results[i] = {**base, "score": 100.0 if ok else 0.0, "correct": ok, "answer": q["answer"], "tolerance": q["tolerance"]}
        elif t == "code":
            sc, why = _code(str(a or ""), q["tests"])
            results[i] = {**base, "score": round(sc, 1), "correct": sc == 100, "feedback": why, "answer": q.get("solution")}
        else:
            if not str(a or "").strip():
                results[i] = {**base, "score": 0.0, "correct": False, "feedback": "Sin respuesta", "answer": q.get("model_answer"), "criteria": q["criteria"]}
            else:
                opens.append(i)
    if opens:
        items = [{"pregunta": questions[i]["q"], "criterios": [c["criterio"] for c in questions[i]["criteria"]], "respuesta": str(answers[i])[:4000]} for i in opens]
        try:
            graded = ai.grade_rubric(prefs, subject, items)
        except ProviderError as exc:
            graded = []
            err = str(exc)
        else:
            err = None
        for j, i in enumerate(opens):
            q = questions[i]
            g = graded[j] if j < len(graded) and isinstance(graded[j], dict) else {}
            marks = g.get("criterios") or []
            total = sum(c["puntos"] for c in q["criteria"])
            got = sum(c["puntos"] for k, c in enumerate(q["criteria"]) if k < len(marks) and isinstance(marks[k], dict) and marks[k].get("cumple") is True)
            results[i] = {"type": q["type"], "topic": q.get("topic"), "points": q.get("points", 3), "score": round(got / total * 100, 1) if total and marks else 0.0,
                          "correct": bool(total) and got == total, "answer": q.get("model_answer"),
                          "criteria": [{**c, "cumple": bool(marks[k].get("cumple")) if k < len(marks) and isinstance(marks[k], dict) else None,
                                        "porque": marks[k].get("porque") if k < len(marks) and isinstance(marks[k], dict) else None} for k, c in enumerate(q["criteria"])],
                          "feedback": g.get("feedback") or (f"No se pudo corregir con IA: {err}" if err else None), "graded_by": "rúbrica + IA (criterios definidos)",
                          "pending": not marks}
    pts = sum(r["points"] for r in results)
    got = sum(r["points"] * r["score"] / 100 for r in results)
    pct = round(got / pts * 100, 1) if pts else 0.0
    topics: dict[str, list[float]] = {}
    for r in results:
        if r.get("topic"):
            topics.setdefault(r["topic"], []).append(r["score"])
    return {"results": results, "score": pct, "grade_10": round(pct / 10, 1), "correct": sum(1 for r in results if r.get("correct")),
            "incorrect": sum(1 for r in results if not r.get("correct")), "points": round(got, 2), "max_points": pts,
            "mastered_topics": sorted(t for t, v in topics.items() if sum(v) / len(v) >= 80),
            "weak_topics": sorted(t for t, v in topics.items() if sum(v) / len(v) < 60), "criteria_note": CRITERIA_NOTE,
            "pending_ai": any(r.get("pending") for r in results)}
