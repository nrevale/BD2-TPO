"""q15 — Actualización masiva del stock: dada una venta registrada, decrementa las unidades
de cada producto del detalle en los lotes de la sucursal del farmacéutico, aplicando FEFO
y omitiendo lotes vencidos. Si el stock vigente no alcanza para algún ítem, la operación
completa se rechaza sin modificar ningún lote.

Motor: MongoDB (colecciones `ventas` y `stock_lotes`, índice `fefo`), en una transacción
multi-documento. Se integra con q14 recibiendo su `session`.

Relación entre entidades: los ítems están embebidos en la venta (no hace falta cruzar con
otra colección para saber qué descontar). La sucursal sale de `venta.id_sucursal`, que es la
del farmacéutico que registró la venta (referencia extendida, ver sección 2). Los lotes se
buscan por `(id_sucursal, id_producto)` con el índice `fefo`.

Algoritmo:
1. Validar la venta: existe, está 'Completada' y todavía no se le aplicó el stock.
2. Agrupar las cantidades por producto (un producto puede repetirse en varios ítems).
3. Por producto, leer los lotes vigentes (`vencimiento >= hoy`, `unidades > 0`) ordenados por
   `(vencimiento, _id)` y armar el plan FEFO: tomar del que vence primero hasta cubrir la
   cantidad. Los vencidos nunca entran al plan.
4. Si a algún producto no le alcanza el stock vigente: StockInsuficiente **antes de escribir**.
5. Aplicar cada descuento con un update condicional
   `{_id, unidades >= n, vencimiento >= hoy}` + `$inc: {unidades: -n}`. Si no modifica
   exactamente un documento, el lote cambió por otra operación: se aborta todo.
6. Marcar la venta (`stock_aplicado = true`, `lotes_consumidos`) con filtro
   `stock_aplicado = false`, para que nunca se aplique dos veces.

Concurrencia: dos ventas que compiten por el mismo lote dentro de transacciones generan un
*write conflict*; `with_transaction` aborta y reintenta la perdedora, que vuelve a leer el
stock ya descontado y, si no le alcanza, falla con StockInsuficiente. El update condicional
y el validador `unidades >= 0` son dos barreras más: el stock nunca queda negativo.

No genera evento de outbox: el stock no se proyecta en el grafo.

Parámetros: `db`, `id_venta`, `session` (opcional, la de q14), `hoy` (fecha del sistema por
defecto; define qué lotes están vencidos).
Retorno: lotes consumidos `[{id_lote, id_producto, unidades}]`, en orden FEFO.
Errores: VENTA_INEXISTENTE, VENTA_NO_COMPLETADA, STOCK_YA_APLICADO, StockInsuficiente.
"""

from __future__ import annotations

from datetime import date

from pymongo.client_session import ClientSession
from pymongo.database import Database

from farmared import reloj
from farmared.errores import StockInsuficiente, ValidacionError
from farmared.servicios._transaccion import OPCIONES, en_transaccion


def descontar_stock(db: Database, id_venta: str, session: ClientSession | None = None,
                    hoy: date | None = None) -> list[dict]:
    """Descuenta el stock de la venta por FEFO. Devuelve [{id_lote, id_producto, unidades}].

    - Sin `session`: abre su propia transacción. Con `session`: se une a la del llamador (q14).
    - Marca la venta con `stock_aplicado = True` y `lotes_consumidos`.
    - Rechaza con VENTA_INEXISTENTE, VENTA_NO_COMPLETADA, STOCK_YA_APLICADO o
      StockInsuficiente (sin modificar ningún lote).
    """
    hoy = hoy if hoy is not None else reloj.hoy()

    def aplicar(s: ClientSession) -> list[dict]:
        return _descontar(db, id_venta, s, hoy)

    if session is None:
        return en_transaccion(db, aplicar)
    if session.in_transaction:
        # Parte de la transacción del llamador: si algo falla, el llamador aborta todo.
        return aplicar(session)
    return session.with_transaction(aplicar, **OPCIONES)


def _descontar(db: Database, id_venta: str, session: ClientSession, hoy: date) -> list[dict]:
    venta = db.ventas.find_one({"_id": id_venta}, session=session)
    if venta is None:
        raise ValidacionError("VENTA_INEXISTENTE", f"no existe la venta {id_venta}")
    if venta["estado"] != "Completada":
        raise ValidacionError("VENTA_NO_COMPLETADA",
                              f"la venta {id_venta} está '{venta['estado']}': solo las completadas descuentan stock")
    if venta["stock_aplicado"]:
        raise ValidacionError("STOCK_YA_APLICADO", f"la venta {id_venta} ya descontó su stock")

    id_sucursal = venta["id_sucursal"]
    desde = reloj.a_datetime(hoy)

    # 2. Cantidad pedida por producto (dict conserva el orden de los ítems).
    pedido: dict[str, int] = {}
    for item in venta["items"]:
        pedido[item["id_producto"]] = pedido.get(item["id_producto"], 0) + item["cantidad"]

    # 3 y 4. Plan FEFO completo antes de escribir nada.
    plan: list[dict] = []
    faltantes: list[str] = []
    for id_producto, cantidad in pedido.items():
        lotes = db.stock_lotes.find(
            {"id_sucursal": id_sucursal, "id_producto": id_producto,
             "vencimiento": {"$gte": desde}, "unidades": {"$gt": 0}},
            {"unidades": 1},
            session=session,
        ).sort([("vencimiento", 1), ("_id", 1)])
        resta = cantidad
        for lote in lotes:
            if resta == 0:
                break
            tomar = min(resta, lote["unidades"])
            plan.append({"id_lote": lote["_id"], "id_producto": id_producto, "unidades": tomar})
            resta -= tomar
        if resta > 0:
            faltantes.append(f"{id_producto}: pide {cantidad}, hay {cantidad - resta} vigentes")
    if faltantes:
        raise StockInsuficiente(f"stock vigente insuficiente en {id_sucursal} para la venta {id_venta} — "
                                + "; ".join(faltantes))

    # 5. Descuento condicional, lote por lote.
    for paso in plan:
        r = db.stock_lotes.update_one(
            {"_id": paso["id_lote"], "unidades": {"$gte": paso["unidades"]}, "vencimiento": {"$gte": desde}},
            {"$inc": {"unidades": -paso["unidades"]}},
            session=session,
        )
        if r.modified_count != 1:
            raise StockInsuficiente(f"el lote {paso['id_lote']} cambió durante la operación; no se descontó nada")

    # 6. La venta queda marcada; el filtro impide aplicarla dos veces.
    r = db.ventas.update_one(
        {"_id": id_venta, "stock_aplicado": False},
        {"$set": {"stock_aplicado": True, "lotes_consumidos": plan}},
        session=session,
    )
    if r.modified_count != 1:
        raise ValidacionError("STOCK_YA_APLICADO", f"la venta {id_venta} ya descontó su stock")
    return plan
