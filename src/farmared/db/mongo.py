"""Conexión a MongoDB (fuente de verdad del sistema).

Se usa un único `MongoClient` por proceso: las transacciones multi-documento
(q13, q14, q15) abren sesiones con `get_client().start_session()`.
"""

from __future__ import annotations

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from farmared.config import cargar_config
from farmared.errores import ConexionError

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        cfg = cargar_config()
        _client = MongoClient(
            cfg.mongo_uri,
            serverSelectionTimeoutMS=5000,
            w="majority",
        )
    return _client


def get_db() -> Database:
    return get_client()[cargar_config().mongo_db]


def estado() -> dict:
    """Ping + estado del replica set. Lanza ConexionError si no responde."""
    try:
        hello = get_client().admin.command("hello")
    except PyMongoError as e:
        detalle = str(e).split(" (configured")[0]
        raise ConexionError(f"MongoDB no responde: {detalle}") from e
    return {
        "replica_set": hello.get("setName"),
        "primario": bool(hello.get("isWritablePrimary")),
        "version": get_client().server_info().get("version"),
    }


def cerrar() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
