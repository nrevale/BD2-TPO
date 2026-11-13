"""Comandos de la CLI, uno por archivo. Cada módulo expone `registrar(app)`, que `cli.py` llama.

Así cada parte del sistema agrega sus comandos sin tocar el archivo de las demás.
"""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()

CODIGO_PENDIENTE = 3


def pendiente(que: str) -> None:
    """Corta el comando con un mensaje claro mientras su implementación no está."""
    console.print(f"[yellow]{que}: todavía no está implementado.[/]")
    raise typer.Exit(code=CODIGO_PENDIENTE)
