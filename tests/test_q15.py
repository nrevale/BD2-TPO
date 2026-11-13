"""q15 — Descuento de stock por FEFO. Requiere MongoDB.

Lotes usados (hoy = 2026-11-13):
- S001 / PRD003: L019 (8 u., vencido @hoy-5), L005 (40 u., vence 2026-11-30), L015 (100 u., 2027-06-30).
- S007 / PRD016: L022 (3 u., vencido @hoy-10), L023 (2 u., vigente).
"""

from __future__ import annotations

import threading
from datetime import date, datetime

import pytest
from pymongo.errors import WriteError

from farmared.errores import StockInsuficiente, ValidacionError
from farmared.servicios.q15_descontar_stock import descontar_stock

HOY = date(2026, 11, 13)
FARMACEUTICO_DE = {"S001": "F001", "S007": "F009"}


@pytest.fixture
def db(mongo_client):
    """Base recién cargada para cada test (q15 modifica lotes)."""
    from farmared.carga import cargar_mongo

    cargar_mongo.cargar(mongo_client, "farmared_test")
    return mongo_client["farmared_test"]


def _venta(db, id_venta: str, id_sucursal: str, items: list[tuple[str, int]], estado: str = "Completada") -> None:
    """Inserta una venta sin stock aplicado (como la deja q14 justo antes de llamar a q15)."""
    detalle = [
        {"id_detalle": f"{id_venta}-{i}", "id_producto": p, "cantidad": c, "precio_unit": 100, "subtotal": 100 * c}
        for i, (p, c) in enumerate(items, 1)
    ]
    db.ventas.insert_one({
        "_id": id_venta, "id_cliente": "C007", "id_farmaceutico": FARMACEUTICO_DE[id_sucursal],
        "id_sucursal": id_sucursal, "id_receta": None, "fecha": datetime(2026, 11, 13), "tipo": "Venta libre",
        "medio_pago": "Efectivo", "total": sum(d["subtotal"] for d in detalle), "estado": estado,
        "stock_aplicado": False, "lotes_consumidos": None, "items": detalle,
    })


def _unidades(db, *lotes: str) -> dict[str, int]:
    return {l["_id"]: l["unidades"] for l in db.stock_lotes.find({"_id": {"$in": list(lotes)}})}


# --- FEFO -----------------------------------------------------------------------------------

def test_fefo_saltea_el_lote_vencido(db):
    _venta(db, "VT01", "S001", [("PRD003", 50)])
    consumidos = descontar_stock(db, "VT01", hoy=HOY)
    assert consumidos == [
        {"id_lote": "L005", "id_producto": "PRD003", "unidades": 40},
        {"id_lote": "L015", "id_producto": "PRD003", "unidades": 10},
    ]
    assert _unidades(db, "L019", "L005", "L015") == {"L019": 8, "L005": 0, "L015": 90}
    venta = db.ventas.find_one({"_id": "VT01"})
    assert venta["stock_aplicado"] is True
    assert venta["lotes_consumidos"] == consumidos


def test_agrupa_items_del_mismo_producto(db):
    _venta(db, "VT01", "S001", [("PRD003", 30), ("PRD001", 5), ("PRD003", 20)])
    consumidos = descontar_stock(db, "VT01", hoy=HOY)
    assert consumidos == [
        {"id_lote": "L005", "id_producto": "PRD003", "unidades": 40},
        {"id_lote": "L015", "id_producto": "PRD003", "unidades": 10},
        {"id_lote": "L001", "id_producto": "PRD001", "unidades": 5},
    ]


def test_hoy_decide_que_lotes_estan_vencidos(db):
    """Con hoy = 2026-12-01, L005 (vence 2026-11-30) ya no se puede dispensar."""
    _venta(db, "VT01", "S001", [("PRD003", 50)])
    consumidos = descontar_stock(db, "VT01", hoy=date(2026, 12, 1))
    assert consumidos == [{"id_lote": "L015", "id_producto": "PRD003", "unidades": 50}]
    assert _unidades(db, "L005", "L015") == {"L005": 40, "L015": 50}


def test_un_lote_que_vence_hoy_todavia_se_dispensa(db):
    _venta(db, "VT01", "S001", [("PRD003", 10)])
    consumidos = descontar_stock(db, "VT01", hoy=date(2026, 11, 30))
    assert consumidos == [{"id_lote": "L005", "id_producto": "PRD003", "unidades": 10}]


# --- Rechazos -------------------------------------------------------------------------------

def test_rechaza_si_el_stock_vigente_no_alcanza(db):
    """PRD016 en S007: 2 vigentes (L023) + 3 vencidas (L022). Pedir 4 no alcanza."""
    _venta(db, "VT01", "S007", [("PRD016", 4)])
    antes = list(db.stock_lotes.find().sort("_id"))
    with pytest.raises(StockInsuficiente) as e:
        descontar_stock(db, "VT01", hoy=HOY)
    assert e.value.codigo == "STOCK_INSUFICIENTE"
    assert "PRD016: pide 4, hay 2 vigentes" in e.value.mensaje
    assert list(db.stock_lotes.find().sort("_id")) == antes
    assert db.ventas.find_one({"_id": "VT01"})["stock_aplicado"] is False


