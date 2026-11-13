"""q11 — Vista agregada: ingresos totales por farmacéutico en el mes actual (solo 'Completada').

Motor: MongoDB.
Relación entre entidades: Consulta la vista v_ingresos_farmaceutico_mes + $lookup a farmaceuticos.

Parámetros: db: Database, hoy: date | None = None
Retorno: list[dict] —
    id_farmaceutico, nombre, apellido, mes ('AAAA-MM'), ingresos, cantidad_ventas.
    Orden desc por ingresos.
"""

from __future__ import annotations

from datetime import date

from pymongo.database import Database

from farmared.carga.esquema import VISTA_INGRESOS
from farmared.consultas._comun import hoy_o_sistema

MOTOR = "mongo"


def pipeline(mes: str) -> list[dict]:
    return [
        {"$match": {"mes": mes}},
        {"$lookup": {"from": "farmaceuticos", "localField": "id_farmaceutico", "foreignField": "_id",
                     "as": "farm"}},
        {"$unwind": "$farm"},
        {"$sort": {"ingresos": -1, "id_farmaceutico": 1}},
        {"$project": {
            "_id": 0,
            "id_farmaceutico": "$id_farmaceutico",
            "nombre": "$farm.nombre",
            "apellido": "$farm.apellido",
            "mes": "$mes",
            "ingresos": "$ingresos",
            "cantidad_ventas": "$cantidad_ventas",
        }},
    ]


def ejecutar(db: Database, hoy: date | None = None) -> list[dict]:
    mes = hoy_o_sistema(hoy).strftime("%Y-%m")
    return list(db[VISTA_INGRESOS].aggregate(pipeline(mes)))
