"""Carga en MongoDB: modelo, idempotencia, validadores e índices. Requiere MongoDB."""

from __future__ import annotations

import shutil
from datetime import datetime

import pytest
from pymongo.errors import DuplicateKeyError, WriteError

from farmared.carga import cargar_mongo
from farmared.carga.esquema import VISTA_INGRESOS
from farmared.carga.lector_csv import ErrorDatasets


def test_conteos(db):
    esperados = {
        "clientes": 18, "sucursales": 15, "farmaceuticos": 17, "proveedores": 15, "productos": 23,
        "stock_lotes": 30, "recetas": 19, "ventas": 31, "outbox": 0,
    }
    for coleccion, n in esperados.items():
        assert db[coleccion].count_documents({}) == n, coleccion


def test_venta_con_items_embebidos(db):
    v = db.ventas.find_one({"_id": "V002"})
    assert v["id_sucursal"] == "S003"  # sucursal de F005
    assert v["total"] == 5750
    assert [(i["id_producto"], i["cantidad"], i["subtotal"]) for i in v["items"]] == [
        ("PRD011", 2, 3500),
        ("PRD001", 1, 2250),
    ]
    assert v["stock_aplicado"] is True and v["lotes_consumidos"] is None
    assert db.ventas.find_one({"_id": "V011"})["stock_aplicado"] is False  # Pendiente


def test_fechas_relativas_resueltas(db):
    assert db.ventas.find_one({"_id": "V023"})["fecha"] == datetime(2026, 11, 13)  # @hoy
    assert db.ventas.find_one({"_id": "V024"})["fecha"] == datetime(2026, 11, 1)  # @mes
    assert db.stock_lotes.find_one({"_id": "L019"})["vencimiento"] == datetime(2026, 11, 8)  # @hoy-5


def test_contadores(db):
    assert {c["_id"]: c["ultimo"] for c in db.contadores.find()} == {"venta": 31, "detalle": 39, "cliente": 18}


def test_vista_ingresos_mes(db):
    filas = {f["id_farmaceutico"]: f["ingresos"] for f in db[VISTA_INGRESOS].find({"mes": "2026-11"})}
    # V023 F016 6300, V024 F001 2600, V029 F003 7200, V030 F002 10500; V031 está anulada.
    assert filas == {"F016": 6300, "F001": 2600, "F003": 7200, "F002": 10500}


def test_validador_impide_stock_negativo(db):
    with pytest.raises(WriteError):
        db.stock_lotes.update_one({"_id": "L010"}, {"$inc": {"unidades": -13}})  # tiene 12
    assert db.stock_lotes.find_one({"_id": "L010"})["unidades"] == 12


def test_indice_unico_de_dni(db):
    cliente = db.clientes.find_one({"_id": "C001"}, {"_id": 0})
    with pytest.raises(DuplicateKeyError):
        db.clientes.insert_one({**cliente, "_id": "C999"})


def test_validador_rechaza_enum_invalido(db):
    with pytest.raises(WriteError):
        db.ventas.update_one({"_id": "V001"}, {"$set": {"estado": "Cancelada"}})


def test_carga_es_idempotente(mongo_client, db):
    def volcado():
        return {c: list(db[c].find().sort("_id")) for c in db.list_collection_names() if c != VISTA_INGRESOS}

    cargar_mongo.cargar(mongo_client, db.name)
    primero = volcado()
    cargar_mongo.cargar(mongo_client, db.name)
    assert volcado() == primero


def test_datos_invalidos_no_tocan_la_base(mongo_client, db, tmp_path):
    malos = tmp_path / "originales"
    shutil.copytree(cargar_mongo.directorios_por_defecto()["originales"], malos)
    (malos / "ventas.csv").write_text(
        (malos / "ventas.csv").read_text(encoding="utf-8").replace("V002,C005", "V002,C099", 1), encoding="utf-8"
    )
    antes = db.ventas.count_documents({})
    with pytest.raises(ErrorDatasets):
        cargar_mongo.cargar(mongo_client, db.name, {"originales": malos})
    assert db.ventas.count_documents({}) == antes
