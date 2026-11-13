"""Validación de datasets: no necesita ningún motor."""

from __future__ import annotations

import shutil
from datetime import date

import pytest

from farmared.carga.cargar_mongo import directorios_por_defecto
from farmared.carga.lector_csv import ErrorDatasets, resolver_fecha
from farmared.carga.tablas import TABLAS
from farmared.carga.validacion import leer_datasets, validar
from tests.conftest import HOY_TESTS


def _cargar(directorios=None):
    ds = leer_datasets(directorios or directorios_por_defecto(), HOY_TESTS)
    return ds, validar(ds)


def test_datasets_reales_son_validos_y_tienen_10_extra_por_tabla():
    ds, _ = _cargar()
    for nombre in TABLAS:
        assert ds.conteo_por_origen[nombre]["extra"] >= 10, nombre


def test_avisos_de_historia_esperados():
    _, avisos = _cargar()
    texto = "\n".join(avisos)
    assert "V001 atendida por F004" in texto
    assert "V014 incluye PRD012" in texto
    assert "RC002 tiene próxima dispensa 2026-09-15" in texto


@pytest.mark.parametrize(
    "valor, esperado",
    [
        ("2026-10-13", date(2026, 10, 13)),
        ("@hoy", date(2026, 11, 13)),
        ("@hoy-5", date(2026, 11, 8)),
        ("@hoy+30", date(2026, 12, 13)),
        ("@mes", date(2026, 11, 1)),
    ],
)
def test_fechas_relativas(valor, esperado):
    assert resolver_fecha(valor, HOY_TESTS) == esperado


# --- Casos de rechazo: se copia originales/ y se altera una línea ---------------------------

@pytest.fixture
def copia_originales(tmp_path):
    destino = tmp_path / "originales"
    shutil.copytree(directorios_por_defecto()["originales"], destino)
    return destino


def _reemplazar(directorio, archivo, viejo, nuevo):
    ruta = directorio / archivo
    texto = ruta.read_text(encoding="utf-8")
    assert viejo in texto, f"'{viejo}' no está en {archivo}"
    ruta.write_text(texto.replace(viejo, nuevo, 1), encoding="utf-8")


@pytest.mark.parametrize(
    "archivo, viejo, nuevo, mensaje",
    [
        ("clientes.csv", "C002,Martín,Gómez,28765432", "C002,Martín,Gómez,31245678", "dni '31245678' duplicado"),
        ("ventas.csv", "V002,C005,F005", "V002,C099,F005", "id_cliente 'C099' no existe"),
        ("ventas.csv", "Débito,5750,Completada", "Débito,5751,Completada", "distinto de la suma de ítems"),
        ("productos.csv", "Venta libre,2800", "Libre,2800", "condicion_venta 'Libre'"),
        ("detalle_ventas.csv", "D002,V002,PRD011", "D002,V002,PRD003", "PRD003 es bajo receta"),
        ("ventas.csv", "V002,C005,F005", "V002,C005,F007", "registrada en S005 (Droguería)"),
        ("clientes.csv", "Sin cobertura,,True", "Sin cobertura,X-1,True", "sin cobertura con nro_afiliado"),
        ("stock_lotes.csv", "L-2501A,120,", "L-2501A,-1,", "unidades negativas"),
        ("ventas.csv", "C004,F004,RC007", "C001,F004,RC007", "la receta RC007 es de C004"),
        ("productos.csv", "2800,PRV001", "2800.5,PRV001", "no es un entero"),
    ],
)
def test_errores_rechazan_la_carga(copia_originales, archivo, viejo, nuevo, mensaje):
    _reemplazar(copia_originales, archivo, viejo, nuevo)
    with pytest.raises(ErrorDatasets) as exc:
        _cargar({"originales": copia_originales})
    assert any(mensaje in e for e in exc.value.errores), exc.value.errores
