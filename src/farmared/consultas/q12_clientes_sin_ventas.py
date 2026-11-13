"""q12 — Clientes sin ventas registradas en el último año.

Motor: Neo4j. "No tiene ventas" es la ausencia de una relación: en el grafo se expresa
directamente con un subpatrón negado.
Relación entre entidades: NOT EXISTS { (c)-[:REALIZO]->(v:Venta) WHERE v.fecha >= desde AND
v.estado <> 'Anulada' } sobre el grafo. desde = hoy - 1 año (duration de Cypher, que resuelve
el 29 de febrero). ultima_compra = la venta no anulada más reciente, de cualquier fecha.
Se listan clientes activos e inactivos.

Parámetros: driver: Driver, hoy: date | None = None
Retorno: list[dict] —
    id_cliente, nombre, apellido, activo, ultima_compra (date o None). Las anuladas no cuentan.
    Orden por id_cliente.
"""

from __future__ import annotations

from datetime import date

from neo4j import Driver

from farmared.consultas._comun import hoy_o_sistema

MOTOR = "neo4j"

CYPHER = """
WITH $hoy - duration({years: 1}) AS desde
MATCH (c:Cliente)
WHERE NOT EXISTS {
    (c)-[:REALIZO]->(v:Venta) WHERE v.fecha >= desde AND v.estado <> 'Anulada'
}
OPTIONAL MATCH (c)-[:REALIZO]->(v:Venta) WHERE v.estado <> 'Anulada'
RETURN c.id AS id_cliente, c.nombre AS nombre, c.apellido AS apellido, c.activo AS activo,
       max(v.fecha) AS ultima_compra
ORDER BY id_cliente
"""


def ejecutar(driver: Driver, hoy: date | None = None) -> list[dict]:
    filas = [r.data() for r in driver.execute_query(CYPHER, hoy=hoy_o_sistema(hoy)).records]
    for f in filas:
        if f["ultima_compra"] is not None:
            f["ultima_compra"] = f["ultima_compra"].to_native()
    return filas
