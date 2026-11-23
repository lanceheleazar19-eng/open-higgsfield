from fastapi import APIRouter

from atlas.api.deps import DB
from atlas.services.dashboard import build_dashboard
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: DB) -> dict:
    return build_dashboard(db, get_prefs(db))
