"""q10 — Clientes atendidos en una sucursal (a través del farmacéutico que registró la venta, esté activo o no).

Motor: Neo4j.
Relación entre entidades: Recorrido Sucursal<-TRABAJA_EN-Farmaceutico<-ATENDIDA_POR-Venta<-REALIZO-Cliente.

Parámetros: driver: Driver, id_sucursal: str
Retorno: list[dict] —
    id_cliente, nombre, apellido, dni, activo (sin repetidos).
    Sucursal inexistente: ValidacionError('SUCURSAL_INEXISTENTE').

Estado: pendiente de implementar.
"""

from __future__ import annotations

from neo4j import Driver

MOTOR = "neo4j"


def ejecutar(driver: Driver, id_sucursal: str) -> list[dict]:
    raise NotImplementedError("q10 todavía no está implementada")
