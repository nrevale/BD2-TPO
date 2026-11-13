"""Contratos entre partes del sistema: nombres de módulos, motores y firmas.

Si una firma cambia, este test falla: avisar al equipo antes de modificarlo.
No necesita ningún motor.
"""

from __future__ import annotations

import inspect

import pytest

from farmared import consultas
from farmared.servicios import q13_abm_clientes, q14_registrar_venta, q15_descontar_stock

FIRMAS_CONSULTAS = {
    1: ("mongo", ["db"]),
    2: ("mongo", ["db"]),
    3: ("neo4j", ["driver", "id_cliente"]),
    4: ("mongo", ["db"]),
    5: ("neo4j", ["driver", "hoy"]),
    6: ("mongo", ["db", "hoy"]),
    7: ("mongo", ["db"]),
    8: ("mongo", ["db", "hoy"]),
    9: ("mongo", ["db"]),
    10: ("neo4j", ["driver", "id_sucursal"]),
    11: ("mongo", ["db", "hoy"]),
    12: ("neo4j", ["driver", "hoy"]),
}


def _parametros(funcion) -> list[str]:
    return list(inspect.signature(funcion).parameters)


def test_registro_tiene_las_12_consultas():
    assert sorted(consultas.REGISTRO) == list(range(1, 13))
    for numero, nombre in consultas.REGISTRO.items():
        assert nombre.startswith(f"q{numero:02d}_")


@pytest.mark.parametrize("numero", range(1, 13))
def test_firma_de_cada_consulta(numero):
    modulo = consultas.obtener(numero)
    motor, parametros = FIRMAS_CONSULTAS[numero]
    assert modulo.MOTOR == motor
    assert _parametros(modulo.ejecutar) == parametros
    if "hoy" in parametros:
        assert inspect.signature(modulo.ejecutar).parameters["hoy"].default is None
    assert modulo.__doc__ and "Motor:" in modulo.__doc__


def test_consulta_inexistente():
    with pytest.raises(KeyError):
        consultas.obtener(13)


def test_firmas_de_servicios():
    assert _parametros(q13_abm_clientes.alta) == ["db", "datos", "driver"]
    assert _parametros(q13_abm_clientes.modificar) == ["db", "id_cliente", "cambios", "driver"]
    assert _parametros(q13_abm_clientes.baja) == ["db", "id_cliente", "driver"]
    assert _parametros(q15_descontar_stock.descontar_stock) == ["db", "id_venta", "session", "hoy"]
    assert _parametros(q14_registrar_venta.registrar_venta) == [
        "db", "id_cliente", "id_farmaceutico", "items", "medio_pago", "id_receta", "driver", "hoy",
    ]
