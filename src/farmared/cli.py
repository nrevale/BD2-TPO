"""CLI de FarmaRed: `python -m farmared <comando>`.

Fase 1 solo expone `salud`. Las fases siguientes agregan `setup`, las consultas
q01–q12 y los servicios q13–q15.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from farmared import reloj
from farmared.db import mongo, neo4j
from farmared.errores import ConexionError

app = typer.Typer(help="FarmaRed — TPO Base de Datos II (MongoDB + Neo4j).", no_args_is_help=True)
console = Console()


@app.callback()
def _main() -> None:
    """Agrupa los subcomandos (sin esto, typer trataría un único comando como raíz)."""


@app.command()
def salud() -> None:
    """Verifica que MongoDB (primario del replica set) y Neo4j respondan."""
    tabla = Table(title=f"Salud de los motores — hoy = {reloj.hoy().isoformat()}")
    tabla.add_column("Motor")
    tabla.add_column("Estado")
    tabla.add_column("Detalle")
    ok = True

    try:
        m = mongo.estado()
        if m["primario"] and m["replica_set"]:
            tabla.add_row("MongoDB", "[green]OK[/]", f"v{m['version']}, replica set {m['replica_set']} (primario)")
        else:
            ok = False
            tabla.add_row("MongoDB", "[red]FALLA[/]", f"replica set={m['replica_set']}, primario={m['primario']} — sin transacciones")
    except ConexionError as e:
        ok = False
        tabla.add_row("MongoDB", "[red]FALLA[/]", str(e))

    try:
        n = neo4j.estado()
        tabla.add_row("Neo4j", "[green]OK[/]", n["version"])
    except ConexionError as e:
        ok = False
        tabla.add_row("Neo4j", "[red]FALLA[/]", str(e))
    finally:
        mongo.cerrar()
        neo4j.cerrar()

    console.print(tabla)
    if not ok:
        raise typer.Exit(code=1)
