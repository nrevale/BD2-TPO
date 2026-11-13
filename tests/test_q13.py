"""q13 — ABM de clientes. Requiere MongoDB (y Neo4j para el test de proyección)."""

from __future__ import annotations

import threading

import pytest

from farmared.errores import ValidacionError
from farmared.grafo import outbox
from farmared.servicios import q13_abm_clientes as q13

NUEVO = {
    "nombre": "Valentina", "apellido": "Ruiz Díaz", "dni": "45123456", "email": "valen.rd@gmail.com",
    "telefono": "1155667788", "ciudad": "San Isidro", "provincia": "Buenos Aires",
    "obra_social": "OSDE", "nro_afiliado": "OS-451234",
}


@pytest.fixture
def db(mongo_client):
    """Base recién cargada para cada test (los servicios escriben)."""
    from farmared.carga import cargar_mongo

    cargar_mongo.cargar(mongo_client, "farmared_test")
    return mongo_client["farmared_test"]


def _eventos(db, id_cliente):
    return list(db.outbox.find({"tipo": "cliente", "ref_id": id_cliente}))


def _codigo(excinfo) -> str:
    return excinfo.value.codigo


# --- Alta -----------------------------------------------------------------------------------

def test_alta_genera_id_con_contador_y_evento(db):
    id_cliente = q13.alta(db, NUEVO)
    assert id_cliente == "C019"
    doc = db.clientes.find_one({"_id": "C019"})
    assert doc == {"_id": "C019", **NUEVO, "activo": True}
    assert db.contadores.find_one({"_id": "cliente"})["ultimo"] == 19
    assert len(_eventos(db, "C019")) == 1  # pendiente para sync (no se pasó driver)
    assert q13.alta(db, {**NUEVO, "dni": "45123457"}) == "C020"


def test_alta_sin_cobertura_normaliza_afiliado_vacio(db):
    id_cliente = q13.alta(db, {**NUEVO, "obra_social": "Sin cobertura", "nro_afiliado": "  "})
    assert db.clientes.find_one({"_id": id_cliente})["nro_afiliado"] is None


@pytest.mark.parametrize("dni,dueno", [("31245678", "C001"), ("25678901", "C008")])
def test_alta_rechaza_dni_duplicado_incluso_de_inactivos(db, dni, dueno):
    with pytest.raises(ValidacionError) as e:
        q13.alta(db, {**NUEVO, "dni": dni})
    assert _codigo(e) == "DNI_DUPLICADO"
    assert dueno in e.value.mensaje
    assert db.clientes.count_documents({}) == 18
    assert db.contadores.find_one({"_id": "cliente"})["ultimo"] == 18
    assert db.outbox.count_documents({}) == 0


@pytest.mark.parametrize("cambio", [
    {"nombre": None},                                       # falta un campo
    {"email": "sin-arroba"},
    {"dni": "31.245.678"},                                  # con puntos
    {"telefono": "11-5566"},
    {"obra_social": "Medicus"},                             # obra social inexistente
    {"nro_afiliado": None},                                 # OSDE sin afiliado
    {"obra_social": "Sin cobertura"},                       # sin cobertura con afiliado
    {"activo": False},                                      # campo que no se elige en el alta
])
def test_alta_rechaza_datos_invalidos(db, cambio):
    with pytest.raises(ValidacionError) as e:
        q13.alta(db, {**NUEVO, **cambio})
    assert _codigo(e) == "DATO_INVALIDO"
    assert db.clientes.count_documents({}) == 18


