"""Gestionar tiendas: renombrar, selectores propios y notas, probar y borrar.

«Probar» descarga un producto de la tienda con los selectores escritos (sin
guardarlos todavía) y enseña lo que saca: nombre, precio, disponibilidad y de
dónde salió el precio. Así se comprueba un selector antes de quedárselo.
"""

from __future__ import annotations

import builtins
import logging
from typing import Any

import wx

from app.services.errores import ErrorComprobacion
from app.services.importes import formato_importe
from app.services.repositorio import ErrorDatos
from app.ui import comunes, espera
from app.ui.accesibilidad.dialogos import preparar_dialogo
from app.ui.accesibilidad.lista import ListaAccesible
from app.ui.accesibilidad.nombres import crear_campo

log = logging.getLogger(__name__)


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


def texto_resultado(resultado: Any) -> str:
	"""«Encontrado: nombre, precio, disponible (origen: JSON-LD).»"""
	disponible = _("disponible") if resultado.disponible else _("agotado")
	precio = formato_importe(resultado.precio, resultado.moneda) if resultado.precio is not None else _("sin precio")
	origen = f" ({_('origen del precio')}: {resultado.origen_precio})" if resultado.origen_precio else ""
	return _("Encontrado: {nombre}, {precio}, {disponible}{origen}.").format(
		nombre=resultado.nombre or _("sin nombre"), precio=precio, disponible=disponible, origen=origen
	)


