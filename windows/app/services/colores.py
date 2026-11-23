"""Colores de la lista (1.1.0): paleta y qué color lleva cada producto.

Todo puro (sin wx) para poder probarlo. La especificación común está en
``compartido/ESPECIFICACION.md``, «Colores de la lista»: Android usa la misma
paleta, los mismos identificadores y la misma regla.

El color nunca es la única pista: la fila ya empieza por su estado («En
oferta», «Agotado»...) y dice «bajó» o «subió». Los colores son para quien ve
la pantalla.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services import errores, vistas
from app.services.repositorio import leer_fecha

# Tipos de color (qué estado se colorea).
BAJADA, SUBIDA, OBJETIVO, PROBLEMA = "bajada", "subida", "objetivo", "problema"
TIPOS = (BAJADA, SUBIDA, OBJETIVO, PROBLEMA)

# Modos: se colorea el fondo de la fila o las letras.
FONDO, TEXTO = "fondo", "texto"
MODOS = ((FONDO, "Fondo de la fila"), (TEXTO, "Texto"))

NINGUNO = "ninguno"


@dataclass(frozen=True)
class Color:
	"""Un color de la paleta: tono claro de fondo y tono oscuro para el texto.

	``fondo_oscuro`` y ``texto_claro`` son los de Android con el tema oscuro;
	Windows solo usa ``fondo`` y ``texto``.
	"""

	id: str
	nombre: str
	fondo: str | None
	texto: str | None
	fondo_oscuro: str | None
	texto_claro: str | None


PALETA: tuple[Color, ...] = (
	Color(NINGUNO, "Sin color", None, None, None, None),
	Color("verde", "Verde", "#C8E6C9", "#1B5E20", "#1E4620", "#A5D6A7"),
	Color("azul", "Azul", "#BBDEFB", "#0D47A1", "#0D3260", "#90CAF9"),
	Color("celeste", "Celeste", "#B3E5FC", "#01579B", "#0A3D5C", "#81D4FA"),
	Color("turquesa", "Turquesa", "#B2DFDB", "#004D40", "#0B3D38", "#80CBC4"),
	Color("morado", "Morado", "#E1BEE7", "#4A148C", "#3B1D4A", "#CE93D8"),
	Color("rosa", "Rosa", "#F8BBD0", "#880E4F", "#4A1830", "#F48FB1"),
	Color("rojo", "Rojo", "#FFCDD2", "#B71C1C", "#5C1A1A", "#EF9A9A"),
	Color("naranja", "Naranja", "#FFE0B2", "#BF360C", "#5A3210", "#FFCC80"),
	Color("amarillo", "Amarillo", "#FFF9C4", "#7A5C00", "#4D4410", "#FFF59D"),
	Color("marron", "Marrón", "#D7CCC8", "#4E342E", "#3E2C26", "#BCAAA4"),
	Color("gris", "Gris", "#E0E0E0", "#424242", "#3A3A3A", "#BDBDBD"),
)
IDS = tuple(c.id for c in PALETA)
_POR_ID = {c.id: c for c in PALETA}

# Color por defecto de cada tipo (mismo valor que en la configuración).
POR_DEFECTO = {BAJADA: "verde", SUBIDA: "rojo", OBJETIVO: "azul", PROBLEMA: "gris"}

# Nombre visible de cada tipo (preferencias, vista previa y manual).
NOMBRES_TIPO = {
	BAJADA: "Bajada u oferta",
	SUBIDA: "Subida",
	OBJETIVO: "Precio deseado alcanzado",
	PROBLEMA: "Agotado o con problemas",
}

# Aviso (tabla avisos) → tipo de color.
_TIPO_AVISO = {
	"objetivo": OBJETIVO,
	"minimo": BAJADA,
	"bajada": BAJADA,
	"subida": SUBIDA,
	"agotado": PROBLEMA,
	"error": PROBLEMA,
}


def color(identificador: str | None, tipo: str | None = None) -> Color:
	"""Color de la paleta; un identificador desconocido vale el de por defecto del tipo (o ninguno)."""
	if identificador in _POR_ID:
		return _POR_ID[identificador]
	return _POR_ID[POR_DEFECTO.get(tipo or "", NINGUNO)]


def tipo_color(p: Mapping[str, Any], ahora: datetime | None = None) -> str | None:
	"""Qué color lleva un producto (``None`` = ninguno), el primero que se cumpla.

	1. En pausa: ninguno. 2. Última comprobación mal o agotado: problema.
	3. Pendiente: ninguno. 4. Precio deseado alcanzado: objetivo.
	5. En oferta (regla de la sección Ofertas): bajada.
	6. Subió en los últimos 7 días: subida.
	"""
	if not p.get("activo", 1):
		return None
	estado = vistas.estado_comprobacion(p)
	if estado in (errores.BLOQUEADA, errores.SIN_PRECIO, errores.SIN_CONEXION, errores.ERROR):
		return PROBLEMA
	if not p.get("disponible", 1):
		return PROBLEMA
	if estado == errores.PENDIENTE:
		return None
	if vistas.objetivo_alcanzado(p):
		return OBJETIVO
	ahora = ahora or datetime.now(timezone.utc)
	if vistas.en_oferta(p, ahora):
		return BAJADA
	actual, anterior = p.get("precio_actual"), p.get("precio_anterior")
	cambio = leer_fecha(p.get("fecha_cambio"))
	if (
		actual is not None and anterior and actual > anterior
		and cambio is not None and ahora - cambio <= timedelta(days=vistas.DIAS_OFERTA)
	):
		return SUBIDA
	return None


def tipo_color_aviso(tipo: str | None) -> str | None:
	"""Color de un aviso de la sección Avisos según su tipo («disponible» no lleva)."""
	return _TIPO_AVISO.get(tipo or "")


@dataclass(frozen=True)
class Ajustes:
	"""Los ajustes de colores ya leídos y comprobados."""

	activos: bool = True
	modo: str = FONDO
	colores: Mapping[str, str] | None = None

	def color_de(self, tipo: str | None) -> Color | None:
		"""Color que toca a un tipo (``None`` si no se colorea)."""
		if not self.activos or tipo is None:
			return None
		elegido = color((self.colores or POR_DEFECTO).get(tipo), tipo)
		return None if elegido.id == NINGUNO else elegido

	def pintura(self, tipo: str | None) -> tuple[str | None, str | None]:
		"""(fondo, texto) en hexadecimal para una fila; ``(None, None)`` = colores normales."""
		elegido = self.color_de(tipo)
		if elegido is None:
			return None, None
		return (elegido.fondo, None) if self.modo == FONDO else (None, elegido.texto)


def leer_ajustes(obtener) -> Ajustes:
	"""Ajustes de colores a partir de ``obtener(clave_de_configuracion, por_defecto)``."""
	modo = obtener("colores.colores_modo", FONDO)
	return Ajustes(
		activos=bool(obtener("colores.colores_lista", True)),
		modo=modo if modo in (FONDO, TEXTO) else FONDO,
		colores={tipo: str(obtener(f"colores.color_{tipo}", POR_DEFECTO[tipo]) or POR_DEFECTO[tipo]) for tipo in TIPOS},
	)
