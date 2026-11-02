"""Notificaciones de Windows asociadas al icono de la bandeja, y sonidos.

``wx.adv.NotificationMessage`` con ``UseTaskBarIcon`` sale como notificación
de Windows sin acceso directo con AUMID (los «toasts» modernos lo exigirían y
son frágiles en una app portable). Al pulsarla se abre el producto.

Las notificaciones desaparecen: por eso cada aviso se guarda ANTES en la
tabla ``avisos`` (sección «Avisos»), que es el registro consultable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import wx
import wx.adv

log = logging.getLogger(__name__)

# Notificaciones vivas: si el recolector se llevara el objeto Python, el clic
# ya no llegaría a nuestro manejador.
MAXIMO_VIVAS = 20


class Notificador:
	"""Muestra notificaciones y avisa al pulsarlas con el id del producto."""

	def __init__(self, padre: wx.Window, al_pulsar: Callable[[int | None], None]) -> None:
		self._padre = padre
		self._al_pulsar = al_pulsar
		self._vivas: list[wx.adv.NotificationMessage] = []
		self._icono_asociado = False

	def asociar_icono(self, icono: wx.adv.TaskBarIcon | None) -> None:
		"""Usa el icono de la bandeja para las notificaciones (Windows)."""
		if icono is None:
			return
		try:
			wx.adv.NotificationMessage.UseTaskBarIcon(icono)
			self._icono_asociado = True
		except (AttributeError, RuntimeError):
			log.warning("No se pudo asociar el icono de la bandeja a las notificaciones", exc_info=True)

	def desasociar(self) -> None:
		"""Olvida el icono ANTES de destruirlo: wx guarda un puntero y, si el icono
		ya no existe, la siguiente notificación o asociación cierra el programa."""
		if not self._icono_asociado:
			return
		try:
			wx.adv.NotificationMessage.UseTaskBarIcon(None)
		except (AttributeError, RuntimeError, TypeError):
			log.debug("No se pudo desasociar el icono de las notificaciones", exc_info=True)
		self._icono_asociado = False
		for notificacion in self._vivas:
			try:
				notificacion.Close()
			except (RuntimeError, wx.PyAssertionError):
				log.debug("No se pudo cerrar una notificación", exc_info=True)
		self._vivas.clear()

	def mostrar(self, titulo: str, mensaje: str, producto_id: int | None = None, error: bool = False) -> bool:
		"""Muestra una notificación. ``False`` si Windows no la aceptó."""
		try:
			notificacion = wx.adv.NotificationMessage(titulo, mensaje, self._padre, wx.ICON_WARNING if error else wx.ICON_INFORMATION)
			notificacion.Bind(wx.adv.EVT_NOTIFICATION_MESSAGE_CLICK, lambda _evento, p=producto_id: self._pulsada(p))
			notificacion.Bind(wx.adv.EVT_NOTIFICATION_MESSAGE_DISMISSED, lambda evento: evento.Skip())
			mostrada = bool(notificacion.Show(wx.adv.NotificationMessage.Timeout_Auto))
		except (RuntimeError, wx.PyAssertionError):
			log.exception("No se pudo mostrar la notificación")
			return False
		self._vivas.append(notificacion)
		del self._vivas[:-MAXIMO_VIVAS]
		log.info("Notificación: %s", titulo)
		return mostrada

	def _pulsada(self, producto_id: int | None) -> None:
		try:
			self._al_pulsar(producto_id)
		except Exception:
			log.exception("Error al abrir el producto desde la notificación")


def sonar(cambios: bool = True) -> None:
	"""Sonido corto del sistema al terminar una comprobación con cambios."""
	try:
		import winsound

		winsound.MessageBeep(winsound.MB_ICONASTERISK if cambios else winsound.MB_OK)
	except (ImportError, RuntimeError, OSError):
		log.debug("No se pudo reproducir el sonido", exc_info=True)
