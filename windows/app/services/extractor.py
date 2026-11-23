"""Extracción del precio, nombre, imagen, moneda y disponibilidad de una página.

El precio se busca con una LISTA ORDENADA DE ESTRATEGIAS (``ESTRATEGIAS``);
se usa el primer resultado válido (precio mayor que 0). Cada estrategia
devuelve un :class:`Hallazgo` con su «origen» y su «confianza», que se guardan
en el producto y se enseñan en los detalles. Orden (especificación común,
incluida la «Extracción ampliada»):

1. ``selector_precio`` del producto. 2. ``selector_precio`` de la tienda.
3. Reglas ``precio`` de ``tiendas.json``. 4. JSON-LD (con variantes,
ofertas en stock primero y sin productos relacionados). 5. Metadatos (nunca
``pretax``, ni a 0, ni tachados). 6. Microdatos. 7 a 12. Plataforma, estado
incrustado, analítica, heurística visible con puntuación y decisión
(``extractor_generico``, adaptado del prototipo común).

Si nada da un precio seguro, el resultado lleva los CANDIDATOS para que el
usuario elija (selección asistida) y, si hay variantes con precios
distintos, la lista de variantes y el precio menor marcado como «desde».

Analizador: BeautifulSoup con ``html.parser`` (sin lxml). Sin wx.
"""

from __future__ import annotations

import html as html_mod
import json
import logging
import re
import unicodedata
import urllib.parse
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup, Tag
from soupsieve import SelectorSyntaxError

from app.services import errores
from app.services import extractor_generico as generico
from app.services.direcciones import limpiar_url
from app.services.importes import analizar_importe, formato_importe, importe_de_maquina
from app.services.reglas import CatalogoReglas, Regla, ReglaDisponible, ReglasTienda

log = logging.getLogger(__name__)

# Orígenes del precio (se muestran en los detalles del producto).
ORIGEN_PRODUCTO = "selector del producto"
ORIGEN_TIENDA = "selector de la tienda"
ORIGEN_REGLA = "regla de la tienda"
ORIGEN_API = "API de la tienda"
ORIGEN_JSONLD = "JSON-LD"
ORIGEN_METADATOS = "metadatos"
ORIGEN_MICRODATOS = "microdatos"
ORIGEN_ANALISIS = "análisis de la página"
ORIGEN_ELEGIDO = "elegido por ti"

ALTA, MEDIA, BAJA = "alta", "media", "baja"

MENSAJE_CATEGORIA = "El producto ya no existe: la tienda redirige a una categoría."
MENSAJE_DUDOSO = "No se pudo decidir cuál es el precio. Abre el producto y elige el precio correcto."
MENSAJE_SELECTOR_ROTO = "La posición del precio en la página ha cambiado. Vuelve a elegir el precio en Editar."

TIPOS_PRODUCTO = {"product", "productgroup", "book", "individualproduct", "productmodel", "vehicle"}
CLAVES_RELACIONADOS = {"itemlistelement", "isrelatedto", "issimilarto"}
TIPOS_CATEGORIA = {"itemlist", "collectionpage"}

_DISPONIBLE_JSONLD = ("instock", "limitedavailability", "onlineonly", "preorder", "presale", "instoreonly")
_AGOTADO_JSONLD = ("outofstock", "soldout", "discontinued")
_DISPONIBLE_META = ("instock", "in stock", "available for order", "preorder")
_AGOTADO_META = ("oos", "out of stock")
_AGOTADO_USUARIO = (
	"agotado", "no disponible", "sin stock", "fuera de stock", "out of stock", "sold out", "unavailable",
)
_SIMBOLOS = (("€", "EUR"), ("£", "GBP"), ("$", "USD"))
_SEPARADORES_TITULO = (" | ", " - ", " – ", " — ", " · ")
_RE_PRECIO_PARTIDO = re.compile(r"(\d)\s*([.,])\s*(\d{2})(?!\d)")
# 1.1.0: «old» no cuenta en font-bold, semibold, gold, sold...; line-through (Tailwind) sí es tachado.
_RE_TACHADO_CLASE = re.compile(r"strike|line-through|(?<![bfghst])old|was|before|antes", re.IGNORECASE)
_ATRIBUTOS_VALOR = ("content", "data-price-amount", "data-price", "data-product-price", "data-price-value", "value")
MAX_CANDIDATOS = 8


@dataclass
class Variante:
	"""Variante de un producto (talla, color...) con su precio."""

	nombre: str
	precio: float | None
	clave: str = ""
	disponible: bool | None = None

	@property
	def texto(self) -> str:
		return f"{self.nombre}: {formato_importe(self.precio)}"


@dataclass
class CandidatoPrecio:
	"""Opción de la selección asistida: importe, descripción para el lector y su elemento."""

	valor: float
	descripcion: str
	puntos: float = 0.0
	contexto: str = ""
	elemento: Any = field(default=None, repr=False)


@dataclass
class Hallazgo:
	"""Lo que una estrategia saca de la página."""

	precio: float | None = None
	moneda: str | None = None
	nombre: str | None = None
	imagen: str | None = None
	disponible: bool | None = None
	origen: str = ""
	confianza: str = ALTA
	texto_precio: str = ""
	desde: bool = False
	variantes: list[Variante] = field(default_factory=list)
	plataforma: str = ""


