"""q01 — Productos activos con todos los datos de su proveedor.

Motor: MongoDB.
Relación entre entidades: $lookup de productos a proveedores (referencia).

Parámetros: db: Database
Retorno: list[dict] —
    Por producto activo: id_producto, nombre, principio_activo, categoria, presentacion,
    condicion_venta, precio_unit y proveedor {id_proveedor, razon_social, cuit, tipo, ciudad,
    provincia, telefono, activo}. Orden por id_producto.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from pymongo.database import Database

MOTOR = "mongo"


def ejecutar(db: Database) -> list[dict]:
    raise NotImplementedError("q01 todavía no está implementada")
