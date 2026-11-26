"""Legal Compliance para empresas y negocios digitales: listas de comprobación por tipo de negocio.
Cada obligación indica su norma, artículo y fuente OFICIAL (identificadores BOE/EUR-Lex), y si es:
- confirmada: se aplica con carácter general a ese tipo de actividad,
- potencial: depende de circunstancias (volumen, datos tratados, tipo de cliente…),
- asesoramiento: requiere análisis profesional.
Son referencias de partida: la vigencia se comprueba con la API del BOE/EUR-Lex desde la propia lista."""

from __future__ import annotations

BOE = "https://www.boe.es/buscar/act.php?id="
EUR = "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:"
RGPD, LOPDGDD, LSSI, TRLGDCU, LCGC, LPI, LGT = (f"{EUR}32016R0679", f"{BOE}BOE-A-2018-16673", f"{BOE}BOE-A-2002-13758",
                                                 f"{BOE}BOE-A-2007-20555", f"{BOE}BOE-A-1998-8789", f"{BOE}BOE-A-1996-8930", f"{BOE}BOE-A-2003-23186")
PROFILES = {"ecommerce": "Tienda online / e-commerce (p. ej. Shopify)", "saas": "Software / SaaS", "servicios": "Servicios profesionales con web",
            "autonomo": "Autónomo con clientes particulares", "sociedad": "Sociedad mercantil (S.L.)"}

_ALL_WEB = [
    ("lssi", "Información general del prestador accesible en la web (identidad, NIF, domicilio, contacto, registro)", "LSSI-CE (Ley 34/2002)", "art. 10", LSSI, "confirmada"),
    ("cookies", "Consentimiento informado para cookies no necesarias y política de cookies", "LSSI-CE (Ley 34/2002)", "art. 22.2", LSSI, "confirmada"),
    ("datos", "Informar a los interesados en la recogida de datos (política de privacidad)", "RGPD (Reglamento UE 2016/679)", "art. 13", RGPD, "confirmada"),
    ("datos", "Registro de actividades de tratamiento", "RGPD (Reglamento UE 2016/679)", "art. 30", RGPD, "potencial"),
    ("datos", "Contratos de encargado del tratamiento con proveedores que acceden a datos (hosting, email, pasarela…)", "RGPD (Reglamento UE 2016/679)", "art. 28", RGPD, "confirmada"),
    ("datos", "Valorar si es obligatorio designar Delegado de Protección de Datos", "LOPDGDD (LO 3/2018)", "art. 34", LOPDGDD, "asesoramiento"),
    ("datos", "Medidas de seguridad adecuadas al riesgo y gestión de brechas", "RGPD (Reglamento UE 2016/679)", "arts. 32-34", RGPD, "confirmada"),
]
_SALES = [
    ("consumo", "Información precontractual en contratos a distancia (precio total, gastos de envío, plazos, desistimiento)", "TRLGDCU (RDL 1/2007)", "art. 97", TRLGDCU, "confirmada"),
    ("consumo", "Derecho de desistimiento y formulario de desistimiento", "TRLGDCU (RDL 1/2007)", "arts. 102-108", TRLGDCU, "confirmada"),
    ("contratacion", "Información previa a la contratación electrónica y confirmación de la aceptación", "LSSI-CE (Ley 34/2002)", "arts. 27-28", LSSI, "confirmada"),
    ("contratacion", "Condiciones generales accesibles, claras y aceptadas antes de contratar", "Ley 7/1998 de Condiciones Generales de la Contratación", "art. 5", LCGC, "confirmada"),
    ("consumo", "Garantía legal de los productos y servicios posventa", "TRLGDCU (RDL 1/2007)", "", TRLGDCU, "confirmada"),
    ("consumo", "Hojas de reclamaciones / sistema de reclamaciones según normativa autonómica (en Cataluña, Código de consumo)", "Normativa autonómica de consumo", "", None, "asesoramiento"),
]
_TAX = [
    ("fiscal", "Obligaciones de facturación e IVA de la actividad (incl. ventas a otros países de la UE)", "Ley General Tributaria (Ley 58/2003) y normativa del IVA", "", LGT, "asesoramiento"),
    ("pi", "Titularidad o licencia de textos, imágenes, software y marca utilizados", "Ley de Propiedad Intelectual (RDL 1/1996)", "", LPI, "potencial"),
]


def items(profile: str) -> list[dict]:
    rows = list(_ALL_WEB)
    if profile in ("ecommerce", "saas", "autonomo"):
        rows += _SALES
    rows += _TAX
    if profile == "sociedad":
        rows.append(("mercantil", "Obligaciones societarias: libros, cuentas anuales y depósito en el Registro Mercantil",
                     "Ley de Sociedades de Capital (RDL 1/2010)", "", f"{BOE}BOE-A-2010-10544", "confirmada"))
    return [{"area": a, "obligation": o, "norm": n, "article": art, "source_url": url, "applicability": ap} for a, o, n, art, url, ap in rows]
