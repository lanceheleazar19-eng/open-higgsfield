"""Multi-model: proveedores, API keys (en el Llavero), enrutado por tarea, privacidad y uso."""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select

from atlas.api.deps import DB
from atlas.brain import router as mr
from atlas.brain.orchestrator import brain_status
from atlas.brain.providers import CLOUD
from atlas.integrations.secrets import delete_secret, get_secret, set_secret
from atlas.models import ModelCall
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs, set_prefs

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
def status(db: DB) -> dict:
    prefs = get_prefs(db)
    ol = brain_status(prefs)
    return {
        "config": mr.config(prefs), "tasks": mr.TASKS, "privacy_options": mr.PRIVACY,
        "providers": [{"id": "ollama", "label": "Ollama (local)", "local": True, "configured": ol["reachable"],
                       "connected": ol["reachable"], "model": ol["model"], "models": [m["name"] for m in ol["models"]],
                       "note": ol["note"]}] +
                     [{"id": p, "label": CLOUD[p].label, "local": False, "configured": mr.has_key(p), "connected": None,
                       "model": mr.config(prefs)["providers"][p]["model"] or None, "models": [],
                       "note": None if mr.has_key(p) else "Falta la API key"} for p in CLOUD],
        "routes": {t: (lambda c: f"{c[0]}:{c[1]}" if c else f"ollama:{ol['model']}" if ol["model"] else "local (sin IA)")(
            mr.cloud_choice(t, prefs)) for t in mr.TASKS},
        "month_cost_usd": round(mr.month_cost(), 4),
    }


@router.post("/{provider}/test")
def test(provider: str) -> dict:
    """Conexión REAL con el proveedor: lista sus modelos con tu key."""
    if provider not in CLOUD:
        raise HTTPException(404, "Proveedor desconocido")
    p = mr.make_cloud(provider)
    if not p:
        raise HTTPException(422, "Primero guarda la API key")
    st = p.status()
    return {"connected": st.reachable, "error": st.error, "models": [m.name for m in st.models][:200]}


class KeyIn(BaseModel):
    api_key: str = Field(min_length=10, max_length=500)


@router.put("/{provider}/key")
def save_key(provider: str, body: KeyIn, db: DB) -> dict:
    if provider not in CLOUD:
        raise HTTPException(404, "Proveedor desconocido")
    where = set_secret(f"{provider}_api_key", body.api_key.strip())
    log_activity(db, "security", "secret_set", f"API key de {provider} guardada ({'Llavero' if where == 'keychain' else 'archivo protegido'})")
    db.commit()
    return {"configured": True, "stored_in": where}


@router.delete("/{provider}/key", status_code=204)
def remove_key(provider: str, db: DB) -> None:
    if provider not in CLOUD:
        raise HTTPException(404, "Proveedor desconocido")
    delete_secret(f"{provider}_api_key")
    log_activity(db, "security", "secret_deleted", f"API key de {provider} eliminada")
    db.commit()


class ConfigIn(BaseModel):
    privacy: str | None = Field(default=None, pattern="^(local_only|local_first|best_quality)$")
    tasks: dict[str, dict] | None = None
    providers: dict[str, dict] | None = None
    prices: dict[str, dict] | None = None
    monthly_limit_usd: float | None = Field(default=None, ge=0)
    clear_limit: bool = False


@router.put("/config")
def put_config(body: ConfigIn, db: DB) -> dict:
    prefs = get_prefs(db)
    c = mr.config(prefs)
    if body.privacy:
        c["privacy"] = body.privacy
    for t, v in (body.tasks or {}).items():
        if t in mr.TASKS and str(v.get("provider", "auto")) in ("auto", "ollama", *CLOUD):
            c["tasks"][t] = {"provider": v.get("provider", "auto"), "model": str(v.get("model") or "")[:120]}
    for p, v in (body.providers or {}).items():
        if p in CLOUD:
            c["providers"][p] = {"model": str(v.get("model") or "")[:120]}
    if body.prices is not None:
        c["prices"] = {k: {"in": float(v.get("in", 0)), "out": float(v.get("out", 0))} for k, v in body.prices.items()}
    if body.monthly_limit_usd is not None:
        c["monthly_limit_usd"] = body.monthly_limit_usd
    if body.clear_limit:
        c["monthly_limit_usd"] = None
    set_prefs(db, {"model_router": c})
    log_activity(db, "security", "settings", f"Model Router actualizado (privacidad: {c['privacy']})")
    db.commit()
    return c


@router.get("/usage")
def usage(db: DB, days: int = 30) -> dict:
    since = datetime.utcnow() - timedelta(days=min(days, 365))
    rows = db.execute(select(ModelCall.provider, ModelCall.model, func.count(ModelCall.id), func.avg(ModelCall.latency_ms),
                             func.sum(case((ModelCall.ok.is_(False), 1), else_=0)),
                             func.sum(ModelCall.cost_usd), func.sum(ModelCall.tokens_in), func.sum(ModelCall.tokens_out))
                      .where(ModelCall.created_at >= since).group_by(ModelCall.provider, ModelCall.model)).all()
    recent = db.scalars(select(ModelCall).order_by(ModelCall.id.desc()).limit(25))
    return {
        "by_model": [{"provider": p, "model": m, "calls": n, "avg_ms": round(a or 0), "errors": int(e or 0),
                      "cost_usd": round(c, 4) if c is not None else None, "tokens_in": ti, "tokens_out": to}
                     for p, m, n, a, e, c, ti, to in rows],
        "recent": [{"provider": c.provider, "model": c.model, "task": c.task, "ok": c.ok, "error": c.error,
                    "latency_ms": c.latency_ms, "cost_usd": c.cost_usd, "created_at": c.created_at.isoformat()} for c in recent],
    }
