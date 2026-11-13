"""Consultas sobre MongoDB (q1, q2, q4, q6, q7, q8, q9, q11). Requiere MongoDB.

Resultados esperados con hoy = 2026-11-13 y la carga de originales + extra.
"""

from __future__ import annotations

from datetime import date

from farmared.consultas import (
    q01_productos_activos,
    q02_ventas_pendientes,
    q04_clientes_varias_recetas,
    q06_recetas_dispensa_atrasada,
)
from tests.conftest import HOY_TESTS


def test_q01_productos_activos_con_proveedor(db):
    filas = q01_productos_activos.ejecutar(db)
    ids = [f["id_producto"] for f in filas]
    assert len(filas) == 20
    assert ids == sorted(ids)
    assert not {"PRD012", "PRD013", "PRD023"} & set(ids)  # discontinuados
    paracetamol = filas[0]
    assert paracetamol["id_producto"] == "PRD001"
    assert paracetamol["proveedor"] == {
        "id_proveedor": "PRV001", "razon_social": "Laboratorios Andinos S.A.", "cuit": "30-71234567-1",
        "tipo": "Laboratorio", "ciudad": "Buenos Aires", "provincia": "Buenos Aires",
        "telefono": "1143001100", "activo": True,
    }


def test_q02_ventas_pendientes_con_farmaceutico(db):
    filas = q02_ventas_pendientes.ejecutar(db)
    assert {f["id_venta"]: (f["farmaceutico"]["id_farmaceutico"], f["total"]) for f in filas} == {
        "V011": ("F006", 4800), "V012": ("F005", 9200), "V022": ("F008", 12500), "V028": ("F010", 4500),
    }
    v011 = next(f for f in filas if f["id_venta"] == "V011")
    assert v011["farmaceutico"]["matricula"] == "MN-18340"
    assert v011["sucursal"] == {"id_sucursal": "S004", "nombre": "Farmacia Nueva Córdoba"}
    assert v011["fecha"] == date(2026, 10, 12)
    assert [f["fecha"] for f in filas] == sorted(f["fecha"] for f in filas)


def test_q04_clientes_con_mas_de_una_receta(db):
    filas = q04_clientes_varias_recetas.ejecutar(db)
    assert [(f["id_cliente"], f["cantidad_recetas"]) for f in filas] == [
        ("C018", 3), ("C001", 2), ("C002", 2), ("C006", 2), ("C011", 2),
    ]
    assert (filas[0]["nombre"], filas[0]["apellido"]) == ("Nicolás", "Acosta")


def test_q06_recetas_con_dispensa_atrasada(db):
    filas = q06_recetas_dispensa_atrasada.ejecutar(db, hoy=HOY_TESTS)
    assert [f["id_receta"] for f in filas] == ["RC002", "RC003", "RC004", "RC016", "RC010"]
    assert all(f["proxima_dispensa"] < HOY_TESTS for f in filas)
    rc002 = filas[0]
    assert rc002["proxima_dispensa"] == date(2026, 9, 15)
    assert rc002["cliente"]["id_cliente"] == "C003" and rc002["cliente"]["obra_social"] == "PAMI"


def test_q06_depende_de_hoy(db):
    # Antes del 15/09 ninguna de las recetas originales estaba atrasada.
    ids = {f["id_receta"] for f in q06_recetas_dispensa_atrasada.ejecutar(db, hoy=date(2026, 9, 1))}
    assert not {"RC002", "RC003", "RC004"} & ids
