"""Comando `farmared q <n>`: ejecuta una de las consultas q01–q12 y muestra el resultado."""

from __future__ import annotations

import inspect
import json as json_lib
from typing import Optional

import typer
from rich.table import Table

from farmared import consultas as registro
from farmared.comandos import console
from farmared.db import mongo, neo4j
from farmared.errores import ValidacionError


def _aplanar(fila: dict, prefijo: str = "") -> dict:
    """{'proveedor': {'cuit': ..}} -> {'proveedor.cuit': ..}. Las listas de dicts (productos de q3)
    se resumen como 'PRD001 x2, PRD004 x1'."""
    plano = {}
    for clave, valor in fila.items():
        nombre = f"{prefijo}{clave}"
        if isinstance(valor, dict):
            plano.update(_aplanar(valor, f"{nombre}."))
        elif isinstance(valor, list):
            plano[nombre] = ", ".join(
                f"{v.get('id_producto', '')} x{v.get('cantidad', '')}" if isinstance(v, dict) else str(v)
                for v in valor
            )
        else:
            plano[nombre] = valor
    return plano


def _tabla(titulo: str, filas: list[dict]) -> Table:
    planas = [_aplanar(f) for f in filas]
    columnas = list(dict.fromkeys(c for f in planas for c in f))  # unión, en orden de aparición
    tabla = Table(title=titulo)
    for c in columnas:
        tabla.add_column(c)
    for f in planas:
        tabla.add_row(*("" if f.get(c) is None else str(f[c]) for c in columnas))
    return tabla


def registrar(app: typer.Typer) -> None:
    @app.command("q")
    def consulta(
        numero: int = typer.Argument(..., help="Número de consulta (1–12)."),
        id_cliente: Optional[str] = typer.Option(None, "--id-cliente", help="Para q3 (ej. C006)."),
        id_sucursal: Optional[str] = typer.Option(None, "--id-sucursal", help="Para q10 (ej. S001)."),
        json: bool = typer.Option(False, "--json", help="Salida en JSON en vez de tabla."),
    ) -> None:
        """Ejecuta una consulta de lectura o agregación (q1–q12)."""
        try:
            modulo = registro.obtener(numero)
        except KeyError as e:
            console.print(f"[red]{e.args[0]}[/]")
            raise typer.Exit(code=1)

        parametros = inspect.signature(modulo.ejecutar).parameters
        kwargs = {}
        for nombre, valor, opcion in (("id_cliente", id_cliente, "--id-cliente"),
                                      ("id_sucursal", id_sucursal, "--id-sucursal")):
            if nombre in parametros:
                if valor is None:
                    console.print(f"[red]q {numero} necesita {opcion}[/]")
                    raise typer.Exit(code=1)
                kwargs[nombre] = valor

        try:
            conexion = mongo.get_db() if modulo.MOTOR == "mongo" else neo4j.get_driver()
            filas = modulo.ejecutar(conexion, **kwargs)
        except ValidacionError as e:
            console.print(f"[red]{e}[/]")
            raise typer.Exit(code=1)
        finally:
            mongo.cerrar()
            neo4j.cerrar()

        if json:
            print(json_lib.dumps(filas, ensure_ascii=False, indent=2, default=str))
        else:
            titulo = (modulo.__doc__ or "").splitlines()[0]
            console.print(_tabla(f"{titulo} ({modulo.MOTOR})", filas))
            console.print(f"{len(filas)} fila(s)")
