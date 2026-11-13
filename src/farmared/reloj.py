"""Fecha "de hoy" del sistema.

Toda consulta que dependa de la fecha actual ("hoy", "mes actual", "últimos 60 días",
"último año") la obtiene de `hoy()`. Nunca se usan fechas fijas en el código.

- Por defecto es la fecha actual en Buenos Aires.
- La variable de entorno `FARMARED_HOY=AAAA-MM-DD` la fija, para tests y demos reproducibles.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def hoy() -> date:
    """Devuelve la fecha comercial actual (o la fijada con FARMARED_HOY)."""
    fijo = os.environ.get("FARMARED_HOY", "").strip()
    if fijo:
        return date.fromisoformat(fijo)
    return datetime.now(ZONA).date()


def a_datetime(d: date) -> datetime:
    """Convierte una fecha comercial a datetime de medianoche (así se guarda como BSON Date)."""
    return datetime(d.year, d.month, d.day)


def inicio_mes(d: date) -> date:
    return d.replace(day=1)


def inicio_mes_siguiente(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)
