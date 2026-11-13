"""Proyección de MongoDB (fuente de verdad) en Neo4j.

Modelo del grafo:

    (:Cliente)-[:REALIZO]->(:Venta)-[:ATENDIDA_POR]->(:Farmaceutico)-[:TRABAJA_EN]->(:Sucursal)
    (:Cliente)-[:TIENE_RECETA]->(:Receta)<-[:DISPENSA]-(:Venta)
    (:Venta)-[:INCLUYE {cantidad, precio_unit}]->(:Producto)

El grafo solo guarda lo que necesitan los recorridos (q3, q5, q10, q12). Nunca se
escribe directamente: se reconstruye completo (`reconstruir`) o se actualiza por
entidad (`proyectar`) leyendo siempre el estado actual desde MongoDB. Por eso todas
las operaciones son idempotentes (MERGE + SET).
"""

from __future__ import annotations

from datetime import date, datetime

from neo4j import Driver
from pymongo.database import Database

CONSTRAINTS = [
    "CREATE CONSTRAINT cliente_id IF NOT EXISTS FOR (n:Cliente) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT farmaceutico_id IF NOT EXISTS FOR (n:Farmaceutico) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT sucursal_id IF NOT EXISTS FOR (n:Sucursal) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT producto_id IF NOT EXISTS FOR (n:Producto) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT receta_id IF NOT EXISTS FOR (n:Receta) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT venta_id IF NOT EXISTS FOR (n:Venta) REQUIRE n.id IS UNIQUE",
    "CREATE INDEX venta_fecha IF NOT EXISTS FOR (n:Venta) ON (n.fecha)",
]

# --- Sentencias por entidad (reciben $filas: lista de dicts) ---------------------------------

CYPHER_SUCURSALES = """
UNWIND $filas AS f
MERGE (s:Sucursal {id: f.id})
SET s.nombre = f.nombre, s.tipo = f.tipo, s.ciudad = f.ciudad, s.provincia = f.provincia, s.activo = f.activo
"""

CYPHER_PRODUCTOS = """
UNWIND $filas AS f
MERGE (p:Producto {id: f.id})
SET p.nombre = f.nombre, p.categoria = f.categoria, p.condicion_venta = f.condicion_venta, p.activo = f.activo
"""

CYPHER_FARMACEUTICOS = """
UNWIND $filas AS f
MERGE (fa:Farmaceutico {id: f.id})
SET fa.nombre = f.nombre, fa.apellido = f.apellido, fa.matricula = f.matricula,
    fa.cargo = f.cargo, fa.activo = f.activo
WITH fa, f
OPTIONAL MATCH (fa)-[vieja:TRABAJA_EN]->()
DELETE vieja
WITH fa, f
MATCH (s:Sucursal {id: f.id_sucursal})
MERGE (fa)-[:TRABAJA_EN]->(s)
"""

CYPHER_CLIENTES = """
UNWIND $filas AS f
MERGE (c:Cliente {id: f.id})
SET c.nombre = f.nombre, c.apellido = f.apellido, c.dni = f.dni, c.ciudad = f.ciudad,
    c.provincia = f.provincia, c.obra_social = f.obra_social, c.activo = f.activo
"""

CYPHER_RECETAS = """
UNWIND $filas AS f
MERGE (r:Receta {id: f.id})
SET r.tipo = f.tipo, r.estado = f.estado, r.medico = f.medico, r.fecha_emision = f.fecha_emision,
    r.dispensas_autorizadas = f.dispensas_autorizadas, r.dispensas_realizadas = f.dispensas_realizadas,
    r.proxima_dispensa = f.proxima_dispensa
WITH r, f
MATCH (c:Cliente {id: f.id_cliente})
MERGE (c)-[:TIENE_RECETA]->(r)
"""

CYPHER_VENTAS = """
UNWIND $filas AS f
MERGE (v:Venta {id: f.id})
SET v.fecha = f.fecha, v.estado = f.estado, v.tipo = f.tipo, v.medio_pago = f.medio_pago, v.total = f.total
WITH v, f
MATCH (c:Cliente {id: f.id_cliente})
MERGE (c)-[:REALIZO]->(v)
WITH v, f
MATCH (fa:Farmaceutico {id: f.id_farmaceutico})
MERGE (v)-[:ATENDIDA_POR]->(fa)
WITH v, f
OPTIONAL MATCH (v)-[viejo:INCLUYE]->()
DELETE viejo
WITH DISTINCT v, f
UNWIND f.items AS item
MATCH (p:Producto {id: item.id_producto})
CREATE (v)-[:INCLUYE {cantidad: item.cantidad, precio_unit: item.precio_unit}]->(p)
WITH DISTINCT v, f
WHERE f.id_receta IS NOT NULL
MATCH (r:Receta {id: f.id_receta})
MERGE (v)-[:DISPENSA]->(r)
"""


