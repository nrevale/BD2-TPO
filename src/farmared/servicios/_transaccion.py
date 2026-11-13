"""Transacciones multi-documento de MongoDB para los servicios de escritura (q13, q14, q15).

`with_transaction` hace commit si la función termina bien, aborta si lanza una excepción y
**reintenta** la función completa ante errores transitorios (`TransientTransactionError`,
por ejemplo un *write conflict* con otra transacción que tocó el mismo documento). Por eso la
función no debe tener efectos fuera de la sesión: en el reintento vuelve a leer y a decidir.

- read concern `snapshot`: todas las lecturas ven una foto consistente de la base.
- write concern `majority`: el commit se confirma cuando lo tiene la mayoría del replica set.
"""

from __future__ import annotations

from typing import Callable, TypeVar

from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

T = TypeVar("T")

OPCIONES = {"read_concern": ReadConcern("snapshot"), "write_concern": WriteConcern("majority")}


def en_transaccion(db: Database, funcion: Callable[[ClientSession], T]) -> T:
    """Abre una sesión, corre `funcion(session)` en una transacción y devuelve su resultado."""
    with db.client.start_session() as session:
        return session.with_transaction(funcion, **OPCIONES)
