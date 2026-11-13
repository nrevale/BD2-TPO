"""q07 — Top 5 productos más vendidos (unidades), considerando solo ventas 'Completada'.

Motor: MongoDB.
Relación entre entidades: $unwind de los ítems embebidos + $group + $lookup a productos.

Parámetros: db: Database
Retorno: list[dict] —
    id_producto, nombre, unidades_vendidas (5 filas). Empate: por id_producto.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from pymongo.database import Database

MOTOR = "mongo"


def ejecutar(db: Database) -> list[dict]:
    raise NotImplementedError("q07 todavía no está implementada")
