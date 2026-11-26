"""Legal Document Studio: borradores con IA LOCAL que NUNCA inventan datos de las partes.
Lo que no aportas aparece como [[PENDIENTE: …]]. Tras generar, un filtro determinista sustituye cualquier DNI/NIE/CIF,
IBAN, email, teléfono, fecha o nombre propio tras «D./Dña.» que no estuviera en tus datos."""

from __future__ import annotations

import re

from atlas.legal import ai

TEMPLATES = {
    "nda": ("Acuerdo de confidencialidad (NDA)", ["parte_reveladora", "parte_receptora", "finalidad", "duracion"]),
    "servicios": ("Contrato de prestación de servicios", ["prestador", "cliente", "servicios", "precio", "plazo"]),
    "compraventa": ("Contrato de compraventa", ["vendedor", "comprador", "objeto", "precio"]),
    "arrendamiento": ("Contrato de arrendamiento", ["arrendador", "arrendatario", "inmueble", "renta", "duracion"]),
    "reclamacion": ("Reclamación", ["reclamante", "destinatario", "hechos", "peticion"]),
    "carta": ("Carta formal", ["remitente", "destinatario", "asunto", "contenido"]),
    "requerimiento_pago": ("Requerimiento de pago", ["acreedor", "deudor", "importe", "concepto", "fecha_vencimiento_original"]),
    "acuerdo_comercial": ("Acuerdo comercial", ["partes", "objeto", "condiciones_economicas"]),
    "autorizacion": ("Autorización", ["autorizante", "autorizado", "objeto"]),
    "privacidad": ("Política de privacidad", ["responsable", "finalidades", "datos_tratados"]),
    "terminos": ("Términos y condiciones", ["titular", "actividad", "productos_o_servicios"]),
    "interno": ("Documento interno", ["asunto", "contenido"]),
    "informe": ("Informe jurídico", ["asunto", "antecedentes", "cuestion"]),
    "alegaciones": ("Alegaciones / escrito administrativo", ["interesado", "organo", "expediente", "hechos", "peticion"]),
}
PENDING = re.compile(r"\[\[PENDIENTE:\s*([^\]]+)\]\]")
HEADER = "BORRADOR — documento generado por VISTAN LEGAL, sujeto a revisión profesional antes de su uso."
SENSITIVE = [
    ("DNI/NIE/CIF", r"\b(?:\d{8}[A-HJ-NP-TV-Z]|[XYZ]\d{7}[A-HJ-NP-TV-Z]|[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J])\b"),
    ("IBAN", r"\bES\d{2}(?:\s?\d{4}){5}\b"),
    ("email", r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    ("teléfono", r"\b(?:\+34\s?)?[6789]\d{2}\s?\d{3}\s?\d{3}\b"),
    ("fecha", r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{1,2} de (?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre) de \d{4}\b"),
    ("nombre", r"\b(?:D\.|Dña\.|Don|Doña|Sr\.|Sra\.)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3}"),
    ("dirección", r"\b(?:[Cc]alle|C/|[Aa]venida|Avda\.|[Pp]laza|[Pp]aseo)\s+[A-ZÁÉÍÓÚÑ][\w\s]{2,40}?,?\s*(?:n[ºo°]\.?\s*)?\d+"),
]


def scrub(text: str, inputs: dict) -> tuple[str, list[str]]:
    """Sustituye datos personales que NO estén en tus datos por marcadores pendientes. Devuelve (texto, sustituciones)."""
    given = " ".join(str(v) for v in inputs.values() if v).lower()
    changed = []
    for label, rx in SENSITIVE:
        def rep(m: re.Match, label=label) -> str:  # noqa: ANN001
            if m.group(0).lower() in given:
                return m.group(0)
            changed.append(f"{label}: «{m.group(0)}»")
            return f"[[PENDIENTE: {label}]]"
        text = re.sub(rx, rep, text)
    return text, changed


def pending(text: str) -> list[str]:
    return sorted(set(m.strip() for m in PENDING.findall(text)))


def generate(prefs: dict, doc_type: str, jurisdiction: str, inputs: dict, request: str, legal_notes: str = "") -> dict:
    label, needed = TEMPLATES.get(doc_type, (doc_type, []))
    missing = [k for k in needed if not str(inputs.get(k) or "").strip()]
    res = ai.call(prefs, [
        {"role": "system", "content": ai.RULES + f"\nRedacta un BORRADOR de «{label}» para la jurisdicción {jurisdiction}. Usa SOLO los DATOS "
         "aportados. Cualquier dato no aportado (nombres, DNI, direcciones, fechas, importes, cuentas) debe escribirse exactamente como "
         "[[PENDIENTE: descripción]]. No cites artículos concretos salvo que aparezcan en las NOTAS JURÍDICAS verificadas. JSON: "
         "{\"titulo\": str, \"contenido\": str (texto completo con cláusulas numeradas), \"revisar\": [{\"clausula\": str, \"motivo\": str}]}"},
        {"role": "user", "content": f"PETICIÓN: {request}\nDATOS APORTADOS: {inputs}\nNOTAS JURÍDICAS VERIFICADAS: {legal_notes or '(ninguna)'}"}],
        "draft", max_calls=2)
    d = res["data"] or {}
    content = str(d.get("contenido") or "").strip()
    if not content:
        raise ValueError("El modelo no devolvió contenido")
    content, scrubbed = scrub(content, inputs)
    if not content.startswith("BORRADOR"):
        content = f"{HEADER}\n\n{content}"
    review = [r for r in (d.get("revisar") or []) if isinstance(r, dict)][:15]
    return {"title": str(d.get("titulo") or label)[:200], "content": content, "pending": pending(content), "review": review,
            "missing_inputs": missing, "scrubbed": scrubbed, "model": res["model"]}
