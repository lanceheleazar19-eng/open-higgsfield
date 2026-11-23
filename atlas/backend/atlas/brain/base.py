"""Interfaz común de proveedores de IA. Añadir un proveedor = implementar esta clase."""

from collections.abc import Iterator
from dataclasses import dataclass, field


class ProviderError(Exception):
    """Fallo del proveedor (no disponible, modelo inexistente, error de la API)."""


@dataclass
class ModelInfo:
    name: str
    size_bytes: int = 0
    parameter_size: str | None = None
    family: str | None = None


@dataclass
class ProviderStatus:
    provider: str
    reachable: bool
    models: list[ModelInfo] = field(default_factory=list)
    error: str | None = None


class LLMProvider:
    name: str = "base"

    def status(self) -> ProviderStatus:  # pragma: no cover - interfaz
        raise NotImplementedError

    def chat_stream(self, model: str, messages: list[dict]) -> Iterator[str]:  # pragma: no cover
        """Genera fragmentos de texto de la respuesta. `messages`: [{role, content}]."""
        raise NotImplementedError

    def complete_json(self, model: str, messages: list[dict]) -> dict:  # pragma: no cover
        """Respuesta completa forzada a JSON (para tareas internas como extraer recuerdos)."""
        raise NotImplementedError
