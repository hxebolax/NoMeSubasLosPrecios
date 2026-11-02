"""Comprobación de precios: descarga, extracción, avisos y guardado.

- Las tiendas distintas se comprueban en paralelo, como mucho 3 a la vez;
  los productos de una misma tienda van de uno en uno con una pausa de
  ``pausa_entre_peticiones`` segundos más un valor al azar (0 a 2 s), para no
  parecer un robot y no cargar a la tienda.
- Cancelación cooperativa: ``cancelado`` es un ``threading.Event`` (o el
  token del gestor de tareas). Las pausas usan ``cancelado.wait`` y no
  ``time.sleep``, así que «Cancelar» o cerrar la aplicación se atienden al
  momento.
- Sin wx: el progreso se entrega con una función que la interfaz pasa a su
  hilo con ``wx.CallAfter``.
"""

from __future__ import annotations

import json
import logging
import random
import re
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from app.services import avisos as logica
from app.services import errores
from app.services.descargador import Descargador, redactar_url
from app.services.errores import ErrorComprobacion
from app.services import api_tienda
from app.services.extractor import (
	BAJA,
	MEDIA,
	ORIGEN_PRODUCTO,
	CandidatoPrecio,
	Resultado,
	candidatos_para_elegir,
	extraer,
	hay_bloqueo,
)
from app.services.reglas import CatalogoReglas
from app.services.repositorio import Repositorio, ahora_iso

log = logging.getLogger(__name__)

MAX_TIENDAS_EN_PARALELO = 3
AZAR_PAUSA = 2.0
# Cambio de precio que, con confianza media o baja, se vuelve a comprobar.
CAMBIO_SOSPECHOSO = 0.5
ESPERA_RECOMPROBACION = 3.0
MENSAJE_SIN_NAVEGADOR = (
	"Esta tienda necesita el navegador integrado y no está disponible. Instale el runtime WebView2 de Microsoft "
	"(https://developer.microsoft.com/microsoft-edge/webview2/) y vuelva a intentarlo."
)
# Navegador integrado: (url, cancelado) -> html; lo pone la interfaz (wx.html2 en el hilo principal).
Navegador = Callable[..., str]


def leer_huella(texto: str | None) -> dict[str, Any]:
	"""Huella de un selector elegido: ``{"importe": 39.99, "contexto": "...", "atributo": "content"}``.

	Formato común con Android (ver la especificación); se acepta también
	``texto`` como sinónimo de ``contexto``.
	"""
	if not texto:
		return {}
	try:
		datos = json.loads(texto)
	except (json.JSONDecodeError, ValueError):
		return {}
	if not isinstance(datos, dict):
		return {}
	if "contexto" not in datos and "texto" in datos:
		datos["contexto"] = datos["texto"]
	return datos


def crear_huella(importe: float, contexto: str, atributo: str | None = None) -> str:
	return json.dumps(
		{"importe": importe, "contexto": (contexto or "")[:120], "atributo": atributo or ""}, ensure_ascii=False
	)


_RE_RAIZ_VACIA = re.compile(
	r"""<(?:div|main)[^>]*\bid=["'](?:root|app|__next)["'][^>]*>\s*</(?:div|main)>|<app-root[^>]*>\s*</app-root>""", re.I
)


