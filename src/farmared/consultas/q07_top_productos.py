"""q07 — Top 5 productos más vendidos (unidades), considerando solo ventas 'Completada'.

Motor: MongoDB.
Relación entre entidades: $unwind de los ítems embebidos + $group + $lookup a productos.

Parámetros: db: Database
Retorno: list[dict] —
    id_producto, nombre, unidades_vendidas (5 filas). Empate: por id_producto.
"""

from __future__ import annotations

from pymongo.database import Database

MOTOR = "mongo"
CANTIDAD = 5

PIPELINE = [
    {"$match": {"estado": "Completada"}},
    {"$unwind": "$items"},
    {"$group": {"_id": "$items.id_producto", "unidades_vendidas": {"$sum": "$items.cantidad"}}},
    {"$sort": {"unidades_vendidas": -1, "_id": 1}},  # desempate estable por id
    {"$limit": CANTIDAD},
    {"$lookup": {"from": "productos", "localField": "_id", "foreignField": "_id", "as": "producto"}},
    {"$unwind": "$producto"},
    {"$project": {
        "_id": 0,
        "id_producto": "$_id",
        "nombre": "$producto.nombre",
        "unidades_vendidas": "$unidades_vendidas",
    }},
]


def ejecutar(db: Database) -> list[dict]:
    return list(db.ventas.aggregate(PIPELINE))
