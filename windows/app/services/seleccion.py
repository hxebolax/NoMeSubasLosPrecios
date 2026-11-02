"""Selección asistida del precio: del candidato elegido a un selector CSS estable.

Apartados 7.2 y 7.3 de ``compartido/EXTRACTOR_GENERICO.md``: se genera el
selector más estable posible (``selector_css.generar_selector``), se valida
(el primer elemento que devuelve es el elegido y su importe es el mismo) y
se guarda con una huella (importe y texto de contexto) para detectar después
que la página ha cambiado. Sin wx.
"""

from __future__ import annotations

import logging

from soupsieve import SelectorSyntaxError

from app.services import selector_css
from app.services.comprobador import crear_huella
from app.services.extractor import CandidatoPrecio, importe_de_texto
from app.services.importes import importe_de_maquina

log = logging.getLogger(__name__)

MENSAJE_NO_VALIDO = "No se pudo crear una regla estable para ese precio. Pruebe con otra opción de la lista."


class ErrorSeleccion(Exception):
	"""El selector generado no pasa la validación (mensaje para el usuario)."""


def raiz_de(elemento):
	"""El documento al que pertenece un elemento de BeautifulSoup."""
	actual = elemento
	while getattr(actual, "parent", None) is not None:
		actual = actual.parent
	return actual


def _importe(elemento, atributo: str | None) -> float | None:
	if atributo:
		return importe_de_maquina(elemento.get(atributo))
	return importe_de_texto(elemento)[0]


def validar(sopa, selector: str, atributo: str | None, elegido, esperado: float) -> bool:
	"""El primer elemento del selector es el elegido y da el mismo importe."""
	try:
		encontrados = sopa.select(selector)
	except (SelectorSyntaxError, ValueError, NotImplementedError):
		return False
	if not encontrados or encontrados[0] is not elegido:
		return False
	return _importe(elegido, atributo) == esperado or importe_de_maquina(elegido.get("content")) == esperado


def selector_para(candidato: CandidatoPrecio) -> tuple[str, str]:
	"""(selector CSS, huella) para guardar en el producto. Lanza :class:`ErrorSeleccion`."""
	elemento = candidato.elemento
	if elemento is None:
		raise ErrorSeleccion(MENSAJE_NO_VALIDO)
	sopa = raiz_de(elemento)
	selector, atributo = selector_css.generar_selector(elemento, sopa)
	if not validar(sopa, selector, atributo, elemento, candidato.valor):
		log.info("El selector generado %r no pasa la validación", selector)
		raise ErrorSeleccion(MENSAJE_NO_VALIDO)
	return selector, crear_huella(candidato.valor, candidato.contexto, atributo)
