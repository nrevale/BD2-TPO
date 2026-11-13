"""Consultas q01–q12. Cada módulo define MOTOR ("mongo" | "neo4j") y una función ejecutar(...).

La CLI (`farmared q <n>`) las busca por número en REGISTRO.
"""

from __future__ import annotations

import importlib
from types import ModuleType

REGISTRO: dict[int, str] = {
    1: "q01_productos_activos",
    2: "q02_ventas_pendientes",
    3: "q03_historial_cliente",
    4: "q04_clientes_varias_recetas",
    5: "q05_farmaceuticos_ventas_60d",
    6: "q06_recetas_dispensa_atrasada",
    7: "q07_top_productos",
    8: "q08_lotes_stock_bajo",
    9: "q09_ventas_libres_menores",
    10: "q10_clientes_por_sucursal",
    11: "q11_ingresos_mes",
    12: "q12_clientes_sin_ventas",
}


def obtener(numero: int) -> ModuleType:
    """Devuelve el módulo de la consulta `numero` (1–12)."""
    if numero not in REGISTRO:
        raise KeyError(f"no existe la consulta {numero} (válidas: 1–12)")
    return importlib.import_module(f"farmared.consultas.{REGISTRO[numero]}")
