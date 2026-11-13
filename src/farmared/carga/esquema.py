"""Esquema de MongoDB: colecciones con validador $jsonSchema, índices y la vista de q11.

El validador es la última línea de defensa (tipos, enums, unidades >= 0). Las reglas
entre documentos (referencias, total = suma de ítems, FEFO, recetas) las garantizan
la carga y los servicios en la aplicación.
"""

from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database

from farmared.carga import tablas as t

ENTERO = {"bsonType": ["int", "long"]}
ENTERO_NO_NEG = {"bsonType": ["int", "long"], "minimum": 0}
TEXTO = {"bsonType": "string"}
TEXTO_O_NULO = {"bsonType": ["string", "null"]}
BOOL = {"bsonType": "bool"}
FECHA = {"bsonType": "date"}
FECHA_O_NULO = {"bsonType": ["date", "null"]}


def _enum(valores: tuple[str, ...]) -> dict:
    return {"bsonType": "string", "enum": list(valores)}


def _schema(props: dict, requeridos: list[str] | None = None) -> dict:
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": requeridos if requeridos is not None else list(props),
            "properties": props,
        }
    }


VALIDADORES: dict[str, dict] = {
    "clientes": _schema({
        "_id": TEXTO, "nombre": TEXTO, "apellido": TEXTO, "dni": TEXTO, "email": TEXTO,
        "telefono": TEXTO, "ciudad": TEXTO, "provincia": TEXTO,
        "obra_social": _enum(t.OBRAS_SOCIALES), "nro_afiliado": TEXTO_O_NULO, "activo": BOOL,
    }),
    "sucursales": _schema({
        "_id": TEXTO, "nombre": TEXTO, "tipo": _enum(t.TIPOS_SUCURSAL), "direccion": TEXTO,
        "ciudad": TEXTO, "provincia": TEXTO, "telefono": TEXTO, "activo": BOOL,
    }),
    "farmaceuticos": _schema({
        "_id": TEXTO, "nombre": TEXTO, "apellido": TEXTO, "matricula": TEXTO,
        "cargo": _enum(t.CARGOS), "id_sucursal": TEXTO, "activo": BOOL,
    }),
    "proveedores": _schema({
        "_id": TEXTO, "razon_social": TEXTO, "cuit": TEXTO, "tipo": _enum(t.TIPOS_PROVEEDOR),
        "ciudad": TEXTO, "provincia": TEXTO, "telefono": TEXTO, "activo": BOOL,
    }),
    "productos": _schema({
        "_id": TEXTO, "nombre": TEXTO, "principio_activo": TEXTO, "categoria": TEXTO,
        "presentacion": TEXTO, "condicion_venta": _enum(t.CONDICIONES_VENTA),
        "precio_unit": ENTERO_NO_NEG, "id_proveedor": TEXTO, "activo": BOOL,
    }),
    "stock_lotes": _schema({
        "_id": TEXTO, "id_producto": TEXTO, "id_sucursal": TEXTO, "nro_lote": TEXTO,
        "unidades": ENTERO_NO_NEG, "vencimiento": FECHA,
    }),
    "recetas": _schema({
        "_id": TEXTO, "id_cliente": TEXTO, "medico": TEXTO, "matricula_medico": TEXTO,
        "fecha_emision": FECHA, "tipo": _enum(t.TIPOS_RECETA),
        "dispensas_autorizadas": {"bsonType": ["int", "long"], "minimum": 1},
        "dispensas_realizadas": ENTERO_NO_NEG, "proxima_dispensa": FECHA_O_NULO,
        "estado": _enum(t.ESTADOS_RECETA),
    }),
    "ventas": _schema(
        {
            "_id": TEXTO, "id_cliente": TEXTO, "id_farmaceutico": TEXTO, "id_sucursal": TEXTO,
            "id_receta": TEXTO_O_NULO, "fecha": FECHA, "tipo": _enum(t.TIPOS_VENTA),
            "medio_pago": _enum(t.MEDIOS_PAGO), "total": ENTERO_NO_NEG,
            "estado": _enum(t.ESTADOS_VENTA), "stock_aplicado": BOOL,
            "lotes_consumidos": {
                "bsonType": ["array", "null"],
                "items": {
                    "bsonType": "object",
                    "required": ["id_lote", "id_producto", "unidades"],
                    "properties": {"id_lote": TEXTO, "id_producto": TEXTO, "unidades": ENTERO_NO_NEG},
                },
            },
            "items": {
                "bsonType": "array",
                "minItems": 1,
                "items": {
                    "bsonType": "object",
                    "required": ["id_detalle", "id_producto", "cantidad", "precio_unit", "subtotal"],
                    "properties": {
                        "id_detalle": TEXTO, "id_producto": TEXTO,
                        "cantidad": {"bsonType": ["int", "long"], "minimum": 1},
                        "precio_unit": ENTERO_NO_NEG, "subtotal": ENTERO_NO_NEG,
                    },
                },
            },
        },
        requeridos=[
            "_id", "id_cliente", "id_farmaceutico", "id_sucursal", "id_receta", "fecha", "tipo",
            "medio_pago", "total", "estado", "stock_aplicado", "items",
        ],
    ),
    "outbox": _schema(
        {"tipo": _enum(("cliente", "venta", "receta")), "ref_id": TEXTO, "creado": FECHA, "procesado": BOOL},
    ),
    "contadores": _schema({"_id": TEXTO, "ultimo": ENTERO_NO_NEG}),
}