def parece_javascript(html: str) -> bool:
	"""La página parece montada con JavaScript: muy poco texto visible o una raíz vacía."""
	if not html:
		return True
	if "__NEXT_DATA__" in html or _RE_RAIZ_VACIA.search(html):
		return True
	sin_scripts = re.sub(r"<(script|style|noscript|template)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
	texto = re.sub(r"<[^>]+>", " ", sin_scripts)
	return len(" ".join(texto.split())) < 200


@dataclass
class AvisoGuardado:
	"""Aviso ya guardado en la base, listo para notificar."""

	id: int
	producto_id: int | None
	tipo: str
	titulo: str
	mensaje: str


@dataclass
class Resumen:
	"""Resultado de una comprobación de varios productos."""

	total: int = 0
	comprobados: int = 0
	correctos: int = 0
	con_error: int = 0
	bloqueados: int = 0
	cambios_precio: int = 0
	cancelado: bool = False
	avisos: list[AvisoGuardado] = field(default_factory=list)
	fecha: str = ""

	def texto(self) -> str:
		"""Frase para la barra de estado y el lector de pantalla."""
		if self.total == 0:
			return "No hay productos activos que comprobar."
		partes = [f"Comprobados {self.comprobados} de {self.total} productos"]
		if self.cambios_precio:
			partes.append(f"{self.cambios_precio} con cambios de precio" if self.cambios_precio != 1 else "1 con cambio de precio")
		else:
			partes.append("sin cambios de precio")
		if self.bloqueados:
			partes.append(f"{self.bloqueados} bloqueados por la tienda")
		otros = self.con_error - self.bloqueados
		if otros:
			partes.append(f"{otros} con error" if otros != 1 else "1 con error")
		texto = ", ".join(partes) + "."
		if self.cancelado:
			texto = "Comprobación cancelada. " + texto
		return texto


class Comprobador:
	"""Comprueba productos y guarda los resultados."""

	def __init__(
		self,
		repositorio: Repositorio,
		descargador: Descargador,
		catalogo: Callable[[], CatalogoReglas],
		ajustes: Callable[[], Mapping[str, Any]],
	) -> None:
		self.repositorio = repositorio
		self.descargador = descargador
		self._catalogo = catalogo
		self._ajustes = ajustes
		self._candado_resumen = threading.Lock()
		#: Navegador integrado (lo pone la interfaz); ``None`` = solo descarga normal.
		self.navegador: Navegador | None = None

	# ── Una página ───────────────────────────────────────────────────────────

	def _descargar_html(
		self, url: str, dominio: str, modo: str, reglas: Any, cancelado: threading.Event | None,
		tiene_precio: Callable[[str], bool] | None = None,
	) -> tuple[str, int, bool]:
		"""(html, estado HTTP, ¿con el navegador?) según el modo de descarga de la tienda."""
		con_navegador = modo == "navegador" or (modo == "auto" and reglas is not None and reglas.navegador)
		if con_navegador:
			return self._con_navegador(url, cancelado, tiene_precio), 200, True
		try:
			pagina = self.descargador.descargar(url, dominio, cancelado)
		except ErrorComprobacion as error:
			if error.estado == errores.BLOQUEADA and modo == "auto" and self.navegador is not None:
				log.info("Bloqueo en la descarga normal de %s; se repite con el navegador integrado", redactar_url(url))
				return self._con_navegador(url, cancelado, tiene_precio), 200, True
			raise
		return pagina.html, pagina.estado, False

	def _con_navegador(
		self, url: str, cancelado: threading.Event | None, tiene_precio: Callable[[str], bool] | None = None
	) -> str:
		if self.navegador is None:
			raise ErrorComprobacion(errores.ERROR, MENSAJE_SIN_NAVEGADOR)
		return self.navegador(url, cancelado, tiene_precio)

	def _por_api(self, url: str, dominio: str, reglas: Any, cancelado: threading.Event | None) -> Resultado | None:
		"""Paso 2 bis: la API pública de la tienda, si ``tiendas.json`` la declara."""
		if reglas is None or not reglas.api:
			return None
		direccion = api_tienda.url_api(reglas.api, url)
		if not direccion:
			return None
		try:
			pagina = self.descargador.descargar(direccion, dominio, cancelado, cabeceras={"Accept": "application/json"})
		except ErrorComprobacion as error:
			log.info("La API de la tienda falló (%s); se sigue con la página", error.mensaje)
			return None
		resultado = api_tienda.resultado_de_api(reglas.api, pagina.html)
		return resultado if resultado.valido else None

	def analizar(
		self,
		url: str,
		dominio: str,
		*,
		nombre_tienda: str = "",
		selector_producto: str | None = None,
		selector_tienda: str | None = None,
		selector_titulo: str | None = None,
		selector_disponible: str | None = None,
		variante: str | None = None,
		modo_descarga: str = "auto",
		huella: str | None = None,
		precio_conocido: float | None = None,
		cancelado: threading.Event | None = None,
		lanzar: bool = True,
	) -> Resultado:
		"""Descarga y extrae sin guardar nada. Con ``lanzar``, un resultado no válido es :class:`ErrorComprobacion`.

		Con ``lanzar=False`` devuelve el resultado tal cual (con sus candidatos):
		lo usa «Añadir producto» para ofrecer la selección asistida.
		"""
		ajustes = self._ajustes()
		self.descargador.tiempo_espera = float(ajustes.get("tiempo_espera", 25) or 25)
		catalogo = self._catalogo()
		reglas = catalogo.buscar(dominio)
		modo = modo_descarga if modo_descarga in ("auto", "directo", "navegador") else "auto"
		if not (selector_producto or "").strip() and not (selector_tienda or "").strip():
			por_api = self._por_api(url, dominio, reglas, cancelado)
			if por_api is not None:
				return por_api
		def tiene_precio(codigo: str) -> bool:
			return extraer(codigo, dominio, catalogo, url=url, pasos_genericos=False).precio is not None

		html, estado, con_navegador = self._descargar_html(url, dominio, modo, reglas, cancelado, tiene_precio)

		atributo_elegido = str(leer_huella(huella).get("atributo") or "")

		def analizar_html(codigo: str, selector: str | None) -> Resultado:
			return extraer(
				codigo, dominio, catalogo, url=url, nombre_tienda=nombre_tienda or catalogo.nombre_tienda(dominio),
				selector_producto=selector, atributo_producto=atributo_elegido if selector else "",
				selector_tienda=selector_tienda, selector_titulo=selector_titulo,
				selector_disponible=selector_disponible, variante=variante,
			)

		resultado = analizar_html(html, selector_producto)
		if (
			modo == "auto" and not con_navegador and self.navegador is not None and not resultado.valido
			and (resultado.bloqueo or estado in (202, 400) or parece_javascript(html))
		):
			log.info("Página de %s sin precio y montada con JavaScript o bloqueada: se usa el navegador", dominio)
			try:
				html = self._con_navegador(url, cancelado, tiene_precio)
				estado, con_navegador = 200, True
				resultado = analizar_html(html, selector_producto)
			except ErrorComprobacion as error:
				log.info("El navegador integrado tampoco pudo: %s", error.mensaje)
		pagina_final = html
		resultado = self._revisar_selector(
			resultado, selector_producto, huella, precio_conocido, lambda: analizar_html(pagina_final, None)
		)
		if estado == 202 and resultado.precio is None:
			# Desafío de AWS WAF (Amazon): responde 202 con una página sin producto.
			resultado.bloqueo = True
		if estado == 400 and resultado.precio is None and hay_bloqueo(html, catalogo, reglas):
			resultado.bloqueo = True
		if estado == 400 and not resultado.valido and not resultado.bloqueo and lanzar:
			raise ErrorComprobacion(errores.ERROR, errores.MENSAJE_HTTP.format(codigo=400))
		if not resultado.valido and lanzar:
			log.info("Sin precio en %s (%s)", redactar_url(url), resultado.estado)
			raise ErrorComprobacion(resultado.estado, resultado.error or errores.MENSAJE_SIN_PRECIO)
		return resultado

	@staticmethod
	def _revisar_selector(
		resultado: Resultado,
		selector: str | None,
		huella: str | None,
		precio_conocido: float | None,
		automatico: Callable[[], Resultado],
	) -> Resultado:
		"""Selector elegido por el usuario: si deja de encontrar el precio, nunca un precio dudoso.

		Si el selector no da nada, o da un importe que se aleja más de un 70 %
		de su huella, se prueba la extracción automática: si da el mismo precio
		que el conocido, vale; si da otro, es «la posición del precio ha cambiado».
		"""
		if not (selector or "").strip() or not huella:
			return resultado
		importe_huella = leer_huella(huella).get("importe")
		del_selector = resultado.origen_precio == ORIGEN_PRODUCTO and resultado.precio is not None
		if del_selector and (not importe_huella or abs(resultado.precio - importe_huella) <= 0.7 * importe_huella):
			return resultado
		otro = automatico()
		if otro.precio is not None and precio_conocido is not None and abs(otro.precio - precio_conocido) < 0.005:
			return otro
		if otro.precio is None and otro.disponible is False:
			return otro
		return Resultado(nombre=otro.nombre, imagen=otro.imagen, moneda=otro.moneda, selector_roto=True)

	def pagina_para_elegir(
		self, url: str, dominio: str, modo_descarga: str = "auto", cancelado: threading.Event | None = None
	) -> list[CandidatoPrecio]:
		"""«Elegir el precio en la página»: todos los candidatos visibles, aunque la extracción automática funcione."""
		catalogo = self._catalogo()
		reglas = catalogo.buscar(dominio)
		modo = modo_descarga if modo_descarga in ("auto", "directo", "navegador") else "auto"
		html, _estado, con_navegador = self._descargar_html(url, dominio, modo, reglas, cancelado)
		candidatos, _sopa = candidatos_para_elegir(html, url)
		if not candidatos and not con_navegador and modo == "auto" and self.navegador is not None and parece_javascript(html):
			candidatos, _sopa = candidatos_para_elegir(self._con_navegador(url, cancelado), url)
		return candidatos

	def argumentos(self, producto: Mapping[str, Any]) -> dict[str, Any]:
		"""Argumentos de ``analizar`` para un producto guardado."""
		return {
			"nombre_tienda": producto.get("tienda") or producto.get("dominio") or "",
			"selector_producto": producto.get("selector_precio"),
			"selector_tienda": producto.get("tienda_selector_precio"),
			"selector_titulo": producto.get("tienda_selector_titulo"),
			"selector_disponible": producto.get("tienda_selector_disponible"),
			"variante": producto.get("variante"),
			"modo_descarga": producto.get("tienda_modo_descarga") or "auto",
			"huella": producto.get("huella_selector"),
			"precio_conocido": producto.get("precio_actual"),
		}

	def comprobar_producto(
		self, producto: Mapping[str, Any], cancelado: threading.Event | None = None
	) -> tuple[logica.Cambios, list[AvisoGuardado]]:
		"""Comprueba un producto, guarda los cambios y devuelve los avisos guardados."""
		ajustes = self._ajustes()
		tienda = producto.get("tienda") or producto.get("dominio") or ""
		ahora = ahora_iso()
		argumentos = self.argumentos(producto)
		try:
			resultado = self.analizar(producto["url"], producto.get("dominio") or "", cancelado=cancelado, **argumentos)
			anterior = producto.get("precio_actual")
			if (
				resultado.confianza in (MEDIA, BAJA) and anterior and resultado.precio is not None
				and abs(resultado.precio - anterior) / anterior > CAMBIO_SOSPECHOSO
			):
				# Confianza media o baja y un cambio de más del 50 %: se vuelve a comprobar una vez.
				log.info("Cambio de más del 50 %% con confianza %s en el producto %s: se recomprueba",
					resultado.confianza, producto.get("id"))
				if cancelado is not None and cancelado.wait(ESPERA_RECOMPROBACION):
					raise ErrorComprobacion(errores.ERROR, "Comprobación cancelada.")
				resultado = self.analizar(producto["url"], producto.get("dominio") or "", cancelado=cancelado, **argumentos)
		except ErrorComprobacion as error:
			cambios = logica.aplicar_error(
				producto, error.mensaje, ahora=ahora, tienda=tienda, estado=error.estado, ajustes=ajustes
			)
		else:
			cambios = logica.aplicar_resultado(
				producto,
				resultado.precio,
				resultado.disponible,
				ahora=ahora,
				tienda=tienda,
				ajustes=ajustes,
				nombre_pagina=resultado.nombre,
				imagen=resultado.imagen,
				moneda=resultado.moneda,
				origen_precio=resultado.origen_precio,
				confianza=resultado.confianza,
				desde=resultado.desde and not producto.get("variante"),
				hay_historial=self.repositorio.tiene_historial(int(producto["id"])),
			)
		ids = self.repositorio.aplicar_cambios(int(producto["id"]), cambios, ahora)
		guardados = [
			AvisoGuardado(i, int(producto["id"]), a.tipo, a.titulo, a.mensaje) for i, a in zip(ids, cambios.avisos, strict=True)
		]
		return cambios, guardados

	# ── Varios productos ─────────────────────────────────────────────────────

	def comprobar(
		self,
		ids: list[int] | None = None,
		cancelado: threading.Event | None = None,
		al_progresar: Callable[[int, int, str], None] | None = None,
		incluir_pausados: bool = False,
	) -> Resumen:
		"""Comprueba los productos indicados (o todos los activos).

		:param al_progresar: ``(hechos, total, nombre)`` tras cada producto (desde un hilo).
		"""
		cancelado = cancelado or threading.Event()
		productos = self.repositorio.productos_por_ids(ids) if ids is not None else self.repositorio.productos()
		if not incluir_pausados:
			productos = [p for p in productos if p.get("activo")]
		resumen = Resumen(total=len(productos), fecha=ahora_iso())
		if not productos:
			return resumen
		por_tienda: dict[str, list[dict[str, Any]]] = {}
		for producto in productos:
			por_tienda.setdefault(producto.get("dominio") or "", []).append(producto)
		ajustes = self._ajustes()
		pausa = max(0.0, float(ajustes.get("pausa_entre_peticiones", 3) or 0))

		def una_tienda(lista: list[dict[str, Any]]) -> None:
			try:
				comprobar_lista(lista)
			finally:
				# Los hilos del grupo son efímeros: su conexión de lectura se cierra al acabar.
				self.repositorio.bd.cerrar_lectura_del_hilo()

		def comprobar_lista(lista: list[dict[str, Any]]) -> None:
			for indice, producto in enumerate(lista):
				if cancelado.is_set():
					return
				if indice and cancelado.wait(pausa + random.uniform(0, AZAR_PAUSA)):  # noqa: S311 - no es criptografía
					return
				try:
					cambios, guardados = self.comprobar_producto(producto, cancelado)
				except Exception:
					log.exception("Fallo inesperado al comprobar el producto %s", producto.get("id"))
					with self._candado_resumen:
						resumen.comprobados += 1
						resumen.con_error += 1
					continue
				with self._candado_resumen:
					resumen.comprobados += 1
					estado = cambios.campos.get("estado")
					if estado == errores.CORRECTA:
						resumen.correctos += 1
						if "precio_anterior" in cambios.campos:
							resumen.cambios_precio += 1
					else:
						resumen.con_error += 1
						if estado == errores.BLOQUEADA:
							resumen.bloqueados += 1
					resumen.avisos.extend(guardados)
					hechos = resumen.comprobados
				if al_progresar is not None:
					try:
						al_progresar(hechos, resumen.total, producto.get("nombre") or producto.get("url") or "")
					except Exception:
						log.exception("Error al informar del progreso")

		with ThreadPoolExecutor(max_workers=MAX_TIENDAS_EN_PARALELO, thread_name_prefix="comprobar") as grupo:
			futuros = [grupo.submit(una_tienda, lista) for lista in por_tienda.values()]
			for futuro in futuros:
				futuro.result()
		resumen.cancelado = cancelado.is_set()
		log.info("Comprobación terminada: %s", resumen.texto())
		return resumen
