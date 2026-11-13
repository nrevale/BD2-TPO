"""Comando `farmared stock descontar <id_venta>` (servicio q15)."""

from __future__ import annotations

import typer
from rich.table import Table

from farmared import reloj
from farmared.comandos import console
from farmared.db import mongo
from farmared.errores import ValidacionError
from farmared.servicios.q15_descontar_stock import descontar_stock

stock_app = typer.Typer(help="Stock por lote (q15).", no_args_is_help=True)


@stock_app.command()
def descontar(id_venta: str = typer.Argument(..., help="Venta Completada sin stock aplicado.")) -> None:
    """Descuenta el stock de una venta por FEFO, omitiendo lotes vencidos."""
    hoy = reloj.hoy()
    try:
        db = mongo.get_db()
        try:
            consumidos = descontar_stock(db, id_venta, hoy=hoy)
        except ValidacionError as e:
            console.print(f"[red]Rechazado {e}[/]")
            console.print("No se modificó ningún lote.")
            raise typer.Exit(code=1)

        lotes = {l["_id"]: l for l in db.stock_lotes.find({"_id": {"$in": [c["id_lote"] for c in consumidos]}})}
        tabla = Table(title=f"Stock descontado para {id_venta} (FEFO, hoy = {hoy.isoformat()})")
        for col in ("Lote", "Producto", "Vencimiento", "Antes", "Descontado", "Después"):
            tabla.add_column(col, justify="right" if col in ("Antes", "Descontado", "Después") else "left")
        for c in consumidos:
            lote = lotes[c["id_lote"]]
            tabla.add_row(c["id_lote"], c["id_producto"], lote["vencimiento"].date().isoformat(),
                          str(lote["unidades"] + c["unidades"]), str(c["unidades"]), str(lote["unidades"]))
        console.print(tabla)
    finally:
        mongo.cerrar()


def registrar(app: typer.Typer) -> None:
    app.add_typer(stock_app, name="stock")
