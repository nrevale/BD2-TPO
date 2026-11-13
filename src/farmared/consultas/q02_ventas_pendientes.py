"""q02 — Ventas en estado 'Pendiente' con el farmacéutico asignado (nombre, matrícula y sucursal) y el total.

Motor: MongoDB.
Relación entre entidades: $lookup de ventas a farmaceuticos y sucursales.

Parámetros: db: Database
Retorno: list[dict] —
    id_venta, fecha, id_cliente, total, farmaceutico {id_farmaceutico, nombre, apellido,
    matricula}, sucursal {id_sucursal, nombre}.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from pymongo.database import Database

MOTOR = "mongo"


def ejecutar(db: Database) -> list[dict]:
    raise NotImplementedError("q02 todavía no está implementada")
