"""Servicios de escritura q13–q15.

Reglas comunes:
- Escriben solo en MongoDB, dentro de una transacción (`db.client.start_session()` +
  `session.with_transaction(...)`), y registran un evento de outbox en esa misma transacción.
- Rechazan con `ValidacionError(codigo, mensaje)` (o `StockInsuficiente`) sin dejar escrituras a medias.
- Si reciben `driver`, después del commit proyectan el outbox en Neo4j.

Códigos de error usados (ValidacionError.codigo):
    DATO_INVALIDO, DNI_DUPLICADO, CAMPO_NO_MODIFICABLE,
    CLIENTE_INEXISTENTE, CLIENTE_INACTIVO,
    FARMACEUTICO_INEXISTENTE, FARMACEUTICO_INACTIVO, SUCURSAL_NO_FARMACIA,
    PRODUCTO_INEXISTENTE, PRODUCTO_INACTIVO, MEDIO_PAGO_INVALIDO,
    RECETA_REQUERIDA, RECETA_INEXISTENTE, RECETA_DE_OTRO_CLIENTE, RECETA_NO_VIGENTE,
    VENTA_INEXISTENTE, VENTA_NO_COMPLETADA, STOCK_YA_APLICADO, STOCK_INSUFICIENTE
"""
