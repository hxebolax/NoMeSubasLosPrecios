"""Importar: resumen previo, modo (Combinar o Reemplazar) y ajustes.

El resumen («El archivo tiene 42 productos, 6 categorías y 9 tiendas. Se
añadirán 10 productos y se actualizarán 32.») está en un campo de solo
lectura que recibe el foco al abrir: el lector lo lee entero y se puede
releer. Al cambiar de modo, el resumen se actualiza.
"""

from __future__ import annotations

import builtins
from typing import Any

import wx

from app.services import intercambio
from app.ui.accesibilidad.dialogos import preparar_dialogo


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


class DialogoImportar(wx.Dialog):
	def __init__(self, padre: wx.Window | None, analisis: intercambio.Analisis, nombre_archivo: str) -> None:
		super().__init__(padre, title=_("Importar {archivo}").format(archivo=nombre_archivo), style=wx.DEFAULT_DIALOG_STYLE)
		self.analisis = analisis
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(self, label=_("Res&umen:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.campo_resumen = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=self.FromDIP(wx.Size(460, 80)))
		self.campo_resumen.SetHelpText(_("Lo que contiene el archivo y lo que pasará al importarlo."))
		sizer.Add(self.campo_resumen, 0, wx.EXPAND | wx.ALL, 8)
		self.modo = wx.RadioBox(
			self, label=_("Modo de importación"),
			choices=[_("Co&mbinar con lo que ya tengo"), _("&Reemplazar todo (se hace una copia de seguridad antes)")],
			majorDimension=1, style=wx.RA_SPECIFY_COLS,
		)
		self.modo.SetHelpText(_("Combinar añade lo nuevo y actualiza lo que ya existe. Reemplazar borra todo lo actual "
			"y carga el archivo; antes se guarda una copia de seguridad."))
		self.modo.Bind(wx.EVT_RADIOBOX, lambda _evento: self._actualizar())
		sizer.Add(self.modo, 0, wx.EXPAND | wx.ALL, 8)
		self.casilla_ajustes = wx.CheckBox(self, label=_("Importar también los a&justes del archivo"))
		self.casilla_ajustes.SetHelpText(_("Intervalo de comprobación, avisos y demás preferencias guardadas en el archivo."))
		self.casilla_ajustes.Enable(analisis.tiene_ajustes)
		sizer.Add(self.casilla_ajustes, 0, wx.ALL, 8)
		botones = wx.StdDialogButtonSizer()
		aceptar = wx.Button(self, wx.ID_OK, _("&Importar"))
		aceptar.SetDefault()
		botones.AddButton(aceptar)
		botones.AddButton(wx.Button(self, wx.ID_CANCEL, _("&Cancelar")))
		botones.Realize()
		sizer.Add(botones, 0, wx.EXPAND | wx.ALL, 8)
		self.SetSizerAndFit(sizer)
		self._actualizar()
		preparar_dialogo(self, foco_inicial=self.campo_resumen)
		self.CentreOnParent()

	def modo_elegido(self) -> str:
		return intercambio.REEMPLAZAR if self.modo.GetSelection() == 1 else intercambio.COMBINAR

	def importar_ajustes(self) -> bool:
		return self.casilla_ajustes.IsEnabled() and self.casilla_ajustes.GetValue()

	def _actualizar(self) -> None:
		texto = self.analisis.texto(self.modo_elegido())
		if self.analisis.tiene_ajustes:
			texto += " " + _("El archivo incluye ajustes.")
		self.campo_resumen.SetValue(texto)

	def resultado(self) -> dict[str, Any]:
		return {"modo": self.modo_elegido(), "ajustes": self.importar_ajustes()}
