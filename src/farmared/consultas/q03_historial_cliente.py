"""q03 — Historial completo de un cliente: ventas y recetas ordenadas cronológicamente por fecha.

Motor: Neo4j.
Relación entre entidades: Recorrido Cliente-REALIZO->Venta-INCLUYE->Producto y Cliente-TIENE_RECETA->Receta.

Parámetros: driver: Driver, id_cliente: str
Retorno: list[dict] —
    Lista cronológica de eventos {tipo: 'venta'|'receta', id, fecha, ...}. Venta: estado,
    total, tipo_venta, id_farmaceutico, productos [{id_producto, nombre, cantidad, precio_unit}].
    Receta: tipo_receta, estado, medico, dispensas_realizadas, dispensas_autorizadas.
    Ante empate de fecha, la receta va antes que la venta.
    Cliente inexistente: ValidacionError('CLIENTE_INEXISTENTE').

Estado: pendiente de implementar.
"""

from __future__ import annotations

from neo4j import Driver

MOTOR = "neo4j"


def ejecutar(driver: Driver, id_cliente: str) -> list[dict]:
    raise NotImplementedError("q03 todavía no está implementada")
