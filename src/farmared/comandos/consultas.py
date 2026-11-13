"""Comando `farmared q <n>`: ejecuta una de las consultas q01–q12 y muestra el resultado."""

from __future__ import annotations

from typing import Optional

import typer

from farmared.comandos import pendiente


def registrar(app: typer.Typer) -> None:
    @app.command("q")
    def consulta(
        numero: int = typer.Argument(..., help="Número de consulta (1–12)."),
        id_cliente: Optional[str] = typer.Option(None, "--id-cliente", help="Para q3 (ej. C006)."),
        id_sucursal: Optional[str] = typer.Option(None, "--id-sucursal", help="Para q10 (ej. S001)."),
        json: bool = typer.Option(False, "--json", help="Salida en JSON en vez de tabla."),
    ) -> None:
        """Ejecuta una consulta de lectura o agregación (q1–q12)."""
        # A implementar: buscar el módulo con farmared.consultas.obtener(numero), pasarle
        # db o driver según su MOTOR (y los parámetros), y mostrar el resultado en tabla o JSON.
        pendiente(f"q {numero}")
