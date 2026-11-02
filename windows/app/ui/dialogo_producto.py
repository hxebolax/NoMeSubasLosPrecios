"""Diálogo «Añadir producto» y «Editar producto».

Accesibilidad: cada campo con su etiqueta creada JUSTO ANTES (el lector toma
de ella el nombre), aceleradores únicos, ayuda para Ctrl+H, «Aceptar» con
Intro y «Cancelar» con Escape, foco inicial en la dirección (o en el nombre
al editar). Un dato no válido se explica y el foco va a su campo.

El diálogo solo recoge datos (``datos()``); comprobar la página y guardar lo
hace la ventana principal, con espera cancelable.
"""

from __future__ import annotations

import builtins
import logging
from collections.abc import Callable
from typing import Any

import wx

from app.services.direcciones import es_url, extraer_primera_url, limpiar_url
from app.services.importes import analizar_importe, formato_numero
from app.services.repositorio import SIN_CATEGORIA, ErrorDatos
from app.ui import comunes
from app.ui.accesibilidad.dialogos import preparar_dialogo
from app.ui.accesibilidad.nombres import crear_campo

log = logging.getLogger(__name__)

NUEVA_CATEGORIA = "Nueva categoría…"


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


class DialogoProducto(wx.Dialog):
	"""Campos de un producto. ``producto`` = ``None`` para añadir."""

	def __init__(
		self,
		padre: wx.Window | None,
		nucleo: Any,
		producto: dict[str, Any] | None = None,
		url_inicial: str = "",
		valores: dict[str, Any] | None = None,
		al_elegir_precio: Callable[[], str | None] | None = None,
	) -> None:
		self.editando = producto is not None
		super().__init__(
			padre,
			title=_("Editar producto") if self.editando else _("Añadir producto"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._nucleo = nucleo
		self._producto = producto or {}
		self._categorias: list[dict[str, Any]] = []
		inicial = dict(self._producto)
		if valores:
			inicial.update(valores)

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		_e, self.campo_url = crear_campo(
			panel, _("&Dirección del producto:"), wx.TextCtrl, value=inicial.get("url") or url_inicial,
			ayuda=_("Dirección de la página del producto en la tienda. Obligatoria. "
				"Se limpian solos los parámetros de seguimiento."), sizer=sizer,
		)
		_e, self.campo_nombre = crear_campo(
			panel, _("&Nombre (opcional):"), wx.TextCtrl, value=inicial.get("nombre") or "",
			ayuda=_("Si lo deja vacío, se usa el nombre que aparece en la página."), sizer=sizer,
		)
		_e, self.lista_categoria = crear_campo(
			panel, _("&Categoría:"), wx.Choice,
			ayuda=_("Categoría del producto. Elija «Nueva categoría…» para crear una."), sizer=sizer,
		)
		self._rellenar_categorias(inicial.get("categoria_id"))
		self.lista_categoria.Bind(wx.EVT_CHOICE, self._al_elegir_categoria)
		grupos = [g for g, _n in nucleo.repositorio.grupos()]
		_e, self.campo_grupo = crear_campo(
			panel, _("&Grupo para comparar (opcional):"), wx.ComboBox, value=inicial.get("grupo") or "",
			choices=grupos, style=wx.CB_DROPDOWN,
			ayuda=_("Ponga el mismo nombre de grupo al mismo producto en varias tiendas para compararlas "
				"en la sección Comparar."), sizer=sizer,
		)
		objetivo = inicial.get("precio_objetivo")
		_e, self.campo_objetivo = crear_campo(
			panel, _("&Precio deseado en euros (opcional):"), wx.TextCtrl,
			value=formato_numero(objetivo) if objetivo is not None else "",
			ayuda=_("Se avisa cuando el precio sea igual o menor. Por ejemplo: 99,95. Vacío: sin precio deseado."),
			sizer=sizer,
		)
		_e, self.campo_alerta = crear_campo(
			panel, _("&Avisar solo de bajadas de al menos (%):"), wx.SpinCtrlDouble,
			min=0, max=100, inc=1, initial=float(inicial.get("alerta_porcentaje") or 0),
			ayuda=_("0 avisa de cualquier bajada. Con 5, solo de bajadas del 5 % o más."), sizer=sizer,
		)
		self.campo_alerta.SetDigits(1)
		self.casilla_disponible = wx.CheckBox(panel, label=_("A&visar si vuelve a estar disponible"))
		self.casilla_disponible.SetValue(bool(inicial.get("avisar_disponible", 1)))
		self.casilla_disponible.SetHelpText(_("Avisa cuando el producto pase de agotado a disponible."))
		sizer.Add(self.casilla_disponible, 0, wx.ALL, 5)
		_e, self.campo_selector = crear_campo(
			panel, _("&Selector CSS propio del precio (avanzado, opcional):"), wx.TextCtrl,
			value=inicial.get("selector_precio") or "",
			ayuda=_("Solo si la aplicación no encuentra bien el precio: selector CSS del elemento con el precio, "
				"por ejemplo «#precio» o «.price-current». Gana a todas las demás reglas."), sizer=sizer,
		)
		self._selector_elegido = (inicial.get("selector_precio") or "") if inicial.get("huella_selector") else None
		if self.editando and al_elegir_precio is not None:
			boton_elegir = wx.Button(panel, label=_("Elegir el p&recio en la página..."))
			boton_elegir.SetHelpText(_("Descarga la página, enseña todos los importes y guarda la posición del que elija."))
			boton_elegir.Bind(wx.EVT_BUTTON, lambda _evento: self._elegir_precio(al_elegir_precio))
			sizer.Add(boton_elegir, 0, wx.ALL, 5)
		_e, self.campo_notas = crear_campo(
			panel, _("N&otas:"), wx.TextCtrl, value=inicial.get("notas") or "", style=wx.TE_MULTILINE,
			size=self.FromDIP(wx.Size(-1, 70)), ayuda=_("Notas libres. También se buscan con Buscar."), sizer=sizer,
		)

		botones = wx.StdDialogButtonSizer()
		self.boton_aceptar = wx.Button(panel, wx.ID_OK, _("&Guardar") if self.editando else _("Comprobar y a&ñadir"))
		self.boton_aceptar.SetDefault()
		self.boton_aceptar.SetHelpText(
			_("Guarda los cambios.") if self.editando else _("Comprueba la página ahora y enseña lo encontrado antes de guardar.")
		)
		botones.AddButton(self.boton_aceptar)
		botones.AddButton(wx.Button(panel, wx.ID_CANCEL, _("&Cancelar")))
		botones.Realize()
		sizer.Add(botones, 0, wx.EXPAND | wx.ALL, 8)
		panel.SetSizer(sizer)
		marco = wx.BoxSizer(wx.VERTICAL)
		marco.Add(panel, 1, wx.EXPAND)
		self.SetSizerAndFit(marco)
		self.SetMinSize(self.FromDIP(wx.Size(520, -1)))
		self.boton_aceptar.Bind(wx.EVT_BUTTON, self._al_aceptar)
		preparar_dialogo(self, foco_inicial=self.campo_nombre if self.editando else self.campo_url)
		self.CentreOnParent()

	def _elegir_precio(self, al_elegir_precio: Callable[[], str | None]) -> None:
		selector = al_elegir_precio()
		if selector:
			self._selector_elegido = selector
			self.campo_selector.SetValue(selector)
			self.campo_selector.SetFocus()

	# ── Categorías ───────────────────────────────────────────────────────────

	def _rellenar_categorias(self, seleccionada: int | None) -> None:
		self._categorias = self._nucleo.repositorio.categorias()
		nombres = [SIN_CATEGORIA] + [c["nombre"] for c in self._categorias] + [NUEVA_CATEGORIA]
		self.lista_categoria.Set(nombres)
		indice = 0
		for posicion, categoria in enumerate(self._categorias, start=1):
			if categoria["id"] == seleccionada:
				indice = posicion
		self.lista_categoria.SetSelection(indice)

	def _al_elegir_categoria(self, evento: wx.CommandEvent) -> None:
		if self.lista_categoria.GetSelection() != self.lista_categoria.GetCount() - 1:
			evento.Skip()
			return
		nombre = comunes.pedir_texto(self, _("&Nombre de la categoría:"), _("Nueva categoría"))
		nuevo_id = None
		if nombre:
			try:
				nuevo_id = self._nucleo.repositorio.crear_categoria(nombre)
			except ErrorDatos as error:
				comunes.error(self, str(error), _("Nueva categoría"))
		self._rellenar_categorias(nuevo_id)
		self.lista_categoria.SetFocus()

	def categoria_id(self) -> int | None:
		indice = self.lista_categoria.GetSelection()
		if 1 <= indice <= len(self._categorias):
			return int(self._categorias[indice - 1]["id"])
		return None

	# ── Validación y datos ───────────────────────────────────────────────────

	def _senalar(self, control: wx.Window, texto: str) -> None:
		comunes.error(self, texto, self.GetTitle())
		control.SetFocus()
		if isinstance(control, wx.TextCtrl):
			control.SelectAll()

	def validar(self) -> bool:
		url = self.campo_url.GetValue().strip()
		if not url:
			self._senalar(self.campo_url, _("Escriba o pegue la dirección del producto."))
			return False
		candidata = url if es_url(url) else (extraer_primera_url(url) or "")
		if not es_url(candidata):
			self._senalar(self.campo_url, _("La dirección no parece válida. Debe ser como https://www.tienda.es/producto."))
			return False
		self.campo_url.SetValue(candidata)
		objetivo = self.campo_objetivo.GetValue().strip()
		if objetivo and analizar_importe(objetivo) is None:
			self._senalar(self.campo_objetivo, _("El precio deseado no es un importe válido. Escríbalo como 99,95."))
			return False
		return True

	def _al_aceptar(self, evento: wx.CommandEvent) -> None:
		if self.validar():
			evento.Skip()

	def datos(self) -> dict[str, Any]:
		"""Campos del producto tal como se guardan (``url`` ya limpia)."""
		objetivo = self.campo_objetivo.GetValue().strip()
		datos = {
			"url": limpiar_url(self.campo_url.GetValue().strip()),
			"nombre": self.campo_nombre.GetValue().strip(),
			"categoria_id": self.categoria_id(),
			"grupo": self.campo_grupo.GetValue().strip() or None,
			"precio_objetivo": analizar_importe(objetivo) if objetivo else None,
			"alerta_porcentaje": float(self.campo_alerta.GetValue()),
			"avisar_disponible": self.casilla_disponible.GetValue(),
			"selector_precio": self.campo_selector.GetValue().strip() or None,
			"notas": self.campo_notas.GetValue().strip() or None,
		}
		if self.campo_selector.GetValue().strip() != (self._selector_elegido or ""):
			# Selector escrito a mano: no tiene huella de «elegido en la página».
			datos["huella_selector"] = None
		return datos
