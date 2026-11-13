"""Comando `farmared venta registrar` (servicio q14)."""

from __future__ import annotations

from typing import Optional

import typer

from farmared.comandos import pendiente

venta_app = typer.Typer(help="Ventas (q14).", no_args_is_help=True)


@venta_app.command("registrar")
def registrar_venta(
    cliente: str = typer.Option(..., help="Id del cliente (ej. C007)."),
    farmaceutico: str = typer.Option(..., help="Id del farmacéutico (ej. F001)."),
    item: list[str] = typer.Option(..., help="Producto y cantidad, ej. PRD003:50. Repetible."),
    pago: str = typer.Option(..., help="Efectivo, Débito, Crédito, Transferencia u Obra social."),
    receta: Optional[str] = typer.Option(None, help="Id de la receta (si hay productos bajo receta)."),
) -> None:
    """Registra una venta Completada: valida, descuenta stock y actualiza la receta."""
    pendiente("venta registrar")


def registrar(app: typer.Typer) -> None:
    app.add_typer(venta_app, name="venta")
