"""Errores de una comprobación de precio, con mensajes para personas.

Los textos de «bloqueo» y «sin precio» son los de la especificación común
(Android escribe los mismos en ``ultimo_error``); por eso el estado de la
última comprobación se puede deducir también de un ``ultimo_error`` que
llegue en un archivo importado.
"""

from __future__ import annotations

# Estados de la última comprobación (se guardan en productos.estado).
CORRECTA = "correcta"
SIN_PRECIO = "sin_precio"
BLOQUEADA = "bloqueada"
SIN_CONEXION = "sin_conexion"
ERROR = "error"
PENDIENTE = "pendiente"

TEXTOS_ESTADO = {
	CORRECTA: "comprobación correcta",
	SIN_PRECIO: "sin precio en la página",
	BLOQUEADA: "bloqueada por la tienda",
	SIN_CONEXION: "sin conexión",
	ERROR: "error al comprobar",
	PENDIENTE: "sin comprobar todavía",
}

MENSAJE_BLOQUEO = (
	"La tienda ha pedido comprobar que no eres un robot. Se volverá a intentar en la próxima comprobación."
)
MENSAJE_SIN_PRECIO = (
	"No se encontró el precio en la página. Puede que la tienda haya cambiado su diseño: "
	"prueba con un selector propio en Editar."
)
MENSAJE_SIN_CONEXION = "No hay conexión a Internet o no se pudo contactar con la tienda. Se volverá a intentar."
MENSAJE_TIEMPO = "La tienda ha tardado demasiado en responder. Se volverá a intentar en la próxima comprobación."
MENSAJE_NO_ENCONTRADA = "La página del producto no existe (error 404). Puede que la tienda la haya retirado."
MENSAJE_SERVIDOR = "La tienda tiene problemas en este momento (error {codigo}). Se volverá a intentar."
MENSAJE_HTTP = "La tienda respondió con un error (código {codigo})."
MENSAJE_CERTIFICADO = "No se pudo comprobar el certificado de seguridad de la tienda."
MENSAJE_DIRECCION = "La dirección del producto no es válida."
MENSAJE_DEMASIADO_GRANDE = "La página del producto es demasiado grande para analizarla."


class ErrorComprobacion(Exception):
	"""Fallo de una comprobación: ``estado`` (constante de este módulo) y mensaje en español."""

	def __init__(self, estado: str, mensaje: str) -> None:
		super().__init__(mensaje)
		self.estado = estado
		self.mensaje = mensaje


def estado_de_error(mensaje: str | None) -> str:
	"""Deduce el estado a partir de un ``ultimo_error`` (por ejemplo, importado de Android)."""
	if not mensaje:
		return CORRECTA
	texto = mensaje.lower()
	if "robot" in texto or "verificación" in texto or "bloque" in texto:
		return BLOQUEADA
	if "precio" in texto and ("no se encontró" in texto or "no se encontro" in texto or "decidir" in texto
		or "posición del precio" in texto):
		return SIN_PRECIO
	if "conexión" in texto or "conexion" in texto or "tardado" in texto or "tiempo" in texto:
		return SIN_CONEXION
	return ERROR
