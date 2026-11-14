"""Integración de venta, receta, stock, outbox y proyección de q14."""

from datetime import datetime

import pytest

from farmared.carga import cargar_mongo
from farmared.errores import StockInsuficiente, ValidacionError
from farmared.grafo import outbox
from farmared.servicios.q14_registrar_venta import registrar_venta
from farmared.servicios.q15_descontar_stock import descontar_stock


@pytest.fixture
def db(mongo_client):
    cargar_mongo.cargar(mongo_client, "farmared_test")
    return mongo_client["farmared_test"]


def _venta_receta_simple(db, cantidad, driver=None):
    return registrar_venta(
        db, "C007", "F001", [{"id_producto": "PRD003", "cantidad": cantidad}],
        "Obra social", "RC006", driver=driver,
    )


def _estado(db):
    return {
        nombre: list(db[nombre].find().sort("_id"))
        for nombre in ("ventas", "recetas", "stock_lotes", "contadores", "outbox")
    }


def test_venta_fefo_con_dispensa_y_proyeccion(db, neo4j_driver):
    outbox.reconstruir_grafo(db, neo4j_driver)

    venta = _venta_receta_simple(db, 50, neo4j_driver)

    assert venta == db.ventas.find_one({"_id": "V032"})
    precio = db.productos.find_one({"_id": "PRD003"})["precio_unit"]
    assert venta["items"] == [
        {"id_detalle": "D040", "id_producto": "PRD003", "cantidad": 50,
         "precio_unit": precio, "subtotal": 50 * precio},
    ]
    assert venta["total"] == 50 * precio and venta["stock_aplicado"]
    assert venta["lotes_consumidos"] == [
        {"id_lote": "L005", "id_producto": "PRD003", "unidades": 40},
        {"id_lote": "L015", "id_producto": "PRD003", "unidades": 10},
    ]
    lotes = db.stock_lotes.find({"_id": {"$in": ["L005", "L015", "L019"]}})
    assert {lote["_id"]: lote["unidades"] for lote in lotes} == {"L005": 0, "L015": 90, "L019": 8}
    receta = db.recetas.find_one({"_id": "RC006"})
    assert (receta["estado"], receta["dispensas_realizadas"], receta["proxima_dispensa"]) == ("Completada", 1, None)
    assert {(e["tipo"], e["ref_id"], e["procesado"]) for e in db.outbox.find()} == {
        ("venta", "V032", True), ("receta", "RC006", True),
    }
    filas, _, _ = neo4j_driver.execute_query(
        """
        MATCH (:Cliente {id: 'C007'})-[:REALIZO]->(v:Venta {id: $venta})-[:DISPENSA]->(r:Receta {id: 'RC006'})
        MATCH (v)-[i:INCLUYE]->(:Producto {id: 'PRD003'})
        RETURN v.total AS total, r.estado AS estado, i.cantidad AS cantidad
        """,
        venta=venta["_id"],
    )
    assert [f.data() for f in filas] == [{"total": 50 * precio, "estado": "Completada", "cantidad": 50}]
    with pytest.raises(ValidacionError, match="STOCK_YA_APLICADO"):
        descontar_stock(db, venta["_id"])


def test_stock_insuficiente_revierte_venta_y_contadores(db):
    antes = _estado(db)
    with pytest.raises(StockInsuficiente, match="pide 200, hay 140 vigentes"):
        _venta_receta_simple(db, 200)
    assert _estado(db) == antes


def test_error_despues_del_descuento_revierte_lotes_y_receta(db, monkeypatch):
    antes = _estado(db)
    registrar_evento = outbox.registrar_evento

    def fallar_al_registrar_receta(db, tipo, ref_id, session):
        if tipo == "receta":
            raise RuntimeError("falló el registro del evento de receta")
        registrar_evento(db, tipo, ref_id, session=session)

    monkeypatch.setattr(outbox, "registrar_evento", fallar_al_registrar_receta)
    with pytest.raises(RuntimeError, match="evento de receta"):
        _venta_receta_simple(db, 50)
    assert _estado(db) == antes


def test_receta_prolongada_programa_y_completa_dispensas(db):
    for realizadas, estado, proxima in (
        (2, "Vigente", datetime(2026, 12, 13)),
        (3, "Completada", None),
    ):
        registrar_venta(db, "C011", "F001", [{"id_producto": "PRD003", "cantidad": 1}], "Efectivo", "RC010")
        receta = db.recetas.find_one({"_id": "RC010"})
        assert (receta["dispensas_realizadas"], receta["estado"], receta["proxima_dispensa"]) == (
            realizadas, estado, proxima,
        )


@pytest.mark.parametrize("cliente,farmaceutico,producto,receta,codigo", [
    ("C015", "F001", "PRD003", None, "CLIENTE_INACTIVO"),
    ("C007", "F015", "PRD003", None, "SUCURSAL_NO_FARMACIA"),
    ("C007", "F013", "PRD003", None, "FARMACEUTICO_INACTIVO"),
    ("C007", "F001", "PRD023", None, "PRODUCTO_INACTIVO"),
    ("C007", "F001", "PRD003", None, "RECETA_REQUERIDA"),
    ("C001", "F001", "PRD003", "RC006", "RECETA_DE_OTRO_CLIENTE"),
    ("C018", "F001", "PRD003", "RC013", "RECETA_NO_VIGENTE"),
    ("C001", "F001", "PRD003", "RC001", "RECETA_NO_VIGENTE"),
])
def test_rechaza_datos_de_venta(db, cliente, farmaceutico, producto, receta, codigo):
    with pytest.raises(ValidacionError) as error:
        registrar_venta(db, cliente, farmaceutico, [{"id_producto": producto, "cantidad": 1}], "Efectivo", receta)
    assert error.value.codigo == codigo
