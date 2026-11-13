"""q05 — Farmacéuticos activos y cantidad de ventas en los últimos 60 días (excluyendo anuladas), incluidos los que tienen cero.

Motor: Neo4j.
Relación entre entidades: OPTIONAL MATCH (f)<-[:ATENDIDA_POR]-(v:Venta): los que no tienen ventas quedan con 0.

Parámetros: driver: Driver, hoy: date | None = None
Retorno: list[dict] —
    id_farmaceutico, nombre, apellido, matricula, id_sucursal, cantidad_ventas.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from datetime import date

from neo4j import Driver

MOTOR = "neo4j"


def ejecutar(driver: Driver, hoy: date | None = None) -> list[dict]:
    raise NotImplementedError("q05 todavía no está implementada")