# --- Conversión de documentos Mongo a filas para Cypher --------------------------------------

def _d(valor: datetime | None) -> date | None:
    return valor.date() if valor is not None else None


def _fila(doc: dict, campos: tuple[str, ...]) -> dict:
    return {"id": doc["_id"], **{c: doc.get(c) for c in campos}}


def _filas_sucursales(docs):
    return [_fila(d, ("nombre", "tipo", "ciudad", "provincia", "activo")) for d in docs]


def _filas_productos(docs):
    return [_fila(d, ("nombre", "categoria", "condicion_venta", "activo")) for d in docs]


def _filas_farmaceuticos(docs):
    return [_fila(d, ("nombre", "apellido", "matricula", "cargo", "id_sucursal", "activo")) for d in docs]


def _filas_clientes(docs):
    return [_fila(d, ("nombre", "apellido", "dni", "ciudad", "provincia", "obra_social", "activo")) for d in docs]


def _filas_recetas(docs):
    return [
        {
            **_fila(d, ("id_cliente", "tipo", "estado", "medico", "dispensas_autorizadas", "dispensas_realizadas")),
            "fecha_emision": _d(d["fecha_emision"]),
            "proxima_dispensa": _d(d.get("proxima_dispensa")),
        }
        for d in docs
    ]


def _filas_ventas(docs):
    return [
        {
            **_fila(d, ("id_cliente", "id_farmaceutico", "id_receta", "estado", "tipo", "medio_pago", "total")),
            "fecha": _d(d["fecha"]),
            "items": [
                {"id_producto": i["id_producto"], "cantidad": i["cantidad"], "precio_unit": i["precio_unit"]}
                for i in d["items"]
            ],
        }
        for d in docs
    ]


# Orden de proyección: primero los nodos que otros referencian.
ENTIDADES = [
    # (colección Mongo, sentencia, conversor)
    ("sucursales", CYPHER_SUCURSALES, _filas_sucursales),
    ("productos", CYPHER_PRODUCTOS, _filas_productos),
    ("farmaceuticos", CYPHER_FARMACEUTICOS, _filas_farmaceuticos),
    ("clientes", CYPHER_CLIENTES, _filas_clientes),
    ("recetas", CYPHER_RECETAS, _filas_recetas),
    ("ventas", CYPHER_VENTAS, _filas_ventas),
]
POR_TIPO = {  # tipo de evento de outbox -> (colección, sentencia, conversor)
    "cliente": ENTIDADES[3],
    "receta": ENTIDADES[4],
    "venta": ENTIDADES[5],
}


def crear_constraints(driver: Driver) -> None:
    for sentencia in CONSTRAINTS:
        driver.execute_query(sentencia)


def reconstruir(db: Database, driver: Driver) -> dict:
    """Borra el grafo y lo proyecta completo desde MongoDB. Devuelve el conteo resultante."""
    crear_constraints(driver)
    driver.execute_query("MATCH (n) DETACH DELETE n")
    for coleccion, cypher, conversor in ENTIDADES:
        filas = conversor(db[coleccion].find())
        if filas:
            driver.execute_query(cypher, filas=filas)
    return contar(driver)


def proyectar(db: Database, driver: Driver, tipo: str, ids: list[str]) -> int:
    """Actualiza en el grafo las entidades `ids` de un tipo ('cliente', 'receta', 'venta').

    Lee el estado actual desde MongoDB. Lanza LookupError si algún id no existe en Mongo
    (no hay borrados físicos, así que eso indica un evento inválido).
    """
    coleccion, cypher, conversor = POR_TIPO[tipo]
    docs = list(db[coleccion].find({"_id": {"$in": ids}}))
    faltan = set(ids) - {d["_id"] for d in docs}
    if faltan:
        raise LookupError(f"{tipo} inexistente en MongoDB: {sorted(faltan)}")
    driver.execute_query(cypher, filas=conversor(docs))
    return len(docs)


def contar(driver: Driver) -> dict:
    """Cantidad de nodos por etiqueta y de relaciones por tipo."""
    nodos, _, _ = driver.execute_query("MATCH (n) RETURN labels(n)[0] AS etiqueta, count(*) AS n ORDER BY etiqueta")
    rels, _, _ = driver.execute_query("MATCH ()-[r]->() RETURN type(r) AS tipo, count(*) AS n ORDER BY tipo")
    return {
        "nodos": {r["etiqueta"]: r["n"] for r in nodos},
        "relaciones": {r["tipo"]: r["n"] for r in rels},
    }