def test_si_un_item_no_alcanza_no_se_toca_ningun_lote(db):
    """PRD003 alcanza en S001, PRD019 no tiene lotes ahí: se rechaza todo, L005 queda igual."""
    _venta(db, "VT01", "S001", [("PRD003", 10), ("PRD019", 1)])
    antes = list(db.stock_lotes.find().sort("_id"))
    with pytest.raises(StockInsuficiente):
        descontar_stock(db, "VT01", hoy=HOY)
    assert list(db.stock_lotes.find().sort("_id")) == antes


@pytest.mark.parametrize("id_venta,codigo", [
    ("V002", "STOCK_YA_APLICADO"),      # histórica completada: el CSV ya refleja su stock
    ("V011", "VENTA_NO_COMPLETADA"),    # pendiente
    ("V015", "VENTA_NO_COMPLETADA"),    # anulada
    ("V999", "VENTA_INEXISTENTE"),
])
def test_rechaza_ventas_que_no_corresponden(db, id_venta, codigo):
    antes = list(db.stock_lotes.find().sort("_id"))
    with pytest.raises(ValidacionError) as e:
        descontar_stock(db, id_venta, hoy=HOY)
    assert e.value.codigo == codigo
    assert list(db.stock_lotes.find().sort("_id")) == antes


def test_no_se_aplica_dos_veces(db):
    _venta(db, "VT01", "S001", [("PRD003", 5)])
    descontar_stock(db, "VT01", hoy=HOY)
    with pytest.raises(ValidacionError) as e:
        descontar_stock(db, "VT01", hoy=HOY)
    assert e.value.codigo == "STOCK_YA_APLICADO"
    assert _unidades(db, "L005")["L005"] == 35


# --- Integración con la transacción del llamador (q14) --------------------------------------

def test_se_une_a_la_transaccion_del_llamador(db):
    """Si el llamador aborta (por ejemplo, falló otra cosa en q14), el descuento no queda."""
    _venta(db, "VT01", "S001", [("PRD003", 50)])
    with db.client.start_session() as s:
        s.start_transaction()
        consumidos = descontar_stock(db, "VT01", session=s, hoy=HOY)
        assert len(consumidos) == 2
        # Dentro de la transacción ya se ve el descuento; afuera todavía no.
        assert db.stock_lotes.find_one({"_id": "L005"}, session=s)["unidades"] == 0
        assert _unidades(db, "L005")["L005"] == 40
        s.abort_transaction()
    assert _unidades(db, "L005", "L015") == {"L005": 40, "L015": 100}
    assert db.ventas.find_one({"_id": "VT01"})["stock_aplicado"] is False


def test_falla_dentro_de_la_transaccion_del_llamador(db):
    _venta(db, "VT01", "S007", [("PRD016", 4)])
    with db.client.start_session() as s:
        with pytest.raises(StockInsuficiente):
            s.with_transaction(lambda ses: descontar_stock(db, "VT01", session=ses, hoy=HOY))
    assert _unidades(db, "L022", "L023") == {"L022": 3, "L023": 2}


# --- Concurrencia ---------------------------------------------------------------------------

def _en_paralelo(db, ventas: list[str]) -> list[str]:
    barrera = threading.Barrier(len(ventas))
    resultados: list[str] = []

    def correr(id_venta):
        barrera.wait()
        try:
            descontar_stock(db, id_venta, hoy=HOY)
            resultados.append("ok")
        except ValidacionError as e:
            resultados.append(e.codigo)

    hilos = [threading.Thread(target=correr, args=(v,)) for v in ventas]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    return sorted(resultados)


def test_dos_ventas_simultaneas_por_las_ultimas_unidades(db):
    _venta(db, "VT01", "S007", [("PRD016", 2)])
    _venta(db, "VT02", "S007", [("PRD016", 2)])
    assert _en_paralelo(db, ["VT01", "VT02"]) == ["STOCK_INSUFICIENTE", "ok"]
    assert _unidades(db, "L022", "L023") == {"L022": 3, "L023": 0}
    aplicadas = db.ventas.count_documents({"_id": {"$in": ["VT01", "VT02"]}, "stock_aplicado": True})
    assert aplicadas == 1


def test_muchas_ventas_simultaneas_nunca_dejan_stock_negativo(db):
    ventas = [f"VT{i:02d}" for i in range(1, 7)]
    for v in ventas:
        _venta(db, v, "S007", [("PRD016", 1)])
    assert _en_paralelo(db, ventas) == ["STOCK_INSUFICIENTE"] * 4 + ["ok"] * 2
    assert _unidades(db, "L023")["L023"] == 0


def test_la_misma_venta_aplicada_dos_veces_a_la_vez(db):
    _venta(db, "VT01", "S001", [("PRD003", 5)])
    assert _en_paralelo(db, ["VT01", "VT01"]) == ["STOCK_YA_APLICADO", "ok"]
    assert _unidades(db, "L005")["L005"] == 35


def test_el_validador_impide_stock_negativo(db):
    """Última barrera: aunque una escritura salteara el servicio, Mongo rechaza unidades < 0."""
    with pytest.raises(WriteError):
        db.stock_lotes.update_one({"_id": "L029"}, {"$inc": {"unidades": -1}})
    assert _unidades(db, "L029")["L029"] == 0
