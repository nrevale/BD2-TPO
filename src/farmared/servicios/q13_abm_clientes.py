"""q13 — ABM completo de clientes: alta (validando DNI único), modificación de datos de
contacto y cobertura, y baja lógica.

Motor: MongoDB (colección `clientes`, índice único `dni_unico`). El cambio se proyecta al
grafo con un evento de outbox ("cliente") registrado en la misma transacción.

Relación entre entidades: el cliente es un documento propio con `_id` = id natural ("C019").
Las recetas y ventas lo referencian por `id_cliente`; por eso nunca se borra (baja lógica).

Cómo se garantiza la consistencia:
- Cada operación corre en una transacción multi-documento (`with_transaction`): la escritura
  en `clientes`, el avance del contador `cliente` y el evento de `outbox` se confirman juntos
  o no se confirma ninguno.
- DNI único en dos niveles: un pre-chequeo para dar un mensaje claro, y el índice único
  `dni_unico` para la condición de carrera (dos altas simultáneas con el mismo DNI: una
  recibe `DuplicateKeyError` y se informa como DNI_DUPLICADO).
- Después del commit, si viene `driver`, se proyecta el outbox en Neo4j. Si no, el evento
  queda pendiente para `farmared sync`.

Parámetros: `db` (Database), `datos` / `id_cliente` / `cambios` según la operación,
`driver` (opcional).
Retorno: `alta` → id del cliente nuevo; `modificar` → cliente actualizado (dict con
`id_cliente`); `baja` → None.
Errores (`ValidacionError.codigo`): DATO_INVALIDO, DNI_DUPLICADO, CAMPO_NO_MODIFICABLE,
CLIENTE_INEXISTENTE.
"""

from __future__ import annotations

import re

from neo4j import Driver
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from farmared.carga.tablas import OBRAS_SOCIALES
from farmared.errores import ValidacionError
from farmared.grafo import outbox
from farmared.servicios._transaccion import en_transaccion

CAMPOS_ALTA = ("nombre", "apellido", "dni", "email", "telefono", "ciudad", "provincia", "obra_social", "nro_afiliado")
CAMPOS_MODIFICABLES = ("email", "telefono", "ciudad", "provincia", "obra_social", "nro_afiliado")

SIN_COBERTURA = "Sin cobertura"
_DNI = re.compile(r"\d{7,8}")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_TELEFONO = re.compile(r"\d{6,15}")


# --- Validaciones ---------------------------------------------------------------------------

def _texto(campo: str, valor) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValidacionError("DATO_INVALIDO", f"'{campo}' es obligatorio y debe ser texto")
    return valor.strip()


def _normalizar(campo: str, valor):
    """Limpia y valida un campo del cliente. Devuelve el valor a guardar."""
    if campo == "nro_afiliado":
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return None
        return _texto(campo, valor)
    valor = _texto(campo, valor)
    if campo == "dni" and not _DNI.fullmatch(valor):
        raise ValidacionError("DATO_INVALIDO", f"DNI inválido: '{valor}' (7 u 8 dígitos, sin puntos)")
    if campo == "email" and not _EMAIL.fullmatch(valor):
        raise ValidacionError("DATO_INVALIDO", f"email inválido: '{valor}'")
    if campo == "telefono" and not _TELEFONO.fullmatch(valor):
        raise ValidacionError("DATO_INVALIDO", f"teléfono inválido: '{valor}' (solo dígitos)")
    if campo == "obra_social" and valor not in OBRAS_SOCIALES:
        raise ValidacionError("DATO_INVALIDO",
                              f"obra social inexistente: '{valor}' (válidas: {', '.join(OBRAS_SOCIALES)})")
    return valor


def _validar_cobertura(obra_social: str, nro_afiliado: str | None) -> None:
    """Misma regla que la carga: con cobertura hay número de afiliado; sin cobertura, no."""
    if obra_social == SIN_COBERTURA and nro_afiliado is not None:
        raise ValidacionError("DATO_INVALIDO", "un cliente 'Sin cobertura' no puede tener nro_afiliado")
    if obra_social != SIN_COBERTURA and nro_afiliado is None:
        raise ValidacionError("DATO_INVALIDO", f"un cliente con {obra_social} necesita nro_afiliado")


def _como_resultado(doc: dict) -> dict:
    """Documento de Mongo -> dict del contrato (id_cliente en lugar de _id)."""
    return {"id_cliente": doc["_id"], **{k: v for k, v in doc.items() if k != "_id"}}


def _proyectar(db: Database, driver: Driver | None) -> None:
    if driver is not None:
        outbox.procesar_pendientes(db, driver)


# --- Operaciones ----------------------------------------------------------------------------

