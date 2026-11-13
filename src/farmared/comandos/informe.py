"""Comando `farmared informe-resultados`: genera los ejemplos de resultado para el informe."""

from __future__ import annotations

from pathlib import Path

import typer

from farmared.comandos import pendiente


def registrar(app: typer.Typer) -> None:
    @app.command("informe-resultados")
    def informe_resultados(
        out: Path = typer.Option(..., "--out", help="Carpeta donde escribir un .md por consulta."),
    ) -> None:
        """Sobre una carga fresca, corre q1–q12 y los casos de demo de q13–q15 (con antes/después)."""
        pendiente("informe-resultados")
