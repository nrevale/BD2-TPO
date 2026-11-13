"""Comando `farmared stock descontar <id_venta>` (servicio q15)."""

from __future__ import annotations

import typer

from farmared.comandos import pendiente

stock_app = typer.Typer(help="Stock por lote (q15).", no_args_is_help=True)


@stock_app.command()
def descontar(id_venta: str = typer.Argument(..., help="Venta Completada sin stock aplicado.")) -> None:
    """Descuenta el stock de una venta por FEFO, omitiendo lotes vencidos."""
    pendiente("stock descontar")


def registrar(app: typer.Typer) -> None:
    app.add_typer(stock_app, name="stock")
