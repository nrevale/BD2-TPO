"""q12 — Clientes sin ventas registradas en el último año.

Motor: Neo4j.
Relación entre entidades: NOT EXISTS { (c)-[:REALIZO]->(v:Venta) WHERE ... } sobre el grafo.

Parámetros: driver: Driver, hoy: date | None = None
Retorno: list[dict] —
    id_cliente, nombre, apellido, activo, ultima_compra (date o None). Las anuladas no cuentan.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from datetime import date

from neo4j import Driver

MOTOR = "neo4j"


def ejecutar(driver: Driver, hoy: date | None = None) -> list[dict]:
    raise NotImplementedError("q12 todavía no está implementada")
