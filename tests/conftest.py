"""Configuración común de los tests.

- "Hoy" queda fijo en 2026-11-13: las fechas relativas de los extra se resuelven contra
  esa fecha y los resultados son deterministas.
- Los tests usan la base `farmared_test`, nunca la de desarrollo.
- Los tests que necesitan MongoDB se saltean si no está levantado.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

HOY_TESTS = date(2026, 11, 13)
os.environ["FARMARED_HOY"] = HOY_TESTS.isoformat()
os.environ["MONGO_DB"] = "farmared_test"


@pytest.fixture(scope="session")
def mongo_client():
    from farmared.db import mongo
    from farmared.errores import ConexionError

    try:
        mongo.estado()
    except ConexionError as e:
        pytest.skip(f"MongoDB no disponible: {e}")
    yield mongo.get_client()
    mongo.cerrar()


@pytest.fixture(scope="module")
def db(mongo_client):
    """Base recién cargada (originales + extra) para el módulo de tests."""
    from farmared.carga import cargar_mongo

    cargar_mongo.cargar(mongo_client, "farmared_test")
    return mongo_client["farmared_test"]
