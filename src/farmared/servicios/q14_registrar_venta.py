"""q14 — Registro de una nueva venta 'Completada' (cabecera e ítems) con validación de cliente,
farmacéutico, sucursal, productos y receta. El total se calcula a partir de los ítems, se
descuenta el stock (q15) y se actualiza la receta según las reglas de negocio.

Motor: MongoDB. Venta, receta y lotes se escriben en **una sola transacción multi-documento**:
si el descuento de stock falla, no queda ni la venta ni la receta modificada.

La venta embebe los ítems con sus precios y referencia al cliente, al farmacéutico,
a la sucursal y a la receta. Los eventos de venta y receta se guardan en la misma
transacción y se proyectan a Neo4j después del commit.
"""

from __future__ import annotations

from datetime import date, timedelta

from neo4j import Driver
from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.collection import Collection
from pymongo.database import Database

from farmared import reloj
from farmared.carga.lector_csv import INT64_MAX
from farmared.carga.tablas import MEDIOS_PAGO
from farmared.errores import ValidacionError
from farmared.grafo import outbox
from farmared.servicios._transaccion import en_transaccion
from farmared.servicios.q15_descontar_stock import descontar_stock


def _validar_id(campo: str, valor: object) -> None:
    if not isinstance(valor, str) or not valor.strip():
        raise ValidacionError("DATO_INVALIDO", f"'{campo}' debe ser texto no vacío")


def _activo(coleccion: Collection, id_documento: str, entidad: str, session: ClientSession) -> dict:
    documento = coleccion.find_one({"_id": id_documento}, session=session)
    if documento is None:
        raise ValidacionError(f"{entidad}_INEXISTENTE", f"no existe {entidad.lower()} {id_documento}")
    if not documento["activo"]:
        raise ValidacionError(f"{entidad}_INACTIVO", f"{entidad.lower()} {id_documento} está inactivo")
    return documento


def _validar_receta(db: Database, id_receta: str, id_cliente: str, session: ClientSession) -> dict:
    receta = db.recetas.find_one({"_id": id_receta}, session=session)
    if receta is None:
        raise ValidacionError("RECETA_INEXISTENTE", f"no existe la receta {id_receta}")
    if receta["id_cliente"] != id_cliente:
        raise ValidacionError("RECETA_DE_OTRO_CLIENTE", f"la receta {id_receta} no pertenece a {id_cliente}")
    if receta["estado"] != "Vigente" or receta["dispensas_realizadas"] >= receta["dispensas_autorizadas"]:
        raise ValidacionError("RECETA_NO_VIGENTE", f"la receta {id_receta} no tiene dispensas vigentes")
    return receta


def _dispensar(db: Database, receta: dict, hoy: date, session: ClientSession) -> None:
    realizadas = receta["dispensas_realizadas"]
    completada = realizadas + 1 == receta["dispensas_autorizadas"]
    resultado = db.recetas.update_one(
        {"_id": receta["_id"], "estado": "Vigente", "dispensas_realizadas": realizadas},
        {
            "$inc": {"dispensas_realizadas": 1},
            "$set": {
                "estado": "Completada" if completada else "Vigente",
                "proxima_dispensa": None if completada else reloj.a_datetime(hoy + timedelta(days=30)),
            },
        },
        session=session,
    )
    if resultado.modified_count != 1:
        raise ValidacionError("RECETA_NO_VIGENTE", f"cambió la disponibilidad de la receta {receta['_id']}")


def _avanzar_contador(db: Database, nombre: str, cantidad: int, session: ClientSession) -> int:
    contador = db.contadores.find_one_and_update(
        {"_id": nombre}, {"$inc": {"ultimo": cantidad}},
        upsert=True, return_document=ReturnDocument.AFTER, session=session,
    )
    return contador["ultimo"]


