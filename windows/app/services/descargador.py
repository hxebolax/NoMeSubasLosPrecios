"""Descarga de las páginas de producto como lo haría un navegador de escritorio.

Reglas (especificación común y agente «red-http»):

- Cabeceras de Chrome para Windows, compresión gzip, redirecciones seguidas.
- Una ``requests.Session`` por tienda que vive toda la sesión de la
  aplicación: guarda las cookies en memoria (Coolmod, por ejemplo, las pone en
  una redirección 307 y las exige en la página siguiente).
- Tiempo de espera de conexión y de lectura por separado; nunca sin límite.
- Un solo reintento, a los 5 segundos, si falla la red o la tienda responde
  5xx. Nunca más de dos intentos: insistir más solo consigue que la tienda
  nos bloquee.
- 403 y 429 son «la tienda pide comprobar que no eres un robot»; el 202 sin
  precio (desafío AWS WAF de Amazon) se decide después de extraer.
- Errores en español para personas; en el registro, la URL sin parámetros.

Sin wx. La cancelación es cooperativa: ``cancelado`` es cualquier objeto con
``wait(segundos)`` e ``is_set()`` (``threading.Event`` o el token de tareas).
"""

from __future__ import annotations

import logging
import re
import threading
import urllib.parse
from dataclasses import dataclass

import requests

from app.services import errores
from app.services.errores import ErrorComprobacion

log = logging.getLogger(__name__)

