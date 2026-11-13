"""Conexión a Neo4j (proyección de relaciones, reconstruible desde MongoDB)."""

from __future__ import annotations

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from farmared.config import cargar_config
from farmared.errores import ConexionError

_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        cfg = cargar_config()
        _driver = GraphDatabase.driver(cfg.neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password))
    return _driver


def estado() -> dict:
    """Verifica conectividad y ejecuta una consulta trivial. Lanza ConexionError si falla."""
    try:
        driver = get_driver()
        driver.verify_connectivity()
        info = driver.get_server_info()
        records, _, _ = driver.execute_query("RETURN 1 AS ok")
    except (ServiceUnavailable, Neo4jError, OSError) as e:
        detalle = str(e).splitlines()[0] if str(e) else type(e).__name__
        raise ConexionError(f"Neo4j no responde: {detalle}") from e
    return {"version": info.agent, "ok": records[0]["ok"] == 1}


def cerrar() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
