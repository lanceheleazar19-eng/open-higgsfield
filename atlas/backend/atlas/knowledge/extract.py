"""Extracción de texto de cada tipo de documento. Todo ocurre en tu ordenador."""

import csv
import io

KINDS = {"pdf": "PDF", "docx": "Word", "txt": "Texto", "md": "Markdown", "csv": "CSV", "xlsx": "Excel",
         "image": "Imagen", "url": "Web", "note": "Nota"}
EXT = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "md", ".markdown": "md", ".csv": "csv",
       ".xlsx": "xlsx", ".xlsm": "xlsx", ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
       ".heic": "image"}


def kind_for(filename: str) -> str | None:
    name = filename.lower()
    for ext, k in EXT.items():
        if name.endswith(ext):
            return k
    return None


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract(kind: str, data: bytes) -> str:
    if kind == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for i, p in enumerate(reader.pages):
            t = (p.extract_text() or "").strip()
            if t:
                pages.append(f"[Página {i + 1}]\n{t}")
        return "\n\n".join(pages)
    if kind == "docx":
        import docx
        d = docx.Document(io.BytesIO(data))
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for t in d.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        return "\n".join(parts)
    if kind == "xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        parts = []
        for ws in wb.worksheets:
            parts.append(f"[Hoja {ws.title}]")
            for row in ws.iter_rows(values_only=True):
                vals = ["" if v is None else str(v) for v in row]
                if any(vals):
                    parts.append(" | ".join(vals))
        return "\n".join(parts)
    if kind == "csv":
        text = _decode(data)
        try:
            dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        return "\n".join(" | ".join(r) for r in csv.reader(io.StringIO(text), dialect))
    if kind in ("txt", "md", "note"):
        return _decode(data)
    raise ValueError(f"Tipo no soportado: {kind}")
