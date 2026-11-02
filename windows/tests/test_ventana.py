"""Ventana principal con wx real, SIN mostrarla: menús, atajos, secciones, lista y acciones."""

from __future__ import annotations

import threading

import pytest
import wx

from app.core.configuracion import Configuracion
from app.core.version import NOMBRE_APLICACION
from app.services import intercambio
from app.services.comprobador import AvisoGuardado, Resumen
from app.services.nucleo import Nucleo
from app.ui import comunes
from app.ui import ventana_principal as vp

from .conftest import PRUEBAS_COMUNES, procesar_eventos

MENUS_ESPERADOS = ["&Archivo", "&Producto", "&Ver", "&Herramientas", "Ay&uda"]
ATAJOS_ESPERADOS = {
	"anadir": (wx.ACCEL_CTRL, ord("N")),
	"importar": (wx.ACCEL_CTRL, ord("I")),
	"exportar": (wx.ACCEL_CTRL, ord("E")),
	"editar": (wx.ACCEL_NORMAL, wx.WXK_F2),
	"comprobar_todos": (wx.ACCEL_NORMAL, wx.WXK_F5),
	"buscar": (wx.ACCEL_CTRL, ord("F")),
	"manual": (wx.ACCEL_NORMAL, wx.WXK_F1),
	"teclas": (wx.ACCEL_CTRL, wx.WXK_F1),
	"ayuda_contextual": (wx.ACCEL_CTRL, ord("H")),
	**{f"seccion_{n}": (wx.ACCEL_CTRL, ord(str(n + 1))) for n in range(7)},
}
PALABRAS_EN_INGLES = {"file", "edit", "view", "tools", "help", "open", "exit", "quit", "about", "options", "refresh", "settings"}


@pytest.fixture
def ventana(app_wx, data_temporal, monkeypatch):
	monkeypatch.setattr(vp.IconoBandeja, "mostrar", lambda self, texto=None: True)
	config = Configuracion()
	nucleo = Nucleo(config)
	intercambio.importar(nucleo.bd, intercambio.leer_archivo(PRUEBAS_COMUNES / "exportacion-ejemplo.json"))
	marco = vp.VentanaPrincipal(config, nucleo)
	yield marco
	if marco:
		marco.salir()
		procesar_eventos(lambda: not marco, 3)


def _elementos(menu: wx.Menu):
	for item in menu.GetMenuItems():
		if not item.IsSeparator():
			yield item


def test_arranca_sin_mostrarse_con_barra_de_estado(ventana):
	assert ventana.GetTitle() == NOMBRE_APLICACION
	assert not ventana.IsShown()
	assert "Última comprobación" in ventana.GetStatusBar().GetStatusText()


def test_menus_en_espanol_con_teclas_de_acceso(ventana):
	barra = ventana.GetMenuBar()
	assert [barra.GetMenuLabel(i) for i in range(barra.GetMenuCount())] == MENUS_ESPERADOS
	for i in range(barra.GetMenuCount()):
		letras = []
		for item in _elementos(barra.GetMenu(i)):
			etiqueta = item.GetItemLabel()
			assert "&" in etiqueta, f"«{etiqueta}» no tiene tecla de acceso"
			letras.append(etiqueta[etiqueta.index("&") + 1].lower())
			palabras = {p.lower().strip(".&()") for p in item.GetItemLabelText().split()}
			assert not palabras & PALABRAS_EN_INGLES, f"«{etiqueta}» parece estar en inglés"
			assert item.GetHelp(), f"«{etiqueta}» no tiene texto de ayuda"
		assert len(letras) == len(set(letras)), f"teclas de acceso repetidas en {barra.GetMenuLabel(i)}: {letras}"


