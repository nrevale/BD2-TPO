"""q09 — Ventas de tipo 'Venta libre' con total menor a $5.000 (excluyendo anuladas).

Motor: MongoDB.
Relación entre entidades: Filtro sobre ventas (sin cruces).

Parámetros: db: Database
Retorno: list[dict] —
    id_venta, fecha, id_cliente, id_farmaceutico, total, estado.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from pymongo.database import Database

MOTOR = "mongo"


def ejecutar(db: Database) -> list[dict]:
    raise NotImplementedError("q09 todavía no está implementada")