def test_altas_simultaneas_con_el_mismo_dni(db):
    """Varias altas a la vez con el mismo DNI: el índice único deja pasar una sola."""
    n = 5
    barrera = threading.Barrier(n)
    resultados: list[str] = []

    def alta():
        barrera.wait()
        try:
            resultados.append(q13.alta(db, NUEVO))
        except ValidacionError as e:
            resultados.append(e.codigo)

    hilos = [threading.Thread(target=alta) for _ in range(n)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(resultados) == ["C019"] + ["DNI_DUPLICADO"] * (n - 1)
    assert db.clientes.count_documents({"dni": NUEVO["dni"]}) == 1
    # Las altas abortadas no consumieron números del contador.
    assert db.contadores.find_one({"_id": "cliente"})["ultimo"] == 19


# --- Modificación ---------------------------------------------------------------------------

def test_modificar_datos_de_contacto(db):
    antes = db.clientes.find_one({"_id": "C001"})
    resultado = q13.modificar(db, "C001", {"email": "lucia.fernandez@outlook.com", "telefono": "1144556677"})
    assert resultado["id_cliente"] == "C001"
    assert resultado["email"] == "lucia.fernandez@outlook.com"
    despues = db.clientes.find_one({"_id": "C001"})
    assert despues == {**antes, "email": "lucia.fernandez@outlook.com", "telefono": "1144556677"}
    assert len(_eventos(db, "C001")) == 1


def test_modificar_cobertura_a_sin_cobertura(db):
    q13.modificar(db, "C001", {"obra_social": "Sin cobertura", "nro_afiliado": ""})
    doc = db.clientes.find_one({"_id": "C001"})
    assert (doc["obra_social"], doc["nro_afiliado"]) == ("Sin cobertura", None)


def test_modificar_rechaza_cobertura_incoherente_sin_tocar_nada(db):
    antes = db.clientes.find_one({"_id": "C001"})
    with pytest.raises(ValidacionError) as e:
        q13.modificar(db, "C001", {"obra_social": "Sin cobertura"})  # le queda el nro de OSDE
    assert _codigo(e) == "DATO_INVALIDO"
    with pytest.raises(ValidacionError) as e:
        q13.modificar(db, "C005", {"obra_social": "PAMI"})  # pasa a PAMI sin nro de afiliado
    assert _codigo(e) == "DATO_INVALIDO"
    assert db.clientes.find_one({"_id": "C001"}) == antes
    assert db.outbox.count_documents({}) == 0


@pytest.mark.parametrize("campo", ["dni", "nombre", "apellido", "activo", "_id"])
def test_modificar_rechaza_campos_no_modificables(db, campo):
    with pytest.raises(ValidacionError) as e:
        q13.modificar(db, "C001", {campo: "x"})
    assert _codigo(e) == "CAMPO_NO_MODIFICABLE"


def test_modificar_rechaza_cliente_inexistente_y_cambios_vacios(db):
    with pytest.raises(ValidacionError) as e:
        q13.modificar(db, "C999", {"email": "a@b.com"})
    assert _codigo(e) == "CLIENTE_INEXISTENTE"
    with pytest.raises(ValidacionError) as e:
        q13.modificar(db, "C001", {})
    assert _codigo(e) == "DATO_INVALIDO"


# --- Baja -----------------------------------------------------------------------------------

def test_baja_logica_es_idempotente_y_no_borra(db):
    recetas, ventas = db.recetas.count_documents({"id_cliente": "C001"}), db.ventas.count_documents({"id_cliente": "C001"})
    q13.baja(db, "C001")
    q13.baja(db, "C001")  # la segunda no falla
    doc = db.clientes.find_one({"_id": "C001"})
    assert doc is not None and doc["activo"] is False
    assert db.clientes.count_documents({}) == 18
    assert db.recetas.count_documents({"id_cliente": "C001"}) == recetas
    assert db.ventas.count_documents({"id_cliente": "C001"}) == ventas
    assert len(_eventos(db, "C001")) == 1  # la segunda baja no escribió nada


def test_baja_de_cliente_inexistente(db):
    with pytest.raises(ValidacionError) as e:
        q13.baja(db, "C999")
    assert _codigo(e) == "CLIENTE_INEXISTENTE"


# --- Proyección en el grafo -----------------------------------------------------------------

def test_abm_se_proyecta_en_neo4j(db, neo4j_driver):
    outbox.reconstruir_grafo(db, neo4j_driver)

    def nodo(id_cliente):
        registros = neo4j_driver.execute_query(
            "MATCH (c:Cliente {id: $id}) RETURN c.activo AS activo, c.obra_social AS os", id=id_cliente).records
        return registros[0].data() if registros else None

    id_cliente = q13.alta(db, NUEVO, driver=neo4j_driver)
    assert nodo(id_cliente) == {"activo": True, "os": "OSDE"}
    q13.modificar(db, id_cliente, {"obra_social": "Galeno", "nro_afiliado": "GA-451234"}, driver=neo4j_driver)
    assert nodo(id_cliente) == {"activo": True, "os": "Galeno"}
    q13.baja(db, id_cliente, driver=neo4j_driver)
    assert nodo(id_cliente) == {"activo": False, "os": "Galeno"}
    assert db.outbox.count_documents({"procesado": False}) == 0
