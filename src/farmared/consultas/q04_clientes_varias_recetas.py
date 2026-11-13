"""q04 — Clientes con más de una receta registrada, indicando la cantidad.

Motor: MongoDB.
Relación entre entidades: $group de recetas por id_cliente + $lookup a clientes.

Parámetros: db: Database
Retorno: list[dict] —
    id_cliente, nombre, apellido, cantidad_recetas. Orden desc por cantidad, luego id.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from pymongo.database import Database

MOTOR = "mongo"


def ejecutar(db: Database) -> list[dict]:
    raise NotImplementedError("q04 todavía no está implementada")
