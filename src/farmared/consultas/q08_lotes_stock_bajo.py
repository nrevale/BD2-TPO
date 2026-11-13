"""q08 — Lotes con menos de 50 unidades, indicando producto, sucursal y proveedor.

Motor: MongoDB.
Relación entre entidades: $lookup de stock_lotes a productos -> proveedores y a sucursales.

Parámetros: db: Database, hoy: date | None = None
Retorno: list[dict] —
    id_lote, nro_lote, unidades, vencimiento, vencido (vencimiento < hoy), producto {id_producto,
    nombre}, sucursal {id_sucursal, nombre, tipo}, proveedor {id_proveedor, razon_social}.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from datetime import date

from pymongo.database import Database

MOTOR = "mongo"


def ejecutar(db: Database, hoy: date | None = None) -> list[dict]:
    raise NotImplementedError("q08 todavía no está implementada")