INDICES: dict[str, list[IndexModel]] = {
    "clientes": [IndexModel("dni", unique=True, name="dni_unico")],
    "farmaceuticos": [
        IndexModel("matricula", unique=True, name="matricula_unica"),
        IndexModel("id_sucursal", name="por_sucursal"),
    ],
    "proveedores": [IndexModel("cuit", unique=True, name="cuit_unico")],
    "productos": [IndexModel("activo", name="por_activo")],
    "stock_lotes": [
        # FEFO: lotes de un producto en una sucursal, por vencimiento ascendente.
        IndexModel([("id_sucursal", ASCENDING), ("id_producto", ASCENDING), ("vencimiento", ASCENDING)], name="fefo"),
        IndexModel("unidades", name="por_unidades"),
    ],
    "recetas": [
        IndexModel("id_cliente", name="por_cliente"),
        IndexModel([("tipo", ASCENDING), ("estado", ASCENDING), ("proxima_dispensa", ASCENDING)], name="seguimiento"),
    ],
    "ventas": [
        IndexModel([("id_cliente", ASCENDING), ("fecha", DESCENDING)], name="por_cliente_fecha"),
        IndexModel([("id_farmaceutico", ASCENDING), ("fecha", DESCENDING)], name="por_farmaceutico_fecha"),
        IndexModel([("estado", ASCENDING), ("fecha", DESCENDING)], name="por_estado_fecha"),
        IndexModel([("tipo", ASCENDING), ("estado", ASCENDING)], name="por_tipo_estado"),
        IndexModel("items.id_producto", name="por_producto"),
    ],
    "outbox": [IndexModel([("procesado", ASCENDING), ("creado", ASCENDING)], name="pendientes")],
}

# Vista agregada para q11: ingresos por farmacéutico y mes, solo ventas Completada.
# No filtra por "mes actual" (eso depende del reloj): q11 la consulta con el mes de hoy.
VISTA_INGRESOS = "v_ingresos_farmaceutico_mes"
PIPELINE_INGRESOS = [
    {"$match": {"estado": "Completada"}},
    {"$group": {
        "_id": {
            "id_farmaceutico": "$id_farmaceutico",
            "mes": {"$dateToString": {"format": "%Y-%m", "date": "$fecha"}},
        },
        "ingresos": {"$sum": "$total"},
        "cantidad_ventas": {"$sum": 1},
    }},
    {"$project": {
        "_id": 0,
        "id_farmaceutico": "$_id.id_farmaceutico",
        "mes": "$_id.mes",
        "ingresos": 1,
        "cantidad_ventas": 1,
    }},
]


def crear_esquema(db: Database) -> None:
    """Crea colecciones (con validador estricto), índices y la vista. Supone la base vacía."""
    for nombre, validador in VALIDADORES.items():
        db.create_collection(nombre, validator=validador, validationLevel="strict", validationAction="error")
    for nombre, indices in INDICES.items():
        db[nombre].create_indexes(indices)
    db.create_collection(VISTA_INGRESOS, viewOn="ventas", pipeline=PIPELINE_INGRESOS)
