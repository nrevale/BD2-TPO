"""q11 — Vista agregada: ingresos totales por farmacéutico en el mes actual (solo 'Completada').

Motor: MongoDB.
Relación entre entidades: Consulta la vista v_ingresos_farmaceutico_mes + $lookup a farmaceuticos.

Parámetros: db: Database, hoy: date | None = None
Retorno: list[dict] —
    id_farmaceutico, nombre, apellido, mes ('AAAA-MM'), ingresos, cantidad_ventas.
    Orden desc por ingresos.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from datetime import date

from pymongo.database import Database

MOTOR = "mongo"


def ejecutar(db: Database, hoy: date | None = None) -> list[dict]:
    raise NotImplementedError("q11 todavía no está implementada")