@dataclass
class Resultado:
	"""Resultado de analizar una página."""

	precio: float | None = None
	moneda: str = "EUR"
	nombre: str = ""
	imagen: str = ""
	disponible: bool | None = None
	origen_precio: str = ""
	confianza: str = ""
	bloqueo: bool = False
	categoria: bool = False
	desde: bool = False
	variantes: list[Variante] = field(default_factory=list)
	candidatos: list[CandidatoPrecio] = field(default_factory=list)
	plataforma: str = ""
	selector_roto: bool = False

	@property
	def valido(self) -> bool:
		"""Hay precio, o la página dice que está agotado (también es una comprobación válida)."""
		if self.categoria or self.selector_roto:
			return False
		return self.precio is not None or self.disponible is False

	@property
	def dudoso(self) -> bool:
		"""Sin precio seguro pero con candidatos para que elija el usuario."""
		return not self.valido and not self.bloqueo and not self.categoria and bool(self.candidatos)

	@property
	def error(self) -> str | None:
		if self.valido:
			return None
		if self.categoria:
			return MENSAJE_CATEGORIA
		if self.selector_roto:
			return MENSAJE_SELECTOR_ROTO
		if self.bloqueo:
			return errores.MENSAJE_BLOQUEO
		if self.candidatos:
			return MENSAJE_DUDOSO
		return errores.MENSAJE_SIN_PRECIO

	@property
	def estado(self) -> str:
		if self.valido:
			return errores.CORRECTA
		if self.bloqueo:
			return errores.BLOQUEADA
		if self.categoria:
			return errores.ERROR
		return errores.SIN_PRECIO


@dataclass
class Contexto:
	"""Todo lo que necesitan las estrategias (se calcula una vez por página)."""

	html: str
	sopa: BeautifulSoup
	url: str = ""
	dominio: str = ""
	nombre_tienda: str = ""
	reglas: ReglasTienda | None = None
	selector_producto: str = ""
	#: Atributo que lee el selector elegido por el usuario (de su huella); vacío = el texto.
	atributo_producto: str = ""
	selector_tienda: str = ""
	selector_titulo: str = ""
	selector_disponible: str = ""
	variante: str = ""
	_jsonld: tuple[list[dict], bool] | None = field(default=None, repr=False)

	@property
	def productos_jsonld(self) -> list[dict]:
		if self._jsonld is None:
			self._jsonld = leer_jsonld(self.sopa)
		return self._jsonld[0]

	@property
	def jsonld_es_categoria(self) -> bool:
		if self._jsonld is None:
			self._jsonld = leer_jsonld(self.sopa)
		return self._jsonld[1]


Estrategia = Callable[[Contexto], "Hallazgo | None"]


# ════════════════════════════════════════════════════════════════════════════
# Utilidades
# ════════════════════════════════════════════════════════════════════════════


def normalizar_espacios(texto: str | None) -> str:
	"""Une los espacios (incluidos duros y finos) en uno y recorta."""
	return " ".join((texto or "").replace(" ", " ").replace(" ", " ").split())


def _sin_acentos(texto: str) -> str:
	descompuesto = unicodedata.normalize("NFKD", texto)
	return "".join(c for c in descompuesto if c.isalnum() and not unicodedata.combining(c)).lower()


def _seleccionar(sopa: BeautifulSoup, css: str) -> list:
	"""``sopa.select`` que nunca rompe la extracción por un selector mal escrito."""
	try:
		return sopa.select(css)
	except (SelectorSyntaxError, ValueError, NotImplementedError):
		log.warning("Selector CSS no válido, se ignora: %r", css)
		return []


def _texto(elemento) -> str:
	return normalizar_espacios(elemento.get_text(" ", strip=True))


def importe_de_texto(elemento) -> tuple[float | None, str]:
	"""Importe del TEXTO de un elemento uniendo sus partes («74 , 99 €», «109€ 95»).

	Las partes se unen sin separador y se normaliza ``(\\d)\\s*([.,])\\s*(\\d{2})``
	antes de ``analizar_importe`` (especificación, apartado 8 de las correcciones).
	"""
	visible = normalizar_espacios(elemento.get_text(" ", strip=True))
	unido = elemento.get_text("", strip=True).replace(" ", " ").replace(" ", " ")
	unido = _RE_PRECIO_PARTIDO.sub(r"\1\2\3", unido)
	return analizar_importe(unido), visible


def _valor_atributos(elemento) -> float | None:
	"""Importe de un atributo de máquina (``content``, ``data-price``...) si el texto no da nada."""
	for atributo in _ATRIBUTOS_VALOR:
		valor = elemento.get(atributo)
		if valor:
			numero = generico.numero_de_maquina(" ".join(valor) if isinstance(valor, list) else valor)
			if numero:
				return numero
	return None


def _valor_regla(elemento, regla: Regla) -> tuple[float | None, str]:
	if regla.atributo:
		bruto = elemento.get(regla.atributo)
		if isinstance(bruto, list):
			bruto = " ".join(bruto)
		texto = str(bruto or "")
		return importe_de_maquina(texto), texto
	precio, texto = importe_de_texto(elemento)
	if precio is None and not texto:
		# Selector que apunta a un <meta> o a un elemento con el importe en un atributo.
		precio = _valor_atributos(elemento)
	return precio, texto


