"""q05 — Farmacéuticos activos y cantidad de ventas en los últimos 60 días (excluyendo anuladas), incluidos los que tienen cero.

Motor: Neo4j. Contar ventas por farmacéutico incluyendo a los que no tienen ninguna es natural
en el grafo: OPTIONAL MATCH conserva al farmacéutico aunque no haya relación que recorrer.
Relación entre entidades: OPTIONAL MATCH (f)<-[:ATENDIDA_POR]-(v:Venta): los que no tienen
ventas quedan con 0. La sucursal sale de (f)-[:TRABAJA_EN]->(s).
Se cuentan Completada + Pendiente (todo lo que no es Anulada). desde = hoy - 60 días (inclusive).

Parámetros: driver: Driver, hoy: date | None = None
Retorno: list[dict] —
    id_farmaceutico, nombre, apellido, matricula, id_sucursal, cantidad_ventas.
    Orden: cantidad_ventas desc, luego id_farmaceutico.
"""

from __future__ import annotations

from datetime import date, timedelta

from neo4j import Driver

from farmared.consultas._comun import hoy_o_sistema

MOTOR = "neo4j"

CYPHER = """
MATCH (f:Farmaceutico {activo: true})-[:TRABAJA_EN]->(s:Sucursal)
OPTIONAL MATCH (f)<-[:ATENDIDA_POR]-(v:Venta)
    WHERE v.fecha >= $desde AND v.estado <> 'Anulada'
WITH f, s, count(v) AS cantidad_ventas
RETURN f.id AS id_farmaceutico, f.nombre AS nombre, f.apellido AS apellido,
       f.matricula AS matricula, s.id AS id_sucursal, cantidad_ventas
ORDER BY cantidad_ventas DESC, id_farmaceutico
"""


def ejecutar(driver: Driver, hoy: date | None = None) -> list[dict]:
    desde = hoy_o_sistema(hoy) - timedelta(days=60)
    return [r.data() for r in driver.execute_query(CYPHER, desde=desde).records]
