"""Icono de la bandeja del sistema con menú accesible.

El icono está siempre puesto mientras la aplicación funciona: la app sigue
comprobando precios con la ventana cerrada, y las notificaciones de Windows
se asocian a este icono (``NotificationMessage.UseTaskBarIcon``).

Menú (español, con ``&``): Mostrar, Comprobar ahora, Salir. Un clic o un
doble clic muestran la ventana. Desde el teclado: Windows+B lleva a la
bandeja, las flechas al icono, e Intro o la tecla Aplicaciones lo activan o
abren el menú.
"""

from __future__ import annotations

import builtins
import logging
from collections.abc import Callable

import wx
import wx.adv

from app.core import paths

log = logging.getLogger(__name__)


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


class IconoBandeja(wx.adv.TaskBarIcon):
	"""Icono de bandeja; las acciones se inyectan desde la ventana principal."""

	def __init__(
		self,
		texto: str,
		al_restaurar: Callable[[], None],
		al_salir: Callable[[], None],
		al_comprobar: Callable[[], None] | None = None,
	) -> None:
		super().__init__()
		self._texto = texto
		self._al_restaurar = al_restaurar
		self._al_salir = al_salir
		self._al_comprobar = al_comprobar
		self.icono = icono_aplicacion()
		self.Bind(wx.adv.EVT_TASKBAR_LEFT_UP, self._restaurar)
		self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self._restaurar)

	def mostrar(self, texto: str | None = None) -> bool:
		"""Pone (o actualiza) el icono. El texto emergente es lo que lee el lector."""
		if texto:
			self._texto = texto
		return bool(self.SetIcon(self.icono, self._texto))

	def quitar(self) -> None:
		"""Quita el icono y destruye el objeto (hay que llamarlo siempre al cerrar)."""
		if self.IsIconInstalled():
			self.RemoveIcon()
		self.Destroy()

	def CreatePopupMenu(self) -> wx.Menu:  # noqa: N802 - nombre impuesto por wx
		menu = wx.Menu()
		elemento_mostrar = menu.Append(wx.ID_ANY, _("&Mostrar"))
		menu.Bind(wx.EVT_MENU, self._restaurar, elemento_mostrar)
		if self._al_comprobar is not None:
			elemento_comprobar = menu.Append(wx.ID_ANY, _("&Comprobar ahora"))
			menu.Bind(wx.EVT_MENU, lambda _evento: self._al_comprobar(), elemento_comprobar)
		menu.AppendSeparator()
		elemento_salir = menu.Append(wx.ID_EXIT, _("&Salir"))
		menu.Bind(wx.EVT_MENU, lambda _evento: self._al_salir(), elemento_salir)
		return menu

	def _restaurar(self, _evento: wx.Event | None = None) -> None:
		self._al_restaurar()


def icono_aplicacion() -> wx.Icon:
	"""``data/icons/app.ico`` si existe; si no, un icono genérico de wx."""
	ruta = paths.ruta_base() / "data" / "icons" / "app.ico"
	if not ruta.is_file():
		ruta = paths.ruta_iconos() / "app.ico"
	if ruta.is_file():
		icono = wx.Icon(str(ruta), wx.BITMAP_TYPE_ICO)
		if icono.IsOk():
			return icono
		log.warning("El icono %s no es válido; se usa el genérico", ruta)
	icono = wx.Icon()
	icono.CopyFromBitmap(wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_OTHER, (16, 16)))
	return icono