def precio_por_reglas(sopa: BeautifulSoup, reglas: tuple[Regla, ...]) -> tuple[float | None, str]:
	"""Primer importe válido de una lista de reglas CSS (y de sus elementos, en orden)."""
	for regla in reglas:
		for elemento in _seleccionar(sopa, regla.css):
			precio, texto = _valor_regla(elemento, regla)
			if precio is not None:
				return precio, texto
	return None, ""


def texto_por_reglas(sopa: BeautifulSoup, reglas: tuple[Regla, ...]) -> str:
	"""Primer texto (o atributo) no vacío de una lista de reglas."""
	for regla in reglas:
		for elemento in _seleccionar(sopa, regla.css):
			if regla.atributo:
				valor = elemento.get(regla.atributo)
				valor = " ".join(valor) if isinstance(valor, list) else valor
			else:
				valor = _texto(elemento)
			valor = normalizar_espacios(str(valor or ""))
			if valor:
				return valor
	return ""


def disponible_por_reglas(sopa: BeautifulSoup, reglas: tuple[ReglaDisponible, ...]) -> bool | None:
	"""Disponibilidad según la primera regla cuyo elemento exista en la página."""
	for regla in reglas:
		elementos = _seleccionar(sopa, regla.css)
		if not elementos:
			continue
		texto = " ".join(_texto(e) for e in elementos).lower()
		if any(agotado == "" or agotado in texto for agotado in regla.agotado):
			return False
		return True
	return None


def moneda_por_simbolo(texto: str) -> str | None:
	"""EUR, GBP o USD según el símbolo que aparezca en el texto."""
	for simbolo, codigo in _SIMBOLOS:
		if simbolo in (texto or ""):
			return codigo
	return None


def disponibilidad_schema(valor: object) -> bool | None:
	"""``…/InStock`` → disponible; ``…/OutOfStock`` → agotado (sin distinguir mayúsculas)."""
	texto = str(valor or "").strip().lower().rstrip("/")
	if not texto:
		return None
	final = texto.rsplit("/", 1)[-1]
	if final.endswith(_AGOTADO_JSONLD):
		return False
	if final.endswith(_DISPONIBLE_JSONLD):
		return True
	return None


def _tachado(elemento) -> bool:
	"""El elemento o un ancestro cercano es un precio tachado (``del``, ``s``, clase «old»...)."""
	actual = elemento
	for _nivel in range(6):
		if actual is None or not isinstance(actual, Tag):
			return False
		if actual.name in ("del", "s", "strike"):
			return True
		# Sin las variantes de Tailwind («before:...», «[&_.x:not(.line-through)]:...»): describen a otros elementos.
		clases = " ".join(c for c in (actual.get("class") or []) if ":" not in c and "[" not in c)
		if clases and _RE_TACHADO_CLASE.search(clases):
			return True
		actual = actual.parent
	return False


# ════════════════════════════════════════════════════════════════════════════
# JSON-LD
# ════════════════════════════════════════════════════════════════════════════


def _minusculas(valor: object) -> object:
	"""Claves en minúsculas en todo el árbol (``"Price"`` en Casa del Libro)."""
	if isinstance(valor, dict):
		return {str(k).lower(): _minusculas(v) for k, v in valor.items()}
	if isinstance(valor, list):
		return [_minusculas(v) for v in valor]
	return valor


def _tipos(objeto: dict) -> set[str]:
	tipo = objeto.get("@type")
	tipos = tipo if isinstance(tipo, list) else [tipo]
	return {t.rsplit("/", 1)[-1].lower() for t in tipos if isinstance(t, str)}


def _es_producto(objeto: dict) -> bool:
	return bool(_tipos(objeto) & TIPOS_PRODUCTO)


def _recorrer_productos(valor: object, dentro_de_producto: bool = False) -> Iterator[dict]:
	"""Product de primer nivel en orden, sin los de listas ni los relacionados.

	Se salta lo que cuelga de ``itemListElement``, ``isRelatedTo``,
	``isSimilarTo``, de un ``ItemList`` y de las ``offers``/``hasVariant`` de
	otro producto (las variantes se tratan dentro de su ProductGroup).
	"""
	if isinstance(valor, list):
		for elemento in valor:
			yield from _recorrer_productos(elemento, dentro_de_producto)
		return
	if not isinstance(valor, dict):
		return
	if "itemlist" in _tipos(valor):
		return
	es_producto = _es_producto(valor)
	if es_producto and not dentro_de_producto:
		yield valor
	for clave, hijo in valor.items():
		if clave in CLAVES_RELACIONADOS:
			continue
		if es_producto and clave in ("offers", "hasvariant", "isvariantof"):
			continue
		yield from _recorrer_productos(hijo, dentro_de_producto)


def _algun_tipo(valor: object, tipos: set[str]) -> bool:
	if isinstance(valor, dict):
		return bool(_tipos(valor) & tipos) or any(_algun_tipo(v, tipos) for v in valor.values())
	if isinstance(valor, list):
		return any(_algun_tipo(v, tipos) for v in valor)
	return False


