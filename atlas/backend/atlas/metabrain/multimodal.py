"""Multimodal Intelligence: qué puede entender VISTAN AHORA, comprobado con los componentes reales instalados.
Cada modalidad dice qué la resuelve, si está disponible y qué falta. No se ofrece ninguna función sin comprobarla."""

from __future__ import annotations

from atlas.metabrain import llm


def matrix(prefs: dict) -> list[dict]:
    inv = llm.inventory(prefs)
    ollama = inv["providers"][0]
    local_models = ollama.get("models") or []
    text_local = [m["name"] for m in local_models if "completion" in m["capabilities"]]
    vision_local = [m["name"] for m in local_models if "vision" in m["capabilities"]]
    cloud = [p for p in inv["providers"][1:] if p["configured"]]
    any_text = bool(text_local or cloud)
    try:
        from atlas.voice import voicestudio
        vs = voicestudio.status() if hasattr(voicestudio, "status") else None
    except Exception:  # noqa: BLE001
        vs = None
    vs_ok = bool(vs and (vs.get("available") or vs.get("reachable") or vs.get("ok")))
    try:
        import docx  # noqa: F401
        docx_ok = True
    except ImportError:
        docx_ok = False
    try:
        import pypdf  # noqa: F401
        pdf_ok = True
    except ImportError:
        try:
            import fitz  # noqa: F401
            pdf_ok = True
        except ImportError:
            pdf_ok = False
    return [
        {"id": "text", "label": "Texto", "available": any_text, "via": ", ".join(text_local[:3] + [f"{p['label']} ({p['model']})" for p in cloud]) or None,
         "missing": None if any_text else "Abre Ollama (ollama pull qwen2.5:7b) o configura un proveedor en Modelos."},
        {"id": "image", "label": "Imágenes", "available": bool(vision_local), "via": ", ".join(vision_local) or None,
         "missing": None if vision_local else "Instala un modelo de visión local: ollama pull qwen2.5vl:7b. "
                                              "(Los modelos en la nube solo se usan con imágenes si los eliges expresamente para «Imágenes» en Modelos.)",
         "where": "Conocimiento (OCR/descripción al subir imágenes), físico y comidas"},
        {"id": "documents", "label": "Documentos (PDF, Word, Markdown, texto)", "available": pdf_ok or docx_ok,
         "via": ", ".join(x for x, ok in (("PDF", pdf_ok), ("Word", docx_ok), ("TXT/MD", True)) if ok),
         "missing": None if (pdf_ok and docx_ok) else "Falta una librería de extracción (pypdf / python-docx).", "where": "Conocimiento → RAG del META-BRAIN"},
        {"id": "structured", "label": "Datos estructurados (CSV, Excel, JSON)", "available": True, "via": "Extracción de Conocimiento (CSV/XLSX) y API",
         "missing": None, "where": "Conocimiento, Finanzas (importación)"},
        {"id": "technical", "label": "Archivos técnicos y código", "available": any_text, "via": "Texto plano + modelo; ejecución solo en el sandbox del Lab",
         "missing": None if any_text else "Necesita un modelo de texto.", "where": "Prototype Studio, Coding Agent"},
        {"id": "audio", "label": "Audio (voz)", "available": True,
         "via": "Reconocimiento de voz del navegador" + (" + VoiceStudio local (síntesis)" if vs_ok else ""),
         "missing": None if vs_ok else "Transcripción de archivos de audio no disponible: VISTAN no incluye un modelo de transcripción local. "
                                       "La voz en directo usa el reconocimiento del navegador; VoiceStudio (opcional) añade voz local.",
         "where": "Chat por voz"},
        {"id": "video", "label": "Vídeo", "available": False, "via": None,
         "missing": "No disponible: ningún componente instalado analiza vídeo. Se activará solo si se integra un proveedor real que lo soporte."},
    ]
