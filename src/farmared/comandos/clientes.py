"""Comandos `farmared cliente alta | modificar | baja` (servicio q13)."""

from __future__ import annotations

from typing import Optional

import typer

from farmared.comandos import pendiente

cliente_app = typer.Typer(help="ABM de clientes (q13).", no_args_is_help=True)


@cliente_app.command()
def alta(
    nombre: str = typer.Option(...),
    apellido: str = typer.Option(...),
    dni: str = typer.Option(...),
    email: str = typer.Option(...),
    telefono: str = typer.Option(...),
    ciudad: str = typer.Option(...),
    provincia: str = typer.Option(...),
    obra_social: str = typer.Option(..., "--obra-social"),
    nro_afiliado: Optional[str] = typer.Option(None, "--nro-afiliado"),
) -> None:
    """Da de alta un cliente (valida DNI único)."""
    pendiente("cliente alta")


@cliente_app.command()
def modificar(
    id_cliente: str = typer.Argument(...),
    email: Optional[str] = typer.Option(None),
    telefono: Optional[str] = typer.Option(None),
    ciudad: Optional[str] = typer.Option(None),
    provincia: Optional[str] = typer.Option(None),
    obra_social: Optional[str] = typer.Option(None, "--obra-social"),
    nro_afiliado: Optional[str] = typer.Option(None, "--nro-afiliado"),
) -> None:
    """Modifica datos de contacto y cobertura."""
    pendiente("cliente modificar")


@cliente_app.command()
def baja(id_cliente: str = typer.Argument(...)) -> None:
    """Baja lógica (activo = False)."""
    pendiente("cliente baja")


def registrar(app: typer.Typer) -> None:
    app.add_typer(cliente_app, name="cliente")