def leer_jsonld(sopa: BeautifulSoup) -> tuple[list[dict], bool]:
	"""(productos de los JSON-LD, ¿la página es una categoría?)."""
	productos: list[dict] = []
	categoria = False
	for script in sopa.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
		contenido = script.string or script.get_text() or ""
		contenido = contenido.strip().removeprefix("<!--").removesuffix("-->").strip().rstrip(";")
		if not contenido:
			continue
		try:
			datos = _minusculas(json.loads(contenido))
		except (json.JSONDecodeError, ValueError):
			# Un JSON-LD mal formado es frecuente y no debe romper nada: se ignora.
			log.debug("JSON-LD mal formado; se ignora (%d caracteres)", len(contenido))
			continue
		productos.extend(_recorrer_productos(datos))
		if _algun_tipo(datos, TIPOS_CATEGORIA):
			categoria = True
	return productos, categoria and not productos


def productos_jsonld(sopa: BeautifulSoup) -> list[dict]:
	return leer_jsonld(sopa)[0]


def _especificacion(oferta: dict) -> dict | None:
	especificacion = oferta.get("pricespecification")
	if isinstance(especificacion, list):
		# Precio de socio (validForMemberTier) no es el precio.
		especificacion = next((e for e in especificacion if isinstance(e, dict) and "validformembertier" not in e), None)
	if isinstance(especificacion, dict) and "validformembertier" not in especificacion:
		return especificacion
	return None


def _precio_de_oferta(oferta: dict) -> float | None:
	precio = importe_de_maquina(oferta.get("price"))
	if precio is None:
		precio = importe_de_maquina(oferta.get("lowprice"))
	if precio is None:
		especificacion = _especificacion(oferta)
		if especificacion is not None:
			precio = importe_de_maquina(especificacion.get("price"))
	return precio


def _moneda_de_oferta(oferta: dict) -> str | None:
	moneda = oferta.get("pricecurrency")
	if not moneda:
		especificacion = _especificacion(oferta)
		if especificacion is not None:
			moneda = especificacion.get("pricecurrency")
	return str(moneda).strip().upper() if isinstance(moneda, str) and moneda.strip() else None


def _ofertas(valor: object) -> Iterator[dict]:
	"""Ofertas de ``offers`` (objeto o lista), incluidas las anidadas en AggregateOffer."""
	pila = [valor]
	while pila:
		actual = pila.pop()
		if isinstance(actual, list):
			pila.extend(reversed(actual))
		elif isinstance(actual, dict):
			yield actual
			if "offers" in actual:
				pila.append(actual["offers"])


def _url_normal(url: str) -> str:
	if not url:
		return ""
	try:
		return limpiar_url(url).rstrip("/").lower()
	except ValueError:
		return url.rstrip("/").lower()


def _url_de(objeto: dict) -> str:
	url = objeto.get("url")
	if not url and isinstance(objeto.get("offers"), dict):
		url = objeto["offers"].get("url")
	return str(url or "")


def _claves_variante(objeto: dict) -> list[str]:
	claves = []
	for clave, valor in objeto.items():
		if clave in ("sku", "productid", "mpn") or clave.startswith("gtin"):
			if isinstance(valor, (str, int)) and len(str(valor)) >= 3:
				claves.append(str(valor))
	return claves


def _variante_de_url(objetos: list[dict], url: str, variante: str = "") -> dict | None:
	"""La variante que corresponde a la dirección (o a la elegida por el usuario)."""
	if variante:
		for objeto in objetos:
			if variante in _claves_variante(objeto) or normalizar_espacios(str(objeto.get("name") or "")) == variante:
				return objeto
	if not url:
		return None
	propia = _url_normal(url)
	completa = urllib.parse.unquote(url)
	for objeto in objetos:
		otra = _url_de(objeto)
		if otra and _url_normal(urllib.parse.urljoin(url, otra)) == propia:
			return objeto
	for objeto in objetos:
		if any(clave in completa for clave in _claves_variante(objeto)):
			return objeto
	return None


def _mejor_oferta(ofertas: list[dict]) -> tuple[float | None, dict | None]:
	"""La de menor precio entre las EN STOCK (si hay alguna); las de 0 € se descartan."""
	con_precio = [(p, o) for o in ofertas if (p := _precio_de_oferta(o)) is not None]
	if not con_precio:
		return None, None
	en_stock = [(p, o) for p, o in con_precio if disponibilidad_schema(o.get("availability")) is True]
	precio, oferta = min(en_stock or con_precio, key=lambda par: par[0])
	return precio, oferta


def _nombre(objeto: dict) -> str | None:
	nombre = objeto.get("name")
	if isinstance(nombre, str) and nombre.strip():
		return normalizar_espacios(html_mod.unescape(nombre))
	return None


def _imagen_jsonld(valor: object) -> str | None:
	if isinstance(valor, str):
		return valor.strip() or None
	if isinstance(valor, list):
		for elemento in valor:
			imagen = _imagen_jsonld(elemento)
			if imagen:
				return imagen
		return None
	if isinstance(valor, dict):
		return _imagen_jsonld(valor.get("url") or valor.get("contenturl"))
	return None


