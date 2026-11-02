"""Acceso a los datos (productos, tiendas, categorías, historial y avisos).

La interfaz nunca escribe SQL: pide y guarda a través de este repositorio.
Todas las consultas van con parámetros; los nombres de columna que llegan de
fuera pasan por listas blancas. Las escrituras relacionadas van en una sola
transacción (``bd.transaccion()``), por ejemplo aplicar una comprobación:
producto, historial y avisos cambian juntos o no cambia nada.

Sin wx. Los productos se devuelven como ``dict`` con, además de sus columnas,
``tienda`` (nombre), ``dominio`` y ``categoria`` (nombre o «Sin categoría»).
"""

from __future__ import annotations

import logging
import sqlite3
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.base_datos import BaseDatos, marcadores
from app.services.avisos import Cambios
from app.services.importes import redondear

log = logging.getLogger(__name__)

SIN_CATEGORIA = "Sin categoría"

COLUMNAS_PRODUCTO = (
	"uuid", "nombre", "url", "tienda_id", "categoria_id", "grupo", "moneda", "precio_actual", "disponible",
	"precio_inicial", "precio_minimo", "fecha_minimo", "precio_maximo", "fecha_maximo", "precio_anterior",
	"fecha_cambio", "precio_objetivo", "alerta_porcentaje", "avisar_disponible", "selector_precio", "imagen_url",
	"notas", "favorito", "activo", "fecha_alta", "ultima_comprobacion", "ultimo_error", "errores_seguidos",
	"estado", "origen_precio", "variante", "confianza", "huella_selector", "desde",
)
COLUMNAS_IMPORTE = {"precio_actual", "precio_inicial", "precio_minimo", "precio_maximo", "precio_anterior", "precio_objetivo"}
COLUMNAS_BOOLEANAS = {"disponible", "avisar_disponible", "favorito", "activo", "desde"}
COLUMNAS_TIENDA = ("uuid", "nombre", "dominio", "selector_precio", "selector_titulo", "selector_disponible", "notas", "modo_descarga")
MODOS_DESCARGA = ("auto", "directo", "navegador")
COLUMNAS_CATEGORIA = ("uuid", "nombre", "descripcion", "orden")

_CONSULTA_PRODUCTOS = """
SELECT p.*, t.nombre AS tienda, t.dominio AS dominio, c.nombre AS categoria_nombre,
	t.selector_precio AS tienda_selector_precio, t.selector_titulo AS tienda_selector_titulo,
	t.selector_disponible AS tienda_selector_disponible, t.modo_descarga AS tienda_modo_descarga
FROM productos AS p
LEFT JOIN tiendas AS t ON t.id = p.tienda_id
LEFT JOIN categorias AS c ON c.id = p.categoria_id
"""


class ErrorDatos(Exception):
	"""Error de datos con un mensaje para el usuario (nombre repetido, tienda con productos...)."""


def ahora_iso(momento: datetime | None = None) -> str:
	"""Fecha ISO 8601 en UTC con ``Z`` y sin fracciones: ``2026-11-02T20:15:00Z``."""
	momento = momento or datetime.now(timezone.utc)
	return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def leer_fecha(texto: str | None) -> datetime | None:
	"""Lee una fecha ISO (con ``Z`` o con desfase). ``None`` si no es válida."""
	if not texto:
		return None
	try:
		fecha = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
	except ValueError:
		return None
	return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def nuevo_uuid() -> str:
	return str(uuid_mod.uuid4())


def _normalizar_valor(columna: str, valor: Any) -> Any:
	if columna in COLUMNAS_IMPORTE:
		return redondear(valor) if valor not in (None, "") else None
	if columna in COLUMNAS_BOOLEANAS:
		return 1 if valor else 0
	return valor


def _fila_producto(fila: sqlite3.Row) -> dict[str, Any]:
	datos = dict(fila)
	datos["categoria"] = datos.pop("categoria_nombre", None) or SIN_CATEGORIA
	datos["tienda"] = datos.get("tienda") or ""
	return datos


