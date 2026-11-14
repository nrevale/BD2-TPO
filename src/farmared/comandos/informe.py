"""Genera ejemplos Markdown de q1–q15 a partir de una carga de demostración."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import typer

from farmared import consultas, reloj
from farmared.carga import cargar_mongo
from farmared.comandos import console
from farmared.comandos.consultas import _aplanar
from farmared.db import mongo, neo4j
from farmared.errores import ValidacionError
from farmared.servicios import q13_abm_clientes as q13
from farmared.servicios.q14_registrar_venta import registrar_venta
from farmared.servicios.q15_descontar_stock import descontar_stock

PARAMETROS_LECTURA = {
    3: ({"id_cliente": "C006"}, " --id-cliente C006"),
    10: ({"id_sucursal": "S001"}, " --id-sucursal S001"),
}


def _celda(valor: object) -> str:
    return str(valor if valor is not None else "—").replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _tabla(filas: list[dict]) -> str:
    filas = [_aplanar(fila) for fila in filas]
    columnas = list(dict.fromkeys(campo for fila in filas for campo in fila))
    if not columnas:
        return "Sin resultados."
    encabezado = "| " + " | ".join(_celda(campo) for campo in columnas) + " |"
    separador = "| " + " | ".join("---" for _ in columnas) + " |"
    cuerpo = ["| " + " | ".join(_celda(fila.get(campo)) for campo in columnas) + " |" for fila in filas]
    return "\n".join([encabezado, separador, *cuerpo])


def _bloque(titulo: str, comando: str, filas: list[dict]) -> str:
    return f"## {titulo}\n\n\x60{comando}\x60\n\n{_tabla(filas)}"


def _comparacion(antes: dict, despues: dict) -> list[dict]:
    return [{"Dato": campo, "Antes": valor, "Después": despues[campo]} for campo, valor in antes.items()]


def _rechazo(operacion, codigo: str) -> str:
    try:
        operacion()
    except ValidacionError as error:
        if error.codigo == codigo:
            return str(error)
        raise
    raise RuntimeError(f"se esperaba el rechazo {codigo}")


def _lecturas(db, driver) -> dict[int, str]:
    bloques = {}
    for numero in consultas.REGISTRO:
        modulo = consultas.obtener(numero)
        parametros, opciones = PARAMETROS_LECTURA.get(numero, ({}, ""))
        conexion = db if modulo.MOTOR == "mongo" else driver
        filas = modulo.ejecutar(conexion, **parametros)
        bloques[numero] = _bloque(modulo.__doc__.splitlines()[0], f"python -m farmared q {numero}{opciones}", filas)
    return bloques


def _clientes(db) -> str:
    dni = "45123456"
    alta = (f'python -m farmared cliente alta --nombre Valentina --apellido Ruiz --dni {dni} '
            '--email demo@example.com --telefono 1155667788 --ciudad San-Isidro '
            '--provincia Buenos-Aires --obra-social "Sin cobertura"')
    datos = {"nombre": "Valentina", "apellido": "Ruiz", "dni": dni, "email": "demo@example.com",
             "telefono": "1155667788", "ciudad": "San-Isidro", "provincia": "Buenos-Aires",
             "obra_social": "Sin cobertura", "nro_afiliado": None}

    def estado():
        doc = db.clientes.find_one({"dni": dni}) or {}
        contador = db.contadores.find_one({"_id": "cliente"})
        return {"Cliente": doc.get("_id"), "Email": doc.get("email"), "Activo": doc.get("activo"),
                "Contador cliente": contador["ultimo"], "Eventos en outbox": db.outbox.count_documents({})}

    inicial = estado()
    cliente = q13.alta(db, datos)
    despues_alta = estado()
    error = _rechazo(lambda: q13.alta(db, datos), "DNI_DUPLICADO")
    rechazo = _bloque(f"Alta duplicada {error}", alta, _comparacion(despues_alta, estado()))
    email = "nuevo@example.com"
    q13.modificar(db, cliente, {"email": email})
    despues_cambio = estado()
    q13.baja(db, cliente)
    return "\n\n".join([
        _bloque("Alta de cliente", alta, _comparacion(inicial, despues_alta)),
        rechazo,
        _bloque("Cambio de contacto", f"python -m farmared cliente modificar {cliente} --email {email}",
                _comparacion(despues_alta, despues_cambio)),
        _bloque("Baja lógica", f"python -m farmared cliente baja {cliente}", _comparacion(despues_cambio, estado())),
    ])


def _estado_venta(db, id_receta: str, ids_lotes: tuple[str, ...]) -> dict:
    receta = db.recetas.find_one({"_id": id_receta})
    contadores = {d["_id"]: d["ultimo"] for d in db.contadores.find()}
    lotes = {d["_id"]: d["unidades"] for d in db.stock_lotes.find({"_id": {"$in": list(ids_lotes)}})}
    return {
        "Ventas registradas": db.ventas.count_documents({}),
        "Contador venta": contadores["venta"],
        "Contador detalle": contadores["detalle"],
        f"Receta {id_receta}": receta["estado"],
        "Dispensas": f"{receta['dispensas_realizadas']}/{receta['dispensas_autorizadas']}",
        "Próxima dispensa": receta["proxima_dispensa"].date() if receta["proxima_dispensa"] else None,
        "Eventos en outbox": db.outbox.count_documents({}),
        **{f"Stock {lote}": lotes[lote] for lote in ids_lotes},
    }


def _caso_venta(db, cliente: str, farmaceutico: str, producto: str, receta: str, cantidad: int):
    comando = (f"python -m farmared venta registrar --cliente {cliente} --farmaceutico {farmaceutico} "
               f'--item {producto}:{cantidad} --receta {receta} --pago "Obra social"')

    def ejecutar():
        return registrar_venta(db, cliente, farmaceutico, [{"id_producto": producto, "cantidad": cantidad}],
                               "Obra social", id_receta=receta)

    return comando, ejecutar


def _ventas_y_stock(db) -> tuple[str, str]:
    lotes = ("L005", "L015", "L019")
    inicial = _estado_venta(db, "RC006", lotes)
    comando, ejecutar = _caso_venta(db, "C007", "F001", "PRD003", "RC006", 200)
    error = _rechazo(ejecutar, "STOCK_INSUFICIENTE")
    rechazo = _bloque(f"Venta rechazada {error}", comando, _comparacion(inicial, _estado_venta(db, "RC006", lotes)))

    comando, ejecutar = _caso_venta(db, "C007", "F001", "PRD003", "RC006", 50)
    venta = ejecutar()
    resumen = [{"Venta": venta["_id"], "Sucursal": venta["id_sucursal"], "Estado": venta["estado"],
                "Total (ARS)": venta["total"], "Stock aplicado": venta["stock_aplicado"]}]
    despues = _estado_venta(db, "RC006", lotes)
    exito = _bloque("Venta con receta simple", comando, resumen) + "\n\n" + _tabla(_comparacion(inicial, despues))

    stock = _bloque("Descuento FEFO ejecutado por q14", comando, venta["lotes_consumidos"])
    antes_reintento = _estado_venta(db, "RC006", lotes)
    error = _rechazo(lambda: descontar_stock(db, venta["_id"]), "STOCK_YA_APLICADO")
    reintento = _bloque(f"Segundo descuento rechazado {error}", f"python -m farmared stock descontar {venta['_id']}",
                       _comparacion(antes_reintento, _estado_venta(db, "RC006", lotes)))
    cambio_stock = _comparacion({f"Stock {lote}": inicial[f"Stock {lote}"] for lote in lotes}, despues)

    lotes_prolongada = ("L020", "L021")
    antes_prolongada = _estado_venta(db, "RC012", lotes_prolongada)
    comando, ejecutar = _caso_venta(db, "C018", "F008", "PRD019", "RC012", 1)
    prolongada = ejecutar()
    despues_prolongada = _estado_venta(db, "RC012", lotes_prolongada)
    bloque_prolongada = _bloque(f"Última dispensa de tratamiento prolongado en {prolongada['_id']}", comando,
                               _comparacion(antes_prolongada, despues_prolongada))
    return "\n\n".join([rechazo, exito, bloque_prolongada]), "\n\n".join([stock, _tabla(cambio_stock), reintento])


def _generar(out: Path, hoy: date) -> None:
    client = mongo.get_client()
    bloques = _lecturas(mongo.get_db(), neo4j.get_driver())
    db_demo = client[f"farmared_informe_{uuid4().hex}"]
    try:
        cargar_mongo.cargar(client, db_demo.name, hoy=hoy)
        bloques[13] = _clientes(db_demo)
        bloques[14], bloques[15] = _ventas_y_stock(db_demo)
        out.mkdir(parents=True, exist_ok=True)
        for numero, bloque in bloques.items():
            contenido = f"# q{numero:02d}\n\nFecha de referencia {hoy.isoformat()}\n\n{bloque}\n"
            (out / f"q{numero:02d}.md").write_text(contenido, encoding="utf-8")
    finally:
        client.drop_database(db_demo.name)


def registrar(app: typer.Typer) -> None:
    @app.command("informe-resultados")
    def informe_resultados(
        out: Path = typer.Option(..., "--out", help="Carpeta donde escribir un .md por consulta."),
    ) -> None:
        """Genera q01.md–q15.md. Corré setup con la misma fecha para reproducir los ejemplos."""
        try:
            _generar(out, reloj.hoy())
        finally:
            mongo.cerrar()
            neo4j.cerrar()
        console.print(f"Se generaron 15 archivos Markdown en {out}.", markup=False)