def _hallazgo_de_ofertas(objeto: dict, url: str, variante: str) -> Hallazgo:
	"""Precio de las ofertas de un objeto; varias URL distintas = variantes."""
	ofertas = [o for o in _ofertas(objeto.get("offers")) if isinstance(o, dict)]
	urls = {_url_normal(urllib.parse.urljoin(url or "", str(o.get("url")))) for o in ofertas if o.get("url")}
	hallazgo = Hallazgo(origen=ORIGEN_JSONLD)
	if len(urls) > 1:
		elegida = _variante_de_url(ofertas, url, variante)
		if elegida is not None:
			ofertas = [elegida]
	precio, oferta = _mejor_oferta(ofertas)
	hallazgo.precio = precio
	for candidata in ([oferta] if oferta else []) + ofertas:
		hallazgo.moneda = hallazgo.moneda or _moneda_de_oferta(candidata)
		if hallazgo.disponible is None:
			hallazgo.disponible = disponibilidad_schema(candidata.get("availability"))
	if len(urls) > 1 and len(ofertas) > 1:
		precios = {p for o in ofertas if (p := _precio_de_oferta(o)) is not None}
		if len(precios) > 1:
			hallazgo.desde = True
			hallazgo.variantes = [
				Variante(_nombre(o) or str(o.get("sku") or o.get("url") or ""), _precio_de_oferta(o),
					(_claves_variante(o) or [str(o.get("url") or "")])[0], disponibilidad_schema(o.get("availability")))
				for o in ofertas
			]
	return hallazgo


def analizar_producto_jsonld(producto: dict, url: str = "", variante: str = "") -> Hallazgo:
	"""Un Product o ProductGroup: variante de la dirección, ofertas, nombre e imagen."""
	variantes = [v for v in (producto.get("hasvariant") or []) if isinstance(v, dict)] if isinstance(
		producto.get("hasvariant"), list) else ([producto["hasvariant"]] if isinstance(producto.get("hasvariant"), dict) else [])
	hallazgo: Hallazgo | None = None
	if variantes:
		elegida = _variante_de_url(variantes, url, variante)
		if elegida is not None:
			hallazgo = _hallazgo_de_ofertas(elegida, url, variante)
			hallazgo.imagen = _imagen_jsonld(elegida.get("image"))
	if hallazgo is None or hallazgo.precio is None:
		propio = _hallazgo_de_ofertas(producto, url, variante)
		if propio.precio is not None or hallazgo is None:
			hallazgo = propio
	if hallazgo.precio is None and variantes:
		precios = [(v, _hallazgo_de_ofertas(v, url, variante)) for v in variantes]
		con_precio = [(v, h) for v, h in precios if h.precio is not None]
		if con_precio:
			distintos = {h.precio for _v, h in con_precio}
			minimo = min(con_precio, key=lambda par: par[1].precio)[1]
			hallazgo.precio = minimo.precio
			hallazgo.moneda = minimo.moneda
			hallazgo.disponible = hallazgo.disponible if hallazgo.disponible is not None else minimo.disponible
			if len(distintos) > 1:
				hallazgo.desde = True
				hallazgo.variantes = [
					Variante(_nombre(v) or str(v.get("sku") or ""), h.precio, (_claves_variante(v) or [_nombre(v) or ""])[0], h.disponible)
					for v, h in con_precio
				]
	if hallazgo.disponible is None:
		hallazgo.disponible = disponibilidad_schema(producto.get("availability"))
	# El nombre del ProductGroup antes que el de la variante (que lleva talla o color).
	hallazgo.nombre = _nombre(producto)
	hallazgo.imagen = hallazgo.imagen or _imagen_jsonld(producto.get("image"))
	hallazgo.origen = ORIGEN_JSONLD
	return hallazgo


def mejor_producto_jsonld(contexto: Contexto) -> Hallazgo | None:
	"""El primer Product con precio; si ninguno tiene, el primero (por su disponibilidad y nombre)."""
	primero = None
	for producto in contexto.productos_jsonld:
		hallazgo = analizar_producto_jsonld(producto, contexto.url, contexto.variante)
		if hallazgo.precio is not None:
			return hallazgo
		if primero is None:
			primero = hallazgo
	return primero


# ════════════════════════════════════════════════════════════════════════════
# Metadatos y microdatos
# ════════════════════════════════════════════════════════════════════════════


def _metas(sopa: BeautifulSoup, nombre: str) -> list[str]:
	valores = []
	for clave in ("property", "name"):
		for etiqueta in sopa.find_all("meta", attrs={clave: nombre}):
			valor = str(etiqueta.get("content") or "").strip()
			if valor:
				valores.append(valor)
	return valores


def _meta(sopa: BeautifulSoup, *nombres: str) -> str:
	for nombre in nombres:
		valores = _metas(sopa, nombre)
		if valores:
			return valores[0]
	return ""


def _disponibilidad_meta(sopa: BeautifulSoup) -> bool | None:
	valor = _meta(sopa, "product:availability", "og:availability").lower()
	if not valor:
		return None
	if valor in _AGOTADO_META or valor.endswith(_AGOTADO_JSONLD):
		return False
	if valor in _DISPONIBLE_META or valor.endswith(_DISPONIBLE_JSONLD):
		return True
	return None


