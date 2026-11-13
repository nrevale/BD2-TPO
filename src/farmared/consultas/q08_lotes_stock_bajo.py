"""q08 — Lotes con menos de 50 unidades, indicando producto, sucursal y proveedor.

Motor: MongoDB.
Relación entre entidades: $lookup de stock_lotes a productos -> proveedores y a sucursales.

Parámetros: db: Database, hoy: date | None = None
Retorno: list[dict] —
    id_lote, nro_lote, unidades, vencimiento, vencido (vencimiento < hoy), producto {id_producto,
    nombre}, sucursal {id_sucursal, nombre, tipo}, proveedor {id_proveedor, razon_social}.
    Orden: unidades ascendente (los más críticos primero).
"""

from __future__ import annotations

from datetime import date

from pymongo.database import Database

from farmared import reloj
from farmared.consultas._comun import fechas_a_date, hoy_o_sistema

MOTOR = "mongo"
UMBRAL = 50


def pipeline(hoy: date) -> list[dict]:
    return [
        {"$match": {"unidades": {"$lt": UMBRAL}}},
        {"$lookup": {"from": "productos", "localField": "id_producto", "foreignField": "_id", "as": "producto"}},
        {"$unwind": "$producto"},
        {"$lookup": {"from": "proveedores", "localField": "producto.id_proveedor", "foreignField": "_id",
                     "as": "proveedor"}},
        {"$unwind": "$proveedor"},
        {"$lookup": {"from": "sucursales", "localField": "id_sucursal", "foreignField": "_id", "as": "sucursal"}},
        {"$unwind": "$sucursal"},
        {"$sort": {"unidades": 1, "_id": 1}},
        {"$project": {
            "_id": 0,
            "id_lote": "$_id",
            "nro_lote": "$nro_lote",
            "unidades": "$unidades",
            "vencimiento": "$vencimiento",
            "vencido": {"$lt": ["$vencimiento", reloj.a_datetime(hoy)]},
            "producto": {"id_producto": "$producto._id", "nombre": "$producto.nombre"},
            "sucursal": {"id_sucursal": "$sucursal._id", "nombre": "$sucursal.nombre", "tipo": "$sucursal.tipo"},
            "proveedor": {"id_proveedor": "$proveedor._id", "razon_social": "$proveedor.razon_social"},
        }},
    ]


def ejecutar(db: Database, hoy: date | None = None) -> list[dict]:
    filas = list(db.stock_lotes.aggregate(pipeline(hoy_o_sistema(hoy))))
    return fechas_a_date(filas, "vencimiento")
