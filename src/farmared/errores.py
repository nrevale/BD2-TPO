"""Errores de dominio. Los servicios de escritura los lanzan para rechazar una operación."""

from __future__ import annotations


class FarmaredError(Exception):
    """Base de los errores de la aplicación."""


class ValidacionError(FarmaredError):
    """Una regla de negocio o de integridad rechazó la operación.

    `codigo` es estable (para tests y para el informe); `mensaje` es para humanos.
    """

    def __init__(self, codigo: str, mensaje: str):
        super().__init__(f"[{codigo}] {mensaje}")
        self.codigo = codigo
        self.mensaje = mensaje


class StockInsuficiente(ValidacionError):
    """El stock vigente (no vencido) de la sucursal no alcanza para algún ítem."""

    def __init__(self, mensaje: str):
        super().__init__("STOCK_INSUFICIENTE", mensaje)


class ConexionError(FarmaredError):
    """No se pudo conectar a uno de los motores."""
