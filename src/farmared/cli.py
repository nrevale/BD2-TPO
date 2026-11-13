"""CLI de FarmaRed: `python -m farmared <comando>`."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from farmared import reloj
from farmared.carga import cargar_mongo
from farmared.carga.lector_csv import ErrorDatasets
from farmared.carga.validacion import leer_datasets, validar
from farmared.comandos import clientes, consultas, informe, stock, ventas
from farmared.config import cargar_config
from farmared.db import mongo, neo4j
from farmared.errores import ConexionError
from farmared.grafo import outbox

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


def _mostrar_conteos(conteos: dict[str, dict[str, int]], documentos: dict[str, int] | None = None) -> None:
    tabla = Table(title="Registros por dataset")
    for col in ("Dataset", "Originales", "Extra", "Total"):
        tabla.add_column(col, justify="left" if col == "Dataset" else "right")
    if documentos is not None:
        tabla.add_column("Documentos en Mongo", justify="right")
    for nombre, c in conteos.items():
        fila = [nombre, str(c.get("originales", 0)), str(c.get("extra", 0)), str(sum(c.values()))]
        if documentos is not None:
            destino = "ventas (ítems embebidos)" if nombre == "detalle_ventas" else str(documentos.get(nombre, ""))
            fila.append(destino)
        tabla.add_row(*fila)
    console.print(tabla)


def _mostrar_avisos(avisos: list[str]) -> None:
    if avisos:
        console.print(f"[yellow]{len(avisos)} aviso(s): la historia no coincide con el estado actual (se carga igual)[/]")
        for a in avisos:
            console.print(f"  [yellow]•[/] {a}")


@app.command("validar-datos")
def validar_datos() -> None:
    """Valida los CSV (originales + extra) sin conectarse a ninguna base."""
    try:
        ds = leer_datasets(cargar_mongo.directorios_por_defecto(), reloj.hoy())
        avisos = validar(ds)
    except ErrorDatasets as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(code=1)
    _mostrar_conteos(ds.conteo_por_origen)
    _mostrar_avisos(avisos)
    console.print("[green]Datasets válidos.[/]")


def _mostrar_grafo(conteo: dict) -> None:
    tabla = Table(title="Grafo en Neo4j")
    tabla.add_column("Nodos")
    tabla.add_column("Cant.", justify="right")
    tabla.add_column("Relaciones")
    tabla.add_column("Cant.", justify="right")
    nodos, rels = list(conteo["nodos"].items()), list(conteo["relaciones"].items())
    for i in range(max(len(nodos), len(rels))):
        n = nodos[i] if i < len(nodos) else ("", "")
        r = rels[i] if i < len(rels) else ("", "")
        tabla.add_row(n[0], str(n[1]), r[0], str(r[1]))
    console.print(tabla)


def _reconstruir_grafo() -> None:
    """Reconstruye Neo4j desde Mongo; si Neo4j no responde, sale con código 1."""
    try:
        conteo = outbox.reconstruir_grafo(mongo.get_db(), neo4j.get_driver())
    except Exception as e:  # el driver lanza varios tipos según la falla
        console.print(f"[red]No se pudo reconstruir el grafo: {e}[/]")
        console.print("[yellow]MongoDB quedó cargado. Reintentar con: python -m farmared rebuild-grafo[/]")
        raise typer.Exit(code=1)
    _mostrar_grafo(conteo)


@app.command()
def setup() -> None:
    """Carga completa e idempotente: valida los CSV, recarga MongoDB y reconstruye el grafo."""
    cfg = cargar_config()
    console.print(f"Cargando en MongoDB '{cfg.mongo_db}' con hoy = {reloj.hoy().isoformat()} ...")
    try:
        try:
            resumen = cargar_mongo.cargar(mongo.get_client(), cfg.mongo_db)
        except ErrorDatasets as e:
            console.print(f"[red]{e}[/]\n[red]No se modificó la base.[/]")
            raise typer.Exit(code=1)
        _mostrar_conteos(resumen.conteos, resumen.documentos)
        _mostrar_avisos(resumen.avisos)
        console.print("[green]MongoDB cargado.[/] Proyectando en Neo4j ...")
        _reconstruir_grafo()
        console.print("[green]Listo.[/]")
    finally:
        mongo.cerrar()
        neo4j.cerrar()


@app.command("rebuild-grafo")
def rebuild_grafo() -> None:
    """Borra el grafo y lo reconstruye completo desde MongoDB (no toca Mongo)."""
    try:
        _reconstruir_grafo()
    finally:
        mongo.cerrar()
        neo4j.cerrar()


@app.command()
def sync() -> None:
    """Proyecta en Neo4j los eventos pendientes del outbox (escrituras ya confirmadas en Mongo)."""
    try:
        r = outbox.procesar_pendientes(mongo.get_db(), neo4j.get_driver())
    finally:
        mongo.cerrar()
        neo4j.cerrar()
    console.print(f"Procesados: {r.procesados} — pendientes: {r.pendientes}")
    for e in r.errores:
        console.print(f"  [red]•[/] {e}")
    if r.pendientes:
        raise typer.Exit(code=1)


# Comandos de consultas y servicios: cada área vive en su archivo de farmared/comandos/.
for _modulo in (consultas, clientes, ventas, stock, informe):
    _modulo.registrar(app)
