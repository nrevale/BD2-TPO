"""Carga reproducible e idempotente de MongoDB a partir de los CSV.

Estrategia: **borrar y recargar**. Cada ejecución:
1. Lee y valida `data/originales/` + `data/extra/` (sin tocar la base).
2. Si no hay errores, borra la base, crea colecciones/validadores/índices/vista.
3. Inserta todos los documentos en **una transacción**: o se cargan todos o ninguno.

Correrla N veces deja siempre el mismo estado (para la misma fecha de carga, que
resuelve las fechas relativas de los registros extra).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pymongo import MongoClient

from farmared import reloj
from farmared.carga.esquema import crear_esquema
from farmared.carga.tablas import TABLAS
from farmared.carga.validacion import Datasets, leer_datasets, validar

RAIZ_DATOS = Path(os.environ.get("FARMARED_DATA", Path(__file__).resolve().parents[3] / "data"))

# Prefijo de cada id natural, para inicializar los contadores de nuevos registros.
PREFIJOS = {"venta": ("ventas", "V"), "detalle": ("detalle_ventas", "D"), "cliente": ("clientes", "C")}


@dataclass
class ResumenCarga:
    hoy: date
    conteos: dict[str, dict[str, int]]  # tabla -> {"originales", "extra"}
    documentos: dict[str, int]  # colección -> cantidad insertada
    avisos: list[str]


def directorios_por_defecto() -> dict[str, Path]:
    return {"originales": RAIZ_DATOS / "originales", "extra": RAIZ_DATOS / "extra"}


def _fecha(d: date | None):
    return reloj.a_datetime(d) if d is not None else None


def _con_id(datos: dict, clave: str) -> dict:
    doc = {"_id": datos[clave]}
    doc.update({k: v for k, v in datos.items() if k != clave})
    return doc


def construir_documentos(ds: Datasets) -> dict[str, list[dict]]:
    """Transforma las filas en documentos MongoDB (id natural como _id, fechas como Date).

    Ventas: los ítems de detalle_ventas se **embeben** en la venta, y se agrega
    `id_sucursal` (sucursal del farmacéutico al momento de la venta: referencia
    extendida, evita un $lookup en las consultas por sucursal).
    """
    docs: dict[str, list[dict]] = {}
    for nombre in ("clientes", "sucursales", "farmaceuticos", "proveedores", "productos"):
        docs[nombre] = [_con_id(d, TABLAS[nombre].clave) for d in ds.datos(nombre)]

    docs["stock_lotes"] = [
        {**_con_id(d, "id_lote"), "vencimiento": _fecha(d["vencimiento"])} for d in ds.datos("stock_lotes")
    ]
    docs["recetas"] = [
        {
            **_con_id(d, "id_receta"),
            "fecha_emision": _fecha(d["fecha_emision"]),
            "proxima_dispensa": _fecha(d["proxima_dispensa"]),
        }
        for d in ds.datos("recetas")
    ]

    sucursal_de = {f["id_farmaceutico"]: f["id_sucursal"] for f in ds.datos("farmaceuticos")}
    items_de: dict[str, list[dict]] = {}
    for d in ds.datos("detalle_ventas"):
        items_de.setdefault(d["id_venta"], []).append({
            "id_detalle": d["id_detalle"],
            "id_producto": d["id_producto"],
            "cantidad": d["cantidad"],
            "precio_unit": d["precio_unit"],
            "subtotal": d["cantidad"] * d["precio_unit"],
        })
    docs["ventas"] = [
        {
            **_con_id(d, "id_venta"),
            "fecha": _fecha(d["fecha"]),
            "id_sucursal": sucursal_de[d["id_farmaceutico"]],
            "items": items_de[d["id_venta"]],
            # Las ventas históricas Completada ya están reflejadas en el stock del CSV:
            # se marcan aplicadas para que q15 no las descuente otra vez. Qué lotes
            # consumieron no se conoce (null).
            "stock_aplicado": d["estado"] == "Completada",
            "lotes_consumidos": None,
        }
        for d in ds.datos("ventas")
    ]

    docs["contadores"] = []
    for nombre_contador, (tabla, prefijo) in PREFIJOS.items():
        clave = TABLAS[tabla].clave
        numeros = [int(m.group(1)) for d in ds.datos(tabla) if (m := re.fullmatch(rf"{prefijo}(\d+)", d[clave]))]
        docs["contadores"].append({"_id": nombre_contador, "ultimo": max(numeros, default=0)})
    return docs


def cargar(client: MongoClient, nombre_db: str, directorios: dict[str, Path] | None = None,
           hoy: date | None = None) -> ResumenCarga:
    """Valida los CSV y recarga la base desde cero. No escribe nada si la validación falla."""
    hoy = hoy or reloj.hoy()
    ds = leer_datasets(directorios or directorios_por_defecto(), hoy)
    avisos = validar(ds)
    docs = construir_documentos(ds)

    client.drop_database(nombre_db)
    db = client[nombre_db]
    crear_esquema(db)

    def insertar_todo(session):
        for coleccion, documentos in docs.items():
            if documentos:
                db[coleccion].insert_many(documentos, session=session)

    with client.start_session() as session:
        session.with_transaction(insertar_todo)

    return ResumenCarga(
        hoy=hoy,
        conteos=ds.conteo_por_origen,
        documentos={c: len(d) for c, d in docs.items()},
        avisos=avisos,
    )
