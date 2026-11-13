"""q14 — Registro de una nueva venta 'Completada' (cabecera e ítems) con validación de cliente,
farmacéutico, sucursal, productos y receta. El total se calcula a partir de los ítems, se
descuenta el stock (q15) y se actualiza la receta según las reglas de negocio.

Motor: MongoDB. Venta, receta y lotes se escriben en **una sola transacción multi-documento**:
si el descuento de stock falla, no queda ni la venta ni la receta modificada.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from datetime import date

from neo4j import Driver
from pymongo.database import Database


def registrar_venta(db: Database, id_cliente: str, id_farmaceutico: str, items: list[dict], medio_pago: str,
                    id_receta: str | None = None, driver: Driver | None = None,
                    hoy: date | None = None) -> dict:
    """Registra la venta y devuelve su documento (con lotes_consumidos).

    `items`: [{"id_producto": "PRD003", "cantidad": 50}, ...]. El precio es el de lista vigente.

    Rechaza con: CLIENTE_INEXISTENTE, CLIENTE_INACTIVO, FARMACEUTICO_INEXISTENTE,
    FARMACEUTICO_INACTIVO, SUCURSAL_NO_FARMACIA, PRODUCTO_INEXISTENTE, PRODUCTO_INACTIVO,
    DATO_INVALIDO, MEDIO_PAGO_INVALIDO, RECETA_REQUERIDA, RECETA_INEXISTENTE,
    RECETA_DE_OTRO_CLIENTE, RECETA_NO_VIGENTE o StockInsuficiente.
    """
    raise NotImplementedError("q14 todavía no está implementada")