def _disponibilidad_microdatos(sopa: BeautifulSoup) -> bool | None:
	for elemento in sopa.find_all(attrs={"itemprop": re.compile(r"^availability$", re.I)}):
		valor = disponibilidad_schema(elemento.get("href") or elemento.get("content") or _texto(elemento))
		if valor is not None:
			return valor
	return None


# ════════════════════════════════════════════════════════════════════════════
# Estrategias de precio (en orden)
# ════════════════════════════════════════════════════════════════════════════


def estrategia_selector_producto(contexto: Contexto) -> Hallazgo | None:
	if not contexto.selector_producto.strip():
		return None
	regla = Regla(contexto.selector_producto.strip(), contexto.atributo_producto)
	precio, texto = precio_por_reglas(contexto.sopa, (regla,))
	return Hallazgo(precio=precio, origen=ORIGEN_PRODUCTO, texto_precio=texto)


def estrategia_selector_tienda(contexto: Contexto) -> Hallazgo | None:
	if not contexto.selector_tienda.strip():
		return None
	precio, texto = precio_por_reglas(contexto.sopa, (Regla(contexto.selector_tienda.strip()),))
	return Hallazgo(precio=precio, origen=ORIGEN_TIENDA, texto_precio=texto)


def estrategia_reglas_tienda(contexto: Contexto) -> Hallazgo | None:
	if contexto.reglas is None or not contexto.reglas.precio:
		return None
	precio, texto = precio_por_reglas(contexto.sopa, contexto.reglas.precio)
	return Hallazgo(precio=precio, origen=ORIGEN_REGLA, texto_precio=texto)


def estrategia_jsonld(contexto: Contexto) -> Hallazgo | None:
	return mejor_producto_jsonld(contexto)


def estrategia_metadatos(contexto: Contexto) -> Hallazgo | None:
	"""``product:price:amount`` / ``og:price:amount`` (los de 0 se saltan; nunca ``pretax``)."""
	sopa = contexto.sopa
	moneda = _meta(sopa, "product:price:currency", "og:price:currency").upper() or None
	for nombre in ("product:price:amount", "og:price:amount"):
		for bruto in _metas(sopa, nombre):
			precio = importe_de_maquina(bruto)
			if precio is not None:
				return Hallazgo(precio=precio, moneda=moneda, origen=ORIGEN_METADATOS, texto_precio=bruto)
	for etiqueta in sopa.find_all("meta", attrs={"itemprop": "price"}):
		if _tachado(etiqueta):
			continue
		bruto = str(etiqueta.get("content") or "")
		precio = importe_de_maquina(bruto)
		if precio is not None:
			return Hallazgo(precio=precio, moneda=moneda, origen=ORIGEN_METADATOS, texto_precio=bruto)
	return None


def estrategia_microdatos(contexto: Contexto) -> Hallazgo | None:
	for elemento in contexto.sopa.find_all(attrs={"itemprop": "price"}):
		if elemento.name == "meta" or _tachado(elemento):
			continue
		if elemento.get("content") is not None:
			texto = str(elemento.get("content"))
			precio = importe_de_maquina(texto)
		else:
			precio, texto = importe_de_texto(elemento)
		if precio is None:
			continue
		moneda_elemento = contexto.sopa.find(attrs={"itemprop": "priceCurrency"})
		moneda = None
		if moneda_elemento is not None:
			moneda = str(moneda_elemento.get("content") or _texto(moneda_elemento)).strip().upper() or None
		return Hallazgo(precio=precio, moneda=moneda, origen=ORIGEN_MICRODATOS, texto_precio=texto)
	return None


# El orden ES el contrato: la primera que da un precio > 0 gana. Los pasos 7 a
# 12 (plataforma, estado, analítica, heurística y decisión) van después, en
# ``extraer``, porque además pueden devolver candidatos para el usuario.
ESTRATEGIAS: list[Estrategia] = [
	estrategia_selector_producto,
	estrategia_selector_tienda,
	estrategia_reglas_tienda,
	estrategia_jsonld,
	estrategia_metadatos,
	estrategia_microdatos,
]


# ════════════════════════════════════════════════════════════════════════════
# Nombre, imagen, bloqueo y candidatos
# ════════════════════════════════════════════════════════════════════════════


def _coincide_con_tienda(sufijo: str, contexto: Contexto) -> bool:
	"""El sufijo del título es la tienda (por nombre o por dominio, sin acentos ni signos)."""
	normal = _sin_acentos(sufijo)
	if not normal:
		return False
	candidatos = {contexto.nombre_tienda}
	if contexto.reglas is not None:
		candidatos.add(contexto.reglas.nombre)
	if contexto.dominio:
		partes = contexto.dominio.split(".")
		candidatos.add(contexto.dominio)
		candidatos.add(".".join(partes[:-1]))
		candidatos.update(partes[:-1])
	return any(normal == _sin_acentos(c) for c in candidatos if c)


def limpiar_titulo(titulo: str, contexto: Contexto) -> str:
	"""Quita « | Tienda» o « - Tienda» del final del ``<title>`` si es la tienda."""
	titulo = normalizar_espacios(titulo)
	for separador in _SEPARADORES_TITULO:
		if separador in titulo:
			principio, sufijo = titulo.rsplit(separador, 1)
			if principio.strip() and _coincide_con_tienda(sufijo, contexto):
				return principio.strip()
	return titulo


