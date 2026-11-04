"""Núcleo de la aplicación: base de datos, repositorio, comprobador y ajustes.

Une las piezas sin wx para que la interfaz (y las pruebas) las usen con una
sola llamada. Se crea al arrancar, ANTES de lanzar hilos, y se cierra al
salir (``cerrar``): sesiones de red y base de datos ordenadas.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core import paths
from app.core.base_datos import BaseDatos
from app.core.configuracion import CLAVES_ESPECIFICACION, Configuracion
from app.core.migraciones import MIGRACIONES
from app.services import avisos as logica
from app.services import reglas
from app.services.comprobador import Comprobador
from app.services.descargador import Descargador
from app.services.direcciones import dominio_de, limpiar_url
from app.services.extractor import Resultado
from app.services.repositorio import Repositorio, ahora_iso, leer_fecha

log = logging.getLogger(__name__)

# Copias diarias que se guardan en data/backups.
COPIAS_CONSERVADAS = 7
#: Primera espera tras un fallo de la comprobación automática (luego se duplica).
ESPERA_TRAS_FALLO = timedelta(minutes=15)


class Nucleo:
	"""Todo lo que la interfaz necesita para trabajar con los datos."""

	def __init__(self, configuracion: Configuracion, ruta_base_datos: Path | None = None) -> None:
		self.config = configuracion
		self.bd = BaseDatos(
			ruta_base_datos or paths.ruta_base_datos() / paths.NOMBRE_BASE_DATOS,
			MIGRACIONES,
			carpeta_copias=paths.ruta_copias(),
			copias_conservadas=COPIAS_CONSERVADAS,
		)
		self.repositorio = Repositorio(self.bd)
		self.descargador = Descargador(float(self.ajustes()["tiempo_espera"]))
		self.comprobador = Comprobador(self.repositorio, self.descargador, reglas.catalogo, self.ajustes)
		# Espera tras fallos de la comprobación automática (ver aplazar_tras_fallo)
		self._fallos_seguidos = 0
		self._no_antes_de: datetime | None = None

	# ── Ajustes ──────────────────────────────────────────────────────────────

	def ajustes(self) -> dict[str, Any]:
		"""Ajustes con las claves de la especificación (``intervalo_horas``...)."""
		return {clave: self.config.obtener(ruta) for clave, ruta in CLAVES_ESPECIFICACION.items()}

	def aplicar_ajustes_importados(self, ajustes: dict[str, Any]) -> int:
		"""Aplica los ajustes de un archivo importado (los no válidos se ignoran)."""
		cambios = {}
		for clave, valor in ajustes.items():
			ruta = CLAVES_ESPECIFICACION.get(clave)
			if ruta is None:
				continue
			actual = self.config.obtener(ruta)
			if isinstance(actual, float) and isinstance(valor, int) and not isinstance(valor, bool):
				valor = float(valor)
			try:
				self.config.validar(ruta, valor)
			except ValueError:
				log.warning("Ajuste importado no válido, se ignora: %s", clave)
				continue
			cambios[ruta] = valor
		if cambios:
			self.config.establecer_varias(cambios)
		return len(cambios)

	# ── Calendario ───────────────────────────────────────────────────────────

	def aplazar_tras_fallo(self, ahora: datetime | None = None) -> timedelta:
		"""Tras un fallo de la comprobación automática, espera antes de reintentar.

		Sin esto, el programador (cada minuto) la repetía sin parar: en la 1.0.1
		un mismo fallo quedó 1039 veces en el registro en una noche. La espera
		crece con cada fallo seguido (15, 30, 60 minutos...) sin pasar del
		intervalo de comprobación. Vive solo en memoria: al reiniciar la app se
		vuelve a intentar.
		"""
		ahora = ahora or datetime.now(timezone.utc)
		self._fallos_seguidos += 1
		intervalo = timedelta(hours=int(self.config.obtener("precios.intervalo_horas") or 6))
		espera = min(ESPERA_TRAS_FALLO * (2 ** (self._fallos_seguidos - 1)), intervalo)
		self._no_antes_de = ahora + espera
		return espera

	def toca_comprobar(self, ahora: datetime | None = None) -> bool:
		"""¿La última comprobación completa es más vieja que el intervalo?"""
		ahora = ahora or datetime.now(timezone.utc)
		if self._no_antes_de is not None and ahora < self._no_antes_de:
			return False
		ultima = leer_fecha(self.config.obtener("general.ultima_comprobacion")) or leer_fecha(
			self.repositorio.ultima_comprobacion_global()
		)
		if ultima is None:
			return True
		intervalo = timedelta(hours=int(self.config.obtener("precios.intervalo_horas") or 6))
		return ahora - ultima >= intervalo or ultima > ahora + timedelta(minutes=5)

	def segundos_hasta_comprobar(self, ahora: datetime | None = None) -> float:
		"""Segundos que faltan para la próxima comprobación automática (0 si ya toca)."""
		ahora = ahora or datetime.now(timezone.utc)
		ultima = leer_fecha(self.config.obtener("general.ultima_comprobacion"))
		if ultima is None or ultima > ahora:
			return 0.0
		intervalo = timedelta(hours=int(self.config.obtener("precios.intervalo_horas") or 6))
		return max(0.0, (ultima + intervalo - ahora).total_seconds())

	def anotar_comprobacion(self, fecha: str | None = None) -> None:
		self.config.establecer("general.ultima_comprobacion", fecha or ahora_iso())
		# Una comprobación completa que termina bien olvida los fallos anteriores
		self._fallos_seguidos = 0
		self._no_antes_de = None

	def copia_diaria_si_toca(self, hoy: date | None = None) -> Path | None:
		"""Copia de seguridad diaria de la base (se guardan las 7 últimas)."""
		hoy_texto = (hoy or date.today()).isoformat()
		if self.config.obtener("general.ultima_copia") == hoy_texto:
			return None
		copia = self.bd.copia_seguridad(motivo="diaria")
		self.config.establecer("general.ultima_copia", hoy_texto)
		return copia

	def purgar_avisos(self) -> int:
		return self.repositorio.purgar_avisos(int(self.config.obtener("precios.conservar_avisos_dias") or 0))

	# ── Productos ────────────────────────────────────────────────────────────

	def tienda_para(self, url: str) -> tuple[int, str]:
		"""(id, nombre) de la tienda del producto; la crea si es su primer producto."""
		dominio = dominio_de(url)
		existente = self.repositorio.tienda_por_dominio(dominio)
		if existente:
			return int(existente["id"]), existente["nombre"]
		nombre = reglas.catalogo().nombre_tienda(dominio)
		return self.repositorio.obtener_o_crear_tienda(dominio, nombre), nombre

	def anadir_producto(self, url: str, resultado: Resultado | None = None, **campos: Any) -> int:
		"""Guarda un producto nuevo y, si se comprobó al añadirlo, su primera lectura."""
		url = limpiar_url(url)
		tienda_id, tienda = self.tienda_para(url)
		ahora = ahora_iso()
		producto_id = self.repositorio.crear_producto(url=url, tienda_id=tienda_id, fecha_alta=ahora, **campos)
		if resultado is not None and resultado.valido:
			producto = self.repositorio.producto(producto_id) or {}
			cambios = logica.aplicar_resultado(
				producto,
				resultado.precio,
				resultado.disponible,
				ahora=ahora,
				tienda=tienda,
				ajustes=self.ajustes(),
				nombre_pagina=resultado.nombre,
				imagen=resultado.imagen,
				moneda=resultado.moneda,
				origen_precio=resultado.origen_precio,
				confianza=resultado.confianza,
				desde=resultado.desde and not campos.get("variante"),
				hay_historial=False,
			)
			self.repositorio.aplicar_cambios(producto_id, cambios, ahora)
		return producto_id

	def cerrar(self) -> None:
		"""Cierra las sesiones de red y la base de datos."""
		try:
			self.descargador.cerrar()
		finally:
			self.bd.cerrar()