class Repositorio:
	"""Operaciones de datos sobre una :class:`BaseDatos` ya migrada."""

	def __init__(self, bd: BaseDatos) -> None:
		self.bd = bd

	# ── Tiendas ──────────────────────────────────────────────────────────────

	def tiendas(self) -> list[dict[str, Any]]:
		"""Tiendas con su número de productos, por nombre."""
		filas = self.bd.consultar(
			"SELECT t.*, (SELECT COUNT(*) FROM productos p WHERE p.tienda_id = t.id) AS productos "
			"FROM tiendas t ORDER BY t.nombre COLLATE NOCASE"
		)
		return [dict(f) for f in filas]

	def tienda(self, tienda_id: int) -> dict[str, Any] | None:
		fila = self.bd.consultar_uno("SELECT * FROM tiendas WHERE id = ?", (tienda_id,))
		return dict(fila) if fila else None

	def tienda_por_dominio(self, dominio: str) -> dict[str, Any] | None:
		fila = self.bd.consultar_uno("SELECT * FROM tiendas WHERE dominio = ?", (dominio,))
		return dict(fila) if fila else None

	def obtener_o_crear_tienda(self, dominio: str, nombre: str) -> int:
		"""Id de la tienda del dominio; la crea si es el primer producto de ese dominio."""
		with self.bd.transaccion() as conexion:
			fila = conexion.execute("SELECT id FROM tiendas WHERE dominio = ?", (dominio,)).fetchone()
			if fila:
				return int(fila[0])
			cursor = conexion.execute(
				"INSERT INTO tiendas (uuid, nombre, dominio) VALUES (?, ?, ?)", (nuevo_uuid(), nombre or dominio, dominio)
			)
			log.info("Tienda nueva: %s", dominio)
			return int(cursor.lastrowid)

	def actualizar_tienda(self, tienda_id: int, **campos: Any) -> None:
		validos = {c: v for c, v in campos.items() if c in COLUMNAS_TIENDA and c not in ("uuid", "dominio")}
		if "nombre" in validos and not str(validos["nombre"] or "").strip():
			raise ErrorDatos("El nombre de la tienda no puede quedar vacío.")
		if "modo_descarga" in validos and validos["modo_descarga"] not in MODOS_DESCARGA:
			validos["modo_descarga"] = "auto"
		if not validos:
			return
		asignaciones = ", ".join(f"{c} = ?" for c in validos)
		self.bd.ejecutar(f"UPDATE tiendas SET {asignaciones} WHERE id = ?", (*validos.values(), tienda_id))  # noqa: S608 - columnas de lista blanca

	def borrar_tienda(self, tienda_id: int) -> None:
		"""Borra una tienda sin productos."""
		with self.bd.transaccion() as conexion:
			cuantos = conexion.execute("SELECT COUNT(*) FROM productos WHERE tienda_id = ?", (tienda_id,)).fetchone()[0]
			if cuantos:
				raise ErrorDatos("La tienda tiene productos: bórrelos o muévalos antes de borrarla.")
			conexion.execute("DELETE FROM tiendas WHERE id = ?", (tienda_id,))

	# ── Categorías ───────────────────────────────────────────────────────────

	def categorias(self) -> list[dict[str, Any]]:
		"""Categorías en su orden (a mano; si empatan, alfabético) con su número de productos."""
		filas = self.bd.consultar(
			"SELECT c.*, (SELECT COUNT(*) FROM productos p WHERE p.categoria_id = c.id) AS productos "
			"FROM categorias c ORDER BY c.orden, c.nombre COLLATE NOCASE"
		)
		return [dict(f) for f in filas]

	def sin_categoria(self) -> int:
		return int(self.bd.valor("SELECT COUNT(*) FROM productos WHERE categoria_id IS NULL", por_defecto=0))

	def categoria_por_nombre(self, nombre: str) -> dict[str, Any] | None:
		nombre = (nombre or "").strip()
		for categoria in self.categorias():
			if categoria["nombre"].casefold() == nombre.casefold():
				return categoria
		return None

	def crear_categoria(self, nombre: str, descripcion: str | None = None) -> int:
		nombre = (nombre or "").strip()
		if not nombre:
			raise ErrorDatos("Escriba un nombre para la categoría.")
		if nombre.casefold() == SIN_CATEGORIA.casefold() or self.categoria_por_nombre(nombre):
			raise ErrorDatos(f"Ya existe una categoría llamada «{nombre}».")
		orden = int(self.bd.valor("SELECT COALESCE(MAX(orden) + 1, 0) FROM categorias", por_defecto=0))
		return self.bd.insertar(
			"INSERT INTO categorias (uuid, nombre, descripcion, orden) VALUES (?, ?, ?, ?)",
			(nuevo_uuid(), nombre, descripcion, orden),
		)

	def renombrar_categoria(self, categoria_id: int, nombre: str) -> None:
		nombre = (nombre or "").strip()
		if not nombre:
			raise ErrorDatos("Escriba un nombre para la categoría.")
		otra = self.categoria_por_nombre(nombre)
		if (otra and otra["id"] != categoria_id) or nombre.casefold() == SIN_CATEGORIA.casefold():
			raise ErrorDatos(f"Ya existe una categoría llamada «{nombre}».")
		self.bd.ejecutar("UPDATE categorias SET nombre = ? WHERE id = ?", (nombre, categoria_id))

	def borrar_categoria(self, categoria_id: int) -> None:
		"""Borra la categoría; sus productos pasan a «Sin categoría»."""
		with self.bd.transaccion() as conexion:
			conexion.execute("UPDATE productos SET categoria_id = NULL WHERE categoria_id = ?", (categoria_id,))
			conexion.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))

	def mover_categoria(self, categoria_id: int, desplazamiento: int) -> bool:
		"""Sube (−1) o baja (+1) una categoría. ``False`` si ya está en el extremo."""
		ids = [c["id"] for c in self.categorias()]
		if categoria_id not in ids:
			return False
		posicion = ids.index(categoria_id)
		destino = posicion + desplazamiento
		if not 0 <= destino < len(ids):
			return False
		ids[posicion], ids[destino] = ids[destino], ids[posicion]
		with self.bd.transaccion() as conexion:
			conexion.executemany("UPDATE categorias SET orden = ? WHERE id = ?", [(i, c) for i, c in enumerate(ids)])
		return True

	# ── Productos ────────────────────────────────────────────────────────────

	def productos(self) -> list[dict[str, Any]]:
		return [_fila_producto(f) for f in self.bd.consultar(_CONSULTA_PRODUCTOS + " ORDER BY p.nombre COLLATE NOCASE")]

	def producto(self, producto_id: int) -> dict[str, Any] | None:
		fila = self.bd.consultar_uno(_CONSULTA_PRODUCTOS + " WHERE p.id = ?", (producto_id,))
		return _fila_producto(fila) if fila else None

	def productos_por_ids(self, ids: list[int]) -> list[dict[str, Any]]:
		if not ids:
			return []
		filas = self.bd.consultar(_CONSULTA_PRODUCTOS + f" WHERE p.id IN ({marcadores(len(ids))})", ids)  # noqa: S608
		return [_fila_producto(f) for f in filas]

	def producto_por_url(self, url: str) -> dict[str, Any] | None:
		fila = self.bd.consultar_uno(_CONSULTA_PRODUCTOS + " WHERE p.url = ?", (url,))
		return _fila_producto(fila) if fila else None

	def crear_producto(self, **campos: Any) -> int:
		"""Crea un producto. Necesita al menos ``url``; el resto toma su valor por defecto."""
		if not campos.get("url"):
			raise ErrorDatos("La dirección del producto es obligatoria.")
		campos.setdefault("uuid", nuevo_uuid())
		campos.setdefault("nombre", "")
		campos.setdefault("fecha_alta", ahora_iso())
		campos.setdefault("estado", "pendiente")
		validos = {c: _normalizar_valor(c, v) for c, v in campos.items() if c in COLUMNAS_PRODUCTO}
		columnas = ", ".join(validos)
		return self.bd.insertar(
			f"INSERT INTO productos ({columnas}) VALUES ({marcadores(len(validos))})",  # noqa: S608 - lista blanca
			tuple(validos.values()),
		)

	def actualizar_producto(self, producto_id: int, **campos: Any) -> None:
		validos = {c: _normalizar_valor(c, v) for c, v in campos.items() if c in COLUMNAS_PRODUCTO and c != "uuid"}
		if not validos:
			return
		asignaciones = ", ".join(f"{c} = ?" for c in validos)
		self.bd.ejecutar(f"UPDATE productos SET {asignaciones} WHERE id = ?", (*validos.values(), producto_id))  # noqa: S608

	def eliminar_productos(self, ids: list[int]) -> int:
		if not ids:
			return 0
		return self.bd.ejecutar(f"DELETE FROM productos WHERE id IN ({marcadores(len(ids))})", ids)  # noqa: S608

	def mover_a_categoria(self, ids: list[int], categoria_id: int | None) -> None:
		if ids:
			self.bd.ejecutar(
				f"UPDATE productos SET categoria_id = ? WHERE id IN ({marcadores(len(ids))})",  # noqa: S608
				(categoria_id, *ids),
			)

	def grupos(self) -> list[tuple[str, int]]:
		"""Grupos de comparación con su número de productos."""
		filas = self.bd.consultar(
			"SELECT grupo, COUNT(*) AS n FROM productos WHERE grupo IS NOT NULL AND TRIM(grupo) <> '' "
			"GROUP BY grupo ORDER BY grupo COLLATE NOCASE"
		)
		return [(f["grupo"], int(f["n"])) for f in filas]

	def ultima_comprobacion_global(self) -> str | None:
		return self.bd.valor("SELECT MAX(ultima_comprobacion) FROM productos WHERE activo = 1")

	# ── Historial ────────────────────────────────────────────────────────────

	def historial(self, producto_id: int) -> list[dict[str, Any]]:
		filas = self.bd.consultar(
			"SELECT fecha, precio, disponible FROM historial WHERE producto_id = ? ORDER BY fecha", (producto_id,)
		)
		return [dict(f) for f in filas]

	def tiene_historial(self, producto_id: int) -> bool:
		return self.bd.valor("SELECT 1 FROM historial WHERE producto_id = ? LIMIT 1", (producto_id,)) is not None

	# ── Avisos ───────────────────────────────────────────────────────────────

	def avisos(self) -> list[dict[str, Any]]:
		"""Avisos del más nuevo al más viejo, con los no leídos primero."""
		filas = self.bd.consultar(
			"SELECT a.*, p.nombre AS producto_nombre FROM avisos a LEFT JOIN productos p ON p.id = a.producto_id "
			"ORDER BY a.leido, a.fecha DESC, a.id DESC"
		)
		return [dict(f) for f in filas]

	def avisos_sin_leer(self) -> int:
		return int(self.bd.valor("SELECT COUNT(*) FROM avisos WHERE leido = 0", por_defecto=0))

	def marcar_avisos(self, ids: list[int], leido: bool = True) -> None:
		if ids:
			self.bd.ejecutar(
				f"UPDATE avisos SET leido = ? WHERE id IN ({marcadores(len(ids))})", (1 if leido else 0, *ids)  # noqa: S608
			)

	def marcar_todos_leidos(self) -> None:
		self.bd.ejecutar("UPDATE avisos SET leido = 1 WHERE leido = 0")

	def borrar_avisos(self, ids: list[int] | None = None) -> int:
		"""Borra los avisos indicados (o todos si ``ids`` es ``None``)."""
		if ids is None:
			return self.bd.ejecutar("DELETE FROM avisos")
		if not ids:
			return 0
		return self.bd.ejecutar(f"DELETE FROM avisos WHERE id IN ({marcadores(len(ids))})", ids)  # noqa: S608

	def purgar_avisos(self, dias: int, ahora: datetime | None = None) -> int:
		"""Borra los avisos más viejos que ``dias`` (0 = se conservan siempre)."""
		if dias <= 0:
			return 0
		limite = ahora_iso((ahora or datetime.now(timezone.utc)) - timedelta(days=dias))
		return self.bd.ejecutar("DELETE FROM avisos WHERE fecha < ?", (limite,))

	def crear_aviso(self, producto_id: int | None, fecha: str, tipo: str, titulo: str, mensaje: str) -> int:
		return self.bd.insertar(
			"INSERT INTO avisos (producto_id, fecha, tipo, titulo, mensaje, leido) VALUES (?, ?, ?, ?, ?, 0)",
			(producto_id, fecha, tipo, titulo, mensaje),
		)

	# ── Comprobaciones ───────────────────────────────────────────────────────

	def aplicar_cambios(self, producto_id: int, cambios: Cambios, fecha: str) -> list[int]:
		"""Guarda una comprobación entera en una transacción. Devuelve los ids de los avisos."""
		ids: list[int] = []
		campos = {c: _normalizar_valor(c, v) for c, v in cambios.campos.items() if c in COLUMNAS_PRODUCTO}
		with self.bd.transaccion() as conexion:
			if campos:
				asignaciones = ", ".join(f"{c} = ?" for c in campos)
				conexion.execute(  # auditoria: ignorar sql-formateado - columnas de COLUMNAS_PRODUCTO, valores con marcadores
					f"UPDATE productos SET {asignaciones} WHERE id = ?",  # noqa: S608 - lista blanca
					(*campos.values(), producto_id),
				)
			if cambios.historial is not None:
				fecha_h, precio, disponible = cambios.historial
				conexion.execute(
					"INSERT OR REPLACE INTO historial (producto_id, fecha, precio, disponible) VALUES (?, ?, ?, ?)",
					(producto_id, fecha_h, redondear(precio), 1 if disponible else 0),
				)
			for aviso in cambios.avisos:
				cursor = conexion.execute(
					"INSERT INTO avisos (producto_id, fecha, tipo, titulo, mensaje, leido) VALUES (?, ?, ?, ?, ?, 0)",
					(producto_id, fecha, aviso.tipo, aviso.titulo, aviso.mensaje),
				)
				ids.append(int(cursor.lastrowid))
		return ids

	# ── Varios ───────────────────────────────────────────────────────────────

	def recuentos(self) -> dict[str, int]:
		return {
			"productos": int(self.bd.valor("SELECT COUNT(*) FROM productos", por_defecto=0)),
			"categorias": int(self.bd.valor("SELECT COUNT(*) FROM categorias", por_defecto=0)),
			"tiendas": int(self.bd.valor("SELECT COUNT(*) FROM tiendas", por_defecto=0)),
			"avisos": int(self.bd.valor("SELECT COUNT(*) FROM avisos", por_defecto=0)),
		}