def extraer_nombre(contexto: Contexto, producto: Hallazgo | None) -> str:
	sopa = contexto.sopa
	reglas: tuple[Regla, ...] = ()
	if contexto.selector_titulo.strip():
		reglas += (Regla(contexto.selector_titulo.strip()),)
	if contexto.reglas is not None:
		reglas += contexto.reglas.titulo
	nombre = texto_por_reglas(sopa, reglas) if reglas else ""
	if not nombre and producto is not None and producto.nombre:
		nombre = producto.nombre
	if not nombre:
		nombre = normalizar_espacios(html_mod.unescape(_meta(sopa, "og:title")))
	if not nombre and sopa.title is not None:
		nombre = limpiar_titulo(sopa.title.get_text(), contexto)
	return nombre


def extraer_imagen(contexto: Contexto, producto: Hallazgo | None) -> str:
	if contexto.reglas is not None and contexto.reglas.imagen:
		imagen = texto_por_reglas(contexto.sopa, contexto.reglas.imagen)
		if imagen:
			return imagen
	if producto is not None and producto.imagen:
		return producto.imagen
	return _meta(contexto.sopa, "og:image")


def hay_bloqueo(html: str, catalogo: CatalogoReglas | None, reglas: ReglasTienda | None) -> bool:
	"""Página de verificación: textos de ``tiendas.json`` (sin distinguir mayúsculas).

	La palabra suelta «captcha» NO cuenta: aparece en páginas normales con reCAPTCHA.
	"""
	minusculas = (html or "").lower()
	textos = list(catalogo.bloqueo_general if catalogo else ()) + list(reglas.bloqueo if reglas else ())
	return any(texto.lower() in minusculas for texto in textos if texto)


_CONTEXTOS = (
	("tachado", "tachado"),
	("bloque principal", "junto al botón de compra"),
	("cerca de comprar", "junto al botón de compra"),
	("zona ajena", "en otra zona (relacionados, carrusel o pie)"),
	("cuota", "cuota o financiación"),
	("kilo", "precio por kilo o litro"),
	("envío", "envío"),
	("sin IVA", "sin IVA"),
	("desde", "desde"),
	("coincide con datos ocultos", "coincide con los datos internos de la página"),
)


def describir(valor: float, motivos: list[str], texto: str, moneda: str = "EUR") -> tuple[str, str]:
	"""(descripción para el lector, tipo de contexto): «39,99 € — junto al botón de compra — "..."»."""
	unidos = " ".join(motivos)
	palabras: list[str] = []
	for clave, frase in _CONTEXTOS:
		if clave in unidos and frase not in palabras:
			palabras.append(frase)
	descripcion = formato_importe(valor, moneda)
	if palabras:
		descripcion += " — " + ", ".join(palabras)
	if texto:
		descripcion += f" — «{normalizar_espacios(texto)[:80]}»"
	return descripcion, ", ".join(palabras)


def candidatos_de(visibles: list, moneda: str = "EUR", maximo: int = MAX_CANDIDATOS) -> list[CandidatoPrecio]:
	"""Agrupa por importe y tipo de contexto (queda el de más puntos) y ordena por puntos."""
	grupos: dict[tuple[float, str], CandidatoPrecio] = {}
	for candidato in visibles:
		descripcion, tipo = describir(candidato.valor, candidato.motivos, candidato.texto, moneda)
		clave = (candidato.valor, tipo)
		if clave not in grupos or candidato.puntos > grupos[clave].puntos:
			grupos[clave] = CandidatoPrecio(candidato.valor, descripcion, candidato.puntos, candidato.texto, candidato.elemento)
	return sorted(grupos.values(), key=lambda c: -c.puntos)[:maximo]


def candidatos_para_elegir(html: str, url: str = "", moneda: str = "EUR") -> tuple[list[CandidatoPrecio], BeautifulSoup]:
	"""Todos los candidatos visibles de la página («Elegir el precio en la página»)."""
	salida = generico.extraer(html or "", url or None, usar_basico=False, con_plataforma=False)
	visibles = salida.get("visibles") or []
	return candidatos_de(visibles, moneda), salida.get("sopa") or BeautifulSoup(html or "", "html.parser")


# ════════════════════════════════════════════════════════════════════════════
# Punto de entrada
# ════════════════════════════════════════════════════════════════════════════


def _pasos_genericos(html: str, url: str) -> Hallazgo | tuple[list[CandidatoPrecio], None]:
	"""Pasos 7 a 12. Devuelve un hallazgo o, si hay que preguntar, los candidatos."""
	try:
		salida = generico.extraer(html, url or None, usar_basico=False)
	except Exception:  # noqa: BLE001 - un fallo del análisis heurístico no debe romper la comprobación
		log.exception("Falló el análisis genérico de la página")
		return [], None
	if salida.get("precio"):
		plataforma = salida.get("plataforma") or ""
		origen = f"plataforma {plataforma}" if plataforma else ORIGEN_ANALISIS
		return Hallazgo(
			precio=salida["precio"], moneda=(salida.get("moneda") or None), origen=origen,
			confianza=salida.get("confianza") or MEDIA, desde=bool(salida.get("desde")), plataforma=plataforma,
		)
	return candidatos_de(salida.get("visibles") or []), None


