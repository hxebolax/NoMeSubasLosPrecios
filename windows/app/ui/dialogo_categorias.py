"""Gestionar categorías: añadir, renombrar, borrar, subir y bajar.

Lista con su etiqueta y un botón por acción (con tecla de acceso). Tras cada
acción el foco vuelve a la lista, a la categoría afectada, para que el lector
diga el resultado sin que el usuario tenga que buscarlo.
"""

from __future__ import annotations

import builtins
import logging
from typing import Any

import wx

from app.services.repositorio import ErrorDatos
from app.ui import comunes
from app.ui.accesibilidad.dialogos import preparar_dialogo
from app.ui.accesibilidad.lista import ListaAccesible

log = logging.getLogger(__name__)


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


class DialogoCategorias(wx.Dialog):
	def __init__(self, padre: wx.Window | None, repositorio: Any, leer_preferencias: Any = None) -> None:
		super().__init__(padre, title=_("Gestionar categorías"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.repositorio = repositorio
		self.cambiado = False
		self._categorias: list[dict[str, Any]] = []
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(self, label=_("&Categorías:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.lista = ListaAccesible(
			self, _("Categorías"), columnas=[(_("Nombre"), 260), (_("Productos"), 100)], leer_preferencias=leer_preferencias
		)
		self.lista.SetMinSize(self.FromDIP(wx.Size(420, 240)))
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.renombrar())
		self.lista.Bind(wx.EVT_KEY_DOWN, self._al_tecla)
		sizer.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		for etiqueta, ayuda, accion in (
			(_("&Añadir..."), _("Crea una categoría nueva."), self.anadir),
			(_("&Renombrar..."), _("Cambia el nombre de la categoría seleccionada (también con Intro)."), self.renombrar),
			(_("&Borrar..."), _("Borra la categoría; sus productos pasan a «Sin categoría» (también con Suprimir)."), self.borrar),
			(_("&Subir"), _("Sube la categoría en el orden."), lambda: self.mover(-1)),
			(_("Ba&jar"), _("Baja la categoría en el orden."), lambda: self.mover(1)),
		):
			boton = wx.Button(self, label=etiqueta)
			boton.SetHelpText(ayuda)
			boton.Bind(wx.EVT_BUTTON, lambda _evento, a=accion: a())
			fila.Add(boton, 0, wx.ALL, 4)
		fila.AddStretchSpacer()
		fila.Add(wx.Button(self, wx.ID_CANCEL, _("&Cerrar")), 0, wx.ALL, 4)
		sizer.Add(fila, 0, wx.EXPAND | wx.ALL, 4)
		self.SetSizerAndFit(sizer)
		preparar_dialogo(self, foco_inicial=self.lista)
		self.recargar()
		self.CentreOnParent()

	def recargar(self, seleccionar: int | None = None) -> None:
		fila_previa = self.lista.fila_actual()
		self._categorias = self.repositorio.categorias()
		filas = [[c["nombre"], str(c["productos"])] for c in self._categorias]
		self.lista.reemplazar_filas(filas)
		if seleccionar is not None:
			for indice, categoria in enumerate(self._categorias):
				if categoria["id"] == seleccionar:
					self.lista.enfocar_fila(indice)
		elif filas and fila_previa >= 0:
			self.lista.enfocar_fila(min(fila_previa, len(filas) - 1))

	def actual(self) -> dict[str, Any] | None:
		fila = self.lista.fila_actual()
		return self._categorias[fila] if 0 <= fila < len(self._categorias) else None

	def _al_tecla(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and not evento.HasAnyModifiers():
			self.borrar()
			return
		evento.Skip()

	def anadir(self) -> None:
		nombre = comunes.pedir_texto(self, _("&Nombre de la categoría:"), _("Añadir categoría"))
		if not nombre:
			self.lista.SetFocus()
			return
		try:
			nuevo = self.repositorio.crear_categoria(nombre)
		except ErrorDatos as error:
			comunes.error(self, str(error), _("Añadir categoría"))
			return
		self.cambiado = True
		self.recargar(nuevo)
		self.lista.SetFocus()

	def renombrar(self) -> None:
		categoria = self.actual()
		if categoria is None:
			return
		nombre = comunes.pedir_texto(self, _("&Nuevo nombre:"), _("Renombrar categoría"), categoria["nombre"])
		if nombre and nombre != categoria["nombre"]:
			try:
				self.repositorio.renombrar_categoria(categoria["id"], nombre)
			except ErrorDatos as error:
				comunes.error(self, str(error), _("Renombrar categoría"))
				return
			self.cambiado = True
			self.recargar(categoria["id"])
		self.lista.SetFocus()

	def borrar(self) -> None:
		categoria = self.actual()
		if categoria is None:
			return
		texto = _("¿Borrar la categoría «{nombre}»?").format(nombre=categoria["nombre"])
		if categoria["productos"]:
			texto += " " + _("Sus {n} productos pasarán a «Sin categoría».").format(n=categoria["productos"])
		if comunes.preguntar(self, texto, _("Borrar categoría"), peligroso=True):
			self.repositorio.borrar_categoria(categoria["id"])
			self.cambiado = True
			self.recargar()
			comunes.anunciar(_("Categoría borrada"))
		self.lista.SetFocus()

	def mover(self, desplazamiento: int) -> None:
		categoria = self.actual()
		if categoria is None:
			return
		if self.repositorio.mover_categoria(categoria["id"], desplazamiento):
			self.cambiado = True
			self.recargar(categoria["id"])
			posicion = self.lista.fila_actual() + 1
			comunes.anunciar(_("{nombre}, posición {n} de {total}").format(
				nombre=categoria["nombre"], n=posicion, total=len(self._categorias)))
		else:
			comunes.anunciar(_("Ya está la primera") if desplazamiento < 0 else _("Ya está la última"))
		self.lista.SetFocus()
