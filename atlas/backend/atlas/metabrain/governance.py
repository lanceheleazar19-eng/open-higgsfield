"""Seguridad y gobierno del META-BRAIN: kill switch, límites de recursos, permisos por agente y privacidad.
Todo se guarda en tus preferencias (tabla settings) y se aplica en cada fase de cada ejecución."""

from __future__ import annotations

from atlas.agents.registry import AGENTS

DEFAULT_META = {
    "kill": False,  # kill switch: detiene META-BRAIN, automatizaciones, Arena, investigaciones y sandbox
    "limits": {"max_calls": 12, "max_seconds": 600, "max_cost_usd": None},
    "council_size": 3,  # especialistas como máximo en el consejo
    "diverse_models": True,  # si hay varios modelos configurados, reparte especialistas entre ellos
    "allow_cloud_personal": False,  # datos personales (salud, dinero, vida privada) solo con modelos locales
    "auto_research": True,  # el crítico puede pedir una investigación nueva si detecta falta de evidencia
}
# Agentes que manejan datos personales sensibles: por defecto sus datos nunca salen a la nube
SENSITIVE = {"finance", "fitness", "discipline", "decision", "communication", "leadership", "memory"}


def meta_conf(prefs: dict) -> dict:
    m = prefs.get("meta") or {}
    out = {**DEFAULT_META, **{k: v for k, v in m.items() if k in DEFAULT_META}}
    out["limits"] = {**DEFAULT_META["limits"], **(m.get("limits") or {})}
    return out


def killed(prefs: dict) -> bool:
    return bool(meta_conf(prefs)["kill"])


def kill_switch_on(db) -> bool:  # noqa: ANN001
    from atlas.services.preferences import get_prefs
    return killed(get_prefs(db))


def agent_perms(prefs: dict) -> dict[str, dict]:
    saved = prefs.get("agent_perms") or {}
    return {a: {"enabled": True, "memory": True, "cloud": a not in SENSITIVE, **(saved.get(a) or {})} for a in AGENTS}


def allowed_agents(prefs: dict, ids: list[str]) -> list[str]:
    p = agent_perms(prefs)
    return [a for a in ids if a in p and p[a]["enabled"]]


def needs_local(prefs: dict, agents: list[str], personal: bool) -> tuple[bool, str | None]:
    """¿Debe esta petición quedarse en modelos locales? Devuelve (sí/no, motivo)."""
    conf = meta_conf(prefs)
    p = agent_perms(prefs)
    blocked = [AGENTS[a].name for a in agents if a in p and not p[a]["cloud"]]
    if blocked:
        return True, f"datos de {', '.join(blocked)} (sin permiso de nube)"
    if personal and not conf["allow_cloud_personal"]:
        return True, "la petición contiene datos personales"
    return False, None
