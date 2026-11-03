"""Diálogos de la aplicación (se crean sin mostrarse; nunca ShowModal real)."""

from __future__ import annotations

import wx

from app.core.configuracion import Configuracion
from app.core.version import APP_VERSION, NOMBRE_APLICACION
from app.services import intercambio
from app.services.extractor import CandidatoPrecio, Resultado
from app.services.nucleo import Nucleo
from app.ui import comunes
from app.ui.acerca_de import texto_acerca_de
from app.ui.bandeja import IconoBandeja
from app.ui.dialogo_categorias import DialogoCategorias
from app.ui.dialogo_detalles import DialogoDetalles
from app.ui.dialogo_elegir import DialogoElegirPrecio, describir_resultado
from app.ui.dialogo_importar import DialogoImportar
from app.ui.dialogo_preferencias import PAGINAS, DialogoPreferencias
from app.ui.dialogo_producto import DialogoProducto
from app.ui.dialogo_tiendas import DialogoEditarTienda, DialogoTiendas
from app.ui.espera import DialogoEspera

from .conftest import PRUEBAS_COMUNES, procesar_eventos


def _botones(ventana: wx.Window) -> dict[int, str]:
	salida = {}
	for hijo in ventana.GetChildren():
		if isinstance(hijo, wx.Button):
			salida[hijo.GetId()] = hijo.GetLabel()
		elif isinstance(hijo, wx.Panel):
			salida.update(_botones(hijo))
	return salida


def _etiqueta_previa(control: wx.Window) -> str:
	hijos = list(control.GetParent().GetChildren())
	anterior = hijos[hijos.index(control) - 1]
	assert isinstance(anterior, wx.StaticText), f"{control} no tiene etiqueta justo antes"
	return anterior.GetLabel()


def _nucleo():
	nucleo = Nucleo(Configuracion())
	intercambio.importar(nucleo.bd, intercambio.leer_archivo(PRUEBAS_COMUNES / "exportacion-ejemplo.json"))
	return nucleo


def test_dialogo_producto_anadir(app_wx, data_temporal):
	nucleo = _nucleo()
	dialogo = DialogoProducto(None, nucleo, None, url_inicial="https://www.amazon.es/x/dp/B0EJEMPLO9?tag=a")
	try:
		assert _etiqueta_previa(dialogo.campo_url) == "&Dirección del producto:"
		assert _etiqueta_previa(dialogo.campo_objetivo).startswith("&Precio deseado")
		assert dialogo.lista_categoria.GetStrings()[0] == "Sin categoría"
		assert dialogo.lista_categoria.GetStrings()[-1] == "Nueva categoría…"
		botones = _botones(dialogo)
		assert botones[wx.ID_OK] == "Comprobar y a&ñadir" and botones[wx.ID_CANCEL] == "&Cancelar"
		dialogo.campo_objetivo.SetValue("1.299,95")
		assert dialogo.validar()
		datos = dialogo.datos()
		assert datos["url"] == "https://www.amazon.es/dp/B0EJEMPLO9" and datos["precio_objetivo"] == 1299.95
		dialogo.campo_url.SetValue("no es una dirección")
		errores = []
		import app.ui.dialogo_producto as modulo

		modulo.comunes.error = lambda padre, texto, titulo="": errores.append(texto)
		try:
			assert not dialogo.validar() and errores
		finally:
			modulo.comunes.error = comunes.error
	finally:
		dialogo.Destroy()
		nucleo.cerrar()


def test_dialogo_producto_editar_conserva_y_avisa_selector(app_wx, data_temporal):
	nucleo = _nucleo()
	producto = nucleo.repositorio.productos()[0]
	dialogo = DialogoProducto(None, nucleo, producto, al_elegir_precio=lambda: "#precio")
	try:
		assert dialogo.GetTitle() == "Editar producto" and _botones(dialogo)[wx.ID_OK] == "&Guardar"
		assert "Elegir el p&recio en la página..." in _botones(dialogo).values()
		dialogo.campo_selector.SetValue(".a-mano")
		assert dialogo.datos()["huella_selector"] is None, "un selector escrito a mano no tiene huella"
	finally:
		dialogo.Destroy()
		nucleo.cerrar()


def test_detalles_resumen_historial_y_botones(app_wx, data_temporal):
	nucleo = _nucleo()
	producto = next(p for p in nucleo.repositorio.productos() if p["nombre"] == "Robot Aspirador Ejemplo R5")
	dialogo = DialogoDetalles(None, producto, nucleo.repositorio.historial(producto["id"]), {})
	try:
		assert dialogo.campo_resumen.GetValue().startswith("Ahora 349,90 €. Mínimo 339,00 €")
		assert dialogo.lista_historial.numero_filas() == 4
		assert dialogo.lista_historial.valores_fila(0)[1] == "349,90 €", "el más nuevo primero"
		assert "Origen del precio" in dialogo.campo_datos.GetValue()
		assert not dialogo.grafica.AcceptsFocusFromKeyboard(), "la gráfica es decorativa"
		etiquetas = set(_botones(dialogo).values())
		assert {"Elegir el &precio en la página...", "Abrir la &tienda en la app", "&Cerrar"} <= etiquetas
	finally:
		dialogo.Destroy()
		nucleo.cerrar()


