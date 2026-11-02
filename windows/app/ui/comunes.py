"""Utilidades de interfaz compartidas por las ventanas de la aplicación.

- Mensajes, errores y preguntas con los diálogos accesibles del proyecto
  (botones en español que dicen la acción, Escape, foco que vuelve).
- ``anunciar``: voz directa SOLO para lo que el lector no puede saber por sí
  mismo (el resultado de una acción en segundo plano, por ejemplo).
- Abrir direcciones en el navegador y copiar al portapapeles.

Son funciones de módulo para poder sustituirlas en las pruebas.
"""

from __future__ import annotations

import builtins
import logging
import webbrowser
from collections.abc import Sequence

import wx

from app.core import voz
from app.ui.accesibilidad import dialogos

log = logging.getLogger(__name__)


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


def mensaje(padre: wx.Window | None, texto: str, titulo: str, icono: int = wx.ICON_INFORMATION) -> None:
	dialogos.mostrar_mensaje(padre, texto, titulo, icono=icono)


def error(padre: wx.Window | None, texto: str, titulo: str = "") -> None:
	dialogos.mostrar_error(padre, texto, titulo or _("Error"))


def preguntar(padre: wx.Window | None, texto: str, titulo: str, peligroso: bool = False) -> bool:
	"""Sí o No. Con ``peligroso``, Intro responde «No»."""
	return dialogos.confirmar(padre, texto, titulo, peligroso=peligroso) == wx.ID_YES


def elegir(padre: wx.Window | None, texto: str, titulo: str, opciones: Sequence[str]) -> int | None:
	"""Botones con la acción; devuelve el índice elegido o ``None`` (Escape)."""
	return dialogos.elegir_opcion(padre, texto, titulo, opciones)


def pedir_texto(padre: wx.Window | None, etiqueta: str, titulo: str, valor: str = "") -> str | None:
	return dialogos.pedir_texto(padre, etiqueta, titulo, valor)


def anunciar(texto: str) -> None:
	"""Dice un texto por el lector de pantalla (si hay voz directa disponible)."""
	voz.hablar(texto)


def abrir_en_navegador(url: str) -> bool:
	try:
		return bool(webbrowser.open(url, new=2))
	except (webbrowser.Error, OSError):
		log.exception("No se pudo abrir el navegador")
		return False


def copiar_texto(texto: str) -> bool:
	"""Copia al portapapeles. ``False`` si otro programa lo tiene bloqueado."""
	if not wx.TheClipboard.Open():
		log.warning("No se pudo abrir el portapapeles")
		return False
	try:
		wx.TheClipboard.SetData(wx.TextDataObject(texto))
		wx.TheClipboard.Flush()
	finally:
		wx.TheClipboard.Close()
	return True


def leer_portapapeles() -> str:
	"""Texto del portapapeles, o cadena vacía."""
	if not wx.TheClipboard.Open():
		return ""
	try:
		datos = wx.TextDataObject()
		if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_UNICODETEXT)) and wx.TheClipboard.GetData(datos):
			return datos.GetText()
		return ""
	finally:
		wx.TheClipboard.Close()


def botonera(padre: wx.Window, botones: Sequence[tuple[int, str]], predeterminado: int | None = None) -> wx.BoxSizer:
	"""Fila de botones alineada a la derecha, en el orden dado (``(id, etiqueta)``)."""
	fila = wx.BoxSizer(wx.HORIZONTAL)
	fila.AddStretchSpacer()
	for identificador, etiqueta in botones:
		boton = wx.Button(padre, identificador, etiqueta)
		if identificador == predeterminado:
			boton.SetDefault()
		fila.Add(boton, 0, wx.ALL, 4)
	return fila
