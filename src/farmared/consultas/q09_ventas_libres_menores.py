"""q09 — Ventas de tipo 'Venta libre' con total menor a $5.000 (excluyendo anuladas).

Motor: MongoDB.
Relación entre entidades: Filtro sobre ventas (sin cruces).

Parámetros: db: Database
Retorno: list[dict] —
    id_venta, fecha, id_cliente, id_farmaceutico, total, estado.
"""

from __future__ import annotations

from pymongo.database import Database

from farmared.consultas._comun import fechas_a_date

MOTOR = "mongo"
TOPE = 5000

FILTRO = {"tipo": "Venta libre", "total": {"$lt": TOPE}, "estado": {"$ne": "Anulada"}}
# Todos los campos como expresión: así se respeta el orden pedido (con 1 quedaría el del documento).
PROYECCION = {"_id": 0, "id_venta": "$_id", "fecha": "$fecha", "id_cliente": "$id_cliente",
              "id_farmaceutico": "$id_farmaceutico", "total": "$total", "estado": "$estado"}


def ejecutar(db: Database) -> list[dict]:
    filas = list(db.ventas.find(FILTRO, PROYECCION).sort([("fecha", 1), ("_id", 1)]))
    return fechas_a_date(filas, "fecha")