USER_AGENT = (
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
	"Chrome/141.0.0.0 Safari/537.36"
)
CABECERAS = {
	"User-Agent": USER_AGENT,
	"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
	"Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
	"Accept-Encoding": "gzip, deflate",
	"Upgrade-Insecure-Requests": "1",
}
ESPERA_REINTENTO = 5.0
MAX_INTENTOS = 2
MAX_BYTES = 15 * 1024 * 1024
MAX_REDIRECCIONES = 10
_PATRON_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?([A-Za-z0-9_\-]+)""", re.IGNORECASE)


@dataclass
class Pagina:
	"""Página descargada."""

	html: str
	estado: int
	url_final: str


def redactar_url(url: str) -> str:
	"""URL sin parámetros ni fragmento, para el registro (pueden llevar datos personales)."""
	partes = urllib.parse.urlsplit(url)
	return urllib.parse.urlunsplit((partes.scheme, partes.netloc, partes.path, "", ""))


def _decodificar(contenido: bytes, cabecera_tipo: str) -> str:
	coincidencia = re.search(r"charset=([\w\-]+)", cabecera_tipo or "", re.IGNORECASE)
	candidatos = [coincidencia.group(1)] if coincidencia else []
	meta = _PATRON_CHARSET.search(contenido[:4096])
	if meta:
		candidatos.append(meta.group(1).decode("ascii", "ignore"))
	candidatos += ["utf-8", "cp1252"]
	for codificacion in candidatos:
		try:
			return contenido.decode(codificacion)
		except (LookupError, UnicodeDecodeError):
			log.debug("La página no está en %s; se prueba otra codificación", codificacion)
			continue
	return contenido.decode("utf-8", "replace")


class Descargador:
	"""Descarga páginas con una sesión (y sus cookies) por tienda."""

	def __init__(self, tiempo_espera: float = 25.0) -> None:
		self.tiempo_espera = float(tiempo_espera)
		self._sesiones: dict[str, requests.Session] = {}
		self._candado = threading.Lock()

	def sesion(self, dominio: str) -> requests.Session:
		"""Sesión de la tienda (se crea la primera vez). Cada tienda va en un solo hilo a la vez."""
		with self._candado:
			sesion = self._sesiones.get(dominio)
			if sesion is None:
				sesion = requests.Session()
				sesion.headers.update(CABECERAS)
				sesion.max_redirects = MAX_REDIRECCIONES
				self._sesiones[dominio] = sesion
			return sesion

	def cerrar(self) -> None:
		"""Cierra todas las sesiones (al salir de la aplicación)."""
		with self._candado:
			for sesion in self._sesiones.values():
				sesion.close()
			self._sesiones.clear()

	def descargar(
		self, url: str, dominio: str = "", cancelado: threading.Event | None = None, cabeceras: dict[str, str] | None = None
	) -> Pagina:
		"""Descarga ``url``. Lanza :class:`ErrorComprobacion` con el mensaje para el usuario.

		Las respuestas 202 y 400 se devuelven como página (con su ``estado``): si
		son un desafío o un bloqueo lo decide quien extrae (202 sin precio, o 400
		con un texto de bloqueo de la tienda).
		"""
		if not url.lower().startswith(("http://", "https://")):
			raise ErrorComprobacion(errores.ERROR, errores.MENSAJE_DIRECCION)
		sesion = self.sesion(dominio or urllib.parse.urlsplit(url).netloc.lower())
		ultimo: ErrorComprobacion | None = None
		for intento in range(1, MAX_INTENTOS + 1):
			if cancelado is not None and cancelado.is_set():
				raise ErrorComprobacion(errores.ERROR, "Comprobación cancelada.")
			try:
				return self._una_peticion(sesion, url, cabeceras)
			except _Reintentable as error:
				ultimo = error.error
				if intento < MAX_INTENTOS:
					log.info("Fallo transitorio en %s (%s); se reintenta en %.0f s", redactar_url(url), error.motivo, ESPERA_REINTENTO)
					if cancelado is not None:
						if cancelado.wait(ESPERA_REINTENTO):
							raise ErrorComprobacion(errores.ERROR, "Comprobación cancelada.") from None
					else:
						threading.Event().wait(ESPERA_REINTENTO)
		assert ultimo is not None
		raise ultimo

	def _una_peticion(self, sesion: requests.Session, url: str, cabeceras: dict[str, str] | None = None) -> Pagina:
		tiempos = (min(10.0, self.tiempo_espera), self.tiempo_espera)
		try:
			respuesta = sesion.get(url, timeout=tiempos, allow_redirects=True, stream=True, headers=cabeceras)
		except requests.exceptions.SSLError as error:
			log.warning("Certificado no válido en %s: %s", redactar_url(url), type(error).__name__)
			raise ErrorComprobacion(errores.ERROR, errores.MENSAJE_CERTIFICADO) from error
		except requests.exceptions.Timeout as error:
			raise _Reintentable("tiempo agotado", ErrorComprobacion(errores.SIN_CONEXION, errores.MENSAJE_TIEMPO)) from error
		except requests.exceptions.TooManyRedirects as error:
			raise ErrorComprobacion(errores.BLOQUEADA, errores.MENSAJE_BLOQUEO) from error
		except (requests.exceptions.InvalidURL, requests.exceptions.MissingSchema, requests.exceptions.InvalidSchema) as error:
			raise ErrorComprobacion(errores.ERROR, errores.MENSAJE_DIRECCION) from error
		except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as error:
			raise _Reintentable(
				"sin conexión", ErrorComprobacion(errores.SIN_CONEXION, errores.MENSAJE_SIN_CONEXION)
			) from error
		with respuesta:
			estado = respuesta.status_code
			log.debug("GET %s → %d", redactar_url(url), estado)
			if estado in (403, 429):
				raise ErrorComprobacion(errores.BLOQUEADA, errores.MENSAJE_BLOQUEO)
			if estado == 404 or estado == 410:
				raise ErrorComprobacion(errores.ERROR, errores.MENSAJE_NO_ENCONTRADA)
			if estado >= 500:
				raise _Reintentable(
					f"HTTP {estado}", ErrorComprobacion(errores.ERROR, errores.MENSAJE_SERVIDOR.format(codigo=estado))
				)
			if estado >= 400 and estado != 400:
				raise ErrorComprobacion(errores.ERROR, errores.MENSAJE_HTTP.format(codigo=estado))
			try:
				contenido = bytearray()
				for bloque in respuesta.iter_content(64 * 1024):
					contenido.extend(bloque)
					if len(contenido) > MAX_BYTES:
						raise ErrorComprobacion(errores.ERROR, errores.MENSAJE_DEMASIADO_GRANDE)
			except requests.exceptions.Timeout as error:
				raise _Reintentable("tiempo agotado", ErrorComprobacion(errores.SIN_CONEXION, errores.MENSAJE_TIEMPO)) from error
			except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as error:
				raise _Reintentable(
					"corte", ErrorComprobacion(errores.SIN_CONEXION, errores.MENSAJE_SIN_CONEXION)
				) from error
			html = _decodificar(bytes(contenido), respuesta.headers.get("Content-Type", ""))
			return Pagina(html=html, estado=estado, url_final=respuesta.url)


class _Reintentable(Exception):
	"""Fallo que merece un segundo intento (red o 5xx)."""

	def __init__(self, motivo: str, error: ErrorComprobacion) -> None:
		super().__init__(motivo)
		self.motivo = motivo
		self.error = error
