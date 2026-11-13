"""q13 — ABM completo de clientes: alta (validando DNI único), modificación de datos de
contacto y cobertura, y baja lógica.

Motor: MongoDB (colección `clientes`, índice único `dni_unico`). El cambio se proyecta al
grafo con un evento de outbox ("cliente") registrado en la misma transacción.

Estado: pendiente de implementar.
"""

from __future__ import annotations

from neo4j import Driver
from pymongo.database import Database

CAMPOS_ALTA = ("nombre", "apellido", "dni", "email", "telefono", "ciudad", "provincia", "obra_social", "nro_afiliado")
CAMPOS_MODIFICABLES = ("email", "telefono", "ciudad", "provincia", "obra_social", "nro_afiliado")


def alta(db: Database, datos: dict, driver: Driver | None = None) -> str:
    """Da de alta un cliente activo con un id nuevo (contador 'cliente'). Devuelve el id ("C019").

    Rechaza con DATO_INVALIDO (campos faltantes, obra social inexistente, nro_afiliado
    incoherente con la cobertura) o DNI_DUPLICADO (incluye clientes dados de baja).
    """
    raise NotImplementedError("q13 alta todavía no está implementada")


def modificar(db: Database, id_cliente: str, cambios: dict, driver: Driver | None = None) -> dict:
    """Modifica datos de contacto y cobertura (solo CAMPOS_MODIFICABLES). Devuelve el cliente actualizado.

    Rechaza con CLIENTE_INEXISTENTE, CAMPO_NO_MODIFICABLE o DATO_INVALIDO.
    """
    raise NotImplementedError("q13 modificar todavía no está implementada")


def baja(db: Database, id_cliente: str, driver: Driver | None = None) -> None:
    """Baja lógica (activo = False). No borra nada. Repetirla no falla.

    Rechaza con CLIENTE_INEXISTENTE.
    """
    raise NotImplementedError("q13 baja todavía no está implementada")
