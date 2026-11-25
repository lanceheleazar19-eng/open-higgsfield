"""VISTAN Trading Agent: tutor educativo. Solo usa los datos reales que se le pasan; nunca ejecuta operaciones."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.desk import analytics, engine, indicators
from atlas.desk import market as mk
from atlas.models import TdAccount, TdJournal, TdOrder, TdPosition

SYSTEM = """Eres el VISTAN Trading Agent, un tutor de trading para principiantes dentro de una plataforma de PAPER TRADING
(dinero VIRTUAL). Reglas:
- Explica de forma educativa, clara y en español, con ejemplos sencillos. Define los términos técnicos la primera vez.
- Usa SOLO los datos del bloque CONTEXTO (cotizaciones, indicadores calculados, cuenta, posiciones, historial, diario,
  estadísticas y límites de riesgo). Si un dato no está, dilo («no tengo ese dato»). Nunca inventes precios ni cifras.
- Indica el tipo de dato (tiempo real, con retraso, histórico) cuando hables de precios.
- Puedes plantear escenarios alcistas y bajistas con lo que los invalidaría, pero NUNCA presentes una predicción como
  certeza ni prometas resultados. Recuerda que el pasado no garantiza el futuro.
- Revisa la gestión del riesgo: tamaño de posición, stop loss, relación riesgo/beneficio, límites de la cuenta.
- No ejecutas operaciones: si el usuario quiere operar, explícale cómo hacerlo él mismo en el ticket de órdenes.
- Todo es simulación; no des asesoramiento financiero personalizado para dinero real.
- Responde en Markdown sencillo, con frases cortas y como máximo unos 250-350 palabras salvo que pidan más."""


def _pos(p: TdPosition) -> dict:
    return {"id": p.id, "activo": p.symbol, "lado": p.side, "cantidad": p.qty, "entrada": p.entry_price, "sl": p.sl, "tp": p.tp,
            "estado": p.status, "salida": p.exit_price, "pnl_realizado": p.realized_pnl, "motivo_salida": p.exit_reason,
            "riesgo_dinero": p.risk_money, "estrategia": p.strategy, "temporalidad": p.timeframe,
            "abierta": p.opened_at.isoformat(timespec="minutes"), "cerrada": p.closed_at.isoformat(timespec="minutes") if p.closed_at else None}


def context(db: Session, acc: TdAccount, symbol: str | None, timeframe: str | None, day_start_utc: datetime) -> dict:
    st = engine.account_state(db, acc)
    opens = list(db.scalars(select(TdPosition).where(TdPosition.account_id == acc.id, TdPosition.status == "open")))
    closed = list(db.scalars(select(TdPosition).where(TdPosition.account_id == acc.id, TdPosition.status == "closed")
                             .order_by(TdPosition.closed_at.desc()).limit(15)))
    ids = [p.id for p in closed]
    journal = [{"posicion": j.position_id, "motivo_entrada": j.entry_reason, "estrategia": j.strategy, "emocion": j.emotion,
                "motivo_salida": j.exit_reason, "errores": j.mistakes, "lecciones": j.lessons}
               for j in db.scalars(select(TdJournal).where(TdJournal.position_id.in_(ids)))] if ids else []
    s = analytics.stats(db, acc)
    ctx: dict = {
        "aviso": "PAPER TRADING: todo es dinero virtual",
        "cuenta": {"nombre": acc.name, "tipo": acc.kind, "divisa": acc.currency, "capital_inicial": acc.initial_capital,
                   "equity": st["equity"], "efectivo": st["cash"], "capital_en_uso": st["used"], "pnl_no_realizado": st["unrealized"],
                   "rentabilidad_pct": st["return_pct"], "exposicion_pct": st["exposure_pct"],
                   "drawdown": engine.drawdown(db, acc, st["equity"]),
                   "limites": {"riesgo_max_por_operacion_pct": acc.max_risk_pct, "perdida_diaria_max_pct": acc.max_daily_loss_pct,
                               "drawdown_max_pct": acc.max_drawdown_pct, "exposicion_max_pct": acc.max_exposure_pct,
                               "stop_obligatorio": acc.require_stop, "bloquea_si_se_supera": acc.enforce_limits},
                   "alertas_activas": engine.check_limits(db, acc, day_start_utc)},
        "posiciones_abiertas": [_pos(p) | {"pnl_no_realizado": st["values"].get(p.id, {}).get("unrealized")} for p in opens],
        "ordenes_pendientes": [{"activo": o.symbol, "tipo": o.type, "lado": o.side, "cantidad": o.qty, "limite": o.limit_price,
                                "stop": o.stop_price} for o in db.scalars(select(TdOrder).where(TdOrder.account_id == acc.id, TdOrder.status == "pending"))],
        "ultimas_operaciones_cerradas": [_pos(p) for p in closed],
        "diario": journal,
        "estadisticas": {k: v for k, v in s.items() if k not in ("curve", "equity_series")},
        "patrones_del_diario": analytics.journal_patterns(db, acc),
    }
    if symbol:
        inst = mk.instruments(db).get(symbol)
        if inst:
            q = mk.quote(inst)
            ctx["activo"] = {"simbolo": inst.symbol, "nombre": inst.name, "clase": mk.CLASSES.get(inst.cls), "divisa": inst.ccy,
                             "precio": q.get("price"), "cambio_pct": q.get("change_pct"), "tipo_dato": mk.KIND_LABEL.get(q.get("kind") or "none"),
                             "fuente": q.get("source"), "error": q.get("error")}
            tf = timeframe or "1d"
            cd = mk.candles(inst, tf, 300)
            ctx["indicadores"] = {"temporalidad": tf, "fuente": cd.get("source"), **indicators.snapshot(cd["candles"])} if cd["candles"] \
                else {"temporalidad": tf, "error": cd.get("error") or "sin velas"}
    return ctx


def ask(db: Session, prefs: dict, acc: TdAccount, question: str, symbol: str | None, timeframe: str | None,
        day_start_utc: datetime, history: list[dict] | None = None) -> dict:
    from atlas.brain import router
    ctx = context(db, acc, symbol, timeframe, day_start_utc)
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "system", "content": "CONTEXTO (datos reales de VISTAN):\n" + json.dumps(ctx, ensure_ascii=False, default=str)[:14000]}]
    for h in (history or [])[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:2000]})
    msgs.append({"role": "user", "content": question})
    text, model = router.complete_text("chat", prefs, msgs)
    return {"answer": text.strip(), "model": model, "used": sorted(k for k in ctx if k != "aviso")}
