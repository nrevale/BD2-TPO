"""q04 — Clientes con más de una receta registrada, indicando la cantidad.

Motor: MongoDB.
Relación entre entidades: $group de recetas por id_cliente + $lookup a clientes.

Parámetros: db: Database
Retorno: list[dict] —
    id_cliente, nombre, apellido, cantidad_recetas. Orden desc por cantidad, luego id.
"""

from __future__ import annotations

from pymongo.database import Database

MOTOR = "mongo"

PIPELINE = [
    {"$group": {"_id": "$id_cliente", "cantidad_recetas": {"$sum": 1}}},
    {"$match": {"cantidad_recetas": {"$gt": 1}}},
    {"$lookup": {"from": "clientes", "localField": "_id", "foreignField": "_id", "as": "cliente"}},
    {"$unwind": "$cliente"},
    {"$sort": {"cantidad_recetas": -1, "_id": 1}},
    {"$project": {
        "_id": 0,
        "id_cliente": "$_id",
        "nombre": "$cliente.nombre",
        "apellido": "$cliente.apellido",
        "cantidad_recetas": "$cantidad_recetas",
    }},
]


def ejecutar(db: Database) -> list[dict]:
    return list(db.recetas.aggregate(PIPELINE))
