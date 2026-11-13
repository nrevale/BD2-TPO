"""Validación de los datasets antes de escribir en MongoDB.

MongoDB no garantiza integridad referencial ni reglas entre documentos, así que la
carga las verifica en la aplicación. Se separan dos niveles:

- **Errores**: datos imposibles (referencia inexistente, clave duplicada, total que no
  coincide con sus ítems, enum inválido...). Si hay alguno, no se carga nada.
- **Avisos**: la historia no coincide con el estado *actual* de una entidad (p. ej. una
  venta atendida por un farmacéutico que hoy está inactivo). Son válidos: el estado
  cambió después de la venta. Se informan y se cargan tal cual.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from farmared.carga.lector_csv import ErrorDatasets, Fila, leer_tabla
from farmared.carga.tablas import REFERENCIAS, TABLAS


@dataclass
class Datasets:
    """Filas convertidas por tabla, más cuántas vinieron de cada directorio."""

    filas: dict[str, list[Fila]]
    conteo_por_origen: dict[str, dict[str, int]]  # tabla -> {"originales": n, "extra": m}

    def datos(self, tabla: str) -> list[dict]:
        return [f.datos for f in self.filas[tabla]]


def leer_datasets(directorios: dict[str, Path], hoy) -> Datasets:
    """Lee los 9 CSV de cada directorio ({"originales": ..., "extra": ...}) y los concatena.

    Un directorio puede no tener alguno de los archivos. Lanza ErrorDatasets si hay
    errores de formato.
    """
    filas: dict[str, list[Fila]] = {nombre: [] for nombre in TABLAS}
    conteo: dict[str, dict[str, int]] = {nombre: {} for nombre in TABLAS}
    errores: list[str] = []
    for etiqueta, directorio in directorios.items():
        for nombre, tabla in TABLAS.items():
            ruta = directorio / tabla.archivo
            if not ruta.exists():
                conteo[nombre][etiqueta] = 0
                continue
            leidas, errs = leer_tabla(ruta, tabla, hoy, f"{etiqueta}/{tabla.archivo}")
            filas[nombre].extend(leidas)
            conteo[nombre][etiqueta] = len(leidas)
            errores.extend(errs)
    if errores:
        raise ErrorDatasets(errores)
    return Datasets(filas, conteo)


def validar(ds: Datasets) -> list[str]:
    """Verifica integridad y reglas de negocio. Devuelve los avisos; lanza ErrorDatasets si hay errores."""
    errores: list[str] = []
    avisos: list[str] = []

    # --- Claves primarias y campos únicos -------------------------------------------------
    indice: dict[str, dict[str, dict]] = {}
    for nombre, tabla in TABLAS.items():
        indice[nombre] = {}
        for campo in (tabla.clave, *tabla.unicos):
            repetidos = Counter(f.datos[campo] for f in ds.filas[nombre])
            for fila in ds.filas[nombre]:
                if repetidos[fila.datos[campo]] > 1:
                    errores.append(f"{fila.ubicacion}: {campo} '{fila.datos[campo]}' duplicado en {nombre}")
        for fila in ds.filas[nombre]:
            indice[nombre][fila.datos[tabla.clave]] = fila.datos

    # --- Enums ------------------------------------------------------------------------------
    for nombre, tabla in TABLAS.items():
        for campo, valores in tabla.enums.items():
            for fila in ds.filas[nombre]:
                if fila.datos[campo] not in valores:
                    errores.append(f"{fila.ubicacion}: {campo} '{fila.datos[campo]}' no es uno de {list(valores)}")

    # --- Referencias (integridad referencial en la aplicación) -------------------------------
    for nombre, campo, destino in REFERENCIAS:
        for fila in ds.filas[nombre]:
            valor = fila.datos[campo]
            if valor is not None and valor not in indice[destino]:
                errores.append(f"{fila.ubicacion}: {campo} '{valor}' no existe en {destino}")

    if errores:  # sin referencias válidas, las reglas siguientes darían errores en cascada
        raise ErrorDatasets(errores)

    clientes, sucursales, farmaceuticos = indice["clientes"], indice["sucursales"], indice["farmaceuticos"]
    productos, recetas = indice["productos"], indice["recetas"]

    # --- Reglas por entidad -----------------------------------------------------------------
    for fila in ds.filas["clientes"]:
        c = fila.datos
        sin_cobertura = c["obra_social"] == "Sin cobertura"
        if sin_cobertura and c["nro_afiliado"] is not None:
            errores.append(f"{fila.ubicacion}: cliente sin cobertura con nro_afiliado")
        if not sin_cobertura and c["nro_afiliado"] is None:
            errores.append(f"{fila.ubicacion}: cliente con {c['obra_social']} sin nro_afiliado")

    for fila in ds.filas["productos"]:
        if fila.datos["precio_unit"] < 0:
            errores.append(f"{fila.ubicacion}: precio_unit negativo")

    for fila in ds.filas["stock_lotes"]:
        if fila.datos["unidades"] < 0:
            errores.append(f"{fila.ubicacion}: unidades negativas")

    for fila in ds.filas["recetas"]:
        r = fila.datos
        aut, real = r["dispensas_autorizadas"], r["dispensas_realizadas"]
        if aut < 1 or not 0 <= real <= aut:
            errores.append(f"{fila.ubicacion}: dispensas {real}/{aut} fuera de rango")
        if r["tipo"] in ("Simple", "Archivada") and aut != 1:
            errores.append(f"{fila.ubicacion}: receta {r['tipo']} con {aut} dispensas autorizadas (debe ser 1)")
        if r["estado"] == "Completada" and (real != aut or r["proxima_dispensa"] is not None):
            errores.append(f"{fila.ubicacion}: receta Completada con dispensas {real}/{aut} o próxima dispensa")
        if r["estado"] == "Vigente" and real >= aut:
            errores.append(f"{fila.ubicacion}: receta Vigente sin dispensas disponibles ({real}/{aut})")

    # --- Ventas y su detalle ------------------------------------------------------------------
    items_por_venta: dict[str, list[dict]] = defaultdict(list)
    for fila in ds.filas["detalle_ventas"]:
        d = fila.datos
        if d["cantidad"] <= 0:
            errores.append(f"{fila.ubicacion}: cantidad debe ser mayor a 0")
        if d["precio_unit"] < 0:
            errores.append(f"{fila.ubicacion}: precio_unit negativo")
        items_por_venta[d["id_venta"]].append(d)

    ventas_completadas_por_receta: dict[str, list[dict]] = defaultdict(list)
    for fila in ds.filas["ventas"]:
        v, ub = fila.datos, fila.ubicacion
        items = items_por_venta.get(v["id_venta"], [])
        if not items:
            errores.append(f"{ub}: venta {v['id_venta']} sin ítems")
        suma = sum(i["cantidad"] * i["precio_unit"] for i in items)
        if items and suma != v["total"]:
            errores.append(f"{ub}: total {v['total']} distinto de la suma de ítems {suma}")

        con_receta = v["id_receta"] is not None
        if (v["tipo"] == "Con receta") != con_receta:
            errores.append(f"{ub}: tipo '{v['tipo']}' incoherente con id_receta={v['id_receta']}")
        if con_receta:
            receta = recetas[v["id_receta"]]
            if receta["id_cliente"] != v["id_cliente"]:
                errores.append(f"{ub}: la receta {v['id_receta']} es de {receta['id_cliente']}, no de {v['id_cliente']}")
            if v["fecha"] < receta["fecha_emision"]:
                avisos.append(f"{ub}: venta {v['id_venta']} anterior a la emisión de {v['id_receta']}")
            if v["estado"] == "Completada":
                ventas_completadas_por_receta[v["id_receta"]].append(v)
        for i in items:
            if productos[i["id_producto"]]["condicion_venta"] != "Venta libre" and not con_receta:
                errores.append(f"{ub}: {i['id_producto']} es bajo receta y la venta {v['id_venta']} no tiene receta")

        farm = farmaceuticos[v["id_farmaceutico"]]
        suc = sucursales[farm["id_sucursal"]]
        if suc["tipo"] != "Farmacia":
            errores.append(f"{ub}: venta {v['id_venta']} registrada en {suc['id_sucursal']} ({suc['tipo']})")

        # Historia vs. estado actual: avisos, no errores.
        if not farm["activo"]:
            avisos.append(f"{ub}: venta {v['id_venta']} atendida por {farm['id_farmaceutico']}, hoy inactivo")
        if not suc["activo"]:
            avisos.append(f"{ub}: venta {v['id_venta']} en {suc['id_sucursal']}, hoy inactiva")
        if not clientes[v["id_cliente"]]["activo"]:
            avisos.append(f"{ub}: venta {v['id_venta']} de {v['id_cliente']}, hoy inactivo")
        for i in items:
            if not productos[i["id_producto"]]["activo"]:
                avisos.append(f"{ub}: venta {v['id_venta']} incluye {i['id_producto']}, hoy discontinuado")

    # --- Recetas vs. ventas que las dispensaron -----------------------------------------------
    for fila in ds.filas["recetas"]:
        r = fila.datos
        ventas = sorted(ventas_completadas_por_receta.get(r["id_receta"], []), key=lambda v: v["fecha"])
        if ventas and len(ventas) != r["dispensas_realizadas"]:
            avisos.append(
                f"{fila.ubicacion}: {r['id_receta']} declara {r['dispensas_realizadas']} dispensas "
                f"y tiene {len(ventas)} ventas completadas"
            )
        if ventas and r["tipo"] == "Tratamiento prolongado" and r["proxima_dispensa"] is not None:
            esperada = ventas[-1]["fecha"] + timedelta(days=30)
            if r["proxima_dispensa"] != esperada:
                avisos.append(
                    f"{fila.ubicacion}: {r['id_receta']} tiene próxima dispensa {r['proxima_dispensa']} "
                    f"y la regla daría {esperada} (última dispensa {ventas[-1]['id_venta']})"
                )

    if errores:
        raise ErrorDatasets(errores)
    return avisos
