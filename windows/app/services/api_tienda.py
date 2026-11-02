"""Reglas ``api`` de ``tiendas.json``: precio desde la API pública de la tienda.

Algunas tiendas (Mercadona, Consum, BM) no traen el precio en el HTML (son
aplicaciones de una sola página), pero tienen una API pública por producto::

	"api": {
	  "id_desde_url": "/product/(\\d+)",
	  "url": "https://tienda.mercadona.es/api/products/{id}/",
	  "precio": ["price_instructions.unit_price"],
	  "nombre": ["display_name"],
	  "imagen": ["photos.0.regular"],
	  "disponible": {"ruta": "published", "igual": true}
	}

Rutas: claves separadas por puntos; un número es una posición de lista;
``clave[campo=valor]`` elige el primer elemento de una lista con ese valor.
Cada lista de rutas se prueba en orden. Sin wx ni red: la descarga la hace el
comprobador.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.extractor import ALTA, ORIGEN_API, Resultado
from app.services.importes import importe_de_maquina

log = logging.getLogger(__name__)

_PATRON_TROZO = re.compile(r"^(?P<clave>[^\[\]]*)(?:\[(?P<campo>[^=\]]+)=(?P<valor>[^\]]*)\])?$")


def url_api(api: dict, url_producto: str) -> str | None:
	"""Dirección de la API para este producto, o ``None`` si la dirección no encaja."""
	patron, plantilla = api.get("id_desde_url"), api.get("url")
	if not isinstance(patron, str) or not isinstance(plantilla, str):
		return None
	try:
		coincidencia = re.search(patron, url_producto or "")
	except re.error:
		log.warning("Expresión id_desde_url no válida en tiendas.json: %r", patron)
		return None
	if not coincidencia or not coincidencia.groups():
		return None
	return plantilla.replace("{id}", coincidencia.group(1))


def leer_ruta(datos: Any, ruta: str) -> Any:
	"""Valor de ``ruta`` (``a.b.0.c``, ``lista[id=X].valor``) o ``None``."""
	actual = datos
	for trozo in str(ruta).split("."):
		if actual is None:
			return None
		coincidencia = _PATRON_TROZO.match(trozo)
		if coincidencia is None:
			return None
		clave, campo, valor = coincidencia.group("clave"), coincidencia.group("campo"), coincidencia.group("valor")
		if clave:
			if isinstance(actual, list) and clave.isdigit():
				indice = int(clave)
				actual = actual[indice] if indice < len(actual) else None
			elif isinstance(actual, dict):
				actual = actual.get(clave)
			else:
				return None
		if campo is not None:
			if not isinstance(actual, list):
				return None
			actual = next((e for e in actual if isinstance(e, dict) and str(e.get(campo)) == valor), None)
	return actual


def _primero(datos: Any, rutas: Any) -> Any:
	for ruta in rutas if isinstance(rutas, list) else [rutas] if isinstance(rutas, str) else []:
		valor = leer_ruta(datos, ruta)
		if valor not in (None, ""):
			return valor
	return None


def _iguales(a: Any, b: Any) -> bool:
	if isinstance(a, bool) or isinstance(b, bool):
		return a is b or str(a).lower() == str(b).lower()
	return a == b or str(a) == str(b)


def resultado_de_api(api: dict, texto_json: str) -> Resultado:
	"""Analiza la respuesta de la API. Un JSON roto da un resultado sin precio."""
	resultado = Resultado(origen_precio=ORIGEN_API, confianza=ALTA)
	try:
		datos = json.loads(texto_json)
	except (json.JSONDecodeError, ValueError):
		log.info("La API de la tienda no devolvió JSON válido")
		resultado.origen_precio = ""
		return resultado
	precio = None
	for ruta in api.get("precio") or []:
		precio = importe_de_maquina(leer_ruta(datos, ruta))
		if precio is not None:
			break
	resultado.precio = precio
	nombre = _primero(datos, api.get("nombre"))
	resultado.nombre = " ".join(str(nombre).split()) if nombre else ""
	imagen = _primero(datos, api.get("imagen"))
	resultado.imagen = str(imagen) if imagen else ""
	regla = api.get("disponible")
	if isinstance(regla, dict) and regla.get("ruta"):
		valor = leer_ruta(datos, regla["ruta"])
		resultado.disponible = _iguales(valor, regla.get("igual")) if valor is not None else None
	if resultado.disponible is None and precio is not None:
		resultado.disponible = True
	return resultado
