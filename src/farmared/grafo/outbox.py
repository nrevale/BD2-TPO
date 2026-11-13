"""Outbox: sincronización de MongoDB hacia Neo4j sin transacciones distribuidas.

Problema: una escritura (alta de cliente, venta, dispensa de receta) se confirma en
MongoDB y además tiene que verse en el grafo. No hay transacción que abarque los
dos motores; si se escribiera en Neo4j "después" y fallara, el grafo quedaría
desactualizado sin que nadie lo sepa.

Solución (patrón *transactional outbox*):
1. El servicio inserta un evento en la colección `outbox` **dentro de la misma
   transacción de MongoDB** que la escritura. O se confirman los dos o ninguno.
2. Después del commit, `procesar_pendientes` proyecta cada evento en Neo4j (leyendo el
   estado actual de Mongo) y lo marca procesado.
3. Si Neo4j no responde, el evento queda pendiente: `farmared sync` lo reintenta.
   Proyectar es idempotente, así que reintentar nunca duplica nada.

El grafo es **eventualmente consistente**: puede atrasarse, pero nunca pierde una
escritura confirmada. MongoDB nunca consulta el grafo para validar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from neo4j import Driver
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from pymongo.client_session import ClientSession
from pymongo.database import Database

from farmared.grafo import proyeccion

TIPOS = ("cliente", "venta", "receta")


def registrar_evento(db: Database, tipo: str, ref_id: str, session: ClientSession | None = None) -> None:
    """Agrega un evento pendiente. Llamarla con la `session` de la transacción de la escritura."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo de evento inválido: {tipo}")
    db.outbox.insert_one(
        {"tipo": tipo, "ref_id": ref_id, "creado": datetime.now(timezone.utc), "procesado": False},
        session=session,
    )


@dataclass
class ResultadoSync:
    procesados: int = 0
    pendientes: int = 0
    errores: list[str] = field(default_factory=list)


def procesar_pendientes(db: Database, driver: Driver) -> ResultadoSync:
    """Proyecta en Neo4j los eventos pendientes, en orden de creación.

    Si Neo4j no está disponible se detiene (el resto queda pendiente). Un evento
    inválido (id inexistente en Mongo) se registra como error y queda pendiente
    para revisión, sin frenar a los demás.
    """
    resultado = ResultadoSync()
    for evento in db.outbox.find({"procesado": False}).sort("creado", 1):
        try:
            proyeccion.proyectar(db, driver, evento["tipo"], [evento["ref_id"]])
        except (ServiceUnavailable, OSError) as e:
            resultado.errores.append(f"Neo4j no disponible: {e}")
            break
        except (LookupError, Neo4jError) as e:
            resultado.errores.append(f"evento {evento['_id']} ({evento['tipo']} {evento['ref_id']}): {e}")
            continue
        db.outbox.update_one(
            {"_id": evento["_id"]},
            {"$set": {"procesado": True, "procesado_en": datetime.now(timezone.utc)}},
        )
        resultado.procesados += 1
    resultado.pendientes = db.outbox.count_documents({"procesado": False})
    return resultado


def reconstruir_grafo(db: Database, driver: Driver) -> dict:
    """Reconstruye el grafo completo y da por procesados los eventos que ya estaban pendientes.

    Solo se marcan los eventos anteriores al inicio: uno que llegue durante la
    reconstrucción queda pendiente y lo toma el próximo `sync`.
    """
    previos = [e["_id"] for e in db.outbox.find({"procesado": False}, {"_id": 1})]
    conteo = proyeccion.reconstruir(db, driver)
    if previos:
        db.outbox.update_many(
            {"_id": {"$in": previos}},
            {"$set": {"procesado": True, "procesado_en": datetime.now(timezone.utc)}},
        )
    return conteo
