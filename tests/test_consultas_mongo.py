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
    q07_top_productos,
    q08_lotes_stock_bajo,
    q09_ventas_libres_menores,
    q11_ingresos_mes,
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


# --- q7, q8, q9, q11 -------------------------------------------------------------------------

def test_q07_top_5_productos_completadas(db):
    filas = q07_top_productos.ejecutar(db)
    assert [(f["id_producto"], f["unidades_vendidas"]) for f in filas] == [
        ("PRD005", 8), ("PRD001", 7), ("PRD011", 7), ("PRD004", 4), ("PRD002", 3),
    ]
    assert filas[0]["nombre"] == "Metformina 850mg x60"


def test_q07_ignora_pendientes_y_anuladas(db):
    # V012 (Pendiente) y V015 (Anulada) tienen PRD002: si contaran, PRD002 tendría 6 unidades.
    prd002 = next(f for f in q07_top_productos.ejecutar(db) if f["id_producto"] == "PRD002")
    assert prd002["unidades_vendidas"] == 3


def test_q08_lotes_con_menos_de_50_unidades(db):
    filas = q08_lotes_stock_bajo.ejecutar(db, hoy=HOY_TESTS)
    assert len(filas) == 18
    assert all(f["unidades"] < 50 for f in filas)
    assert [f["unidades"] for f in filas] == sorted(f["unidades"] for f in filas)
    assert {f["id_lote"] for f in filas if f["vencido"]} == {"L012", "L018", "L019", "L022"}
    assert filas[0]["id_lote"] == "L029" and filas[0]["unidades"] == 0
    l005 = next(f for f in filas if f["id_lote"] == "L005")
    assert l005["producto"] == {"id_producto": "PRD003", "nombre": "Amoxicilina 500mg x21"}
    assert l005["sucursal"] == {"id_sucursal": "S001", "nombre": "Farmacia Palermo", "tipo": "Farmacia"}
    assert l005["proveedor"] == {"id_proveedor": "PRV003", "razon_social": "FarmaLitoral S.A."}
    assert l005["vencimiento"] == date(2026, 11, 30) and l005["vencido"] is False


def test_q08_vencido_depende_de_hoy(db):
    filas = q08_lotes_stock_bajo.ejecutar(db, hoy=date(2026, 12, 1))
    assert next(f for f in filas if f["id_lote"] == "L005")["vencido"] is True


def test_q09_ventas_libres_menores_a_5000(db):
    filas = q09_ventas_libres_menores.ejecutar(db)
    assert [(f["id_venta"], f["total"], f["estado"]) for f in filas] == [
        ("V013", 4400, "Completada"), ("V014", 4600, "Completada"),
        ("V024", 2600, "Completada"), ("V028", 4500, "Pendiente"),
    ]
    ids = {f["id_venta"] for f in filas}
    assert "V031" not in ids and "V015" not in ids  # anuladas
    assert isinstance(filas[0]["fecha"], date)


def test_q11_ingresos_por_farmaceutico_mes_actual(db):
    filas = q11_ingresos_mes.ejecutar(db, hoy=HOY_TESTS)
    assert [(f["id_farmaceutico"], f["ingresos"], f["cantidad_ventas"]) for f in filas] == [
        ("F002", 10500, 1), ("F003", 7200, 1), ("F016", 6300, 1), ("F001", 2600, 1),
    ]
    assert all(f["mes"] == "2026-11" for f in filas)
    assert (filas[0]["nombre"], filas[0]["apellido"]) == ("Sebastián", "Ledesma")


def test_q11_otro_mes(db):
    # Agosto 2026 solo tiene ventas originales: V005 (F006, 12400) y V006 (F002, 22100).
    filas = q11_ingresos_mes.ejecutar(db, hoy=date(2026, 8, 20))
    assert [(f["id_farmaceutico"], f["ingresos"]) for f in filas] == [("F002", 22100), ("F006", 12400)]
