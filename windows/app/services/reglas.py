"""Reglas de extracción por tienda (``tiendas.json``, compartido con Android).

El archivo se carga UNA vez y se indexa por dominio en un diccionario: va a
crecer mucho (cientos de tiendas) y se consulta en cada comprobación. Para
buscar se prueban los sufijos del dominio de más largo a más corto
(``tienda.ejemplo.es`` → ``ejemplo.es`` → ``es``), que es la regla «igual o
termina en ``.`` + dominio» sin recorrer la lista entera.

El usuario no edita este archivo: sus selectores van en la tienda o en el
producto de la base de datos, que ganan a estas reglas.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from app.core import paths

log = logging.getLogger(__name__)

NOMBRE_ARCHIVO = "tiendas.json"
# Sufijos de dos niveles habituales: «tiendaejemplo.co.uk» → «Tiendaejemplo».
# Sufijos públicos de dos niveles que reconoce la especificación común
_SUFIJOS_DOBLES = {
	"co.uk", "org.uk", "com.mx", "com.ar", "com.br", "com.au", "co.jp",
	"com.es", "nom.es", "org.es", "com.pt", "com.tr", "co.nz", "co.za",
}


@dataclass(frozen=True)
class Regla:
	"""Selector CSS y, opcionalmente, el atributo que se lee en vez del texto."""

	css: str
	atributo: str = ""


@dataclass(frozen=True)
class ReglaDisponible:
	"""Si el elemento existe y su texto contiene alguno de ``agotado``, está agotado.

	``""`` en ``agotado`` significa «si existe, agotado»; una lista vacía,
	«si existe, disponible».
	"""

	css: str
	agotado: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReglasTienda:
	"""Reglas de una tienda de ``tiendas.json``."""

	id: str
	nombre: str
	dominios: tuple[str, ...]
	precio: tuple[Regla, ...] = ()
	titulo: tuple[Regla, ...] = ()
	imagen: tuple[Regla, ...] = ()
	disponible: tuple[ReglaDisponible, ...] = ()
	bloqueo: tuple[str, ...] = ()
	notas: str = ""
	# Descarga con el navegador integrado (tiendas que no dan la página a una descarga normal).
	navegador: bool = False
	# API pública de la tienda (Mercadona, Consum, BM...): ver app/services/api_tienda.py.
	api: dict | None = None


@dataclass
class CatalogoReglas:
	"""Todas las reglas, indexadas por dominio."""

	bloqueo_general: tuple[str, ...] = ()
	tiendas: list[ReglasTienda] = field(default_factory=list)
	version: int = 0
	_por_dominio: dict[str, ReglasTienda] = field(default_factory=dict, repr=False)

	def __post_init__(self) -> None:
		for tienda in self.tiendas:
			for dominio in tienda.dominios:
				# Si dos tiendas declaran el mismo dominio, gana la primera (orden del archivo).
				self._por_dominio.setdefault(dominio.lower(), tienda)

	def buscar(self, dominio: str) -> ReglasTienda | None:
		"""Reglas de la tienda de ``dominio`` (o de un dominio padre), o ``None``."""
		partes = (dominio or "").lower().strip(".").split(".")
		for inicio in range(len(partes) - 1):
			tienda = self._por_dominio.get(".".join(partes[inicio:]))
			if tienda is not None:
				return tienda
		return None

	def nombre_tienda(self, dominio: str) -> str:
		"""Nombre visible de la tienda de un dominio.

		El de ``tiendas.json`` si lo conoce; si no, la etiqueta que va justo
		antes del sufijo público, con la primera letra en mayúscula
		(``tiendaejemplo.es`` → «Tiendaejemplo»).
		"""
		tienda = self.buscar(dominio)
		return tienda.nombre if tienda else nombre_desde_dominio(dominio)


def nombre_desde_dominio(dominio: str) -> str:
	"""``tiendaejemplo.es`` → «Tiendaejemplo»; ``informatica.ejemplo.es`` y ``tienda.ejemplo.co.uk`` → «Ejemplo»."""
	partes = [p for p in (dominio or "").lower().split(".") if p]
	if len(partes) < 2:
		base = partes[0] if partes else (dominio or "")
	elif len(partes) > 2 and ".".join(partes[-2:]) in _SUFIJOS_DOBLES:
		base = partes[-3]
	else:
		base = partes[-2]
	return base[:1].upper() + base[1:]


def _reglas(lista: object) -> tuple[Regla, ...]:
	resultado = []
	for elemento in lista if isinstance(lista, list) else []:
		if isinstance(elemento, dict) and isinstance(elemento.get("css"), str) and elemento["css"].strip():
			resultado.append(Regla(elemento["css"].strip(), str(elemento.get("atributo") or "")))
	return tuple(resultado)


def _reglas_disponible(lista: object) -> tuple[ReglaDisponible, ...]:
	resultado = []
	for elemento in lista if isinstance(lista, list) else []:
		if isinstance(elemento, dict) and isinstance(elemento.get("css"), str) and elemento["css"].strip():
			agotado = elemento.get("agotado") or []
			textos = tuple(str(t).lower() for t in agotado) if isinstance(agotado, list) else ()
			resultado.append(ReglaDisponible(elemento["css"].strip(), textos))
	return tuple(resultado)


def _textos(lista: object) -> tuple[str, ...]:
	return tuple(str(t) for t in lista if str(t)) if isinstance(lista, list) else ()


def catalogo_desde_datos(datos: dict) -> CatalogoReglas:
	"""Construye el catálogo a partir del JSON ya leído (tolera campos que falten)."""
	tiendas = []
	for crudo in datos.get("tiendas") or []:
		if not isinstance(crudo, dict) or not crudo.get("dominios"):
			continue
		tiendas.append(
			ReglasTienda(
				id=str(crudo.get("id") or ""),
				nombre=str(crudo.get("nombre") or ""),
				dominios=tuple(str(d).lower() for d in crudo.get("dominios") or []),
				precio=_reglas(crudo.get("precio")),
				titulo=_reglas(crudo.get("titulo")),
				imagen=_reglas(crudo.get("imagen")),
				disponible=_reglas_disponible(crudo.get("disponible")),
				bloqueo=_textos(crudo.get("bloqueo")),
				notas=str(crudo.get("notas") or ""),
				navegador=crudo.get("navegador") is True,
				api=crudo.get("api") if isinstance(crudo.get("api"), dict) else None,
			)
		)
	return CatalogoReglas(
		bloqueo_general=_textos(datos.get("bloqueo_general")),
		tiendas=tiendas,
		version=int(datos.get("version") or 0),
	)


def cargar_catalogo(ruta: Path | str) -> CatalogoReglas:
	"""Lee ``tiendas.json``. Un archivo dañado da un catálogo vacío (queda la extracción genérica)."""
	try:
		datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
	except (OSError, UnicodeDecodeError, json.JSONDecodeError):
		log.exception("No se pudo leer %s; se usa solo la extracción genérica", ruta)
		return CatalogoReglas()
	if not isinstance(datos, dict):
		log.error("%s no contiene un objeto JSON; se usa solo la extracción genérica", ruta)
		return CatalogoReglas()
	catalogo = catalogo_desde_datos(datos)
	log.info("Reglas de %d tiendas cargadas de %s (versión %s)", len(catalogo.tiendas), ruta, catalogo.version)
	return catalogo


_catalogo: CatalogoReglas | None = None
_candado = threading.Lock()


def catalogo() -> CatalogoReglas:
	"""Catálogo de la aplicación, cargado la primera vez que se pide."""
	global _catalogo
	with _candado:
		if _catalogo is None:
			ruta = paths.buscar_recurso(NOMBRE_ARCHIVO)
			if ruta is None:
				log.error("No se encuentra %s en data/recursos; se usa solo la extracción genérica", NOMBRE_ARCHIVO)
				_catalogo = CatalogoReglas()
			else:
				_catalogo = cargar_catalogo(ruta)
		return _catalogo


def reiniciar_catalogo() -> None:
	"""Olvida el catálogo cargado (pruebas, o tras actualizar ``tiendas.json``)."""
	global _catalogo
	with _candado:
		_catalogo = None
