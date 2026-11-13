"""q06 — Recetas de tratamiento prolongado 'Vigente' cuya próxima dispensa es anterior a hoy, con los datos del cliente.

Motor: MongoDB.
Relación entre entidades: $lookup de recetas a clientes.

Parámetros: db: Database, hoy: date | None = None
Retorno: list[dict] —
    id_receta, fecha_emision, proxima_dispensa, dispensas_realizadas, dispensas_autorizadas,
    medico, cliente {id_cliente, nombre, apellido, dni, telefono, email, obra_social}.
    Orden por proxima_dispensa.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from datetime import date

from pymongo.database import Database

MOTOR = "mongo"


def ejecutar(db: Database, hoy: date | None = None) -> list[dict]:
    raise NotImplementedError("q06 todavía no está implementada")
