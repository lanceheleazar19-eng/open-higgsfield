"""Conversión entre la hora local del usuario y UTC (formato de almacenamiento)."""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo


def now_local(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz))


def local_to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def utc_naive_to_local(dt: datetime, tz: str) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz))


def local_day_bounds_utc(day: date, tz: str) -> tuple[datetime, datetime]:
    """[inicio, fin) del día local, expresado en UTC naive."""
    z = ZoneInfo(tz)
    start = datetime.combine(day, time.min, tzinfo=z)
    nxt = date.fromordinal(day.toordinal() + 1)
    end = datetime.combine(nxt, time.min, tzinfo=z)
    return local_to_utc_naive(start), local_to_utc_naive(end)


def part_of_day(hour: int) -> str:
    if 6 <= hour < 13:
        return "morning"
    if 13 <= hour < 21:
        return "afternoon"
    return "night"
