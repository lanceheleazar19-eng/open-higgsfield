"""Interpretación de lenguaje natural en español para crear tareas.

«Apúntame llamar al gestor el viernes a las 10, es urgente» →
título «Llamar al gestor», vence el próximo viernes 10:00, prioridad crítica.
Determinista (sin IA): funciona aunque no haya modelo y es fácil de probar.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

A = "[aá]"
E = "[eé]"
N = "[nñ]"
WEEKDAYS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
          "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
NUM_WORDS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
             "ocho": 8, "nueve": 9, "diez": 10, "quince": 15, "veinte": 20}
WD_RX = rf"lunes|martes|mi{E}rcoles|jueves|viernes|s{A}bado|domingo"

I = "[ií]"
TASK_TRIGGER = re.compile(
    rf"^(?:oye\s+)?(?:(?:atlas|vistan|bistan)[,:\s]+)?(?:por favor[,\s]+)?"
    rf"(?P<trig>ap[uú]ntame|an[oó]tame|apunta (?:una )?tarea|a{N}ade (?:una )?tarea|a{N}ade|crea (?:una )?tarea|"
    rf"nueva tarea|recu{E}rdame|av{I}same|ponme (?:una tarea|un recordatorio)|pon (?:una tarea|un recordatorio))"
    rf"(?:\s+(?:de|para|que|a|:))?[\s:,]+(?P<body>.{{2,}})$",
    re.IGNORECASE | re.DOTALL,
)
COMPLETE_TRIGGER = re.compile(
    rf"^(?:(?:atlas|vistan|bistan)[,:\s]+)?(?:ya\s+)?(?:he terminado|he acabado|he hecho|ya est{A}|marca como hecha|marca como completada|"
    rf"completa|termina|tacha)(?:\s+la tarea)?(?:\s+de)?[\s:,]+(?P<body>.{{2,}})$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class ParsedTask:
    title: str
    due: datetime | None = None  # hora local (sin zona)
    all_day: bool = False
    priority: str = "medium"
    category: str | None = None
    reminder: bool = False


def _wd(name: str) -> int:
    import unicodedata
    n = "".join(c for c in unicodedata.normalize("NFD", name.lower()) if unicodedata.category(c) != "Mn")
    return WEEKDAYS[n]


def _num(s: str) -> int:
    return int(s) if s.isdigit() else NUM_WORDS[s.lower()]


def parse_task_text(text: str, now: datetime) -> ParsedTask:
    """`now`: hora local actual. Devuelve título limpio + fecha/hora/prioridad/categoría."""
    t = " " + text.strip().rstrip(".!") + " "
    today = now.date()
    day: date | None = None
    hm: tuple[int, int] | None = None
    priority = "medium"
    category = None

    def cut(rx: str, fn=None) -> bool:
        nonlocal t
        m = re.search(rx, t, re.IGNORECASE)
        if not m:
            return False
        if fn:
            fn(m)
        t = t[: m.start()] + " " + t[m.end():]
        return True

    # categoría (#trabajo) y prioridad
    def set_cat(m):
        nonlocal category
        category = m.group(1).lower()
    cut(r"\s#([\wáéíóúñ-]+)", set_cat)

    def set_prio(p):
        def f(_m):
            nonlocal priority
            priority = p
        return f
    (cut(r"[,\s]+(?:que\s+)?(?:es\s+)?(?:muy\s+)?(urgent[ií]simo|urgente|cr[ií]tic[oa])\b", set_prio("critical"))
     or cut(r"[,\s]+(?:es\s+)?(?:muy\s+)?importante\b|\s!alta\b|[,\s]+prioridad alta\b", set_prio("high"))
     or cut(r"[,\s]+(?:sin prisa|cuando pueda|prioridad baja)\b|\s!baja\b", set_prio("low")))

    # hora
    def set_time(m):
        nonlocal hm
        h, mi = int(m.group("h")), int(m.group("m") or 0)
        part = (m.group("part") or "").lower()
        if ("tarde" in part or "noche" in part) and h < 12:
            h += 12
        elif not part and 1 <= h <= 7:
            h += 12  # «a las 5» casi siempre significa 17:00
        hm = (h % 24, mi)
    time_rx = (rf"\s(?:a\s+las?|sobre\s+las?|para\s+las?)\s+(?P<h>\d{{1,2}})(?:[:.h](?P<m>\d{{2}}))?(?:\s*(?:h\b|horas\b))?"
               rf"(?:\s+de\s+la\s+(?P<part>ma{N}ana|tarde|noche|madrugada))?")
    if not cut(time_rx, set_time):
        cut(r"\s(?P<h>\d{1,2})[:.](?P<m>\d{2})(?P<part>)\s", set_time)
    part_map = {rf"\s(?:por|de)\s+la\s+ma{N}ana\b": (9, 0), r"\s(?:por|de)\s+la\s+tarde\b": (17, 0),
                r"\s(?:por|de)\s+la\s+noche\b": (21, 0), rf"\sa\s+mediod{'[ií]'}a\b": (13, 0)}
    if hm is None:
        for rx, val in part_map.items():
            if cut(rx, lambda m, v=val: None):
                hm = val
                break

    # fecha
    def set_day(d):
        nonlocal day
        day = d

    def weekday(m):
        target = _wd(m.group("wd"))
        delta = (target - today.weekday()) % 7
        if delta == 0 and (m.group("next") or (hm and (hm[0], hm[1]) <= (now.hour, now.minute))):
            delta = 7
        set_day(today + timedelta(days=delta))

    def date_words(m):
        d, mon = int(m.group("d")), MONTHS[m.group("mon").lower().replace("é", "e")]
        y = int(m.group("y")) if m.group("y") else today.year
        cand = date(y, mon, d)
        if not m.group("y") and cand < today:
            cand = date(y + 1, mon, d)
        set_day(cand)

    def date_nums(m):
        d, mon = int(m.group("d")), int(m.group("mo"))
        y = m.group("y")
        yy = (int(y) + 2000 if y and len(y) == 2 else int(y)) if y else today.year
        cand = date(yy, mon, d)
        if not y and cand < today:
            cand = date(yy + 1, mon, d)
        set_day(cand)

    _ = (cut(rf"\spasado\s+ma{N}ana\b", lambda m: set_day(today + timedelta(days=2)))
         or cut(r"\s(?:para\s+)?hoy\b", lambda m: set_day(today))
         or cut(r"\sesta\s+tarde\b", lambda m: (set_day(today), None))
         or cut(rf"\s(?:para\s+)?(?<!la\s)ma{N}ana\b(?!\s+por)", lambda m: set_day(today + timedelta(days=1)))
         or cut(rf"\s(?:el\s+|del\s+|este\s+|para\s+el\s+|el\s+pr{'[oó]'}ximo\s+)?(?P<wd>{WD_RX})(?P<next>\s+que\s+viene|\s+pr{'[oó]'}ximo)?\b", weekday)
         or cut(rf"\s(?:el\s+)?(?:d{'[ií]'}a\s+)?(?P<d>\d{{1,2}})\s+de\s+(?P<mon>{'|'.join(MONTHS)})(?:\s+de\s+(?P<y>\d{{4}}))?\b", date_words)
         or cut(r"\s(?:el\s+)?(?P<d>\d{1,2})/(?P<mo>\d{1,2})(?:/(?P<y>\d{2,4}))?\b", date_nums)
         or cut(r"\s(?:en|dentro\s+de)\s+(?P<n>\d+|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|quince|veinte)\s+d[ií]as?\b",
                lambda m: set_day(today + timedelta(days=_num(m.group("n")))))
         or cut(r"\s(?:en|dentro\s+de)\s+(?P<n>\d+|un|una|dos|tres|cuatro)\s+semanas?\b",
                lambda m: set_day(today + timedelta(weeks=_num(m.group("n")))))
         or cut(rf"\s(?:la\s+)?(?:semana\s+que\s+viene|pr{'[oó]'}xima\s+semana)\b",
                lambda m: set_day(today + timedelta(days=7 - today.weekday())))
         or cut(r"\s(?:este\s+)?fin\s+de\s+semana\b", lambda m: set_day(today + timedelta(days=(5 - today.weekday()) % 7))))
    if re.search(r"\sesta\s+tarde\b", text, re.IGNORECASE) and hm is None:
        hm = (17, 0)
    if re.search(r"\sesta\s+noche\b", text, re.IGNORECASE):
        cut(r"\sesta\s+noche\b")
        day = day or today
        hm = hm or (21, 0)

    due, all_day = None, False
    if day and hm:
        due = datetime.combine(day, time(*hm))
    elif day:
        due, all_day = datetime.combine(day, time(23, 59, 59)), True
    elif hm:
        cand = datetime.combine(today, time(*hm))
        due = cand if cand > now else cand + timedelta(days=1)

    title = re.sub(r"\s+", " ", t).strip(" ,.;:-")
    title = re.sub(r"^(?:que\s+|de\s+|para\s+|a\s+)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+(?:el|para|a|de|y|,)$", "", title, flags=re.IGNORECASE).strip(" ,.;:-")
    if title:
        title = title[0].upper() + title[1:]
    return ParsedTask(title=title or text.strip(), due=due, all_day=all_day, priority=priority, category=category)


def parse_task_command(text: str, now: datetime) -> ParsedTask | None:
    """Si el mensaje pide crear una tarea o recordatorio, la interpreta."""
    m = TASK_TRIGGER.match(text.strip())
    if not m:
        return None
    p = parse_task_text(m.group("body"), now)
    trig = m.group("trig").lower()
    p.reminder = trig.startswith(("rec", "av", "ponme un rec", "pon un rec")) or (p.due is not None and not p.all_day)
    return p


def parse_complete_command(text: str) -> str | None:
    m = COMPLETE_TRIGGER.match(text.strip().rstrip(".!"))
    return m.group("body").strip() if m else None
