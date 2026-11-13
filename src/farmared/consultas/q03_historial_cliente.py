"""q03 — Historial completo de un cliente: ventas y recetas ordenadas cronológicamente por fecha.

Motor: Neo4j. El historial es un recorrido desde el cliente por dos caminos distintos (sus
ventas con los productos de cada una, y sus recetas); en el grafo son relaciones directas.
Relación entre entidades: Recorrido Cliente-REALIZO->Venta-INCLUYE->Producto (más
Venta-ATENDIDA_POR->Farmaceutico) y Cliente-TIENE_RECETA->Receta. Las dos ramas se unen con
CALL { ... UNION ... } y se ordenan por fecha (venta.fecha / receta.fecha_emision).

Parámetros: driver: Driver, id_cliente: str
Retorno: list[dict] —
    Lista cronológica de eventos {tipo: 'venta'|'receta', id, fecha, ...}. Venta: estado,
    total, tipo_venta, id_farmaceutico, productos [{id_producto, nombre, cantidad, precio_unit}].
    Receta: tipo_receta, estado, medico, dispensas_realizadas, dispensas_autorizadas.
    Ante empate de fecha, la receta va antes que la venta.
    Cliente inexistente: ValidacionError('CLIENTE_INEXISTENTE').
"""

from __future__ import annotations

from neo4j import Driver

from farmared.errores import ValidacionError

MOTOR = "neo4j"

EXISTE = "MATCH (c:Cliente {id: $id_cliente}) RETURN c.id AS id"

CYPHER = """
MATCH (c:Cliente {id: $id_cliente})
CALL (c) {
    MATCH (c)-[:REALIZO]->(v:Venta)-[:ATENDIDA_POR]->(f:Farmaceutico),
          (v)-[i:INCLUYE]->(p:Producto)
    WITH v, f, i, p ORDER BY p.id
    WITH v, f, collect({id_producto: p.id, nombre: p.nombre,
                        cantidad: i.cantidad, precio_unit: i.precio_unit}) AS productos
    RETURN {tipo: 'venta', id: v.id, fecha: v.fecha, estado: v.estado, total: v.total,
            tipo_venta: v.tipo, id_farmaceutico: f.id, productos: productos} AS evento, 1 AS orden
  UNION
    MATCH (c)-[:TIENE_RECETA]->(r:Receta)
    RETURN {tipo: 'receta', id: r.id, fecha: r.fecha_emision, tipo_receta: r.tipo, estado: r.estado,
            medico: r.medico, dispensas_realizadas: r.dispensas_realizadas,
            dispensas_autorizadas: r.dispensas_autorizadas} AS evento, 0 AS orden
}
RETURN evento
ORDER BY evento.fecha, orden, evento.id
"""


# Neo4j no conserva el orden de las claves de un map: se reordenan acá para una salida estable.
CAMPOS = {
    "venta": ("tipo", "id", "fecha", "estado", "total", "tipo_venta", "id_farmaceutico", "productos"),
    "receta": ("tipo", "id", "fecha", "tipo_receta", "estado", "medico",
               "dispensas_realizadas", "dispensas_autorizadas"),
}
CAMPOS_PRODUCTO = ("id_producto", "nombre", "cantidad", "precio_unit")


def ejecutar(driver: Driver, id_cliente: str) -> list[dict]:
    if not driver.execute_query(EXISTE, id_cliente=id_cliente).records:
        raise ValidacionError("CLIENTE_INEXISTENTE", f"no existe el cliente {id_cliente}")
    eventos = []
    for r in driver.execute_query(CYPHER, id_cliente=id_cliente).records:
        e = r["evento"]
        evento = {c: e[c] for c in CAMPOS[e["tipo"]]}
        evento["fecha"] = evento["fecha"].to_native()
        if "productos" in evento:
            evento["productos"] = [{c: p[c] for c in CAMPOS_PRODUCTO} for p in evento["productos"]]
        eventos.append(evento)
    return eventos
