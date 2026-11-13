"""Consultas sobre Neo4j (q3, q5, q10, q12). Requiere MongoDB y Neo4j.

El grafo se reconstruye desde `farmared_test`. Resultados esperados con hoy = 2026-11-13.
"""

from __future__ import annotations

from datetime import date

import pytest

from farmared.consultas import (
    q03_historial_cliente,
    q05_farmaceuticos_ventas_60d,
    q10_clientes_por_sucursal,
    q12_clientes_sin_ventas,
)
from farmared.errores import ValidacionError
from farmared.grafo import outbox
from tests.conftest import HOY_TESTS


@pytest.fixture(scope="module")
def grafo(db, neo4j_driver):
    outbox.reconstruir_grafo(db, neo4j_driver)
    return neo4j_driver


def test_q03_historial_cronologico_receta_antes_que_venta(grafo):
    eventos = q03_historial_cliente.ejecutar(grafo, "C006")
    assert [e["id"] for e in eventos] == ["RC003", "V006", "V007", "RC004", "V008", "V016", "V030"]
    assert eventos[0]["fecha"] == eventos[1]["fecha"] == date(2026, 8, 1)  # empate: receta primero
    fechas = [e["fecha"] for e in eventos]
    assert fechas == sorted(fechas)


def test_q03_campos_de_venta_y_receta(grafo):
    eventos = {e["id"]: e for e in q03_historial_cliente.ejecutar(grafo, "C006")}
    venta, receta = eventos["V006"], eventos["RC003"]
    assert venta["tipo"] == "venta"
    assert {"estado", "total", "tipo_venta", "id_farmaceutico", "productos"} <= set(venta)
    assert venta["productos"] and {"id_producto", "nombre", "cantidad", "precio_unit"} == set(venta["productos"][0])
    assert sum(p["cantidad"] * p["precio_unit"] for p in venta["productos"]) == venta["total"]
    assert receta["tipo"] == "receta"
    assert {"tipo_receta", "estado", "medico", "dispensas_realizadas", "dispensas_autorizadas"} <= set(receta)


def test_q03_cliente_inexistente(grafo):
    with pytest.raises(ValidacionError) as e:
        q03_historial_cliente.ejecutar(grafo, "C999")
    assert e.value.codigo == "CLIENTE_INEXISTENTE"


def test_q05_incluye_farmaceuticos_con_cero_ventas(grafo):
    filas = q05_farmaceuticos_ventas_60d.ejecutar(grafo, hoy=HOY_TESTS)
    conteo = {f["id_farmaceutico"]: f["cantidad_ventas"] for f in filas}
    assert conteo == {
        "F002": 3, "F005": 3, "F001": 2, "F003": 2, "F010": 2, "F014": 2, "F016": 2,
        "F006": 1, "F008": 1, "F011": 1,
        "F007": 0, "F009": 0, "F012": 0, "F015": 0, "F017": 0,
    }
    assert [f["cantidad_ventas"] for f in filas] == sorted(conteo.values(), reverse=True)
    assert {"nombre", "apellido", "matricula", "id_sucursal"} <= set(filas[0])


def test_q10_clientes_por_sucursal(grafo):
    ids = lambda s: [c["id_cliente"] for c in q10_clientes_por_sucursal.ejecutar(grafo, s)]
    assert ids("S001") == ["C001", "C006", "C009"]
    assert ids("S002") == ["C001", "C002", "C004"]  # C004 por F004, inactivo
    assert ids("S011") == ["C016"]
    assert set(q10_clientes_por_sucursal.ejecutar(grafo, "S001")[0]) == {
        "id_cliente", "nombre", "apellido", "dni", "activo",
    }


def test_q10_sucursal_inexistente(grafo):
    with pytest.raises(ValidacionError) as e:
        q10_clientes_por_sucursal.ejecutar(grafo, "S999")
    assert e.value.codigo == "SUCURSAL_INEXISTENTE"


def test_q12_clientes_sin_ventas_en_el_ultimo_anio(grafo):
    filas = q12_clientes_sin_ventas.ejecutar(grafo, hoy=HOY_TESTS)
    assert [f["id_cliente"] for f in filas] == ["C004", "C008", "C010", "C012", "C015", "C017"]
    for f in filas:
        assert f["ultima_compra"] is None or f["ultima_compra"] < date(2025, 11, 13)
