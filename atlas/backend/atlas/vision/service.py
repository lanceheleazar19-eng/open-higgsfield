"""Análisis de imágenes privadas. Por defecto TODO es local (modelo de visión de Ollama). Una foto solo sale
de tu ordenador si eliges un proveedor en la nube para la tarea «Imágenes» Y das tu consentimiento en esa petición."""

import base64
import io
import time

from PIL import Image

from atlas.brain import router
from atlas.brain.base import ProviderError
from atlas.brain.providers import CLOUD, IMAGE_JSON


class NeedsConsent(Exception):
    def __init__(self, provider: str, model: str):
        super().__init__(f"La imagen se enviaría a {CLOUD[provider].label} ({model}). Necesito tu consentimiento.")
        self.provider, self.model = provider, model


def route(prefs: dict) -> dict:
    """Quién procesaría una imagen ahora mismo (para mostrarlo ANTES de analizar)."""
    from atlas.brain.orchestrator import get_provider
    from atlas.nutrition.service import pick_vision_model
    choice = router.cloud_choice("vision", prefs)
    if choice:
        return {"provider": choice[0], "label": CLOUD[choice[0]].label, "model": choice[1], "local": False, "available": True,
                "note": f"Las fotos se enviarían a {CLOUD[choice[0]].label}; te pediré permiso cada vez."}
    st = get_provider().status()
    model = pick_vision_model(st.models) if st.reachable else None
    return {"provider": "ollama", "label": "Ollama (en tu Mac)", "model": model, "local": True, "available": bool(model),
            "note": None if model else ("Instala un modelo de visión: ollama pull qwen2.5vl:7b" if st.reachable
                                        else "Ollama no está abierto: ábrelo para analizar fotos")}


def to_b64_jpeg(path_or_bytes, max_side: int = 1280) -> str:  # noqa: ANN001
    img = Image.open(path_or_bytes if not isinstance(path_or_bytes, bytes) else io.BytesIO(path_or_bytes)).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def analyze(prefs: dict, system: str, text: str, images: list[str], allow_cloud: bool = False) -> tuple[dict, str, str]:
    """(json, 'proveedor:modelo', proveedor). Lanza NeedsConsent o ProviderError."""
    r = route(prefs)
    t0 = time.perf_counter()
    if not r["local"]:
        if not allow_cloud:
            raise NeedsConsent(r["provider"], r["model"])
        p = router.make_cloud(r["provider"])
        if not p:
            raise ProviderError("Falta la API key del proveedor elegido")
        try:
            data = IMAGE_JSON[r["provider"]](p, r["model"], system, text, images)
        except ProviderError as exc:
            router.record(r["provider"], r["model"], "vision", t0, False, str(exc), prefs=prefs)
            raise
        router.record(r["provider"], r["model"], "vision", t0, True, prefs=prefs)
        return data, f"{r['provider']}:{r['model']}", r["provider"]
    if not r["available"]:
        raise ProviderError(r["note"])
    from atlas.brain.orchestrator import get_provider
    prov = get_provider()
    try:
        data = prov.complete_json(r["model"], [{"role": "system", "content": system},
                                               {"role": "user", "content": text, "images": images}])
    except ProviderError as exc:
        router.record("ollama", r["model"], "vision", t0, False, str(exc), prefs=prefs)
        raise
    router.record("ollama", r["model"], "vision", t0, True, prefs=prefs)
    if not isinstance(data, dict):
        raise ProviderError("Respuesta inválida del modelo de visión")
    return data, f"ollama:{r['model']}", "ollama"
