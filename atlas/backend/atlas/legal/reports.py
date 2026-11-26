"""Legal Report Generator: informes profesionales en PDF (fpdf2) y DOCX (python-docx) a partir de un modelo común:
portada, fecha, identificador, resumen ejecutivo, análisis, evidencias, fuentes, conclusiones, limitaciones y anexos."""

from __future__ import annotations

import io
from datetime import datetime

from atlas.legal.ai import DISCLAIMER

CRIMSON = (181, 18, 36)


def build(kind: str, title: str, ident: str, summary: str, sections: list[dict], evidence: list[str] | None = None,
          sources: list[dict] | None = None, conclusions: list[str] | None = None, limitations: list[str] | None = None,
          annexes: list[dict] | None = None) -> dict:
    return {"kind": kind, "title": title, "id": ident, "date": datetime.now().strftime("%d/%m/%Y %H:%M"), "summary": summary,
            "sections": sections, "evidence": evidence or [], "sources": sources or [], "conclusions": conclusions or [],
            "limitations": (limitations or []) + [DISCLAIMER], "annexes": annexes or []}


_MAP = str.maketrans({"€": "EUR", "“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-", "…": "...", "•": "-", "→": "->", "≠": "!=",
                      " ": " ", "º": "o", "ª": "a"})


def _l1(t: object) -> str:
    return str(t if t is not None else "").translate(_MAP).encode("latin-1", "replace").decode("latin-1")


def pdf(rep: dict) -> bytes:
    from fpdf import FPDF

    class P(FPDF):
        def footer(self) -> None:
            self.set_y(-12)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(119, 119, 119)
            self.cell(0, 8, _l1(f"VISTAN LEGAL · {rep['id']} · página {self.page_no()}"), align="C")

    p = P(format="A4")
    p.set_auto_page_break(True, 16)
    p.set_margins(18, 18, 18)
    p.add_page()
    p.set_fill_color(8, 8, 8)
    p.rect(0, 0, 210, 297, "F")
    p.set_text_color(*CRIMSON)
    p.set_font("Helvetica", "B", 12)
    p.set_xy(18, 40)
    p.cell(0, 8, "VISTAN LEGAL", new_x="LMARGIN", new_y="NEXT")
    p.set_text_color(234, 234, 234)
    p.set_font("Helvetica", "B", 22)
    p.multi_cell(0, 10, _l1(rep["title"]), new_x="LMARGIN", new_y="NEXT")
    p.ln(4)
    p.set_font("Helvetica", "", 11)
    p.set_text_color(170, 170, 170)
    for line in (rep["kind"], f"Identificador: {rep['id']}", f"Fecha: {rep['date']}", "BORRADOR / INFORMACIÓN ORIENTATIVA"):
        p.cell(0, 7, _l1(line), new_x="LMARGIN", new_y="NEXT")
    p.add_page()
    p.set_text_color(20, 20, 20)

    def h(t: str) -> None:
        p.ln(3)
        p.set_font("Helvetica", "B", 13)
        p.set_text_color(*CRIMSON)
        p.multi_cell(0, 7, _l1(t), new_x="LMARGIN", new_y="NEXT")
        p.set_text_color(20, 20, 20)
        p.set_font("Helvetica", "", 10)

    def para(t: str) -> None:
        p.set_font("Helvetica", "", 10)
        p.multi_cell(0, 5.2, _l1(t), new_x="LMARGIN", new_y="NEXT")
        p.ln(1)

    def bullets(items: list) -> None:
        for it in items:
            p.set_x(p.l_margin)
            p.multi_cell(0, 5.2, _l1(f"- {it}"), new_x="LMARGIN", new_y="NEXT")

    h("Resumen ejecutivo")
    para(rep["summary"] or "—")
    for s in rep["sections"]:
        h(s["title"])
        for t in s.get("paragraphs", []):
            para(t)
        bullets(s.get("bullets", []))
    if rep["evidence"]:
        h("Evidencias")
        bullets(rep["evidence"])
    if rep["sources"]:
        h("Fuentes")
        bullets([f"[{x.get('id', '')}] {x.get('title', '')} — {x.get('url') or 's/url'}" + (f" (consultada {x['accessed']})" if x.get("accessed") else "")
                 for x in rep["sources"]])
    if rep["conclusions"]:
        h("Conclusiones")
        bullets(rep["conclusions"])
    h("Limitaciones")
    bullets(rep["limitations"])
    for a in rep["annexes"]:
        h(f"Anexo: {a['title']}")
        para(a.get("text", ""))
    return bytes(p.output())


def docx(rep: dict) -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor
    d = Document()
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10.5)
    t = d.add_paragraph()
    r = t.add_run("VISTAN LEGAL")
    r.bold, r.font.color.rgb = True, RGBColor(*CRIMSON)
    d.add_heading(rep["title"], 0)
    for line in (rep["kind"], f"Identificador: {rep['id']}", f"Fecha: {rep['date']}", "BORRADOR / INFORMACIÓN ORIENTATIVA"):
        d.add_paragraph(line)
    d.add_page_break()
    d.add_heading("Resumen ejecutivo", 1)
    d.add_paragraph(rep["summary"] or "—")
    for s in rep["sections"]:
        d.add_heading(s["title"], 1)
        for x in s.get("paragraphs", []):
            d.add_paragraph(x)
        for b in s.get("bullets", []):
            d.add_paragraph(str(b), style="List Bullet")
    for title, items in (("Evidencias", rep["evidence"]),
                         ("Fuentes", [f"[{x.get('id', '')}] {x.get('title', '')} — {x.get('url') or 's/url'}" for x in rep["sources"]]),
                         ("Conclusiones", rep["conclusions"]), ("Limitaciones", rep["limitations"])):
        if items:
            d.add_heading(title, 1)
            for b in items:
                d.add_paragraph(str(b), style="List Bullet")
    for a in rep["annexes"]:
        d.add_heading(f"Anexo: {a['title']}", 1)
        d.add_paragraph(a.get("text", ""))
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def text_doc(title: str, content: str, fmt: str) -> bytes:
    """Exporta un borrador del Document Studio tal cual (los [[PENDIENTE]] se conservan visibles)."""
    rep = build("Borrador de documento", title, "BORRADOR", "", [{"title": "Texto", "paragraphs": content.split("\n\n")}], limitations=[])
    if fmt == "pdf":
        return pdf(rep)
    return docx(rep)