def test_atajos_de_teclado(ventana):
	for nombre, (modificadores, tecla) in ATAJOS_ESPERADOS.items():
		atajo = ventana.elementos_menu[nombre].GetAccel()
		assert atajo is not None, f"{nombre} no tiene atajo"
		assert (atajo.GetFlags(), atajo.GetKeyCode()) == (modificadores, tecla), nombre
	for item in ventana.elementos_menu.values():
		atajo = item.GetAccel()
		if atajo is not None and atajo.GetFlags() == wx.ACCEL_NORMAL:
			# Escape, Suprimir e Intro sin modificadores son de los controles (búsqueda, lista).
			assert atajo.GetKeyCode() not in (wx.WXK_ESCAPE, wx.WXK_DELETE, wx.WXK_RETURN), item.GetItemLabel()


def test_etiquetas_creadas_justo_antes_de_cada_control(ventana):
	hijos = list(ventana.panel.GetChildren())
	for control, etiqueta in (
		(ventana.lista_secciones, "&Secciones:"),
		(ventana.campo_buscar, "&Buscar:"),
		(ventana.lista_orden, "&Orden:"),
		(ventana.lista, "Pro&ductos:"),
		(ventana.lista_avisos, "Avisos guar&dados:"),
	):
		anterior = hijos[hijos.index(control) - 1]
		assert isinstance(anterior, wx.StaticText) and anterior.GetLabel() == etiqueta
		assert control.GetHelpText(), "Ctrl+H necesita la ayuda del control"
	assert [ventana.lista.GetColumn(i).GetText() for i in range(ventana.lista.GetColumnCount())] == [
		"Estado", "Nombre", "Precio", "Cambio", "Tienda", "Categoría", "Precio deseado", "Última comprobación"]


def test_lista_de_productos_se_lee_con_el_estado_primero(ventana):
	ventana.ir_a_seccion(0)
	assert ventana.lista.numero_filas() == 3
	textos = {ventana.lista.texto_celda(f, 1): ventana.lista.valores_fila(f) for f in range(3)}
	robot = textos["Robot Aspirador Ejemplo R5"]
	assert robot[2] == "349,90 €" and robot[3] == "bajó 19,10 € (5,2 %)" and robot[4] == "Amazon"
	assert textos["Consola Ejemplo Pro"][0] == "Agotado"
	assert ventana.lista.GetFocusedItem() >= 0, "siempre hay un elemento enfocado"


def test_secciones_y_grupos(ventana):
	ventana.ir_a_seccion(vp.vistas.CATEGORIAS)
	assert ventana.lista_grupos.IsShown()
	assert [ventana.lista_grupos.GetString(i) for i in range(ventana.lista_grupos.GetCount())] == [
		"Electrónica, 1 producto", "Hogar, 2 productos", "Sin categoría, 0 productos"]
	assert ventana.lista.numero_filas() == 1
	ventana.ir_a_seccion(vp.vistas.COMPARAR)
	assert ventana.lista.GetColumn(vp.COLUMNA_CAMBIO).GetText() == "Diferencia"
	assert [ventana.lista.texto_celda(f, vp.COLUMNA_CAMBIO) for f in range(2)] == ["el más barato", "9,10 € más (2,6 %)"]
	ventana.ir_a_seccion(vp.vistas.FAVORITOS)
	assert not ventana.lista_grupos.IsShown() and ventana.lista.numero_filas() == 1
	ventana.ir_a_seccion(vp.vistas.AVISOS)
	assert ventana.lista_avisos.IsShown() and not ventana.lista.IsShown()
	assert ventana.lista_avisos.valores_fila(0)[0] == "Sin leer", "los no leídos primero"
	ventana._marcar_todos_leidos()
	assert ventana.lista_avisos.valores_fila(0)[0] == "Leído"


def test_busqueda_filtros_y_orden(ventana):
	ventana.ir_a_seccion(0)
	ventana.campo_buscar.ChangeValue("black friday")
	ventana.refrescar_lista()
	assert ventana.lista.numero_filas() == 1, "busca también en las notas"
	ventana.campo_buscar.ChangeValue("")
	ventana.cambiar_filtro("solo_agotados", True)
	assert ventana.lista.numero_filas() == 1
	ventana.cambiar_filtro("solo_agotados", False)
	ventana.cambiar_orden("precio")
	assert ventana.lista.texto_celda(0, 2) == "349,90 €"
	assert ventana.elementos_orden["precio"].IsChecked()


