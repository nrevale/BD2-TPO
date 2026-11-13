"""Utilidades compartidas por las consultas."""

from __future__ import annotations

from datetime import date, datetime

from farmared import reloj


def hoy_o_sistema(hoy: date | None) -> date:
    """El `hoy` recibido, o la fecha del sistema si no se pasó."""
    return hoy if hoy is not None else reloj.hoy()


def fechas_a_date(filas: list[dict], *campos: str) -> list[dict]:
    """Convierte a `date` los campos datetime indicados (MongoDB devuelve datetime).

    Acepta campos anidados con punto, ej. "cliente.fecha_alta".
    """
    for fila in filas:
        for campo in campos:
            *ruta, ultimo = campo.split(".")
            destino = fila
            for parte in ruta:
                destino = destino.get(parte) or {}
            valor = destino.get(ultimo)
            if isinstance(valor, datetime):
                destino[ultimo] = valor.date()
    return filas
