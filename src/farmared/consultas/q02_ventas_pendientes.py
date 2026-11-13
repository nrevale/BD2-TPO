"""q02 — Ventas en estado 'Pendiente' con el farmacéutico asignado (nombre, matrícula y sucursal) y el total.

Motor: MongoDB.
Relación entre entidades: $lookup de ventas a farmaceuticos y sucursales.

Parámetros: db: Database
Retorno: list[dict] —
    id_venta, fecha, id_cliente, total, farmaceutico {id_farmaceutico, nombre, apellido,
    matricula}, sucursal {id_sucursal, nombre}.
"""

from __future__ import annotations

from pymongo.database import Database

from farmared.consultas._comun import fechas_a_date

MOTOR = "mongo"

PIPELINE = [
    {"$match": {"estado": "Pendiente"}},
    {"$lookup": {"from": "farmaceuticos", "localField": "id_farmaceutico", "foreignField": "_id", "as": "farm"}},
    {"$unwind": "$farm"},
    {"$lookup": {"from": "sucursales", "localField": "farm.id_sucursal", "foreignField": "_id", "as": "suc"}},
    {"$unwind": "$suc"},
    {"$sort": {"fecha": 1, "_id": 1}},
    {"$project": {
        "_id": 0,
        "id_venta": "$_id",
        "fecha": "$fecha",
        "id_cliente": "$id_cliente",
        "total": "$total",
        "farmaceutico": {
            "id_farmaceutico": "$farm._id",
            "nombre": "$farm.nombre",
            "apellido": "$farm.apellido",
            "matricula": "$farm.matricula",
        },
        "sucursal": {"id_sucursal": "$suc._id", "nombre": "$suc.nombre"},
    }},
]


def ejecutar(db: Database) -> list[dict]:
    return fechas_a_date(list(db.ventas.aggregate(PIPELINE)), "fecha")