def test_acciones_de_producto(ventana, monkeypatch):
	ventana.ir_a_seccion(0)
	copiado = []
	monkeypatch.setattr(comunes, "copiar_texto", lambda texto: copiado.append(texto) or True)
	monkeypatch.setattr(comunes, "preguntar", lambda *a, **k: True)
	ventana.lista.enfocar_fila(0)
	producto = ventana.producto_actual()
	ventana._al_copiar_enlace(None)
	assert copiado == [producto["url"]]
	ventana._al_favorito(None)
	assert ventana.nucleo.repositorio.producto(producto["id"])["favorito"] != producto["favorito"]
	ventana._al_pausa(None)
	assert vp.vistas.texto_estado(ventana.nucleo.repositorio.producto(producto["id"])) == "En pausa"
	ventana._actualizar_menus_producto()
	assert ventana.elementos_menu["pausa"].GetItemLabelText().startswith("Reanudar")
	menu = ventana.menu_producto()
	etiquetas = [i.GetItemLabelText() for i in menu.GetMenuItems() if not i.IsSeparator()]
	menu.Destroy()
	assert "Reanudar la comprobación" in etiquetas and "Ver detalles" in etiquetas
	ventana._al_eliminar(None)
	assert ventana.nucleo.repositorio.producto(producto["id"]) is None
	assert ventana.lista.numero_filas() == 2 and ventana.lista.GetFocusedItem() >= 0


def test_comprobacion_en_segundo_plano_y_notificaciones(ventana, monkeypatch):
	notificadas = []
	monkeypatch.setattr(ventana.notificador, "mostrar", lambda titulo, mensaje, pid=None, error=False: notificadas.append(titulo) or True)
	monkeypatch.setattr(vp, "sonar", lambda cambios=True: None)
	hilos = []

	def comprobar(ids=None, cancelado=None, al_progresar=None, incluir_pausados=False):
		hilos.append(threading.current_thread() is threading.main_thread())
		if al_progresar:
			al_progresar(1, 5, "x")
		avisos = [AvisoGuardado(i, 1, "bajada", f"Aviso {i}", "m") for i in range(5)]
		return Resumen(total=5, comprobados=5, correctos=5, cambios_precio=5, avisos=avisos, fecha="2026-11-02T20:00:00Z")

	monkeypatch.setattr(ventana.nucleo.comprobador, "comprobar", comprobar)
	assert ventana.comprobar()
	assert not ventana.comprobar(), "una sola comprobación a la vez"
	assert procesar_eventos(lambda: ventana._comprobacion is None, 5)
	assert hilos == [False], "la red va en un hilo"
	assert notificadas == ["Aviso 0", "Aviso 1", "Aviso 2", NOMBRE_APLICACION], "3 individuales y un resumen"
	assert "Comprobados 5 de 5" in ventana.GetStatusBar().GetStatusText()
	assert not ventana.nucleo.toca_comprobar()


def test_cerrar_minimiza_a_la_bandeja_y_salir_cierra(app_wx, data_temporal, monkeypatch):
	monkeypatch.setattr(vp.IconoBandeja, "mostrar", lambda self, texto=None: True)
	config = Configuracion()
	marco = vp.VentanaPrincipal(config, Nucleo(config))
	ocultada = []
	monkeypatch.setattr(marco, "Hide", lambda: ocultada.append(True) or True)
	marco.Close()
	procesar_eventos(segundos=0.2)
	assert marco and ocultada == [True], "minimizar_a_bandeja está activado por defecto"
	marco.salir()
	assert procesar_eventos(lambda: not marco)
	assert (data_temporal / "config" / "settings.json").is_file()


def test_ayuda_contextual_sin_ayuda(ventana, monkeypatch):
	mensajes = []
	monkeypatch.setattr(comunes, "mensaje", lambda padre, texto, *a, **k: mensajes.append(texto))
	monkeypatch.setattr(wx.Window, "FindFocus", staticmethod(lambda: None))
	ventana._al_ayuda_contextual(None)
	assert mensajes and "F1" in mensajes[0]
