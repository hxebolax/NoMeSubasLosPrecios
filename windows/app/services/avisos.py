"""Lógica de una comprobación: qué cambia en el producto y qué avisos se generan.

Función pura (sin base de datos ni wx): recibe el producto como estaba, lo
que se leyó en la página y los ajustes, y devuelve los cambios. Así se prueba
cada regla de la especificación común por separado (primera lectura,
objetivo, mínimo, bajada, subida, cambio mínimo, disponibilidad, errores) y
Windows y Android generan exactamente los mismos textos.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.services import errores
from app.services.importes import MENOS, formato_importe, formato_porcentaje, porcentaje_cambio, redondear

OBJETIVO = "objetivo"
MINIMO = "minimo"
BAJADA = "bajada"
SUBIDA = "subida"
DISPONIBLE = "disponible"
AGOTADO = "agotado"
ERROR = "error"
TIPOS = (OBJETIVO, MINIMO, BAJADA, SUBIDA, DISPONIBLE, AGOTADO, ERROR)

TITULOS = {
	OBJETIVO: "¡Precio deseado alcanzado!",
	MINIMO: "Mínimo histórico",
	BAJADA: "Ha bajado de precio",
	SUBIDA: "¡Te han subido el precio!",
	DISPONIBLE: "Vuelve a estar disponible",
	AGOTADO: "Agotado",
	ERROR: "No se puede leer el precio",
}
# Errores seguidos de un mismo producto que provocan el aviso de tipo «error».
ERRORES_PARA_AVISAR = 3

# Valores por defecto de los ajustes que usa esta lógica (claves de la especificación).
AJUSTES_POR_DEFECTO = {
	"avisar_bajadas": True,
	"avisar_subidas": True,
	"avisar_objetivo": True,
	"avisar_minimo": True,
	"avisar_disponible": True,
	"avisar_agotado": False,
	"avisar_errores": False,
	"cambio_minimo_porcentaje": 0.0,
}


@dataclass
class Aviso:
	"""Un aviso para guardar en la tabla ``avisos`` y enseñar como notificación."""

	tipo: str
	titulo: str
	mensaje: str


@dataclass
class Cambios:
	"""Resultado de aplicar una comprobación a un producto."""

	campos: dict[str, Any] = field(default_factory=dict)
	historial: tuple[str, float | None, bool] | None = None
	avisos: list[Aviso] = field(default_factory=list)


def _ajuste(ajustes: Mapping[str, Any] | None, clave: str) -> Any:
	if ajustes is not None and clave in ajustes:
		return ajustes[clave]
	return AJUSTES_POR_DEFECTO[clave]


def _texto_objetivo(nombre: str, p1: float, tienda: str, objetivo: float, moneda: str) -> str:
	return f"{nombre}: {formato_importe(p1, moneda)} en {tienda} (querías {formato_importe(objetivo, moneda)} o menos)."


def _texto_minimo(nombre: str, p1: float, tienda: str, p0: float, moneda: str) -> str:
	return f"{nombre}: {formato_importe(p1, moneda)} en {tienda}, el precio más bajo visto (antes {formato_importe(p0, moneda)})."


def _texto_cambio(nombre: str, p0: float, p1: float, tienda: str, moneda: str) -> str:
	signo = MENOS if p1 < p0 else "+"
	diferencia = formato_importe(abs(p1 - p0), moneda)
	porcentaje = formato_porcentaje(porcentaje_cambio(p0, p1))
	return (
		f"{nombre}: de {formato_importe(p0, moneda)} a {formato_importe(p1, moneda)} en {tienda} "
		f"({signo}{diferencia}, {signo}{porcentaje} %)."
	)


def texto_disponible(nombre: str, tienda: str, precio: float | None, moneda: str) -> str:
	if precio is None:
		return f"{nombre} vuelve a estar disponible en {tienda}."
	return f"{nombre} vuelve a estar disponible en {tienda} a {formato_importe(precio, moneda)}."


def texto_agotado(nombre: str, tienda: str) -> str:
	return f"{nombre} se ha agotado en {tienda}."


def texto_error(nombre: str, tienda: str, error: str) -> str:
	return f"{nombre} ({tienda}): {error}"


def aplicar_resultado(
	producto: Mapping[str, Any],
	precio: float | None,
	disponible: bool | None,
	*,
	ahora: str,
	tienda: str,
	ajustes: Mapping[str, Any] | None = None,
	nombre_pagina: str = "",
	imagen: str = "",
	moneda: str = "",
	origen_precio: str = "",
	confianza: str = "",
	desde: bool | None = None,
	hay_historial: bool = True,
) -> Cambios:
	"""Aplica una comprobación correcta (pasos 2 a 6 de «Comprobación y avisos»).

	:param producto: fila actual (``precio_actual``, ``disponible``, ``precio_minimo``...).
	:param precio: precio leído, o ``None`` si la página dice agotado sin precio.
	:param disponible: disponibilidad leída.
	:param hay_historial: si el producto ya tiene alguna fila de historial (si no,
		esta comprobación la crea aunque no haya cambios).
	"""
	cambios = Cambios()
	campos = cambios.campos
	campos.update(ultimo_error="", errores_seguidos=0, ultima_comprobacion=ahora, estado=errores.CORRECTA)
	if origen_precio:
		campos["origen_precio"] = origen_precio
	if confianza:
		campos["confianza"] = confianza
	if desde is not None and precio is not None:
		campos["desde"] = 1 if desde else 0
	nombre = (producto.get("nombre") or "").strip()
	if not nombre and nombre_pagina:
		nombre = nombre_pagina.strip()
		campos["nombre"] = nombre
	if imagen and imagen != (producto.get("imagen_url") or ""):
		campos["imagen_url"] = imagen
	moneda = (moneda or producto.get("moneda") or "EUR").upper()
	if moneda != (producto.get("moneda") or ""):
		campos["moneda"] = moneda

	p0 = redondear(producto.get("precio_actual"))
	p1 = redondear(precio)
	d0 = bool(producto.get("disponible", True))
	d1 = d0 if disponible is None else bool(disponible)
	objetivo = redondear(producto.get("precio_objetivo"))
	minimo_anterior = redondear(producto.get("precio_minimo"))
	avisar_disponible_producto = bool(producto.get("avisar_disponible", True))

	aviso_precio: Aviso | None = None
	precio_cambiado = False
	if p1 is not None and p0 is None:
		# 4. Primera lectura.
		campos.update(
			precio_actual=p1, precio_inicial=p1, precio_minimo=p1, fecha_minimo=ahora, precio_maximo=p1, fecha_maximo=ahora
		)
		precio_cambiado = True
		if objetivo is not None and p1 <= objetivo and _ajuste(ajustes, "avisar_objetivo"):
			aviso_precio = Aviso(OBJETIVO, TITULOS[OBJETIVO], _texto_objetivo(nombre, p1, tienda, objetivo, moneda))
	elif p1 is not None and p0 is not None and p1 != p0:
		# 5. Cambio de precio.
		precio_cambiado = True
		campos.update(precio_actual=p1, precio_anterior=p0, fecha_cambio=ahora)
		if minimo_anterior is None or p1 < minimo_anterior:
			campos.update(precio_minimo=p1, fecha_minimo=ahora)
		maximo_anterior = redondear(producto.get("precio_maximo"))
		if maximo_anterior is None or p1 > maximo_anterior:
			campos.update(precio_maximo=p1, fecha_maximo=ahora)
		cambio = porcentaje_cambio(p0, p1)
		umbral = float(_ajuste(ajustes, "cambio_minimo_porcentaje") or 0)
		if abs(cambio) >= umbral:
			alerta = float(producto.get("alerta_porcentaje") or 0)
			if objetivo is not None and p1 <= objetivo < p0 and _ajuste(ajustes, "avisar_objetivo"):
				aviso_precio = Aviso(OBJETIVO, TITULOS[OBJETIVO], _texto_objetivo(nombre, p1, tienda, objetivo, moneda))
			elif minimo_anterior is not None and p1 < minimo_anterior and _ajuste(ajustes, "avisar_minimo"):
				aviso_precio = Aviso(MINIMO, TITULOS[MINIMO], _texto_minimo(nombre, p1, tienda, p0, moneda))
			elif p1 < p0 and _ajuste(ajustes, "avisar_bajadas") and (alerta <= 0 or -cambio >= alerta):
				aviso_precio = Aviso(BAJADA, TITULOS[BAJADA], _texto_cambio(nombre, p0, p1, tienda, moneda))
			elif p1 > p0 and _ajuste(ajustes, "avisar_subidas"):
				aviso_precio = Aviso(SUBIDA, TITULOS[SUBIDA], _texto_cambio(nombre, p0, p1, tienda, moneda))

	# 6. Cambio de disponibilidad.
	aviso_disponibilidad: Aviso | None = None
	disponibilidad_cambiada = d1 != d0
	if disponibilidad_cambiada:
		campos["disponible"] = 1 if d1 else 0
		precio_referencia = p1 if p1 is not None else p0
		if d1 and _ajuste(ajustes, "avisar_disponible") and avisar_disponible_producto:
			aviso_disponibilidad = Aviso(
				DISPONIBLE, TITULOS[DISPONIBLE], texto_disponible(nombre, tienda, precio_referencia, moneda)
			)
		elif not d1 and _ajuste(ajustes, "avisar_agotado"):
			aviso_disponibilidad = Aviso(AGOTADO, TITULOS[AGOTADO], texto_agotado(nombre, tienda))

	if aviso_precio is not None and aviso_disponibilidad is not None:
		# Un solo aviso por producto y comprobación: la disponibilidad va en el mismo mensaje.
		aviso_precio.mensaje = f"{aviso_precio.mensaje} {aviso_disponibilidad.mensaje}"
		cambios.avisos.append(aviso_precio)
	elif aviso_precio is not None:
		cambios.avisos.append(aviso_precio)
	elif aviso_disponibilidad is not None:
		cambios.avisos.append(aviso_disponibilidad)

	if precio_cambiado or disponibilidad_cambiada or not hay_historial:
		cambios.historial = (ahora, p1 if p1 is not None else p0, d1)
	return cambios


def aplicar_error(
	producto: Mapping[str, Any],
	mensaje: str,
	*,
	ahora: str,
	tienda: str,
	estado: str = errores.ERROR,
	ajustes: Mapping[str, Any] | None = None,
) -> Cambios:
	"""Paso 1: la comprobación falló. Solo cambian el error, el contador y la fecha."""
	seguidos = int(producto.get("errores_seguidos") or 0) + 1
	cambios = Cambios(
		campos={"ultimo_error": mensaje, "errores_seguidos": seguidos, "ultima_comprobacion": ahora, "estado": estado}
	)
	if seguidos == ERRORES_PARA_AVISAR and _ajuste(ajustes, "avisar_errores"):
		nombre = (producto.get("nombre") or "").strip() or (producto.get("url") or "")
		cambios.avisos.append(Aviso(ERROR, TITULOS[ERROR], texto_error(nombre, tienda, mensaje)))
	return cambios


def texto_resumen(cantidad: int) -> str:
	"""Resumen cuando una comprobación genera más de 3 avisos."""
	return f"{cantidad} productos han cambiado de precio"
