"""Espera cancelable: ejecuta un trabajo en un hilo con un diálogo «Comprobando...».

La interfaz nunca se congela: el trabajo va en un hilo y el resultado vuelve
con ``wx.CallAfter``. El diálogo tiene un texto de estado de solo lectura
(el lector lo lee al abrirse y se puede releer), una barra que se mueve sola
y un botón «Cancelar» (también Escape). Al cancelar, el diálogo se cierra al
momento; el hilo se avisa con un ``threading.Event`` y su resultado tardío se
descarta.
"""

from __future__ import annotations

import builtins
import logging
import threading
from collections.abc import Callable
from typing import Any

import wx

log = logging.getLogger(__name__)


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


class Cancelado(Exception):
	"""El usuario canceló la espera."""


class DialogoEspera(wx.Dialog):
	"""Diálogo modal que espera a ``trabajo(cancelado)`` sin bloquear la interfaz."""

	def __init__(self, padre: wx.Window | None, titulo: str, texto: str, trabajo: Callable[[threading.Event], Any]) -> None:
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE)
		self._trabajo = trabajo
		self.cancelado = threading.Event()
		self.resultado: Any = None
		self.error: BaseException | None = None
		sizer = wx.BoxSizer(wx.VERTICAL)
		etiqueta = wx.StaticText(self, label=_("&Estado:"))
		self.estado = wx.TextCtrl(self, value=texto, style=wx.TE_READONLY, size=self.FromDIP(wx.Size(420, -1)))
		self.barra = wx.Gauge(self, range=100, size=self.FromDIP(wx.Size(420, 16)))
		self.boton_cancelar = wx.Button(self, wx.ID_CANCEL, _("&Cancelar"))
		self.boton_cancelar.SetHelpText(_("Deja de esperar. La tienda puede tardar hasta el tiempo máximo de espera."))
		sizer.Add(etiqueta, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
		sizer.Add(self.estado, 0, wx.EXPAND | wx.ALL, 10)
		sizer.Add(self.barra, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		sizer.Add(self.boton_cancelar, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		self.SetSizerAndFit(sizer)
		self.SetEscapeId(wx.ID_CANCEL)
		self.boton_cancelar.Bind(wx.EVT_BUTTON, self._al_cancelar)
		self.Bind(wx.EVT_CLOSE, lambda _evento: self._al_cancelar(None))
		self._pulso = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, lambda _evento: self.barra.Pulse(), self._pulso)
		self.CentreOnParent()
		self.estado.SetFocus()
		self._hilo: threading.Thread | None = None

	def iniciar(self) -> None:
		"""Lanza el hilo (lo llama ``ejecutar`` justo antes de ``ShowModal``)."""
		self._pulso.Start(150)

		def envoltorio() -> None:
			try:
				resultado = self._trabajo(self.cancelado)
			except BaseException as error:  # noqa: BLE001 - se entrega al hilo principal
				wx.CallAfter(self._terminar, None, error)
				return
			wx.CallAfter(self._terminar, resultado, None)

		self._hilo = threading.Thread(target=envoltorio, name="espera", daemon=True)
		self._hilo.start()

	def _terminar(self, resultado: Any, error: BaseException | None) -> None:
		if not self or self.cancelado.is_set():
			return
		self._pulso.Stop()
		self.resultado, self.error = resultado, error
		if self.IsModal():
			self.EndModal(wx.ID_OK)

	def _al_cancelar(self, _evento: wx.CommandEvent | None) -> None:
		self.cancelado.set()
		self._pulso.Stop()
		if self.IsModal():
			self.EndModal(wx.ID_CANCEL)


def ejecutar(padre: wx.Window | None, titulo: str, texto: str, trabajo: Callable[[threading.Event], Any]) -> Any:
	"""Ejecuta ``trabajo`` con el diálogo de espera.

	Devuelve su resultado; relanza su excepción; lanza :class:`Cancelado` si el
	usuario cancela.
	"""
	dialogo = DialogoEspera(padre, titulo, texto, trabajo)
	foco_previo = wx.Window.FindFocus()
	try:
		dialogo.iniciar()
		codigo = dialogo.ShowModal()
		if codigo != wx.ID_OK:
			raise Cancelado
		if dialogo.error is not None:
			raise dialogo.error
		return dialogo.resultado
	finally:
		dialogo.cancelado.set()
		dialogo.Destroy()
		if foco_previo:
			foco_previo.SetFocus()
