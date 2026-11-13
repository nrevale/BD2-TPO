"""q06 — Recetas de tratamiento prolongado 'Vigente' cuya próxima dispensa es anterior a hoy, con los datos del cliente.

Motor: MongoDB.
Relación entre entidades: $lookup de recetas a clientes.

Parámetros: db: Database, hoy: date | None = None
Retorno: list[dict] —
    id_receta, fecha_emision, proxima_dispensa, dispensas_realizadas, dispensas_autorizadas,
    medico, cliente {id_cliente, nombre, apellido, dni, telefono, email, obra_social}.
    Orden por proxima_dispensa.
"""

from __future__ import annotations

from datetime import date

from pymongo.database import Database

from farmared import reloj
from farmared.consultas._comun import fechas_a_date, hoy_o_sistema

MOTOR = "mongo"


def pipeline(hoy: date) -> list[dict]:
    return [
        {"$match": {
            "tipo": "Tratamiento prolongado",
            "estado": "Vigente",
            "proxima_dispensa": {"$lt": reloj.a_datetime(hoy)},
        }},
        {"$lookup": {"from": "clientes", "localField": "id_cliente", "foreignField": "_id", "as": "cliente"}},
        {"$unwind": "$cliente"},
        {"$sort": {"proxima_dispensa": 1, "_id": 1}},
        {"$project": {
            "_id": 0,
            "id_receta": "$_id",
            "fecha_emision": "$fecha_emision",
            "proxima_dispensa": "$proxima_dispensa",
            "dispensas_realizadas": "$dispensas_realizadas",
            "dispensas_autorizadas": "$dispensas_autorizadas",
            "medico": "$medico",
            "cliente": {
                "id_cliente": "$cliente._id",
                "nombre": "$cliente.nombre",
                "apellido": "$cliente.apellido",
                "dni": "$cliente.dni",
                "telefono": "$cliente.telefono",
                "email": "$cliente.email",
                "obra_social": "$cliente.obra_social",
            },
        }},
    ]


def ejecutar(db: Database, hoy: date | None = None) -> list[dict]:
    filas = list(db.recetas.aggregate(pipeline(hoy_o_sistema(hoy))))
    return fechas_a_date(filas, "fecha_emision", "proxima_dispensa")
