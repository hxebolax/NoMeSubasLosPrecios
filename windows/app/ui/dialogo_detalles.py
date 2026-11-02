"""Detalles de un producto: resumen hablado, datos, historial, gráfica y acciones.

Orden pensado para el lector de pantalla: el foco empieza en el resumen de
una línea («Ahora 129,99 €. Mínimo 119,00 € el 3 de octubre...»), después
vienen los datos (un campo de solo lectura que se recorre por líneas), la
lista del historial (fecha, precio, cambio, disponibilidad) y los botones de
acción. La gráfica es decorativa y no recibe el foco.

Las acciones las ejecuta la ventana principal (``acciones``); el diálogo se
refresca con ``recargar`` cuando el producto cambia.
"""

from __future__ import annotations

import builtins
import logging
from collections.abc import Callable
from typing import Any

import wx

from app.services import vistas
from app.ui.accesibilidad.dialogos import preparar_dialogo
from app.ui.accesibilidad.lista import ListaAccesible
from app.ui.grafica import GraficaPrecios

log = logging.getLogger(__name__)


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


class DialogoDetalles(wx.Dialog):
	"""Diálogo modal con los detalles de un producto.

	:param acciones: nombre → función(producto_id) para «navegador», «comprobar»,
		«editar» y «copiar».
	"""

	def __init__(
		self,
		padre: wx.Window | None,
		producto: dict[str, Any],
		historial: list[dict[str, Any]],
		acciones: dict[str, Callable[[int], None]] | None = None,
		leer_preferencias: Callable[[], Any] | None = None,
	) -> None:
		super().__init__(
			padre,
			title=_("Detalles de {nombre}").format(nombre=producto.get("nombre") or _("producto")),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
		)
		self.producto = producto
		self._acciones = acciones or {}
		sizer = wx.BoxSizer(wx.VERTICAL)

		sizer.Add(wx.StaticText(self, label=_("&Resumen:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.campo_resumen = wx.TextCtrl(self, style=wx.TE_READONLY)
		self.campo_resumen.SetHelpText(_("Resumen del precio en una línea."))
		sizer.Add(self.campo_resumen, 0, wx.EXPAND | wx.ALL, 8)

		sizer.Add(wx.StaticText(self, label=_("&Datos del producto:")), 0, wx.LEFT | wx.RIGHT, 8)
		self.campo_datos = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=self.FromDIP(wx.Size(-1, 170)))
		self.campo_datos.SetHelpText(_("Todos los datos del producto, uno por línea. Recórralos con las flechas."))
		sizer.Add(self.campo_datos, 1, wx.EXPAND | wx.ALL, 8)

		sizer.Add(wx.StaticText(self, label=_("&Historial de precios:")), 0, wx.LEFT | wx.RIGHT, 8)
		self.lista_historial = ListaAccesible(
			self,
			_("Historial de precios"),
			columnas=[(_("Fecha"), 190), (_("Precio"), 110), (_("Cambio"), 200), (_("Disponibilidad"), 110)],
			leer_preferencias=leer_preferencias,
		)
		self.lista_historial.SetMinSize(self.FromDIP(wx.Size(620, 150)))
		self.lista_historial.SetHelpText(_("Cada fila es un cambio de precio o de disponibilidad, del más nuevo al más viejo."))
		sizer.Add(self.lista_historial, 1, wx.EXPAND | wx.ALL, 8)

		self.grafica = GraficaPrecios(self, historial, producto.get("moneda") or "EUR")
		sizer.Add(self.grafica, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

		botones = wx.WrapSizer(wx.HORIZONTAL)
		self.botones: dict[str, wx.Button] = {}
		for nombre, etiqueta, ayuda in (
			("navegador", _("Abrir en el &navegador"), _("Abre la página del producto en su navegador.")),
			("comprobar", _("Comprobar &ahora"), _("Vuelve a leer el precio ahora mismo.")),
			("editar", _("&Editar..."), _("Cambia la dirección, el precio deseado, el selector propio...")),
			("elegir_precio", _("Elegir el &precio en la página..."),
				_("Descarga la página y enseña todos los importes para que elija el precio correcto.")),
			("variante", _("Elegir &variante..."), _("El producto tiene variantes con precios distintos: elija la que sigue.")),
			("abrir_tienda", _("Abrir la &tienda en la app"),
				_("Muestra la página en el navegador integrado para resolver una verificación o aceptar las cookies. Escape la cierra.")),
			("copiar", _("Copiar en&lace"), _("Copia la dirección del producto al portapapeles.")),
		):
			boton = wx.Button(self, label=etiqueta)
			boton.SetHelpText(ayuda)
			boton.Bind(wx.EVT_BUTTON, lambda _evento, n=nombre: self._accion(n))
			botones.Add(boton, 0, wx.ALL, 4)
			self.botones[nombre] = boton
		cerrar = wx.Button(self, wx.ID_CANCEL, _("&Cerrar"))
		botones.Add(cerrar, 0, wx.ALL, 4)
		sizer.Add(botones, 0, wx.EXPAND | wx.ALL, 4)
		self.SetSizer(sizer)
		self.SetSize(self.FromDIP(wx.Size(760, 720)))
		preparar_dialogo(self, foco_inicial=self.campo_resumen)
		self.recargar(producto, historial)
		self.CentreOnParent()

	def recargar(self, producto: dict[str, Any], historial: list[dict[str, Any]]) -> None:
		"""Vuelve a pintar todo con los datos actuales (tras comprobar o editar)."""
		self.producto = producto
		self.SetTitle(_("Detalles de {nombre}").format(nombre=producto.get("nombre") or _("producto")))
		self.campo_resumen.SetValue(vistas.resumen_hablado(producto))
		self.campo_datos.SetValue("\n".join(f"{etiqueta}: {valor}" for etiqueta, valor in vistas.lineas_detalles(producto, historial)))
		self.campo_datos.SetInsertionPoint(0)
		self.lista_historial.reemplazar_filas(vistas.filas_historial(historial, producto.get("moneda")))
		self.grafica.historial = list(historial)
		self.grafica.moneda = producto.get("moneda") or "EUR"
		self.grafica.Refresh()
		# «Elegir variante» solo con un precio «desde»; «Abrir la tienda» con más sentido si la tienda bloquea.
		self.botones["variante"].Show(bool(producto.get("desde") or producto.get("variante")))
		self.Layout()

	def _accion(self, nombre: str) -> None:
		funcion = self._acciones.get(nombre)
		if funcion is not None:
			funcion(int(self.producto["id"]))
