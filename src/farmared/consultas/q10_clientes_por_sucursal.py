"""q10 — Clientes atendidos en una sucursal (a través del farmacéutico que registró la venta, esté activo o no).

Motor: Neo4j. La venta no guarda la sucursal en el grafo: se llega a ella por un camino de tres
saltos, que en el grafo es un solo patrón.
Relación entre entidades: Recorrido Sucursal<-TRABAJA_EN-Farmaceutico<-ATENDIDA_POR-Venta<-REALIZO-Cliente,
con DISTINCT para no repetir clientes. No se filtra por farmacéutico activo.

Parámetros: driver: Driver, id_sucursal: str
Retorno: list[dict] —
    id_cliente, nombre, apellido, dni, activo (sin repetidos), ordenados por id_cliente.
    Sucursal inexistente: ValidacionError('SUCURSAL_INEXISTENTE').
"""

from __future__ import annotations

from neo4j import Driver

from farmared.errores import ValidacionError

MOTOR = "neo4j"

EXISTE = "MATCH (s:Sucursal {id: $id_sucursal}) RETURN s.id AS id"

CYPHER = """
MATCH (:Sucursal {id: $id_sucursal})<-[:TRABAJA_EN]-(:Farmaceutico)<-[:ATENDIDA_POR]-(:Venta)<-[:REALIZO]-(c:Cliente)
RETURN DISTINCT c.id AS id_cliente, c.nombre AS nombre, c.apellido AS apellido, c.dni AS dni, c.activo AS activo
ORDER BY id_cliente
"""


def ejecutar(driver: Driver, id_sucursal: str) -> list[dict]:
    if not driver.execute_query(EXISTE, id_sucursal=id_sucursal).records:
        raise ValidacionError("SUCURSAL_INEXISTENTE", f"no existe la sucursal {id_sucursal}")
    return [r.data() for r in driver.execute_query(CYPHER, id_sucursal=id_sucursal).records]
