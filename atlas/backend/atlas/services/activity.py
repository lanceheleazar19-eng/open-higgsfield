from sqlalchemy.orm import Session

from atlas.models import ActivityLog


def log_activity(db: Session, module: str, action: str, summary: str) -> ActivityLog:
    entry = ActivityLog(module=module, action=action, summary=summary)
    db.add(entry)
    return entry
