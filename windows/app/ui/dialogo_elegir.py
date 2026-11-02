"""Diálogos de elección: «Elegir el precio en la página» y «Elegir variante».

Selección asistida (apartado 7.1 de EXTRACTOR_GENERICO.md): una lista con una
línea por candidato, escrita para el lector de pantalla («39,99 € — junto al
botón de compra — "Precio: 39,99 €"»), más «Ninguno es el precio». El foco
empieza en la primera opción; Intro usa el precio elegido.

Si el selector generado no pasa la validación, se explica y la lista sigue
abierta para elegir otra opción.
"""

from __future__ import annotations

import builtins
import logging
from collections.abc import Callable, Sequence
from typing import Any

import wx

from app.services.extractor import CandidatoPrecio, Variante
from app.ui import comunes
from app.ui.accesibilidad.dialogos import preparar_dialogo

log = logging.getLogger(__name__)

NINGUNO = "Ninguno es el precio"


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


class DialogoElegirPrecio(wx.Dialog):
	"""Lista de candidatos. ``validar(candidato)`` devuelve un mensaje de error o ``None``."""

	def __init__(
		self,
		padre: wx.Window | None,
		candidatos: Sequence[CandidatoPrecio],
		texto: str,
		validar: Callable[[CandidatoPrecio], str | None] | None = None,
		permitir_tienda: bool = True,
	) -> None:
		super().__init__(padre, title=_("Elegir el precio en la página"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.candidatos = list(candidatos)
		self._validar = validar
		self.elegido: CandidatoPrecio | None = None
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.etiqueta = wx.StaticText(self, label=texto)
		self.etiqueta.Wrap(self.FromDIP(560))
		sizer.Add(self.etiqueta, 0, wx.ALL, 8)
		sizer.Add(wx.StaticText(self, label=_("&Precios encontrados:")), 0, wx.LEFT | wx.RIGHT, 8)
		self.lista = wx.ListBox(self, choices=[c.descripcion for c in self.candidatos] + [_(NINGUNO)], style=wx.LB_SINGLE)
		self.lista.SetMinSize(self.FromDIP(wx.Size(580, 220)))
		self.lista.SetHelpText(_("Cada opción dice el importe y dónde está en la página. Elija la que es el precio del producto."))
		self.lista.SetSelection(0)
		self.lista.Bind(wx.EVT_LISTBOX_DCLICK, self._al_aceptar)
		sizer.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
		self.casilla_tienda = wx.CheckBox(self, label=_("Usar también para &todos los productos de esta tienda"))
		self.casilla_tienda.SetHelpText(_("Guarda la posición del precio en la tienda, para todos sus productos."))
		self.casilla_tienda.Show(permitir_tienda)
		sizer.Add(self.casilla_tienda, 0, wx.ALL, 8)
		botones = wx.StdDialogButtonSizer()
		aceptar = wx.Button(self, wx.ID_OK, _("&Usar este precio"))
		aceptar.SetDefault()
		aceptar.Bind(wx.EVT_BUTTON, self._al_aceptar)
		botones.AddButton(aceptar)
		botones.AddButton(wx.Button(self, wx.ID_CANCEL, _("&Cancelar")))
		botones.Realize()
		sizer.Add(botones, 0, wx.EXPAND | wx.ALL, 8)
		self.SetSizerAndFit(sizer)
		preparar_dialogo(self, foco_inicial=self.lista)
		self.CentreOnParent()

	def _al_aceptar(self, _evento: wx.Event | None) -> None:
		indice = self.lista.GetSelection()
		if indice < 0 or indice >= len(self.candidatos):
			self.elegido = None
			self.EndModal(wx.ID_NO)
			return
		candidato = self.candidatos[indice]
		problema = self._validar(candidato) if self._validar else None
		if problema:
			comunes.error(self, problema, self.GetTitle())
			self.lista.SetFocus()
			return
		self.elegido = candidato
		self.EndModal(wx.ID_OK)

	@property
	def para_tienda(self) -> bool:
		return self.casilla_tienda.IsShown() and self.casilla_tienda.GetValue()


def elegir_precio(
	padre: wx.Window | None,
	candidatos: Sequence[CandidatoPrecio],
	texto: str,
	validar: Callable[[CandidatoPrecio], str | None] | None = None,
	permitir_tienda: bool = True,
) -> tuple[CandidatoPrecio, bool] | None:
	"""Devuelve (candidato, ¿también para la tienda?) o ``None`` (Cancelar o «Ninguno»)."""
	dialogo = DialogoElegirPrecio(padre, candidatos, texto, validar, permitir_tienda)
	try:
		if dialogo.ShowModal() != wx.ID_OK or dialogo.elegido is None:
			return None
		return dialogo.elegido, dialogo.para_tienda
	finally:
		dialogo.Destroy()


def elegir_variante(padre: wx.Window | None, variantes: Sequence[Variante]) -> Variante | None:
	"""Lista de variantes (nombre y precio). Devuelve la elegida o ``None``."""
	opciones = [v.texto for v in variantes]
	dialogo = wx.SingleChoiceDialog(
		padre, _("Este producto tiene variantes con precios distintos. Elija la que quiere seguir:"), _("Elegir variante"), opciones
	)
	try:
		if dialogo.ShowModal() != wx.ID_OK:
			return None
		return variantes[dialogo.GetSelection()]
	finally:
		dialogo.Destroy()


def describir_resultado(resultado: Any) -> str:
	"""«Encontrado: nombre, desde 12,00 €, disponible (origen: JSON-LD).»"""
	from app.services.importes import formato_importe

	precio = formato_importe(resultado.precio, resultado.moneda) if resultado.precio is not None else _("sin precio")
	if resultado.desde and resultado.precio is not None:
		precio = _("desde {precio}").format(precio=precio)
	disponible = _("disponible") if resultado.disponible else _("agotado")
	return _("{nombre}, {precio}, {disponible}").format(nombre=resultado.nombre or _("sin nombre"), precio=precio, disponible=disponible)
