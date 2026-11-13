"""Lectura y conversión de los CSV (UTF-8, separador coma).

Convenciones del enunciado: celda vacía = nulo; booleanos True/False; fechas ISO;
importes enteros. Además, los registros propios (`data/extra/`) pueden usar
**fechas relativas** al día de carga, para que las consultas que dependen de "hoy"
siempre tengan datos sin importar cuándo se corra el sistema:

    @hoy       el día de carga (reloj.hoy())
    @hoy-15    15 días antes
    @hoy+30    30 días después
    @mes       el día 1 del mes actual
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from farmared.carga.tablas import BOOL, DATE, DATE_NULL, INT, STR, STR_NULL, Tabla

FECHA_RELATIVA = re.compile(r"^@(hoy|mes)([+-]\d+)?$")
ENTERO = re.compile(r"^-?\d+$")
INT64_MAX = 2**63 - 1


@dataclass
class Fila:
    """Una fila ya convertida, con su ubicación para mensajes de error."""

    datos: dict
    ubicacion: str  # ej. "extra/ventas.csv:4"


class ErrorDatasets(Exception):
    """Errores de formato o integridad. La carga no escribe nada si hay alguno."""

    def __init__(self, errores: list[str]):
        super().__init__(f"{len(errores)} error(es) en los datasets:\n" + "\n".join(f"  - {e}" for e in errores))
        self.errores = errores


def resolver_fecha(valor: str, hoy: date) -> date:
    """Convierte 'AAAA-MM-DD' o un token relativo (@hoy-N, @mes) en fecha."""
    m = FECHA_RELATIVA.match(valor)
    if m:
        base = hoy if m.group(1) == "hoy" else hoy.replace(day=1)
        return base + timedelta(days=int(m.group(2) or 0))
    return date.fromisoformat(valor)


def _convertir(valor: str, tipo: str, hoy: date):
    if valor == "":
        if tipo.endswith("?"):
            return None
        raise ValueError("vacío en un campo obligatorio")
    if tipo in (STR, STR_NULL):
        return valor
    if tipo == INT:
        if not ENTERO.match(valor):
            raise ValueError(f"'{valor}' no es un entero")
        n = int(valor)
        if abs(n) > INT64_MAX:
            raise ValueError(f"'{valor}' excede el rango de int64")
        return n
    if tipo == BOOL:
        if valor not in ("True", "False"):
            raise ValueError(f"'{valor}' no es True/False")
        return valor == "True"
    if tipo in (DATE, DATE_NULL):
        try:
            return resolver_fecha(valor, hoy)
        except ValueError:
            raise ValueError(f"'{valor}' no es una fecha AAAA-MM-DD ni @hoy±N/@mes") from None
    raise AssertionError(f"tipo desconocido {tipo}")


def leer_tabla(ruta: Path, tabla: Tabla, hoy: date, etiqueta: str) -> tuple[list[Fila], list[str]]:
    """Lee un CSV y devuelve (filas convertidas, errores). No lanza por errores de datos."""
    filas: list[Fila] = []
    errores: list[str] = []
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f)
        try:
            encabezado = next(lector)
        except StopIteration:
            return [], [f"{etiqueta}: archivo vacío"]
        esperado = list(tabla.columnas)
        if encabezado != esperado:
            return [], [f"{etiqueta}: encabezado {encabezado} distinto del esperado {esperado}"]
        for valores in lector:
            ubicacion = f"{etiqueta}:{lector.line_num}"
            if not any(v.strip() for v in valores):
                continue  # línea en blanco
            if len(valores) != len(esperado):
                errores.append(f"{ubicacion}: {len(valores)} columnas, se esperaban {len(esperado)}")
                continue
            datos = {}
            ok = True
            for columna, valor in zip(esperado, valores):
                try:
                    datos[columna] = _convertir(valor, tabla.columnas[columna], hoy)
                except ValueError as e:
                    errores.append(f"{ubicacion}: {columna}: {e}")
                    ok = False
            if ok:
                filas.append(Fila(datos, ubicacion))
    return filas, errores