_RE_TITULO_LISTADO = re.compile(
	r"^\s*(buscador|b[uú]squeda|resultados?\b|search\b|buscar\b|p[aá]gina no encontrada|404\b|not found\b)", re.IGNORECASE
)


def es_pagina_de_listado(sopa: BeautifulSoup) -> bool:
	"""El ``<title>`` es el de un buscador, un listado de resultados o una página de error."""
	titulo = sopa.title.get_text(" ", strip=True) if sopa.title else ""
	return bool(_RE_TITULO_LISTADO.match(titulo))


def extraer(
	html: str,
	dominio: str = "",
	catalogo: CatalogoReglas | None = None,
	*,
	url: str = "",
	nombre_tienda: str = "",
	selector_producto: str | None = None,
	atributo_producto: str | None = None,
	selector_tienda: str | None = None,
	selector_titulo: str | None = None,
	selector_disponible: str | None = None,
	variante: str | None = None,
	estrategias: list[Estrategia] | None = None,
	pasos_genericos: bool = True,
) -> Resultado:
	"""Analiza el HTML y devuelve lo encontrado (sin lanzar: un fallo es un resultado no válido)."""
	reglas = catalogo.buscar(dominio) if catalogo is not None and dominio else None
	sopa = BeautifulSoup(html or "", "html.parser")
	contexto = Contexto(
		html=html or "",
		sopa=sopa,
		url=url or "",
		dominio=dominio,
		nombre_tienda=nombre_tienda or (reglas.nombre if reglas else ""),
		reglas=reglas,
		selector_producto=selector_producto or "",
		atributo_producto=atributo_producto or "",
		selector_tienda=selector_tienda or "",
		selector_titulo=selector_titulo or "",
		selector_disponible=selector_disponible or "",
		variante=variante or "",
	)
	ganador: Hallazgo | None = None
	for estrategia in estrategias if estrategias is not None else ESTRATEGIAS:
		try:
			hallazgo = estrategia(contexto)
		except Exception:  # noqa: BLE001 - una estrategia rota no debe impedir las siguientes
			log.exception("Falló la estrategia de extracción %s", getattr(estrategia, "__name__", estrategia))
			continue
		if hallazgo is not None and hallazgo.precio is not None and hallazgo.precio > 0:
			ganador = hallazgo
			break

	producto = mejor_producto_jsonld(contexto)
	resultado = Resultado()
	if ganador is None and pasos_genericos:
		generico_o_candidatos = _pasos_genericos(html or "", url)
		if isinstance(generico_o_candidatos, Hallazgo):
			ganador = generico_o_candidatos
		else:
			resultado.candidatos = generico_o_candidatos[0]
	if ganador is not None:
		resultado.precio = ganador.precio
		resultado.origen_precio = ganador.origen
		resultado.confianza = ganador.confianza
		resultado.desde = ganador.desde
		resultado.variantes = list(ganador.variantes)
		resultado.plataforma = ganador.plataforma

	# Moneda: la del dato ganador, JSON-LD o metadatos; si no, el símbolo del texto; si no, EUR.
	moneda = ganador.moneda if ganador is not None and ganador.moneda else None
	if not moneda and producto is not None and producto.moneda:
		moneda = producto.moneda
	if not moneda:
		moneda = _meta(sopa, "product:price:currency", "og:price:currency").upper() or None
	if not moneda and ganador is not None:
		moneda = moneda_por_simbolo(ganador.texto_precio)
	resultado.moneda = (moneda or "EUR")[:3].upper()

	# Disponibilidad: JSON-LD → metadatos → microdatos → regla de la tienda → disponible si hay precio.
	disponible = producto.disponible if producto is not None else None
	if disponible is None:
		disponible = _disponibilidad_meta(sopa)
	if disponible is None:
		disponible = _disponibilidad_microdatos(sopa)
	if disponible is None and contexto.selector_disponible.strip():
		disponible = disponible_por_reglas(
			sopa, (ReglaDisponible(contexto.selector_disponible.strip(), _AGOTADO_USUARIO),)
		)
	if disponible is None and reglas is not None and reglas.disponible:
		disponible = disponible_por_reglas(sopa, reglas.disponible)
	if disponible is None and resultado.precio is not None:
		disponible = True
	resultado.disponible = disponible

	resultado.nombre = extraer_nombre(contexto, producto)
	resultado.imagen = extraer_imagen(contexto, producto)
	if es_pagina_de_listado(sopa):
		# Ficha retirada que lleva al buscador o a una página de error: cualquier
		# precio de ahí es de otro artículo (Zara, 2026-11-02).
		resultado.precio = None
		resultado.disponible = None
		resultado.categoria = True
	if resultado.precio is None and resultado.disponible is None and not resultado.categoria:
		# El bloqueo solo se mira si no hay ni precio ni disponibilidad: así un
		# «Access Denied» suelto en una página normal no da un falso bloqueo.
		resultado.bloqueo = hay_bloqueo(html, catalogo, reglas)
		if not resultado.bloqueo and contexto.jsonld_es_categoria:
			resultado.categoria = True
	if resultado.bloqueo or resultado.categoria:
		resultado.candidatos = []
	return resultado
