"""Comprobaciones deterministas del Critic Engine y del verificador. No dependen de ningún modelo:
recalculan operaciones, detectan afirmaciones absolutas sin evidencia, posible desactualización e
instrucciones maliciosas, y miden si cada «hecho» tiene apoyo textual en la evidencia que cita."""

from __future__ import annotations

import re
import unicodedata

NUM = r"-?\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|-?\d+(?:[.,]\d+)?"
ARITH = re.compile(rf"({NUM})\s*([+\-×x*/÷])\s*({NUM})\s*=\s*({NUM})")
PCT = re.compile(rf"({NUM})\s*%\s*de\s*({NUM})\s*(?:€|euros|\$)?\s*(?:=|es|son|equivale a)\s*({NUM})", re.I)
ABSOLUTE = re.compile(r"\b(est[aá] (cient[ií]ficamente )?demostrado|siempre funciona|garantizad[oa]|100 ?% seguro|sin ning[uú]n riesgo|"
                      r"todos los expertos|nunca falla|seg[uú]n (los )?estudios)\b", re.I)
RECENT = re.compile(r"\b(actualmente|hoy en d[ií]a|este a[nñ]o|[uú]ltim[oa]s? (versi[oó]n|noticias|datos)|recientemente|en la actualidad)\b", re.I)
STOP = set("""de la que el en y a los del se las por un para con no una su al lo como mas pero sus le ya o este si porque esta entre
cuando muy sin sobre tambien me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese eso ante ellos e esto
mi antes algunos que unos yo otro otras otra el tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas algo
nosotros es son fue ser ha han muy cada the and of to in is are""".split())


def _num(s: str) -> float | None:
    s = s.strip().replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s):  # 1.234,5
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def check_calculations(text: str) -> list[dict]:
    issues = []
    for m in ARITH.finditer(text):
        a, op, b, c = _num(m.group(1)), m.group(2), _num(m.group(3)), _num(m.group(4))
        if None in (a, b, c):
            continue
        try:
            real = {"+": a + b, "-": a - b, "×": a * b, "x": a * b, "*": a * b, "/": a / b, "÷": a / b}[op]
        except ZeroDivisionError:
            continue
        if abs(real - c) > max(0.01, abs(real) * 0.005):
            issues.append({"tipo": "cálculo", "gravedad": "alta", "detalle": f"«{m.group(0)}» es incorrecto: el resultado es {round(real, 4)}"})
    for m in PCT.finditer(text):
        p, base, c = _num(m.group(1)), _num(m.group(2)), _num(m.group(3))
        if None in (p, base, c):
            continue
        real = p / 100 * base
        if abs(real - c) > max(0.01, abs(real) * 0.005):
            issues.append({"tipo": "cálculo", "gravedad": "alta", "detalle": f"«{m.group(0)}» es incorrecto: el {p}% de {base} es {round(real, 4)}"})
    return issues


def deterministic_critique(answer: str, evidence: list[dict], injection_flags: int, specialists: dict | None = None) -> list[dict]:
    issues = check_calculations(answer)
    for m in ABSOLUTE.finditer(answer):
        issues.append({"tipo": "afirmación sin evidencia", "gravedad": "media", "detalle": f"Afirmación absoluta: «{m.group(0)}». Exige fuente o matiz."})
    external = [e for e in evidence if e["kind"] in ("research", "document")]
    if RECENT.search(answer) and not external:
        issues.append({"tipo": "posible desactualización", "gravedad": "media",
                       "detalle": "Habla de la situación actual sin fuentes consultadas hoy: el conocimiento del modelo tiene fecha de corte."})
    if injection_flags:
        issues.append({"tipo": "instrucción maliciosa", "gravedad": "alta",
                       "detalle": f"{injection_flags} fragmento(s) de contenido externo parecían instrucciones para la IA y se neutralizaron."})
    if specialists and len(specialists) >= 2:
        confs = [str(s.get("confianza", "")).lower() for s in specialists.values() if isinstance(s, dict)]
        if confs and all(c == "alta" for c in confs) and not external:
            issues.append({"tipo": "consenso no es verdad", "gravedad": "media",
                           "detalle": "Todos los especialistas coinciden con confianza alta pero sin fuentes externas: el acuerdo entre modelos no prueba que sea cierto."})
    return issues


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _terms(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{4,}", _norm(t)) if w not in STOP}


def support(claim: str, texts: list[str]) -> float:
    """Proporción de términos relevantes de la afirmación presentes en la evidencia citada (0-1).
    Los números de la afirmación deben aparecer tal cual."""
    ev = _norm(" ".join(texts))
    terms = _terms(claim)
    nums = re.findall(r"\d+(?:[.,]\d+)?", claim)
    if nums and not all(n in ev or n.replace(",", ".") in ev or n.replace(".", ",") in ev for n in nums):
        return 0.0
    if not terms:
        return 1.0 if nums else 0.0
    return sum(1 for w in terms if w in ev) / len(terms)


def verify(facts: list[dict], evidence: list[dict]) -> dict:
    """Verificación de soporte textual: cada hecho debe citar evidencia (E1, E2…) que lo respalde.
    Mide apoyo documental, no «verdad absoluta»."""
    by_id = {e["id"]: e for e in evidence}
    out, supported = [], 0
    for f in facts:
        txt = str(f.get("texto") or f.get("text") or "").strip()
        if not txt:
            continue
        refs = [r.strip("[] ") for r in re.findall(r"E\d+", str(f.get("evidencia") or f.get("fuente") or "") + " " + txt)]
        refs = [r for r in dict.fromkeys(refs) if r in by_id]
        if not refs:
            out.append({"claim": txt, "status": "sin_fuente", "score": 0.0, "refs": []})
            continue
        s = support(txt, [by_id[r]["text"] for r in refs])
        st = "respaldado" if s >= 0.5 else "debil" if s >= 0.25 else "sin_respaldo"
        supported += st == "respaldado"
        out.append({"claim": txt, "status": st, "score": round(s, 2), "refs": refs})
    return {"checked": len(out), "supported": supported, "claims": out,
            "rate": round(supported / len(out) * 100, 1) if out else None,
            "note": "Comprueba que cada hecho tenga apoyo textual en la evidencia que cita (términos y cifras). "
                    "No demuestra que la fuente sea cierta: la fiabilidad de cada fuente se indica aparte."}
