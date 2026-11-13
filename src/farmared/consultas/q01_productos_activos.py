"""q01 — Productos activos con todos los datos de su proveedor.

Motor: MongoDB.
Relación entre entidades: $lookup de productos a proveedores (referencia).

Parámetros: db: Database
Retorno: list[dict] —
    Por producto activo: id_producto, nombre, principio_activo, categoria, presentacion,
    condicion_venta, precio_unit y proveedor {id_proveedor, razon_social, cuit, tipo, ciudad,
    provincia, telefono, activo}. Orden por id_producto.
"""

from __future__ import annotations

from pymongo.database import Database

MOTOR = "mongo"

PIPELINE = [
    {"$match": {"activo": True}},
    {"$lookup": {"from": "proveedores", "localField": "id_proveedor", "foreignField": "_id", "as": "proveedor"}},
    {"$unwind": "$proveedor"},
    {"$sort": {"_id": 1}},
    {"$project": {
        "_id": 0,
        "id_producto": "$_id",
        "nombre": "$nombre",
        "principio_activo": "$principio_activo",
        "categoria": "$categoria",
        "presentacion": "$presentacion",
        "condicion_venta": "$condicion_venta",
        "precio_unit": "$precio_unit",
        "proveedor": {
            "id_proveedor": "$proveedor._id",
            "razon_social": "$proveedor.razon_social",
            "cuit": "$proveedor.cuit",
            "tipo": "$proveedor.tipo",
            "ciudad": "$proveedor.ciudad",
            "provincia": "$proveedor.provincia",
            "telefono": "$proveedor.telefono",
            "activo": "$proveedor.activo",
        },
    }},
]


def ejecutar(db: Database) -> list[dict]:
    return list(db.productos.aggregate(PIPELINE))
