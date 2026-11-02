"""Importar y exportar: formato de intercambio JSON común con Android y CSV.

Formato: ``compartido/FORMATO_INTERCAMBIO.md``. Claves en el orden del
documento y sangría de 2 espacios (el archivo se puede leer y comparar), sin
los ``id`` internos (las relaciones van por ``uuid``), escritura atómica
(temporal + ``os.replace``).

Importar es atómico: todo va en UNA transacción sobre la conexión de
escritura (las lecturas también, porque una conexión de lectura no vería lo
que la transacción lleva escrito). Si algo falla, no cambia nada.

Sin wx.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.base_datos import BaseDatos
from app.core.version import APP_VERSION
from app.services import errores
from app.services.direcciones import dominio_de, limpiar_url
from app.services.importes import formato_numero, redondear
from app.services.reglas import CatalogoReglas, nombre_desde_dominio
from app.services.repositorio import ahora_iso, leer_fecha, nuevo_uuid

log = logging.getLogger(__name__)

FORMATO = "NoMeSubasLosPrecios"
VERSION_FORMATO = 1
APP = "windows"

COMBINAR = "combinar"
REEMPLAZAR = "reemplazar"

MENSAJE_NO_ES_EXPORTACION = "Este archivo no es una exportación de No Me Subas Los Precios."
MENSAJE_VERSION_NUEVA = "El archivo es de una versión más nueva de la app. Actualízala para importarlo."

# Claves de ajustes de la especificación (las de Windows al final).
CLAVES_AJUSTES = (
	"intervalo_horas", "comprobar_al_iniciar", "avisar_bajadas", "avisar_subidas", "avisar_objetivo",
	"avisar_minimo", "avisar_disponible", "avisar_agotado", "avisar_errores", "cambio_minimo_porcentaje",
	"pausa_entre_peticiones", "tiempo_espera", "conservar_avisos_dias", "buscar_actualizaciones",
	"iniciar_con_windows", "minimizar_a_bandeja", "sonidos",
)

_PRECIOS = ("precio_actual", "precio_inicial", "precio_minimo", "precio_maximo", "precio_anterior", "precio_objetivo")
_FECHAS = ("fecha_minimo", "fecha_maximo", "fecha_cambio", "fecha_alta", "ultima_comprobacion")
_BOOLEANOS = ("disponible", "avisar_disponible", "favorito", "activo")
_TEXTOS = ("selector_precio", "imagen_url", "notas", "ultimo_error")
# Extracción ampliada (pueden faltar en archivos antiguos: valen nulo).
_EXTRACCION = ("variante", "origen_precio", "confianza", "huella_selector")
# Lo que «puso el usuario»: al combinar se toma siempre del archivo.
_DEL_USUARIO = (
	"nombre", "grupo", "precio_objetivo", "alerta_porcentaje", "avisar_disponible", "selector_precio", "notas", "favorito",
	"activo", "variante", "huella_selector",
)
# Lo que sale de las comprobaciones: gana la ``ultima_comprobacion`` más reciente.
_DE_COMPROBACION = (
	"moneda", "precio_actual", "disponible", "precio_inicial", "precio_minimo", "fecha_minimo", "precio_maximo",
	"fecha_maximo", "precio_anterior", "fecha_cambio", "imagen_url", "ultima_comprobacion", "ultimo_error", "errores_seguidos",
	"origen_precio", "confianza", "desde",
)


class ErrorIntercambio(Exception):
	"""Error de importación o exportación con un mensaje para el usuario."""


# ════════════════════════════════════════════════════════════════════════════
# Exportar
# ════════════════════════════════════════════════════════════════════════════


def _o_nulo(valor: Any) -> Any:
	"""Texto vacío → ``None`` (el formato usa ``null`` para «sin valor»)."""
	if isinstance(valor, str) and not valor.strip():
		return None
	return valor


def _numero(valor: Any) -> float | int | None:
	if valor is None:
		return None
	numero = float(valor)
	return numero


def construir_exportacion(bd: BaseDatos, ajustes: dict[str, Any] | None = None, exportado: str | None = None) -> dict:
	"""Diccionario con todo (categorías, tiendas, productos con historial y avisos)."""
	categorias = bd.consultar("SELECT * FROM categorias ORDER BY orden, nombre COLLATE NOCASE")
	tiendas = bd.consultar("SELECT * FROM tiendas ORDER BY nombre COLLATE NOCASE")
	uuid_categoria = {c["id"]: c["uuid"] for c in categorias}
	uuid_tienda = {t["id"]: t["uuid"] for t in tiendas}
	historiales: dict[int, list[dict]] = {}
	for fila in bd.consultar("SELECT producto_id, fecha, precio, disponible FROM historial ORDER BY producto_id, fecha"):
		historiales.setdefault(fila["producto_id"], []).append(
			{"fecha": fila["fecha"], "precio": _numero(fila["precio"]), "disponible": bool(fila["disponible"])}
		)
	productos = []
	uuid_producto: dict[int, str] = {}
	for p in bd.consultar("SELECT * FROM productos ORDER BY fecha_alta, id"):
		uuid_producto[p["id"]] = p["uuid"]
		productos.append({
			"uuid": p["uuid"],
			"nombre": p["nombre"] or "",
			"url": p["url"],
			"tienda": uuid_tienda.get(p["tienda_id"]),
			"categoria": uuid_categoria.get(p["categoria_id"]),
			"grupo": _o_nulo(p["grupo"]),
			"moneda": p["moneda"] or "EUR",
			**{clave: _numero(p[clave]) for clave in _PRECIOS},
			**{clave: _o_nulo(p[clave]) for clave in _FECHAS},
			**{clave: bool(p[clave]) for clave in _BOOLEANOS},
			"alerta_porcentaje": _numero(p["alerta_porcentaje"]) or 0,
			**{clave: _o_nulo(p[clave]) for clave in _TEXTOS},
			"errores_seguidos": int(p["errores_seguidos"] or 0),
			**{clave: _o_nulo(p[clave]) for clave in _EXTRACCION},
			"desde": bool(p["desde"]),
			"historial": historiales.get(p["id"], []),
		})
	avisos = [
		{
			"producto": uuid_producto.get(a["producto_id"]),
			"fecha": a["fecha"],
			"tipo": a["tipo"],
			"titulo": a["titulo"],
			"mensaje": a["mensaje"],
			"leido": bool(a["leido"]),
		}
		for a in bd.consultar("SELECT * FROM avisos ORDER BY fecha, id")
	]
	datos: dict[str, Any] = {
		"formato": FORMATO,
		"version_formato": VERSION_FORMATO,
		"app": APP,
		"version_app": APP_VERSION,
		"exportado": exportado or ahora_iso(),
		"categorias": [
			{"uuid": c["uuid"], "nombre": c["nombre"], "descripcion": _o_nulo(c["descripcion"]), "orden": int(c["orden"] or 0)}
			for c in categorias
		],
		"tiendas": [
			{
				"uuid": t["uuid"],
				"nombre": t["nombre"],
				"dominio": t["dominio"],
				"selector_precio": _o_nulo(t["selector_precio"]),
				"selector_titulo": _o_nulo(t["selector_titulo"]),
				"selector_disponible": _o_nulo(t["selector_disponible"]),
				"notas": _o_nulo(t["notas"]),
				"modo_descarga": t["modo_descarga"] or "auto",
			}
			for t in tiendas
		],
		"productos": productos,
		"avisos": avisos,
	}
	if ajustes is not None:
		datos["ajustes"] = {clave: ajustes[clave] for clave in CLAVES_AJUSTES if clave in ajustes}
	return datos


def escribir_atomico(ruta: Path | str, texto: str, codificacion: str = "utf-8") -> None:
	"""Escribe en un temporal de la misma carpeta y lo renombra: nunca queda un archivo a medias."""
	ruta = Path(ruta)
	temporal = ruta.with_name(ruta.name + ".tmp")
	try:
		with open(temporal, "w", encoding=codificacion, newline="") as archivo:
			archivo.write(texto)
			archivo.flush()
			os.fsync(archivo.fileno())
		os.replace(temporal, ruta)
	except OSError as error:
		temporal.unlink(missing_ok=True)
		raise ErrorIntercambio(f"No se pudo escribir el archivo {ruta.name}: {error.strerror or error}") from error


def exportar_json(bd: BaseDatos, ruta: Path | str, ajustes: dict[str, Any] | None = None) -> dict:
	"""Exporta todo a ``ruta`` y devuelve lo exportado."""
	datos = construir_exportacion(bd, ajustes)
	escribir_atomico(ruta, json.dumps(datos, ensure_ascii=False, indent=2) + "\n")
	log.info("Exportados %d productos a %s", len(datos["productos"]), Path(ruta).name)
	return datos


def nombre_propuesto(fecha: str | None = None) -> str:
	"""``NoMeSubasLosPrecios-AAAA-MM-DD.json``."""
	return f"{FORMATO}-{(fecha or ahora_iso())[:10]}.json"


def _celda_numero(valor: Any) -> str:
	return "" if valor is None else formato_numero(float(valor))


def exportar_csv(productos: list[dict[str, Any]], ruta: Path | str) -> int:
	"""Productos para hojas de cálculo: ``;``, coma decimal y UTF-8 con BOM (Excel)."""
	salida = io.StringIO()
	escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
	escritor.writerow([
		"Nombre", "Tienda", "Categoría", "Grupo", "Precio actual", "Moneda", "Disponible", "Precio anterior",
		"Precio inicial", "Precio mínimo", "Fecha del mínimo", "Precio máximo", "Fecha del máximo", "Precio deseado",
		"Alerta de bajada (%)", "Favorito", "Activo", "Fecha de alta", "Última comprobación", "Último error",
		"Dirección", "Notas",
	])
	for p in productos:
		escritor.writerow([
			p.get("nombre") or "", p.get("tienda") or "", p.get("categoria") or "", p.get("grupo") or "",
			_celda_numero(p.get("precio_actual")), p.get("moneda") or "EUR", "Sí" if p.get("disponible") else "No",
			_celda_numero(p.get("precio_anterior")), _celda_numero(p.get("precio_inicial")),
			_celda_numero(p.get("precio_minimo")), p.get("fecha_minimo") or "", _celda_numero(p.get("precio_maximo")),
			p.get("fecha_maximo") or "", _celda_numero(p.get("precio_objetivo")),
			_celda_numero(p.get("alerta_porcentaje") or 0), "Sí" if p.get("favorito") else "No",
			"Sí" if p.get("activo") else "No", p.get("fecha_alta") or "", p.get("ultima_comprobacion") or "",
			p.get("ultimo_error") or "", p.get("url") or "", (p.get("notas") or "").replace("\r", " ").replace("\n", " "),
		])
	escribir_atomico(ruta, salida.getvalue(), codificacion="utf-8-sig")
	return len(productos)


# ════════════════════════════════════════════════════════════════════════════
# Importar
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class Analisis:
	"""Lo que hay en el archivo y lo que pasaría al importarlo."""

	datos: dict
	productos: int = 0
	categorias: int = 0
	tiendas: int = 0
	nuevos: int = 0
	actualizados: int = 0
	no_validos: int = 0
	tiene_ajustes: bool = False

	def texto(self, modo: str = COMBINAR) -> str:
		"""«El archivo tiene 42 productos, 6 categorías y 9 tiendas. Se añadirán 10 productos y se actualizarán 32.»"""
		texto = (
			f"El archivo tiene {self.productos} {_plural(self.productos, 'producto', 'productos')}, "
			f"{self.categorias} {_plural(self.categorias, 'categoría', 'categorías')} y "
			f"{self.tiendas} {_plural(self.tiendas, 'tienda', 'tiendas')}."
		)
		if modo == REEMPLAZAR:
			validos = self.productos - self.no_validos
			texto += f" Se borrará todo lo actual y se cargarán {validos} {_plural(validos, 'producto', 'productos')}."
		else:
			texto += (
				f" Se añadirán {self.nuevos} {_plural(self.nuevos, 'producto', 'productos')}"
				f" y se actualizarán {self.actualizados}."
			)
		if self.no_validos:
			texto += f" {self.no_validos} {_plural(self.no_validos, 'producto no es válido', 'productos no son válidos')} y se {_plural(self.no_validos, 'saltará', 'saltarán')}."
		return texto


@dataclass
class ResultadoImportacion:
	nuevos: int = 0
	actualizados: int = 0
	no_validos: int = 0
	copia: Path | None = None
	ajustes: dict[str, Any] = field(default_factory=dict)

	def texto(self) -> str:
		texto = f"Importación terminada: {self.nuevos} productos añadidos y {self.actualizados} actualizados."
		if self.no_validos:
			texto += f" Se saltaron {self.no_validos} no válidos."
		return texto


def _plural(n: int, singular: str, plural: str) -> str:
	return singular if n == 1 else plural


def leer_archivo(ruta: Path | str) -> dict:
	"""Lee y valida la cabecera de un archivo de intercambio."""
	try:
		texto = Path(ruta).read_text(encoding="utf-8-sig")
	except OSError as error:
		raise ErrorIntercambio(f"No se pudo leer el archivo: {error.strerror or error}") from error
	except UnicodeDecodeError as error:
		raise ErrorIntercambio(MENSAJE_NO_ES_EXPORTACION) from error
	try:
		datos = json.loads(texto)
	except json.JSONDecodeError as error:
		raise ErrorIntercambio(MENSAJE_NO_ES_EXPORTACION) from error
	return validar(datos)


def validar(datos: Any) -> dict:
	if not isinstance(datos, dict) or datos.get("formato") != FORMATO:
		raise ErrorIntercambio(MENSAJE_NO_ES_EXPORTACION)
	try:
		version = int(datos.get("version_formato") or 0)
	except (TypeError, ValueError) as error:
		raise ErrorIntercambio(MENSAJE_NO_ES_EXPORTACION) from error
	if version > VERSION_FORMATO:
		raise ErrorIntercambio(MENSAJE_VERSION_NUEVA)
	for clave in ("categorias", "tiendas", "productos", "avisos"):
		if not isinstance(datos.get(clave) or [], list):
			raise ErrorIntercambio(MENSAJE_NO_ES_EXPORTACION)
	return datos


def _lista(datos: dict, clave: str) -> list[dict]:
	return [e for e in (datos.get(clave) or []) if isinstance(e, dict)]


def _producto_valido(p: dict) -> bool:
	return bool(isinstance(p.get("url"), str) and p["url"].strip() and isinstance(p.get("uuid"), str) and p["uuid"].strip())


def analizar(bd: BaseDatos, datos: dict) -> Analisis:
	"""Resumen previo: cuántos productos se añadirían y cuántos se actualizarían al combinar."""
	productos = _lista(datos, "productos")
	analisis = Analisis(
		datos=datos,
		productos=len(productos),
		categorias=len(_lista(datos, "categorias")),
		tiendas=len(_lista(datos, "tiendas")),
		tiene_ajustes=isinstance(datos.get("ajustes"), dict) and bool(datos.get("ajustes")),
	)
	uuids = {f["uuid"] for f in bd.consultar("SELECT uuid FROM productos")}
	urls = {f["url"] for f in bd.consultar("SELECT url FROM productos")}
	vistos: set[str] = set()
	for p in productos:
		if not _producto_valido(p):
			analisis.no_validos += 1
			continue
		url = limpiar_url(p["url"])
		if p["uuid"] in uuids or url in urls or url in vistos:
			analisis.actualizados += 1
		else:
			analisis.nuevos += 1
		vistos.add(url)
	return analisis


def _texto(valor: Any) -> str | None:
	if valor is None:
		return None
	texto = str(valor)
	return texto if texto.strip() else None


def _real(valor: Any) -> float | None:
	if valor is None or isinstance(valor, bool):
		return None
	try:
		return redondear(float(valor))
	except (TypeError, ValueError):
		return None


def _booleano(valor: Any, defecto: bool) -> int:
	if valor is None:
		return 1 if defecto else 0
	return 1 if bool(valor) else 0


def _fecha(valor: Any) -> str | None:
	if not isinstance(valor, str) or leer_fecha(valor) is None:
		return None
	return valor


def _mas_reciente(a: str | None, b: str | None) -> bool:
	"""¿``a`` es más reciente que ``b``?"""
	fa, fb = leer_fecha(a), leer_fecha(b)
	if fa is None:
		return False
	return fb is None or fa > fb


def _campos_producto(p: dict) -> dict[str, Any]:
	"""Campos de producto del archivo, con sus valores por defecto si faltan."""
	return {
		"nombre": str(p.get("nombre") or ""),
		"grupo": _texto(p.get("grupo")),
		"moneda": str(p.get("moneda") or "EUR").upper()[:3],
		**{clave: _real(p.get(clave)) for clave in _PRECIOS},
		**{clave: _fecha(p.get(clave)) for clave in _FECHAS},
		"disponible": _booleano(p.get("disponible"), True),
		"avisar_disponible": _booleano(p.get("avisar_disponible"), True),
		"favorito": _booleano(p.get("favorito"), False),
		"activo": _booleano(p.get("activo"), True),
		"alerta_porcentaje": _real(p.get("alerta_porcentaje")) or 0.0,
		"selector_precio": _texto(p.get("selector_precio")),
		"imagen_url": _texto(p.get("imagen_url")),
		"notas": _texto(p.get("notas")),
		"ultimo_error": _texto(p.get("ultimo_error")) or "",
		"errores_seguidos": int(p.get("errores_seguidos") or 0) if str(p.get("errores_seguidos") or "0").isdigit() else 0,
		**{clave: _texto(p.get(clave)) for clave in _EXTRACCION},
		"desde": _booleano(p.get("desde"), False),
	}


def importar(
	bd: BaseDatos,
	datos: dict,
	modo: str = COMBINAR,
	catalogo: CatalogoReglas | None = None,
) -> ResultadoImportacion:
	"""Importa ``datos`` (ya validados con :func:`validar`) de forma atómica."""
	validar(datos)
	resultado = ResultadoImportacion()
	if modo == REEMPLAZAR:
		# Antes de borrar nada, copia de seguridad automática.
		resultado.copia = bd.copia_seguridad(motivo="antes-de-reemplazar")
	with bd.transaccion() as conexion:
		if modo == REEMPLAZAR:
			for tabla in ("avisos", "historial", "productos", "categorias", "tiendas"):
				conexion.execute(f"DELETE FROM {tabla}")  # noqa: S608 - nombres fijos  # auditoria: ignorar sql-formateado - nombres de tabla fijos de una tupla del código
		mapa_categorias = _importar_categorias(conexion, _lista(datos, "categorias"))
		mapa_tiendas = _importar_tiendas(conexion, _lista(datos, "tiendas"))
		mapa_productos = _importar_productos(conexion, _lista(datos, "productos"), mapa_categorias, mapa_tiendas, catalogo, resultado)
		_importar_avisos(conexion, _lista(datos, "avisos"), mapa_productos)
	if isinstance(datos.get("ajustes"), dict):
		resultado.ajustes = {k: v for k, v in datos["ajustes"].items() if k in CLAVES_AJUSTES}
	log.info("Importación (%s): %d nuevos, %d actualizados, %d no válidos", modo, resultado.nuevos, resultado.actualizados, resultado.no_validos)
	return resultado


def _importar_categorias(conexion: sqlite3.Connection, categorias: list[dict]) -> dict[str, int]:
	mapa: dict[str, int] = {}
	for c in categorias:
		uuid = str(c.get("uuid") or "").strip()
		nombre = str(c.get("nombre") or "").strip()
		if not uuid or not nombre:
			continue
		descripcion = _texto(c.get("descripcion"))
		orden = int(c.get("orden") or 0) if isinstance(c.get("orden"), (int, float)) else 0
		fila = conexion.execute("SELECT id FROM categorias WHERE uuid = ?", (uuid,)).fetchone()
		if fila is None:
			fila = next(
				(f for f in conexion.execute("SELECT id, nombre FROM categorias") if f[1].casefold() == nombre.casefold()),
				None,
			)
		if fila is not None:
			id_ = int(fila[0])
			repetida = next(
				(f for f in conexion.execute("SELECT id, nombre FROM categorias WHERE id <> ?", (id_,)) if f[1].casefold() == nombre.casefold()),
				None,
			)
			if repetida is None:
				conexion.execute(
					"UPDATE categorias SET nombre = ?, descripcion = ?, orden = ? WHERE id = ?", (nombre, descripcion, orden, id_)
				)
		else:
			id_ = int(conexion.execute(
				"INSERT INTO categorias (uuid, nombre, descripcion, orden) VALUES (?, ?, ?, ?)", (uuid, nombre, descripcion, orden)
			).lastrowid)
		mapa[uuid] = id_
	return mapa


def _importar_tiendas(conexion: sqlite3.Connection, tiendas: list[dict]) -> dict[str, int]:
	mapa: dict[str, int] = {}
	for t in tiendas:
		uuid = str(t.get("uuid") or "").strip()
		dominio = str(t.get("dominio") or "").strip().lower()
		if not uuid or not dominio:
			continue
		nombre = str(t.get("nombre") or "").strip() or nombre_desde_dominio(dominio)
		modo = str(t.get("modo_descarga") or "auto")
		valores = (
			nombre, _texto(t.get("selector_precio")), _texto(t.get("selector_titulo")), _texto(t.get("selector_disponible")),
			_texto(t.get("notas")), modo if modo in ("auto", "directo", "navegador") else "auto",
		)
		fila = conexion.execute("SELECT id FROM tiendas WHERE uuid = ?", (uuid,)).fetchone()
		if fila is None:
			fila = conexion.execute("SELECT id FROM tiendas WHERE dominio = ?", (dominio,)).fetchone()
		if fila is not None:
			id_ = int(fila[0])
			conexion.execute(
				"UPDATE tiendas SET nombre = ?, selector_precio = ?, selector_titulo = ?, selector_disponible = ?, notas = ?, "
				"modo_descarga = ? WHERE id = ?",
				(*valores, id_),
			)
		else:
			id_ = int(conexion.execute(
				"INSERT INTO tiendas (uuid, nombre, selector_precio, selector_titulo, selector_disponible, notas, modo_descarga, dominio) "
				"VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
				(uuid, *valores, dominio),
			).lastrowid)
		mapa[uuid] = id_
	return mapa


def _tienda_por_dominio(conexion: sqlite3.Connection, dominio: str, catalogo: CatalogoReglas | None) -> int:
	fila = conexion.execute("SELECT id FROM tiendas WHERE dominio = ?", (dominio,)).fetchone()
	if fila:
		return int(fila[0])
	nombre = catalogo.nombre_tienda(dominio) if catalogo else nombre_desde_dominio(dominio)
	return int(conexion.execute(
		"INSERT INTO tiendas (uuid, nombre, dominio) VALUES (?, ?, ?)", (nuevo_uuid(), nombre, dominio)
	).lastrowid)


def _importar_productos(
	conexion: sqlite3.Connection,
	productos: list[dict],
	mapa_categorias: dict[str, int],
	mapa_tiendas: dict[str, int],
	catalogo: CatalogoReglas | None,
	resultado: ResultadoImportacion,
) -> dict[str, int]:
	mapa: dict[str, int] = {}
	for p in productos:
		if not _producto_valido(p):
			resultado.no_validos += 1
			continue
		uuid = p["uuid"].strip()
		url = limpiar_url(p["url"])
		campos = _campos_producto(p)
		tienda_id = mapa_tiendas.get(str(p.get("tienda") or ""))
		if tienda_id is None:
			tienda_id = _tienda_por_dominio(conexion, dominio_de(url), catalogo)
		categoria_uuid = p.get("categoria")
		categoria_id = mapa_categorias.get(str(categoria_uuid)) if categoria_uuid else None
		existente = conexion.execute("SELECT * FROM productos WHERE uuid = ?", (uuid,)).fetchone()
		if existente is None:
			existente = conexion.execute("SELECT * FROM productos WHERE url = ?", (url,)).fetchone()
		if existente is None:
			campos.update(uuid=uuid, url=url, tienda_id=tienda_id, categoria_id=categoria_id)
			campos["fecha_alta"] = campos["fecha_alta"] or ahora_iso()
			campos["estado"] = errores.estado_de_error(campos["ultimo_error"]) if campos["ultima_comprobacion"] else errores.PENDIENTE
			columnas = ", ".join(campos)
			id_ = int(conexion.execute(  # auditoria: ignorar sql-formateado - columnas propias de _campos_producto, valores con marcadores
				f"INSERT INTO productos ({columnas}) VALUES ({', '.join('?' for _ in campos)})",  # noqa: S608 - claves propias
				tuple(campos.values()),
			).lastrowid)
			resultado.nuevos += 1
		else:
			id_ = int(existente["id"])
			cambios: dict[str, Any] = {clave: campos[clave] for clave in _DEL_USUARIO}
			if not cambios["nombre"]:
				cambios.pop("nombre")
			cambios["categoria_id"] = categoria_id
			cambios["tienda_id"] = tienda_id
			if _mas_reciente(campos["ultima_comprobacion"], existente["ultima_comprobacion"]):
				cambios.update({clave: campos[clave] for clave in _DE_COMPROBACION})
				cambios["estado"] = errores.estado_de_error(campos["ultimo_error"])
			asignaciones = ", ".join(f"{c} = ?" for c in cambios)
			conexion.execute(f"UPDATE productos SET {asignaciones} WHERE id = ?", (*cambios.values(), id_))  # noqa: S608  # auditoria: ignorar sql-formateado - columnas de listas blancas, valores con marcadores
			resultado.actualizados += 1
		for h in p.get("historial") or []:
			if isinstance(h, dict) and _fecha(h.get("fecha")):
				conexion.execute(
					"INSERT OR IGNORE INTO historial (producto_id, fecha, precio, disponible) VALUES (?, ?, ?, ?)",
					(id_, h["fecha"], _real(h.get("precio")), _booleano(h.get("disponible"), True)),
				)
		mapa[uuid] = id_
	return mapa


def _importar_avisos(conexion: sqlite3.Connection, avisos: list[dict], mapa_productos: dict[str, int]) -> None:
	for a in avisos:
		fecha, tipo = _fecha(a.get("fecha")), str(a.get("tipo") or "")
		if not fecha or not tipo:
			continue
		producto_id = mapa_productos.get(str(a.get("producto") or "")) if a.get("producto") else None
		titulo, mensaje = str(a.get("titulo") or ""), str(a.get("mensaje") or "")
		repetido = conexion.execute(
			"SELECT 1 FROM avisos WHERE fecha = ? AND tipo = ? AND mensaje = ? AND producto_id IS ?",
			(fecha, tipo, mensaje, producto_id),
		).fetchone()
		if repetido is None:
			conexion.execute(
				"INSERT INTO avisos (producto_id, fecha, tipo, titulo, mensaje, leido) VALUES (?, ?, ?, ?, ?, ?)",
				(producto_id, fecha, tipo, titulo, mensaje, _booleano(a.get("leido"), False)),
			)