def test_gestionar_categorias_y_tiendas(app_wx, data_temporal, monkeypatch):
	nucleo = _nucleo()
	monkeypatch.setattr(comunes, "pedir_texto", lambda *a, **k: "Jardín")
	monkeypatch.setattr(comunes, "preguntar", lambda *a, **k: True)
	categorias = DialogoCategorias(None, nucleo.repositorio)
	tiendas = DialogoTiendas(None, nucleo)
	try:
		assert _etiqueta_previa(categorias.lista) == "Ca&tegorías:"
		categorias.anadir()
		assert categorias.lista.numero_filas() == 3 and categorias.cambiado
		categorias.lista.enfocar_fila(2)
		categorias.mover(-1)
		assert [c["nombre"] for c in nucleo.repositorio.categorias()][1] == "Jardín"
		categorias.borrar()
		assert tiendas.lista.numero_filas() == 2
		assert tiendas.lista.valores_fila(0)[:3] == ["Amazon", "amazon.es", "2"]
		editar = DialogoEditarTienda(None, nucleo, nucleo.repositorio.tienda_por_dominio("amazon.es"))
		try:
			assert _etiqueta_previa(editar.campo_precio) == "Selector CSS del &precio:"
			assert editar.valores()["modo_descarga"] == "auto"
		finally:
			editar.Destroy()
	finally:
		categorias.Destroy()
		tiendas.Destroy()
		nucleo.cerrar()


def test_dialogo_importar_resumen(app_wx, data_temporal):
	nucleo = Nucleo(Configuracion())
	try:
		analisis = intercambio.analizar(nucleo.bd, intercambio.leer_archivo(PRUEBAS_COMUNES / "exportacion-ejemplo.json"))
		dialogo = DialogoImportar(None, analisis, "ejemplo.json")
		try:
			assert "Se añadirán 3 productos" in dialogo.campo_resumen.GetValue()
			assert dialogo.casilla_ajustes.IsEnabled()
			dialogo.modo.SetSelection(1)
			dialogo._actualizar()
			assert "Se borrará todo" in dialogo.campo_resumen.GetValue()
			assert dialogo.resultado()["modo"] == intercambio.REEMPLAZAR
		finally:
			dialogo.Destroy()
	finally:
		nucleo.cerrar()


def test_preferencias_reales_y_notificacion_de_prueba(app_wx, data_temporal):
	config = Configuracion()
	pulsada = []
	dialogo = DialogoPreferencias(None, config, botones_extra=(("&Enviar una notificación de prueba", "ayuda", lambda: pulsada.append(1)),))
	try:
		assert dialogo.control_de("precios.intervalo_horas") is not None
		assert [dialogo.libro.GetPageText(i) for i in range(dialogo.libro.GetPageCount())] == [p.titulo for p in PAGINAS]
		for pagina in PAGINAS:
			letras = [o.etiqueta[o.etiqueta.index("&") + 1].lower() for o in pagina.opciones]
			assert len(letras) == len(set(letras)), pagina.titulo
			assert not set(letras) & {"r", "e", "a", "c", "p"}, f"acelerador repetido con un botón en {pagina.titulo}"
		boton = dialogo.botones_extra[0]
		evento = wx.CommandEvent(wx.wxEVT_BUTTON, boton.GetId())
		evento.SetEventObject(boton)
		boton.GetEventHandler().ProcessEvent(evento)
		assert pulsada == [1]
		dialogo.control_de("precios.avisar_agotado").SetValue(True)
		assert dialogo.aplicar()
		assert Configuracion().obtener("precios.avisar_agotado") is True
	finally:
		dialogo.Destroy()


def test_elegir_precio_lista_accesible(app_wx):
	candidatos = [CandidatoPrecio(39.99, "39,99 € — junto al botón de compra"), CandidatoPrecio(47.05, "47,05 € — tachado")]
	dialogo = DialogoElegirPrecio(None, candidatos, "Elige el correcto:")
	try:
		assert dialogo.lista.GetStrings() == ["39,99 € — junto al botón de compra", "47,05 € — tachado", "Ninguno es el precio"]
		assert dialogo.lista.GetSelection() == 0
		assert _botones(dialogo)[wx.ID_OK] == "&Usar este precio"
	finally:
		dialogo.Destroy()
	resultado = Resultado(precio=12.0, nombre="Café", disponible=True, desde=True)
	assert describir_resultado(resultado) == "Café, desde 12,00 €, disponible"


def test_espera_cancelable_entrega_en_el_hilo_principal(app_wx):
	dialogo = DialogoEspera(None, "Prueba", "Comprobando...", lambda cancelado: 42)
	try:
		assert dialogo.estado.GetValue() == "Comprobando..." and _botones(dialogo)[wx.ID_CANCEL] == "&Cancelar"
		dialogo.iniciar()
		assert procesar_eventos(lambda: dialogo.resultado == 42 or dialogo.cancelado.is_set(), 3) or dialogo.resultado is None
		dialogo._al_cancelar(None)
		assert dialogo.cancelado.is_set()
	finally:
		dialogo.Destroy()


def test_texto_acerca_de():
	texto = texto_acerca_de()
	assert NOMBRE_APLICACION in texto and APP_VERSION in texto and "Carpeta de datos" in texto


def test_menu_de_bandeja_en_espanol(app_wx):
	llamadas = []
	icono = IconoBandeja("Prueba", lambda: llamadas.append("restaurar"), lambda: llamadas.append("salir"), lambda: llamadas.append("comprobar"))
	try:
		menu = icono.CreatePopupMenu()
		etiquetas = [item.GetItemLabel() for item in menu.GetMenuItems() if not item.IsSeparator()]
		assert etiquetas == ["&Mostrar", "&Comprobar ahora", "&Salir"]
		menu.Destroy()
		icono._restaurar()
		assert llamadas == ["restaurar"]
	finally:
		icono.quitar()