class DialogoEditarTienda(wx.Dialog):
	"""Nombre, selectores propios y notas de una tienda, con «Probar»."""

	def __init__(self, padre: wx.Window | None, nucleo: Any, tienda: dict[str, Any]) -> None:
		super().__init__(padre, title=_("Tienda {nombre}").format(nombre=tienda["nombre"]),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._nucleo = nucleo
		self.tienda = tienda
		sizer = wx.BoxSizer(wx.VERTICAL)
		_e, self.campo_nombre = crear_campo(self, _("&Nombre:"), wx.TextCtrl, value=tienda["nombre"],
			ayuda=_("Nombre visible de la tienda."), sizer=sizer)
		_e, self.campo_precio = crear_campo(self, _("Selector CSS del &precio:"), wx.TextCtrl,
			value=tienda.get("selector_precio") or "",
			ayuda=_("Selector propio del precio para todos los productos de esta tienda. Vacío: reglas de la aplicación."),
			sizer=sizer)
		_e, self.campo_titulo = crear_campo(self, _("Selector CSS del &título:"), wx.TextCtrl,
			value=tienda.get("selector_titulo") or "", ayuda=_("Selector propio del nombre del producto."), sizer=sizer)
		_e, self.campo_disponible = crear_campo(self, _("Selector CSS de la &disponibilidad:"), wx.TextCtrl,
			value=tienda.get("selector_disponible") or "",
			ayuda=_("Elemento que dice si hay existencias: si su texto dice «agotado», «no disponible» o «sin stock», "
				"se toma como agotado."), sizer=sizer)
		self._modos = ("auto", "directo", "navegador")
		_e, self.lista_modo = crear_campo(self, _("&Modo de descarga:"), wx.Choice,
			choices=[_("Automático"), _("Descarga directa"), _("Navegador integrado")],
			ayuda=_("Automático: descarga normal y, si la tienda bloquea o monta la página con JavaScript, el navegador "
				"integrado. Navegador integrado: siempre con el motor Edge (más lento)."), sizer=sizer)
		modo = tienda.get("modo_descarga") or "auto"
		self.lista_modo.SetSelection(self._modos.index(modo) if modo in self._modos else 0)
		_e, self.campo_notas = crear_campo(self, _("N&otas:"), wx.TextCtrl, value=tienda.get("notas") or "",
			style=wx.TE_MULTILINE, size=self.FromDIP(wx.Size(-1, 60)), ayuda=_("Notas libres."), sizer=sizer)
		_e, self.campo_resultado = crear_campo(self, _("&Resultado de la prueba:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY, size=self.FromDIP(wx.Size(-1, 60)),
			ayuda=_("Lo que se sacó del producto de prueba con estos selectores."), sizer=sizer)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		probar = wx.Button(self, label=_("Pro&bar con un producto"))
		probar.SetHelpText(_("Descarga un producto de esta tienda con los selectores escritos y enseña lo que saca."))
		probar.Bind(wx.EVT_BUTTON, lambda _evento: self.probar())
		fila.Add(probar, 0, wx.ALL, 4)
		abrir = wx.Button(self, label=_("Abr&ir la tienda en la app"))
		abrir.SetHelpText(_("Muestra un producto de la tienda en el navegador integrado para resolver una verificación "
			"o aceptar las cookies. Escape la cierra; las cookies se quedan."))
		abrir.Bind(wx.EVT_BUTTON, lambda _evento: self.abrir_en_app())
		fila.Add(abrir, 0, wx.ALL, 4)
		fila.AddStretchSpacer()
		aceptar = wx.Button(self, wx.ID_OK, _("&Aceptar"))
		aceptar.SetDefault()
		aceptar.Bind(wx.EVT_BUTTON, self._al_aceptar)
		fila.Add(aceptar, 0, wx.ALL, 4)
		fila.Add(wx.Button(self, wx.ID_CANCEL, _("&Cancelar")), 0, wx.ALL, 4)
		sizer.Add(fila, 0, wx.EXPAND | wx.ALL, 4)
		self.SetSizerAndFit(sizer)
		self.SetMinSize(self.FromDIP(wx.Size(520, -1)))
		preparar_dialogo(self, foco_inicial=self.campo_nombre)
		self.CentreOnParent()

	def valores(self) -> dict[str, Any]:
		return {
			"nombre": self.campo_nombre.GetValue().strip(),
			"selector_precio": self.campo_precio.GetValue().strip() or None,
			"selector_titulo": self.campo_titulo.GetValue().strip() or None,
			"selector_disponible": self.campo_disponible.GetValue().strip() or None,
			"notas": self.campo_notas.GetValue().strip() or None,
			"modo_descarga": self._modos[max(0, self.lista_modo.GetSelection())],
		}

	def _al_aceptar(self, evento: wx.CommandEvent) -> None:
		if not self.campo_nombre.GetValue().strip():
			comunes.error(self, _("El nombre de la tienda no puede quedar vacío."), self.GetTitle())
			self.campo_nombre.SetFocus()
			return
		evento.Skip()

	def abrir_en_app(self) -> None:
		productos = [p for p in self._nucleo.repositorio.productos() if p.get("tienda_id") == self.tienda["id"]]
		url = productos[0]["url"] if productos else f"https://www.{self.tienda['dominio']}/"
		abrir = getattr(wx.GetApp().GetTopWindow(), "abrir_tienda_en_app", None)
		if abrir is not None:
			abrir(url)

	def probar(self) -> None:
		productos = [p for p in self._nucleo.repositorio.productos() if p.get("tienda_id") == self.tienda["id"]]
		if not productos:
			comunes.mensaje(self, _("Esta tienda no tiene productos con los que probar."), self.GetTitle())
			return
		producto = productos[0]
		if len(productos) > 1:
			opciones = [p.get("nombre") or p["url"] for p in productos]
			dialogo = wx.SingleChoiceDialog(self, _("Elija el producto de prueba:"), _("Probar selectores"), opciones)
			try:
				if dialogo.ShowModal() != wx.ID_OK:
					return
				producto = productos[dialogo.GetSelection()]
			finally:
				dialogo.Destroy()
		valores = self.valores()

		def trabajo(cancelado):
			return self._nucleo.comprobador.analizar(
				producto["url"], producto.get("dominio") or self.tienda["dominio"], nombre_tienda=valores["nombre"],
				selector_producto=producto.get("selector_precio"), selector_tienda=valores["selector_precio"],
				selector_titulo=valores["selector_titulo"], selector_disponible=valores["selector_disponible"],
				modo_descarga=valores["modo_descarga"], variante=producto.get("variante"), cancelado=cancelado,
			)

		try:
			resultado = espera.ejecutar(self, _("Probar selectores"), _("Descargando {nombre}...").format(
				nombre=producto.get("nombre") or producto["url"]), trabajo)
		except espera.Cancelado:
			return
		except ErrorComprobacion as error:
			texto = error.mensaje
		except Exception as error:  # noqa: BLE001 - se informa al usuario y queda en el registro
			log.exception("Fallo al probar los selectores")
			texto = _("No se pudo probar: {error}").format(error=error)
		else:
			texto = texto_resultado(resultado)
		self.campo_resultado.SetValue(texto)
		self.campo_resultado.SetFocus()
		self.campo_resultado.SetInsertionPoint(0)
		comunes.anunciar(texto)


class DialogoTiendas(wx.Dialog):
	def __init__(self, padre: wx.Window | None, nucleo: Any, leer_preferencias: Any = None) -> None:
		super().__init__(padre, title=_("Gestionar tiendas"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._nucleo = nucleo
		self.cambiado = False
		self._tiendas: list[dict[str, Any]] = []
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(self, label=_("&Tiendas:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.lista = ListaAccesible(
			self, _("Tiendas"),
			columnas=[(_("Nombre"), 180), (_("Dominio"), 180), (_("Productos"), 80), (_("Selectores propios"), 150)],
			leer_preferencias=leer_preferencias,
		)
		self.lista.SetMinSize(self.FromDIP(wx.Size(620, 260)))
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.editar())
		self.lista.Bind(wx.EVT_KEY_DOWN, self._al_tecla)
		sizer.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		for etiqueta, ayuda, accion in (
			(_("&Editar y probar..."), _("Nombre, selectores propios y notas de la tienda; permite probarlos (también con Intro)."), self.editar),
			(_("&Renombrar..."), _("Cambia el nombre de la tienda."), self.renombrar),
			(_("&Borrar"), _("Borra la tienda si no tiene productos (también con Suprimir)."), self.borrar),
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

	def recargar(self) -> None:
		self._tiendas = self._nucleo.repositorio.tiendas()
		filas = []
		for t in self._tiendas:
			propios = [n for n, c in ((_("precio"), "selector_precio"), (_("título"), "selector_titulo"),
				(_("disponibilidad"), "selector_disponible")) if t.get(c)]
			filas.append([t["nombre"], t["dominio"], str(t["productos"]), ", ".join(propios) or _("ninguno")])
		self.lista.reemplazar_filas(filas)

	def actual(self) -> dict[str, Any] | None:
		fila = self.lista.fila_actual()
		return self._tiendas[fila] if 0 <= fila < len(self._tiendas) else None

	def _al_tecla(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and not evento.HasAnyModifiers():
			self.borrar()
			return
		evento.Skip()

	def editar(self) -> None:
		tienda = self.actual()
		if tienda is None:
			return
		dialogo = DialogoEditarTienda(self, self._nucleo, tienda)
		try:
			if dialogo.ShowModal() == wx.ID_OK:
				try:
					self._nucleo.repositorio.actualizar_tienda(tienda["id"], **dialogo.valores())
				except ErrorDatos as error:
					comunes.error(self, str(error), _("Tienda"))
				self.cambiado = True
				self.recargar()
		finally:
			dialogo.Destroy()
		self.lista.SetFocus()

	def renombrar(self) -> None:
		tienda = self.actual()
		if tienda is None:
			return
		nombre = comunes.pedir_texto(self, _("&Nuevo nombre:"), _("Renombrar tienda"), tienda["nombre"])
		if nombre and nombre.strip() != tienda["nombre"]:
			try:
				self._nucleo.repositorio.actualizar_tienda(tienda["id"], nombre=nombre.strip())
			except ErrorDatos as error:
				comunes.error(self, str(error), _("Renombrar tienda"))
				return
			self.cambiado = True
			self.recargar()
		self.lista.SetFocus()

	def borrar(self) -> None:
		tienda = self.actual()
		if tienda is None:
			return
		if tienda["productos"]:
			comunes.mensaje(self, _("La tienda «{nombre}» tiene {n} productos: solo se puede borrar una tienda sin productos.").format(
				nombre=tienda["nombre"], n=tienda["productos"]), _("Borrar tienda"), wx.ICON_WARNING)
			return
		if comunes.preguntar(self, _("¿Borrar la tienda «{nombre}»?").format(nombre=tienda["nombre"]), _("Borrar tienda"), peligroso=True):
			try:
				self._nucleo.repositorio.borrar_tienda(tienda["id"])
			except ErrorDatos as error:
				comunes.error(self, str(error), _("Borrar tienda"))
				return
			self.cambiado = True
			self.recargar()
			comunes.anunciar(_("Tienda borrada"))
		self.lista.SetFocus()


