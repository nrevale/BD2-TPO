"""Comando `farmared venta registrar` (servicio q14)."""

from __future__ import annotations

from typing import Optional

import typer
from rich.table import Table

from farmared.comandos import console
from farmared.db import mongo, neo4j
from farmared.errores import ValidacionError
from farmared.servicios import q14_registrar_venta as q14

venta_app = typer.Typer(help="Ventas (q14).", no_args_is_help=True)


def _parsear_items(argumentos: list[str]) -> list[dict]:
    items = []
    for argumento in argumentos:
        producto, _, cantidad = argumento.partition(":")
        try:
            unidades = int(cantidad)
        except ValueError:
            raise ValidacionError(
                "DATO_INVALIDO", f"ítem inválido {argumento!r}; usá PRODUCTO:CANTIDAD (ej. PRD003:50)"
            ) from None
        items.append({"id_producto": producto.strip(), "cantidad": unidades})
    return items


@venta_app.command("registrar")
def registrar_venta(
    cliente: str = typer.Option(..., help="Id del cliente (ej. C007)."),
    farmaceutico: str = typer.Option(..., help="Id del farmacéutico (ej. F001)."),
    item: list[str] = typer.Option(..., help="Producto y cantidad, ej. PRD003:50. Repetible."),
    pago: str = typer.Option(..., help="Efectivo, Débito, Crédito, Transferencia u Obra social."),
    receta: Optional[str] = typer.Option(None, help="Id de la receta (si hay productos bajo receta)."),
) -> None:
    """Registra una venta Completada: valida, descuenta stock y actualiza la receta."""
    try:
        items = _parsear_items(item)
        venta = q14.registrar_venta(
            mongo.get_db(), cliente, farmaceutico, items, pago, id_receta=receta, driver=neo4j.get_driver(),
        )
    except ValidacionError as e:
        console.print(f"Rechazado {e}", style="red", markup=False)
        raise typer.Exit(code=1) from None
    finally:
        mongo.cerrar()
        neo4j.cerrar()

    console.print(f"[green]Venta {venta['_id']} registrada en {venta['id_sucursal']}. Total: $ {venta['total']}.[/]")
    tabla = Table(title="Lotes descontados por FEFO")
    tabla.add_column("Lote")
    tabla.add_column("Producto")
    tabla.add_column("Unidades", justify="right")
    for lote in venta["lotes_consumidos"]:
        tabla.add_row(lote["id_lote"], lote["id_producto"], str(lote["unidades"]))
    console.print(tabla)


def registrar(app: typer.Typer) -> None:
    app.add_typer(venta_app, name="venta")