def alta(db: Database, datos: dict, driver: Driver | None = None) -> str:
    """Da de alta un cliente activo con un id nuevo (contador 'cliente'). Devuelve el id ("C019").

    Rechaza con DATO_INVALIDO (campos faltantes, obra social inexistente, nro_afiliado
    incoherente con la cobertura) o DNI_DUPLICADO (incluye clientes dados de baja).
    """
    if not isinstance(datos, dict):
        raise ValidacionError("DATO_INVALIDO", "los datos del cliente deben ser un diccionario")
    desconocidos = sorted(set(datos) - set(CAMPOS_ALTA))
    if desconocidos:
        raise ValidacionError("DATO_INVALIDO", f"campos desconocidos: {', '.join(desconocidos)}")
    cliente = {campo: _normalizar(campo, datos.get(campo)) for campo in CAMPOS_ALTA}
    _validar_cobertura(cliente["obra_social"], cliente["nro_afiliado"])

    # Pre-chequeo (mensaje claro). La garantía real es el índice único, dentro de la transacción.
    previo = db.clientes.find_one({"dni": cliente["dni"]}, {"_id": 1, "activo": 1})
    if previo is not None:
        estado = "activo" if previo["activo"] else "dado de baja"
        raise ValidacionError("DNI_DUPLICADO", f"el DNI {cliente['dni']} ya es del cliente {previo['_id']} ({estado})")

    def insertar(session) -> str:
        contador = db.contadores.find_one_and_update(
            {"_id": "cliente"}, {"$inc": {"ultimo": 1}},
            upsert=True, return_document=ReturnDocument.AFTER, session=session,
        )
        id_cliente = f"C{contador['ultimo']:03d}"
        db.clientes.insert_one({"_id": id_cliente, **cliente, "activo": True}, session=session)
        outbox.registrar_evento(db, "cliente", id_cliente, session=session)
        return id_cliente

    try:
        id_cliente = en_transaccion(db, insertar)
    except DuplicateKeyError as e:
        # Carrera: otra alta con el mismo DNI se confirmó entre el pre-chequeo y el insert.
        raise ValidacionError("DNI_DUPLICADO", f"el DNI {cliente['dni']} ya está registrado") from e
    _proyectar(db, driver)
    return id_cliente


def modificar(db: Database, id_cliente: str, cambios: dict, driver: Driver | None = None) -> dict:
    """Modifica datos de contacto y cobertura (solo CAMPOS_MODIFICABLES). Devuelve el cliente actualizado.

    Rechaza con CLIENTE_INEXISTENTE, CAMPO_NO_MODIFICABLE o DATO_INVALIDO.
    """
    if not isinstance(cambios, dict) or not cambios:
        raise ValidacionError("DATO_INVALIDO", "no se indicó ningún cambio")
    prohibidos = sorted(set(cambios) - set(CAMPOS_MODIFICABLES))
    if prohibidos:
        raise ValidacionError("CAMPO_NO_MODIFICABLE",
                              f"no se puede modificar: {', '.join(prohibidos)} "
                              f"(modificables: {', '.join(CAMPOS_MODIFICABLES)})")
    nuevos = {campo: _normalizar(campo, valor) for campo, valor in cambios.items()}

    def actualizar(session) -> dict:
        actual = db.clientes.find_one({"_id": id_cliente}, session=session)
        if actual is None:
            raise ValidacionError("CLIENTE_INEXISTENTE", f"no existe el cliente {id_cliente}")
        # La coherencia obra social / afiliado se valida sobre el resultado final.
        final = {**actual, **nuevos}
        _validar_cobertura(final["obra_social"], final["nro_afiliado"])
        db.clientes.update_one({"_id": id_cliente}, {"$set": nuevos}, session=session)
        outbox.registrar_evento(db, "cliente", id_cliente, session=session)
        return final

    final = en_transaccion(db, actualizar)
    _proyectar(db, driver)
    return _como_resultado(final)


def baja(db: Database, id_cliente: str, driver: Driver | None = None) -> None:
    """Baja lógica (activo = False). No borra nada. Repetirla no falla.

    Rechaza con CLIENTE_INEXISTENTE.
    """

    def dar_de_baja(session) -> bool:
        actual = db.clientes.find_one({"_id": id_cliente}, {"activo": 1}, session=session)
        if actual is None:
            raise ValidacionError("CLIENTE_INEXISTENTE", f"no existe el cliente {id_cliente}")
        if not actual["activo"]:
            return False  # ya estaba dado de baja: no hay nada que escribir ni proyectar
        db.clientes.update_one({"_id": id_cliente}, {"$set": {"activo": False}}, session=session)
        outbox.registrar_evento(db, "cliente", id_cliente, session=session)
        return True

    if en_transaccion(db, dar_de_baja):
        _proyectar(db, driver)
