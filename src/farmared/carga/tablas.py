"""Definición de los 9 datasets: columnas, tipos, clave, enums y referencias.

Es la única fuente de verdad sobre el formato de los CSV; la usan el lector,
la validación y el esquema de MongoDB.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Tipos de columna. El sufijo "?" indica que admite nulo (celda vacía).
STR = "str"
STR_NULL = "str?"
INT = "int"
BOOL = "bool"
DATE = "date"
DATE_NULL = "date?"

OBRAS_SOCIALES = ("OSDE", "Swiss Medical", "PAMI", "IOMA", "Galeno", "Sin cobertura")
TIPOS_SUCURSAL = ("Farmacia", "Droguería")
CARGOS = ("Director Técnico", "Farmacéutico")
TIPOS_PROVEEDOR = ("Laboratorio", "Droguería")
CONDICIONES_VENTA = ("Venta libre", "Bajo receta", "Bajo receta archivada")
TIPOS_RECETA = ("Simple", "Archivada", "Tratamiento prolongado")
ESTADOS_RECETA = ("Vigente", "Completada", "Vencida")
TIPOS_VENTA = ("Venta libre", "Con receta")
MEDIOS_PAGO = ("Efectivo", "Débito", "Crédito", "Transferencia", "Obra social")
ESTADOS_VENTA = ("Completada", "Pendiente", "Anulada")


@dataclass(frozen=True)
class Tabla:
    nombre: str
    clave: str
    columnas: dict[str, str]
    enums: dict[str, tuple[str, ...]] = field(default_factory=dict)
    unicos: tuple[str, ...] = ()

    @property
    def archivo(self) -> str:
        return f"{self.nombre}.csv"


TABLAS: dict[str, Tabla] = {
    t.nombre: t
    for t in [
        Tabla(
            "clientes",
            "id_cliente",
            {
                "id_cliente": STR, "nombre": STR, "apellido": STR, "dni": STR, "email": STR,
                "telefono": STR, "ciudad": STR, "provincia": STR, "obra_social": STR,
                "nro_afiliado": STR_NULL, "activo": BOOL,
            },
            enums={"obra_social": OBRAS_SOCIALES},
            unicos=("dni",),
        ),
        Tabla(
            "sucursales",
            "id_sucursal",
            {
                "id_sucursal": STR, "nombre": STR, "tipo": STR, "direccion": STR, "ciudad": STR,
                "provincia": STR, "telefono": STR, "activo": BOOL,
            },
            enums={"tipo": TIPOS_SUCURSAL},
        ),
        Tabla(
            "farmaceuticos",
            "id_farmaceutico",
            {
                "id_farmaceutico": STR, "nombre": STR, "apellido": STR, "matricula": STR,
                "cargo": STR, "id_sucursal": STR, "activo": BOOL,
            },
            enums={"cargo": CARGOS},
            unicos=("matricula",),
        ),
        Tabla(
            "proveedores",
            "id_proveedor",
            {
                "id_proveedor": STR, "razon_social": STR, "cuit": STR, "tipo": STR, "ciudad": STR,
                "provincia": STR, "telefono": STR, "activo": BOOL,
            },
            enums={"tipo": TIPOS_PROVEEDOR},
            unicos=("cuit",),
        ),
        Tabla(
            "productos",
            "id_producto",
            {
                "id_producto": STR, "nombre": STR, "principio_activo": STR, "categoria": STR,
                "presentacion": STR, "condicion_venta": STR, "precio_unit": INT,
                "id_proveedor": STR, "activo": BOOL,
            },
            enums={"condicion_venta": CONDICIONES_VENTA},
        ),
        Tabla(
            "stock_lotes",
            "id_lote",
            {
                "id_lote": STR, "id_producto": STR, "id_sucursal": STR, "nro_lote": STR,
                "unidades": INT, "vencimiento": DATE,
            },
        ),
        Tabla(
            "recetas",
            "id_receta",
            {
                "id_receta": STR, "id_cliente": STR, "medico": STR, "matricula_medico": STR,
                "fecha_emision": DATE, "tipo": STR, "dispensas_autorizadas": INT,
                "dispensas_realizadas": INT, "proxima_dispensa": DATE_NULL, "estado": STR,
            },
            enums={"tipo": TIPOS_RECETA, "estado": ESTADOS_RECETA},
        ),
        Tabla(
            "ventas",
            "id_venta",
            {
                "id_venta": STR, "id_cliente": STR, "id_farmaceutico": STR, "id_receta": STR_NULL,
                "fecha": DATE, "tipo": STR, "medio_pago": STR, "total": INT, "estado": STR,
            },
            enums={"tipo": TIPOS_VENTA, "medio_pago": MEDIOS_PAGO, "estado": ESTADOS_VENTA},
        ),
        Tabla(
            "detalle_ventas",
            "id_detalle",
            {
                "id_detalle": STR, "id_venta": STR, "id_producto": STR, "cantidad": INT,
                "precio_unit": INT,
            },
        ),
    ]
}

# Referencias entre datasets (enunciado §2.10): (tabla, columna, tabla referenciada).
REFERENCIAS: list[tuple[str, str, str]] = [
    ("farmaceuticos", "id_sucursal", "sucursales"),
    ("productos", "id_proveedor", "proveedores"),
    ("stock_lotes", "id_producto", "productos"),
    ("stock_lotes", "id_sucursal", "sucursales"),
    ("recetas", "id_cliente", "clientes"),
    ("ventas", "id_cliente", "clientes"),
    ("ventas", "id_farmaceutico", "farmaceuticos"),
    ("ventas", "id_receta", "recetas"),
    ("detalle_ventas", "id_venta", "ventas"),
    ("detalle_ventas", "id_producto", "productos"),
]