def registrar_venta(db: Database, id_cliente: str, id_farmaceutico: str, items: list[dict], medio_pago: str,
                    id_receta: str | None = None, driver: Driver | None = None,
                    hoy: date | None = None) -> dict:
    """Registra la venta y devuelve su documento (con lotes_consumidos).

    `items`: [{"id_producto": "PRD003", "cantidad": 50}, ...]. El precio es el de lista vigente.
    `hoy` fija la fecha comercial; por defecto se usa el reloj del sistema.
    Si se pasa `driver`, se intenta sincronizar el grafo después de confirmar la venta.

    Rechaza con: CLIENTE_INEXISTENTE, CLIENTE_INACTIVO, FARMACEUTICO_INEXISTENTE,
    FARMACEUTICO_INACTIVO, SUCURSAL_NO_FARMACIA, PRODUCTO_INEXISTENTE, PRODUCTO_INACTIVO,
    DATO_INVALIDO, MEDIO_PAGO_INVALIDO, RECETA_REQUERIDA, RECETA_INEXISTENTE,
    RECETA_DE_OTRO_CLIENTE, RECETA_NO_VIGENTE o StockInsuficiente.
    """
    _validar_id("id_cliente", id_cliente)
    _validar_id("id_farmaceutico", id_farmaceutico)
    if id_receta is not None:
        _validar_id("id_receta", id_receta)
    if medio_pago not in MEDIOS_PAGO:
        raise ValidacionError("MEDIO_PAGO_INVALIDO", f"medio de pago inválido: {medio_pago!r}")
    if not isinstance(items, list) or not items:
        raise ValidacionError("DATO_INVALIDO", "la venta debe tener al menos un ítem")
    for numero, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValidacionError("DATO_INVALIDO", f"el ítem {numero} debe ser un diccionario")
        _validar_id(f"id_producto del ítem {numero}", item.get("id_producto"))
        cantidad = item.get("cantidad")
        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or not 1 <= cantidad <= INT64_MAX:
            raise ValidacionError("DATO_INVALIDO", f"la cantidad del ítem {numero} debe ser un entero positivo válido")

    hoy = hoy if hoy is not None else reloj.hoy()

    def insertar(session: ClientSession) -> dict:
        _activo(db.clientes, id_cliente, "CLIENTE", session)
        farmaceutico = _activo(db.farmaceuticos, id_farmaceutico, "FARMACEUTICO", session)
        id_sucursal = farmaceutico["id_sucursal"]
        sucursal = db.sucursales.find_one({"_id": id_sucursal}, session=session)
        if sucursal is None or sucursal["tipo"] != "Farmacia" or not sucursal["activo"]:
            raise ValidacionError("SUCURSAL_NO_FARMACIA", f"{id_sucursal} no es una farmacia activa")

        detalle = []
        requiere_receta = False
        for item in items:
            producto = _activo(db.productos, item["id_producto"], "PRODUCTO", session)
            requiere_receta = requiere_receta or producto["condicion_venta"] != "Venta libre"
            precio = producto["precio_unit"]
            cantidad = item["cantidad"]
            detalle.append({
                "id_producto": producto["_id"], "cantidad": cantidad,
                "precio_unit": precio, "subtotal": precio * cantidad,
            })
        total = sum(item["subtotal"] for item in detalle)
        if total > INT64_MAX:
            raise ValidacionError("DATO_INVALIDO", "el importe total excede el rango admitido")
        if requiere_receta and id_receta is None:
            raise ValidacionError("RECETA_REQUERIDA", "la venta incluye productos bajo receta")
        receta = _validar_receta(db, id_receta, id_cliente, session) if id_receta is not None else None

        numero_venta = _avanzar_contador(db, "venta", 1, session)
        ultimo_detalle = _avanzar_contador(db, "detalle", len(detalle), session)
        primer_detalle = ultimo_detalle - len(detalle) + 1
        for numero, item in enumerate(detalle, primer_detalle):
            item["id_detalle"] = f"D{numero:03d}"
        id_venta = f"V{numero_venta:03d}"
        venta = {
            "_id": id_venta, "id_cliente": id_cliente, "id_farmaceutico": id_farmaceutico,
            "id_sucursal": id_sucursal, "id_receta": id_receta, "fecha": reloj.a_datetime(hoy),
            "tipo": "Con receta" if receta is not None else "Venta libre", "medio_pago": medio_pago,
            "total": total, "estado": "Completada", "stock_aplicado": False,
            "lotes_consumidos": None, "items": detalle,
        }
        db.ventas.insert_one(venta, session=session)
        venta["lotes_consumidos"] = descontar_stock(db, id_venta, session=session, hoy=hoy)
        venta["stock_aplicado"] = True

        if receta is not None:
            _dispensar(db, receta, hoy, session)
        outbox.registrar_evento(db, "venta", id_venta, session=session)
        if receta is not None:
            outbox.registrar_evento(db, "receta", receta["_id"], session=session)
        return venta

    venta = en_transaccion(db, insertar)
    if driver is not None:
        outbox.procesar_pendientes(db, driver)
    return venta
