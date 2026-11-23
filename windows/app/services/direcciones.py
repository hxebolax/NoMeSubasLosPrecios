"""Limpieza de direcciones de productos y dominio de la tienda.

Contrato común con Android (``limpiarUrl`` y ``dominioDe``), probado con
``compartido/pruebas/direcciones.json``. Una URL limpia es la «identidad» de
un producto: con ella se detectan duplicados al añadir y se combinan los
datos al importar, así que las dos apps deben limpiar exactamente igual.

Solo se tocan el esquema, el host (a minúsculas), los parámetros de
seguimiento y el fragmento; la ruta y los demás parámetros se conservan tal
cual (con su codificación) porque algunas tiendas los necesitan.
"""

from __future__ import annotations

import re
import urllib.parse

# Parámetros de seguimiento que se quitan (nombre exacto).
PARAMETROS_SEGUIMIENTO = frozenset({
	"gclid", "fbclid", "ref", "ref_", "tag", "psc", "smid", "spLa", "th", "_encoding",
	"qid", "sr", "keywords", "crid", "sprefix", "dib", "dib_tag", "linkCode", "linkId", "srsltid", "suid",
})
# Prefijos de parámetros de seguimiento.
PREFIJOS_SEGUIMIENTO = ("utm_", "pd_rd_", "pf_rd_")

# ASIN de Amazon en /dp/, /gp/product/ o /gp/aw/d/.
_PATRON_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Za-z0-9]{10})(?:[/?#]|$)")
_PATRON_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"'«»]+", re.IGNORECASE)


def _es_seguimiento(clave: str) -> bool:
	return clave in PARAMETROS_SEGUIMIENTO or clave.startswith(PREFIJOS_SEGUIMIENTO)


def dominio_de_host(host: str) -> str:
	"""Host sin puerto, en minúsculas y sin ``www.`` ni ``m.`` delante."""
	host = (host or "").strip().lower().rstrip(".")
	if "@" in host:
		host = host.rsplit("@", 1)[1]
	if host.startswith("[") or host.count(":") == 1:
		host = host.split(":", 1)[0] if not host.startswith("[") else host
	for prefijo in ("www.", "m."):
		if host.startswith(prefijo):
			host = host[len(prefijo):]
	return host


def _con_esquema(url: str) -> str:
	url = (url or "").strip()
	if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
		url = "https://" + url.lstrip("/")
	return url


def dominio_de(url: str) -> str:
	"""Dominio de la tienda de una URL: ``https://www.Amazon.es/x`` → ``amazon.es``."""
	return dominio_de_host(urllib.parse.urlsplit(_con_esquema(url)).netloc)


def limpiar_url(url: str) -> str:
	"""Devuelve la dirección limpia que se guarda (ver «Direcciones» en la especificación)."""
	partes = urllib.parse.urlsplit(_con_esquema(url))
	host = partes.netloc.lower()
	dominio = dominio_de_host(host)
	if dominio.startswith("amazon.") or ".amazon." in dominio:
		asin = _PATRON_ASIN.search(partes.path + "/")
		if asin:
			tld = dominio.split("amazon.", 1)[1]
			return f"https://www.amazon.{tld}/dp/{asin.group(1)}"
	consulta = "&".join(
		trozo for trozo in partes.query.split("&")
		if trozo and not _es_seguimiento(urllib.parse.unquote_plus(trozo.split("=", 1)[0]))
	)
	esquema = partes.scheme.lower() or "https"
	return urllib.parse.urlunsplit((esquema, host, partes.path, consulta, ""))


def es_url(texto: str) -> bool:
	"""Indica si ``texto`` parece una dirección web (para el portapapeles)."""
	texto = (texto or "").strip()
	if not texto or " " in texto or "\n" in texto:
		return False
	partes = urllib.parse.urlsplit(_con_esquema(texto))
	return partes.scheme in ("http", "https") and "." in partes.netloc and len(partes.netloc) > 3


def extraer_primera_url(texto: str) -> str | None:
	"""Primera dirección de un texto (lo compartido o pegado suele traer más cosas)."""
	coincidencia = _PATRON_URL.search(texto or "")
	if not coincidencia:
		return None
	return coincidencia.group(0).rstrip(".,;:)]}»")
