"""q15 — Actualización masiva del stock: dada una venta registrada, decrementa las unidades
de cada producto del detalle en los lotes de la sucursal del farmacéutico, aplicando FEFO
y omitiendo lotes vencidos. Si el stock vigente no alcanza para algún ítem, la operación
completa se rechaza sin modificar ningún lote.

Motor: MongoDB (colecciones `ventas` y `stock_lotes`, índice `fefo`), en una transacción
multi-documento. Se integra con q14 recibiendo su `session`.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from datetime import date

from pymongo.client_session import ClientSession
from pymongo.database import Database


def descontar_stock(db: Database, id_venta: str, session: ClientSession | None = None,
                    hoy: date | None = None) -> list[dict]:
    """Descuenta el stock de la venta por FEFO. Devuelve [{id_lote, id_producto, unidades}].

    - Sin `session`: abre su propia transacción. Con `session`: se une a la del llamador (q14).
    - Marca la venta con `stock_aplicado = True` y `lotes_consumidos`.
    - Rechaza con VENTA_INEXISTENTE, VENTA_NO_COMPLETADA, STOCK_YA_APLICADO o
      StockInsuficiente (sin modificar ningún lote).
    """
    raise NotImplementedError("q15 todavía no está implementada")
