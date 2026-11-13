"""Comandos `farmared cliente alta | modificar | baja` (servicio q13)."""

from __future__ import annotations

from typing import Callable, Optional, TypeVar

import typer
from rich.table import Table

from farmared.comandos import console
from farmared.db import mongo, neo4j
from farmared.errores import ValidacionError
from farmared.servicios import q13_abm_clientes as q13

cliente_app = typer.Typer(help="ABM de clientes (q13).", no_args_is_help=True)

T = TypeVar("T")


def _ejecutar(operacion: Callable[..., T]) -> T:
    """Corre la operación con la base y el grafo; un rechazo sale con código 1."""
    try:
        return operacion(mongo.get_db(), neo4j.get_driver())
    except ValidacionError as e:
        console.print(f"[red]Rechazado {e}[/]")
        raise typer.Exit(code=1)


def _mostrar(cliente: dict) -> None:
    tabla = Table(title=f"Cliente {cliente['_id']}")
    tabla.add_column("Campo")
    tabla.add_column("Valor")
    for campo, valor in cliente.items():
        tabla.add_row("id_cliente" if campo == "_id" else campo, "" if valor is None else str(valor))
    console.print(tabla)


def _cliente(id_cliente: str) -> dict:
    return mongo.get_db().clientes.find_one({"_id": id_cliente})


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
    datos = {"nombre": nombre, "apellido": apellido, "dni": dni, "email": email, "telefono": telefono,
             "ciudad": ciudad, "provincia": provincia, "obra_social": obra_social, "nro_afiliado": nro_afiliado}
    try:
        id_cliente = _ejecutar(lambda db, driver: q13.alta(db, datos, driver=driver))
        console.print(f"[green]Alta del cliente {id_cliente}.[/]")
        _mostrar(_cliente(id_cliente))
    finally:
        mongo.cerrar()
        neo4j.cerrar()


@cliente_app.command()
def modificar(
    id_cliente: str = typer.Argument(...),
    email: Optional[str] = typer.Option(None),
    telefono: Optional[str] = typer.Option(None),
    ciudad: Optional[str] = typer.Option(None),
    provincia: Optional[str] = typer.Option(None),
    obra_social: Optional[str] = typer.Option(None, "--obra-social"),
    nro_afiliado: Optional[str] = typer.Option(None, "--nro-afiliado", help='"" para borrarlo (Sin cobertura).'),
) -> None:
    """Modifica datos de contacto y cobertura."""
    opciones = {"email": email, "telefono": telefono, "ciudad": ciudad, "provincia": provincia,
                "obra_social": obra_social, "nro_afiliado": nro_afiliado}
    cambios = {campo: valor for campo, valor in opciones.items() if valor is not None}
    try:
        antes = _cliente(id_cliente)
        _ejecutar(lambda db, driver: q13.modificar(db, id_cliente, cambios, driver=driver))
        despues = _cliente(id_cliente)
        tabla = Table(title=f"Cliente {id_cliente} modificado")
        for col in ("Campo", "Antes", "Después"):
            tabla.add_column(col)
        for campo in q13.CAMPOS_MODIFICABLES:
            a, d = antes.get(campo), despues.get(campo)
            marca = "[bold]" if a != d else ""
            tabla.add_row(campo, "" if a is None else str(a), f"{marca}{'' if d is None else d}")
        console.print(tabla)
    finally:
        mongo.cerrar()
        neo4j.cerrar()


@cliente_app.command()
def baja(id_cliente: str = typer.Argument(...)) -> None:
    """Baja lógica (activo = False)."""
    try:
        _ejecutar(lambda db, driver: q13.baja(db, id_cliente, driver=driver))
        console.print(f"[green]Cliente {id_cliente} dado de baja (activo = False). No se borró nada.[/]")
    finally:
        mongo.cerrar()
        neo4j.cerrar()


def registrar(app: typer.Typer) -> None:
    app.add_typer(cliente_app, name="cliente")
