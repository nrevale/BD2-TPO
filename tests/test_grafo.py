"""Proyección en Neo4j y sincronización por outbox. Requiere MongoDB y Neo4j."""

from __future__ import annotations

from datetime import date

import pytest

from farmared.grafo import outbox, proyeccion


@pytest.fixture(scope="module")
def grafo(db, neo4j_driver):
    outbox.reconstruir_grafo(db, neo4j_driver)
    return neo4j_driver


def _uno(driver, cypher, **params):
    registros = driver.execute_query(cypher, **params).records
    return registros[0] if registros else None


def test_conteos_del_grafo(grafo):
    assert proyeccion.contar(grafo) == {
        "nodos": {"Cliente": 18, "Farmaceutico": 17, "Producto": 23, "Receta": 19, "Sucursal": 15, "Venta": 31},
        "relaciones": {
            "ATENDIDA_POR": 31, "DISPENSA": 17, "INCLUYE": 39,
            "REALIZO": 31, "TIENE_RECETA": 19, "TRABAJA_EN": 17,
        },
    }


def test_camino_completo_de_una_venta(grafo):
    r = _uno(
        grafo,
        """
        MATCH (c:Cliente)-[:REALIZO]->(v:Venta {id: 'V005'})-[:ATENDIDA_POR]->(f)-[:TRABAJA_EN]->(s),
              (v)-[:DISPENSA]->(rc:Receta)<-[:TIENE_RECETA]-(c),
              (v)-[i:INCLUYE]->(p:Producto)
        RETURN c.id AS c, f.id AS f, s.id AS s, rc.id AS rc, p.id AS p, i.cantidad AS cant, v.fecha AS fecha
        """,
    )
    assert (r["c"], r["f"], r["s"], r["rc"], r["p"], r["cant"]) == ("C003", "F006", "S004", "RC002", "PRD004", 2)
    assert r["fecha"].to_native() == date(2026, 8, 15)


def test_reconstruir_es_idempotente(db, grafo):
    antes = proyeccion.contar(grafo)
    outbox.reconstruir_grafo(db, grafo)
    assert proyeccion.contar(grafo) == antes


def test_outbox_proyecta_cambio_confirmado(mongo_client, db, grafo):
    with mongo_client.start_session() as s:
        def tx(s):
            db.clientes.update_one({"_id": "C010"}, {"$set": {"activo": False}}, session=s)
            outbox.registrar_evento(db, "cliente", "C010", session=s)
        s.with_transaction(tx)

    assert _uno(grafo, "MATCH (c:Cliente {id:'C010'}) RETURN c.activo AS a")["a"] is True  # todavía no sincronizado
    r = outbox.procesar_pendientes(db, grafo)
    assert (r.procesados, r.pendientes, r.errores) == (1, 0, [])
    assert _uno(grafo, "MATCH (c:Cliente {id:'C010'}) RETURN c.activo AS a")["a"] is False


def test_outbox_transaccion_abortada_no_deja_evento(mongo_client, db):
    antes = db.outbox.count_documents({})
    with mongo_client.start_session() as s:
        def tx(s):
            outbox.registrar_evento(db, "cliente", "C001", session=s)
            raise RuntimeError("falla de la escritura")
        with pytest.raises(RuntimeError):
            s.with_transaction(tx)
    assert db.outbox.count_documents({}) == antes


def test_outbox_proyecta_venta_nueva_con_relaciones(db, grafo):
    venta = db.ventas.find_one({"_id": "V003"})
    nueva = {**venta, "_id": "V900", "items": [{**venta["items"][0], "id_detalle": "D900"}]}
    db.ventas.insert_one(nueva)
    outbox.registrar_evento(db, "venta", "V900")
    outbox.procesar_pendientes(db, grafo)
    r = _uno(
        grafo,
        "MATCH (c:Cliente)-[:REALIZO]->(v:Venta {id:'V900'})-[:DISPENSA]->(rc:Receta) "
        "MATCH (v)-[:INCLUYE]->(p) RETURN c.id AS c, rc.id AS rc, count(p) AS items",
    )
    assert (r["c"], r["rc"], r["items"]) == ("C001", "RC001", 1)


def test_reproyectar_venta_no_duplica_items(db, grafo):
    proyeccion.proyectar(db, grafo, "venta", ["V002"])
    proyeccion.proyectar(db, grafo, "venta", ["V002"])
    r = _uno(grafo, "MATCH (:Venta {id:'V002'})-[i:INCLUYE]->() RETURN count(i) AS n")
    assert r["n"] == 2


def test_evento_invalido_queda_pendiente_sin_frenar_los_demas(db, grafo):
    outbox.registrar_evento(db, "venta", "V999")  # no existe en Mongo
    outbox.registrar_evento(db, "receta", "RC001")
    r = outbox.procesar_pendientes(db, grafo)
    assert r.procesados == 1 and r.pendientes == 1
    assert "V999" in r.errores[0]
    # una reconstrucción completa da por resueltos los pendientes previos
    outbox.reconstruir_grafo(db, grafo)
    assert db.outbox.count_documents({"procesado": False}) == 0
