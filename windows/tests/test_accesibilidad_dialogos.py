"""Recorrido de accesibilidad de todos los diálogos: lo que oiría el lector al tabular.

Cada control que recibe el foco con el teclado se enfoca de verdad y se lee su
nombre MSAA desde la ventana que Windows dice que tiene el foco (en los
controles compuestos, su campo interno). Así se detecta un campo que NVDA lee
vacío, como el del porcentaje de «Añadir producto» en la 1.0.0. También se
comprueba que no haya dos botones con el mismo nombre en una ventana.

Una prueba MSAA correcta no sustituye a probar con NVDA o JAWS: es una red
contra regresiones.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from ctypes import POINTER, byref, wintypes

import pytest
import wx

from app.core.configuracion import Configuracion
from app.services import intercambio
from app.services.extractor import CandidatoPrecio
from app.services.nucleo import Nucleo
from app.ui.accesibilidad import dialogos
from app.ui.dialogo_categorias import DialogoCategorias
from app.ui.dialogo_detalles import DialogoDetalles
from app.ui.dialogo_elegir import DialogoElegirPrecio
from app.ui.dialogo_importar import DialogoImportar
from app.ui.dialogo_preferencias import DialogoPreferencias
from app.ui.dialogo_producto import DialogoProducto
from app.ui.dialogo_tiendas import DialogoEditarTienda, DialogoTiendas

from . import msaa
from .conftest import PRUEBAS_COMUNES, procesar_eventos

_ROL_PESTANAS = 0x3C
_ESTADO_SELECCIONADO = 0x2
_user32 = ctypes.windll.user32
_user32.GetFocus.restype = wintypes.HWND


def _nombre_del_foco() -> tuple[str, int]:
	"""(nombre, rol) MSAA de la ventana que tiene el foco del teclado."""
	hwnd = _user32.GetFocus()
	assert hwnd, "ninguna ventana tiene el foco"
	puntero = POINTER(msaa._IAccessible)()
	msaa._oleacc.AccessibleObjectFromWindow(
		wintypes.HWND(hwnd), wintypes.DWORD(msaa._OBJID_CLIENT & 0xFFFFFFFF), byref(msaa._IAccessible._iid_), byref(puntero)
	)
	rol = puntero.accRole(0)
	hijo = 0
	if rol == _ROL_PESTANAS:
		# En unas pestañas, el lector lee la pestaña que tiene el foco (un hijo)
		try:
			foco = puntero.accFocus
			hijo = foco if isinstance(foco, int) else 0
		except Exception:  # noqa: BLE001 - sin hijo con foco
			hijo = 0
		if not hijo:
			# Sin ventana en primer plano no hay hijo con foco: la pestaña seleccionada
			for indice in range(1, puntero.accChildCount + 1):
				try:
					if puntero.accState(indice) & _ESTADO_SELECCIONADO:
						hijo = indice
						break
				except Exception:  # noqa: BLE001 - hijo que no es una pestaña
					continue
	try:
		nombre = puntero.accName(hijo) or ""
	except Exception:  # noqa: BLE001 - control sin nombre implementado
		nombre = ""
	return nombre.strip(), rol


#: Controles genéricos en Windows: el foco cae en un campo interno que NVDA no
#: asocia a la etiqueta aunque MSAA dé un nombre puesto a mano (comprobado por
#: el usuario con NVDA en la 1.0.1). No deben usarse: campo de texto o SpinCtrl.
_COMPUESTOS_PROHIBIDOS = (wx.SpinCtrlDouble, wx.SearchCtrl)


def _enfocables(ventana: wx.Window) -> list[wx.Window]:
	"""Controles visibles que deberían alcanzarse con Tab."""
	salida = []
	for hijo in ventana.GetChildren():
		if not hijo.IsShownOnScreen() or not hijo.IsEnabled() or isinstance(hijo, wx.TopLevelWindow):
			continue
		if isinstance(hijo, _COMPUESTOS_PROHIBIDOS):
			salida.append(hijo)
		elif hijo.AcceptsFocusFromKeyboard() and not isinstance(hijo, (wx.Panel, wx.ScrolledWindow)):
			salida.append(hijo)
		else:
			salida.extend(_enfocables(hijo))
	return salida


def _compuesto_que_contiene(control: wx.Window | None) -> wx.Window | None:
	while control is not None and not isinstance(control, wx.TopLevelWindow):
		if isinstance(control, _COMPUESTOS_PROHIBIDOS):
			return control
		control = control.GetParent()
	return None


def _recorrer_con_tabulador(ventana: wx.TopLevelWindow) -> list[wx.Window]:
	"""Pulsa Tab (navegación de wx) desde el foco inicial hasta dar la vuelta."""
	if wx.Window.FindFocus() is None:
		primeros = _enfocables(ventana)
		if primeros:
			primeros[0].SetFocus()
	visitados: list[wx.Window] = []
	for _paso in range(120):
		procesar_eventos(segundos=0.03)
		foco = wx.Window.FindFocus()
		if foco is None or foco in visitados:
			break
		visitados.append(foco)
		foco.Navigate(wx.NavigationKeyEvent.IsForward)
	return visitados


def _botones(ventana: wx.Window) -> list[str]:
	salida = []
	for hijo in ventana.GetChildren():
		if isinstance(hijo, wx.Button) and hijo.IsShown():
			salida.append(hijo.GetLabel().replace("&", "").strip())
		elif not isinstance(hijo, wx.TopLevelWindow):
			salida.extend(_botones(hijo))
	return salida


def revisar(ventana: wx.TopLevelWindow) -> list[str]:
	"""Problemas de accesibilidad de una ventana ya creada (la muestra y la recorre)."""
	problemas = []
	ventana.Show()
	ventana.Raise()
	procesar_eventos(segundos=0.2)
	# 1. Lo que se oye al tabular: cada parada con nombre y fuera de controles compuestos
	recorrido = _recorrer_con_tabulador(ventana)
	for foco in recorrido:
		compuesto = _compuesto_que_contiene(foco)
		if compuesto is not None:
			problemas.append(f"{type(compuesto).__name__} «{compuesto.GetName()}»: NVDA no lee su etiqueta al tabular")
			continue
		foco.SetFocus()
		procesar_eventos(segundos=0.03)
		nombre, rol = _nombre_del_foco()
		if not nombre:
			problemas.append(f"{type(foco).__name__} «{foco.GetName()}» (rol {rol}) sin nombre para el lector")
	# 2. Todo control visible se alcanza con Tab
	alcanzados = set(recorrido) | {_compuesto_que_contiene(f) for f in recorrido}
	for control in _enfocables(ventana):
		if control not in alcanzados and not any(control.IsDescendant(f) or f.IsDescendant(control) for f in recorrido):
			problemas.append(f"{type(control).__name__} «{control.GetName()}» no se alcanza con Tabulador")
	for control in _enfocables(ventana):
		if isinstance(control, _COMPUESTOS_PROHIBIDOS) and control not in alcanzados:
			problemas.append(f"{type(control).__name__} «{control.GetName()}»: NVDA no lee su etiqueta al tabular")
	botones = _botones(ventana)
	repetidos = sorted({b for b in botones if botones.count(b) > 1})
	if repetidos:
		problemas.append(f"botones repetidos: {repetidos}")
	letras = _aceleradores(ventana)
	dobles = sorted({f"Alt+{letra.upper()}: {', '.join(e for l, e in letras if l == letra)}" for letra, _e in letras
		if sum(1 for otra, _x in letras if otra == letra) > 1})
	if dobles:
		problemas.append(f"accesos rápidos repetidos: {dobles}")
	return problemas


_CON_ACELERADOR = (wx.StaticText, wx.Button, wx.CheckBox, wx.RadioButton, wx.StaticBox)


def _aceleradores(ventana: wx.Window) -> list[tuple[str, str]]:
	"""(letra, etiqueta) de cada «&letra» visible en pantalla en esta ventana."""
	salida = []
	for hijo in ventana.GetChildren():
		if isinstance(hijo, wx.TopLevelWindow) or not hijo.IsShownOnScreen():
			continue
		if isinstance(hijo, _CON_ACELERADOR):
			etiqueta = hijo.GetLabel().replace("&&", "")
			posicion = etiqueta.find("&")
			if 0 <= posicion < len(etiqueta) - 1:
				salida.append((etiqueta[posicion + 1].lower(), etiqueta.replace("&", "")))
		salida.extend(_aceleradores(hijo))
	return salida


@pytest.fixture
def nucleo(app_wx, data_temporal):
	nucleo = Nucleo(Configuracion())
	intercambio.importar(nucleo.bd, intercambio.leer_archivo(PRUEBAS_COMUNES / "exportacion-ejemplo.json"))
	yield nucleo
	nucleo.cerrar()


def _producto(nucleo):
	return next(p for p in nucleo.repositorio.productos() if p["nombre"] == "Robot Aspirador Ejemplo R5")


DIALOGOS: dict[str, Callable] = {
	"añadir producto": lambda n: DialogoProducto(None, n, None, url_inicial="https://www.amazon.es/dp/B0EJEMPLO9"),
	"editar producto": lambda n: DialogoProducto(None, n, _producto(n), al_elegir_precio=lambda: "#precio"),
	"detalles": lambda n: DialogoDetalles(None, _producto(n), n.repositorio.historial(_producto(n)["id"]), {}),
	"categorías": lambda n: DialogoCategorias(None, n.repositorio),
	"tiendas": lambda n: DialogoTiendas(None, n),
	"editar tienda": lambda n: DialogoEditarTienda(None, n, n.repositorio.tienda_por_dominio("amazon.es")),
	"importar": lambda n: DialogoImportar(
		None, intercambio.analizar(n.bd, intercambio.leer_archivo(PRUEBAS_COMUNES / "exportacion-ejemplo.json")), "x.json"
	),
	"preferencias": lambda n: DialogoPreferencias(None, Configuracion()),
	"elegir precio": lambda n: DialogoElegirPrecio(None, [CandidatoPrecio(39.99, "39,99 €, junto al botón de compra")], "Elige:"),
	"confirmar añadir": lambda n: dialogos.DialogoMensaje(
		None, "Encontrado: Café, 12,00 €. ¿Guardar?", "Añadir producto", opciones=["&Guardar", "&Editar", "&Cancelar"]
	),
	"elegir sin cancelar propio": lambda n: dialogos.DialogoMensaje(
		None, "¿Qué hacer?", "Prueba", opciones=["&Abrir el producto"]
	),
}


def _actualizacion(nucleo, carpeta):
	from app.services import actualizador
	from app.ui.dialogo_actualizacion import DialogoActualizacion

	(carpeta / "NoMeSubasLosPrecios.exe").write_bytes(b"EXE")
	config = actualizador.Configuracion(version_actual="1.0.0", carpeta_app=carpeta, comando=[], permitir_desde_codigo=True)
	info = actualizador.InfoActualizacion(
		version="1.0.1", archivo="x.zip", url_zip="https://ejemplo.invalid/x.zip", sha256="0" * 64,
		tamano=10, fecha="2026-11-03", novedades="- Arreglo",
	)
	return DialogoActualizacion(None, config, info)


def _otros(nombre, nucleo, carpeta):
	from app.ui.dialogo_error import DialogoError
	from app.ui.dialogo_texto import DialogoTexto
	from app.ui.espera import DialogoEspera
	from app.ui.visor_ayuda import VisorAyuda

	return {
		"espera": lambda: DialogoEspera(None, "Añadir producto", "Comprobando la página...", lambda cancelado: cancelado.wait(5)),
		"error": lambda: DialogoError(None, "Algo falló", "Traceback...", None),
		"texto": lambda: DialogoTexto(None, "Lista de teclas", "&Teclas:", "F1: manual", copiable=True),
		"pedir texto": lambda: dialogos.DialogoTexto(None, "&Nombre de la categoría:", "Nueva categoría"),
		"manual en texto": lambda: VisorAyuda(None, "Manual", "# Manual\n\n## Uno\n\nTexto.", forzar_texto=True),
		"actualización": lambda: _actualizacion(nucleo, carpeta),
	}[nombre]()


@pytest.mark.parametrize("nombre", ["espera", "error", "texto", "pedir texto", "manual en texto", "actualización"])
def test_otros_dialogos_accesibles(nucleo, tmp_path, nombre):
	dialogo = _otros(nombre, nucleo, tmp_path)
	try:
		assert revisar(dialogo) == []
	finally:
		if nombre == "espera":
			dialogo.cancelado.set() if hasattr(dialogo, "cancelado") else None
		dialogo.Destroy()


@pytest.mark.parametrize("nombre", list(DIALOGOS))
def test_dialogo_accesible(nucleo, nombre):
	dialogo = DIALOGOS[nombre](nucleo)
	try:
		assert revisar(dialogo) == []
	finally:
		dialogo.Destroy()


def test_preferencias_todas_las_paginas(nucleo):
	dialogo = DialogoPreferencias(None, Configuracion())
	try:
		problemas = []
		for pagina in range(dialogo.libro.GetPageCount()):
			dialogo.libro.SetSelection(pagina)
			problemas += [f"{dialogo.libro.GetPageText(pagina)}: {p}" for p in revisar(dialogo)]
		assert problemas == []
	finally:
		dialogo.Destroy()


def test_ventana_principal_accesible(nucleo, monkeypatch):
	from app.ui import ventana_principal as vp

	monkeypatch.setattr(vp.IconoBandeja, "mostrar", lambda self, texto=None: True)
	ventana = vp.VentanaPrincipal(Configuracion(), nucleo)
	try:
		assert revisar(ventana) == []
	finally:
		ventana.salir()
		procesar_eventos(lambda: not ventana)


def test_elegir_con_cancelar_propio_devuelve_su_indice(app_wx):
	dialogo = dialogos.DialogoMensaje(None, "¿Guardar?", "Prueba", opciones=["&Guardar", "&Editar", "&Cancelar"])
	try:
		assert _botones(dialogo) == ["Guardar", "Editar", "Cancelar"]
		assert dialogo.ids_opciones[2] == wx.ID_CANCEL, "Escape elige la opción Cancelar"
	finally:
		dialogo.Destroy()


def test_el_recorrido_detecta_un_spinctrldouble(app_wx):
	"""El caso de la 1.0.1: con nombre MSAA puesto a mano, NVDA seguía sin leerlo al tabular."""
	from app.ui.accesibilidad.nombres import crear_campo

	dialogo = wx.Dialog(None, title="Prueba")
	panel = wx.Panel(dialogo)
	sizer = wx.BoxSizer(wx.VERTICAL)
	crear_campo(panel, "&Nombre:", wx.TextCtrl, sizer=sizer)
	crear_campo(panel, "&Avisar desde (%):", wx.SpinCtrlDouble, min=0, max=100, sizer=sizer)
	sizer.Add(wx.Button(panel, wx.ID_OK, "&Aceptar"))
	panel.SetSizer(sizer)
	try:
		problemas = revisar(dialogo)
		assert any("SpinCtrlDouble" in p and "NVDA no lee" in p for p in problemas), problemas
	finally:
		dialogo.Destroy()
