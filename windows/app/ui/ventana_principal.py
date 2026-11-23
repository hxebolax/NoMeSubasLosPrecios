"""Ventana principal de No Me Subas Los Precios.

Distribución (de izquierda a derecha, que es también el orden de tabulación):

1. Lista «Secciones»: Todos los productos, Categorías, Tiendas, Ofertas,
   Favoritos, Comparar y Avisos (lo mismo que el menú lateral de Android).
2. Lista de grupos, solo en las secciones que los tienen (categorías,
   tiendas y grupos de comparar).
3. Buscar, orden y filtros rápidos.
4. Lista de productos (``ListaAccesible``, modo informe) con las columnas
   Estado, Nombre, Precio, Cambio, Tienda, Categoría, Precio deseado y Última
   comprobación. El estado va primero: el lector dice «En oferta, Robot...,
   349,90 €...» de una vez. En «Avisos», la lista de avisos ocupa su lugar.

Reglas que se cumplen (agentes «accesibilidad-wx» y «proyecto-nuevo»):
etiquetas creadas justo antes de cada control, ``&`` en todo, atajos en los
menús, F1/Ctrl+F1/Ctrl+H, menú contextual con la tecla Aplicaciones, Escape
no cierra la ventana principal, foco que vuelve a la lista tras cada acción,
y TODO lo lento (red, copias) en hilos: los controles solo se tocan en el
hilo principal.
"""

from __future__ import annotations

import builtins
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

import wx
import wx.adv

from app.core import paths, voz
from app.core.configuracion import Configuracion
from app.core.instancia_unica import ORDEN_ABRIR, ORDEN_MOSTRAR, InstanciaUnica, traer_al_frente
from app.core.tareas import GestorTareas, HitosProgreso, TareaCancelada, TareaDuplicada
from app.core.version import APP_VERSION, NOMBRE_APLICACION
from app.services import avisos as logica
from app.services import colores, intercambio, vistas
from app.services.direcciones import dominio_de, es_url, extraer_primera_url
from app.services.errores import ErrorComprobacion
from app.services.extractor import ORIGEN_ELEGIDO, Resultado
from app.services.importes import formato_importe
from app.services.inicio_windows import ErrorInicio
from app.services.repositorio import SIN_CATEGORIA, ErrorDatos
from app.ui import comunes, espera
from app.ui.accesibilidad.composicion import PreferenciasLectura
from app.ui.accesibilidad.lista import ListaAccesible
from app.ui.accesibilidad.visual import alto_contraste_activo
from app.ui.bandeja import IconoBandeja
from app.ui.dialogo_elegir import describir_resultado, elegir_precio, elegir_variante
from app.ui.navegador import MENSAJE_SIN_MOTOR, URL_WEBVIEW2, NavegadorIntegrado
from app.ui.notificaciones import Notificador, sonar

log = logging.getLogger(__name__)


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


INTERVALO_BUZON_MS = 500
INTERVALO_PROGRAMADOR_MS = 60_000
RETRASO_PRIMERA_COMPROBACION_MS = 4_000
RETRASO_BUSQUEDA_MS = 300
TAMANO_MINIMO = (500, 350)
MAX_NOTIFICACIONES_INDIVIDUALES = 3

COLUMNAS_PRODUCTOS = (
	("Estado", 120), ("Nombre", 300), ("Precio", 100), ("Cambio", 190), ("Tienda", 120), ("Categoría", 120),
	("Precio deseado", 110), ("Última comprobación", 170),
)
COLUMNA_CAMBIO = 3
COLUMNAS_AVISOS = (("Estado", 80), ("Fecha", 170), ("Aviso", 190), ("Mensaje", 520))

# Menús: (título, [(nombre, etiqueta, ayuda, tipo) | None]). ``nombre`` es el
# sufijo del manejador ``_al_<nombre>``. Los atajos van en inglés (Ctrl, Shift)
# porque así los interpreta wx; en pantalla se muestran traducidos.
MENUS: list[tuple[str, list[tuple[str, str, str, int] | None]]] = [
	("&Archivo", [
		("anadir", "&Añadir producto...\tCtrl+N", "Añade un producto a partir de la dirección de su página.", wx.ITEM_NORMAL),
		None,
		("importar", "&Importar...\tCtrl+I", "Importa un archivo de No Me Subas Los Precios (de Windows o de Android).", wx.ITEM_NORMAL),
		("exportar", "&Exportar...\tCtrl+E", "Guarda todo en un archivo para pasarlo a otro equipo o al móvil.", wx.ITEM_NORMAL),
		("exportar_csv", "Exportar a &CSV...", "Guarda los productos en un archivo para hojas de cálculo.", wx.ITEM_NORMAL),
		None,
		("salir", "&Salir", "Cierra la aplicación del todo (también la bandeja).", wx.ITEM_NORMAL),
	]),
	("&Producto", [
		("navegador", "Abrir en el &navegador\tCtrl+Enter", "Abre la página del producto en su navegador.", wx.ITEM_NORMAL),
		("detalles", "Ver &detalles (Intro)", "Precio, historial y gráfica del producto. En la lista, también con Intro.", wx.ITEM_NORMAL),
		("comprobar_producto", "&Comprobar ahora\tShift+F5", "Vuelve a leer el precio de este producto.", wx.ITEM_NORMAL),
		("editar", "&Editar...\tF2", "Cambia la dirección, el nombre, el precio deseado...", wx.ITEM_NORMAL),
		("mover", "&Mover a categoría...\tCtrl+M", "Cambia la categoría del producto.", wx.ITEM_NORMAL),
		("favorito", "Marcar como &favorito\tCtrl+D", "Añade o quita el producto de Favoritos.", wx.ITEM_NORMAL),
		("pausa", "&Pausar la comprobación\tCtrl+P", "Pausa o reanuda la comprobación de este producto.", wx.ITEM_NORMAL),
		("copiar_enlace", "Copiar en&lace\tCtrl+Shift+C", "Copia la dirección del producto al portapapeles.", wx.ITEM_NORMAL),
		None,
		("eliminar", "Elim&inar... (Suprimir)", "Elimina el producto y su historial. En la lista, también con Suprimir.", wx.ITEM_NORMAL),
	]),
	("&Ver", [
		("seccion_0", "&Todos los productos\tCtrl+1", "Muestra todos los productos.", wx.ITEM_NORMAL),
		("seccion_1", "&Categorías\tCtrl+2", "Muestra las categorías y sus productos.", wx.ITEM_NORMAL),
		("seccion_2", "T&iendas\tCtrl+3", "Muestra las tiendas y sus productos.", wx.ITEM_NORMAL),
		("seccion_3", "&Ofertas\tCtrl+4", "Productos que han bajado en los últimos 7 días, en su mínimo o en el precio deseado.", wx.ITEM_NORMAL),
		("seccion_4", "&Favoritos\tCtrl+5", "Productos marcados como favoritos.", wx.ITEM_NORMAL),
		("seccion_5", "Co&mparar\tCtrl+6", "Grupos de productos para comparar tiendas.", wx.ITEM_NORMAL),
		("seccion_6", "A&visos\tCtrl+7", "Historial de avisos.", wx.ITEM_NORMAL),
		None,
		("buscar", "&Buscar...\tCtrl+F", "Lleva al campo de búsqueda.", wx.ITEM_NORMAL),
		("ORDEN", "O&rdenar por", "Orden de la lista de productos.", wx.ITEM_NORMAL),
		("solo_activos", "&Solo activos", "Oculta los productos en pausa.", wx.ITEM_CHECK),
		("solo_error", "Solo con &error", "Muestra solo los productos cuya última comprobación falló.", wx.ITEM_CHECK),
		("solo_agotados", "Solo a&gotados", "Muestra solo los productos agotados.", wx.ITEM_CHECK),
		None,
		("barra_estado", "Barra de esta&do", "Muestra u oculta la barra de estado.", wx.ITEM_CHECK),
	]),
	("&Herramientas", [
		("comprobar_todos", "&Comprobar todos ahora\tF5", "Comprueba ahora todos los productos activos.", wx.ITEM_NORMAL),
		("cancelar_comprobacion", "Cance&lar la comprobación", "Detiene la comprobación en curso.", wx.ITEM_NORMAL),
		None,
		("categorias", "Gestionar c&ategorías...", "Añadir, renombrar, borrar y ordenar categorías.", wx.ITEM_NORMAL),
		("tiendas", "Gestionar &tiendas...", "Nombre, selectores propios y notas de cada tienda.", wx.ITEM_NORMAL),
		None,
		("preferencias", "&Preferencias...\tCtrl+,", "Intervalo de comprobación, avisos, bandeja, inicio con Windows...", wx.ITEM_NORMAL),
		("carpeta_registros", "Abrir la carpeta de &registros", "Abre en el Explorador la carpeta de registros.", wx.ITEM_NORMAL),
	]),
	("Ay&uda", [
		("manual", "&Manual\tF1", "Abre el manual de usuario.", wx.ITEM_NORMAL),
		("teclas", "&Lista de teclas\tCtrl+F1", "Muestra todos los atajos de teclado.", wx.ITEM_NORMAL),
		("novedades", "&Novedades", "Muestra los cambios de cada versión.", wx.ITEM_NORMAL),
		("ayuda_contextual", "Ayuda del control &enfocado\tCtrl+H", "Explica para qué sirve el control que tiene el foco.", wx.ITEM_NORMAL),
		None,
		("actualizaciones", "Buscar &actualizaciones...", "Comprueba si hay una versión nueva de la aplicación.", wx.ITEM_NORMAL),
		("carpeta_datos", "Abrir la carpeta de &datos", "Abre en el Explorador la carpeta data (base de datos, copias, ajustes).", wx.ITEM_NORMAL),
		None,
		("acerca_de", "A&cerca de {nombre}...", "Versión y datos técnicos de la aplicación.", wx.ITEM_NORMAL),
	]),
]
ORDENES_MENU = [
	("nombre", "&Nombre"), ("precio", "&Precio"), ("bajada", "&Mayor bajada"), ("cambio", "Último &cambio"),
	("alta", "&Fecha de alta"), ("tienda", "&Tienda"),
]


class VentanaPrincipal(wx.Frame):
	"""Ventana principal con secciones, productos, bandeja y comprobación periódica."""

	def __init__(self, configuracion: Configuracion, nucleo: Any, instancia: InstanciaUnica | None = None) -> None:
		super().__init__(None, title=NOMBRE_APLICACION)
		self._config = configuracion
		self.nucleo = nucleo
		self._instancia = instancia
		self._saliendo = False
		self._forzar_salida = False
		self._rect_normal: wx.Rect | None = None
		self.elementos_menu: dict[str, wx.MenuItem] = {}
		self.elementos_orden: dict[str, wx.MenuItem] = {}
		self.tareas = GestorTareas(max_hilos=3, nombre="tareas")
		self._comprobacion = None
		self._comprobacion_automatica = False
		self._hitos = HitosProgreso(paso=25)
		self._detalles = None
		self._productos: list[dict[str, Any]] = []
		self._todos: list[dict[str, Any]] = []
		self._avisos: list[dict[str, Any]] = []
		self._grupos: list[tuple[Any, str]] = []
		self._comparacion: dict[int, str] = {}
		self._busqueda_pendiente: wx.CallLater | None = None
		self.actualizador = None
		self.comprobador_actualizaciones = None
		self._desuscribir = None

		self._crear_menus()
		self._crear_contenido()
		self.CreateStatusBar()
		self._aplicar_barra_estado(bool(self._config.obtener("ventana.barra_estado", True)))
		from app.ui.bandeja import icono_aplicacion

		self.SetIcon(icono_aplicacion())
		self._restaurar_geometria()

		self.notificador = Notificador(self, self._al_pulsar_notificacion)
		# Navegador integrado (oculto) para las tiendas que lo necesitan.
		self.navegador = NavegadorIntegrado(self)
		self.nucleo.comprobador.navegador = self.navegador.obtener_html
		self.bandeja: IconoBandeja | None = None
		self._poner_bandeja()

		self.Bind(wx.EVT_CLOSE, self._al_cerrar)
		self.Bind(wx.EVT_SIZE, self._al_cambiar_geometria)
		self.Bind(wx.EVT_MOVE, self._al_cambiar_geometria)
		self.Bind(wx.EVT_MENU_OPEN, self._al_abrir_menu)
		if hasattr(wx, "EVT_POWER_RESUME"):
			self.Bind(wx.EVT_POWER_RESUME, self._al_reanudar_equipo)

		self._temporizador_buzon = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self._al_revisar_buzon, self._temporizador_buzon)
		if self._instancia is not None:
			self._temporizador_buzon.Start(INTERVALO_BUZON_MS)
		self._programador = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self._al_programador, self._programador)
		self._desuscribir = self._config.suscribir(self._al_cambiar_configuracion)
		# Colores de la lista: se repintan al cambiar las preferencias o el tema de Windows.
		self._repintado_pendiente = False
		self.Bind(wx.EVT_SYS_COLOUR_CHANGED, self._al_cambiar_colores_sistema)

		self._aplicar_seccion(int(self._config.obtener("lista.seccion", 0) or 0), enfocar=False)
		self._mostrar_ultima_comprobacion()

	# ════════════════════════════════════════════════════════════════════════
	# Construcción
	# ════════════════════════════════════════════════════════════════════════

	def _crear_menus(self) -> None:
		barra = wx.MenuBar()
		for titulo, elementos in MENUS:
			menu = wx.Menu()
			for elemento in elementos:
				if elemento is None:
					menu.AppendSeparator()
					continue
				nombre, etiqueta, ayuda, tipo = elemento
				if nombre == "ORDEN":
					submenu = wx.Menu()
					for clave, texto in ORDENES_MENU:
						item = submenu.AppendRadioItem(wx.ID_ANY, _(texto), _("Ordena la lista por {criterio}.").format(
							criterio=_(texto).replace("&", "").lower()))
						self.Bind(wx.EVT_MENU, lambda _evento, c=clave: self.cambiar_orden(c), item)
						self.elementos_orden[clave] = item
					item = menu.AppendSubMenu(submenu, _(etiqueta), _(ayuda))
					self.elementos_menu["orden"] = item
					continue
				item = menu.Append(wx.ID_ANY, _(etiqueta).format(nombre=NOMBRE_APLICACION), _(ayuda), tipo)
				if nombre.startswith("seccion_"):
					self.Bind(wx.EVT_MENU, lambda _evento, s=int(nombre[8:]): self.ir_a_seccion(s), item)
				else:
					self.Bind(wx.EVT_MENU, getattr(self, f"_al_{nombre}"), item)
				self.elementos_menu[nombre] = item
			barra.Append(menu, _(titulo))
		self.SetMenuBar(barra)
		orden = str(self._config.obtener("lista.orden", "nombre"))
		if orden in self.elementos_orden:
			self.elementos_orden[orden].Check(True)
		for filtro in ("solo_activos", "solo_error", "solo_agotados"):
			self.elementos_menu[filtro].Check(bool(self._config.obtener(f"lista.{filtro}", False)))
		self.elementos_menu["cancelar_comprobacion"].Enable(False)

	def _leer_preferencias(self) -> PreferenciasLectura:
		"""Preferencias de lectura por columnas (se leen en cada anuncio)."""
		return PreferenciasLectura(
			numero_fila=bool(self._config.obtener("lectura.numero_fila", False)),
			cabecera=bool(self._config.obtener("lectura.cabecera", True)),
			contenido=bool(self._config.obtener("lectura.contenido", True)),
		)

	def _crear_contenido(self) -> None:
		"""Controles en orden de tabulación; cada etiqueta, JUSTO ANTES de su control."""
		self.panel = wx.Panel(self)
		principal = wx.BoxSizer(wx.HORIZONTAL)

		columna_secciones = wx.BoxSizer(wx.VERTICAL)
		self.etiqueta_secciones = wx.StaticText(self.panel, label=_("&Secciones:"))
		self.lista_secciones = wx.ListBox(self.panel, choices=[_(s) for s in vistas.SECCIONES], style=wx.LB_SINGLE)
		self.lista_secciones.SetHelpText(_("Secciones de la aplicación. También con Control+1 a Control+7."))
		self.lista_secciones.Bind(wx.EVT_LISTBOX, lambda _evento: self._aplicar_seccion(self.lista_secciones.GetSelection(), enfocar=False))
		columna_secciones.Add(self.etiqueta_secciones, 0, wx.ALL, 4)
		columna_secciones.Add(self.lista_secciones, 1, wx.EXPAND | wx.ALL, 4)
		principal.Add(columna_secciones, 0, wx.EXPAND)

		self.columna_grupos = wx.BoxSizer(wx.VERTICAL)
		self.etiqueta_grupos = wx.StaticText(self.panel, label=_("Lista de g&rupos:"))
		self.lista_grupos = wx.ListBox(self.panel, style=wx.LB_SINGLE, size=self.FromDIP(wx.Size(220, -1)))
		self.lista_grupos.SetHelpText(_("Elija una categoría, tienda o grupo para ver sus productos."))
		self.lista_grupos.Bind(wx.EVT_LISTBOX, lambda _evento: self.refrescar_lista())
		self.lista_grupos.Bind(wx.EVT_LISTBOX_DCLICK, lambda _evento: self._enfocar_lista())
		self.lista_grupos.Bind(wx.EVT_KEY_DOWN, self._al_tecla_grupos)
		self.columna_grupos.Add(self.etiqueta_grupos, 0, wx.ALL, 4)
		self.columna_grupos.Add(self.lista_grupos, 1, wx.EXPAND | wx.ALL, 4)
		principal.Add(self.columna_grupos, 0, wx.EXPAND)

		derecha = wx.BoxSizer(wx.VERTICAL)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		fila.Add(wx.StaticText(self.panel, label=_("&Buscar:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
		self.campo_buscar = wx.TextCtrl(self.panel, size=self.FromDIP(wx.Size(200, -1)))
		self.campo_buscar.SetHelpText(_("Busca en el nombre, la tienda, la categoría, las notas y el grupo. Control+F lleva aquí."))
		self.campo_buscar.Bind(wx.EVT_TEXT, self._al_escribir_busqueda)
		self.campo_buscar.Bind(wx.EVT_KEY_DOWN, self._al_tecla_buscar)
		fila.Add(self.campo_buscar, 1, wx.ALL, 4)
		fila.Add(wx.StaticText(self.panel, label=_("&Orden:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
		self.lista_orden = wx.Choice(self.panel, choices=[_(t) for _c, t in vistas.ORDENES])
		self.lista_orden.SetHelpText(_("Orden de la lista de productos. Se recuerda."))
		claves_orden = [c for c, _t in vistas.ORDENES]
		orden = str(self._config.obtener("lista.orden", "nombre"))
		self.lista_orden.SetSelection(claves_orden.index(orden) if orden in claves_orden else 0)
		self.lista_orden.Bind(wx.EVT_CHOICE, lambda _evento: self.cambiar_orden(claves_orden[self.lista_orden.GetSelection()]))
		fila.Add(self.lista_orden, 0, wx.ALL, 4)
		derecha.Add(fila, 0, wx.EXPAND)
		filtros = wx.BoxSizer(wx.HORIZONTAL)
		self.casillas_filtro: dict[str, wx.CheckBox] = {}
		for clave, etiqueta, ayuda in (
			("solo_activos", _("Solo a&ctivos"), _("Oculta los productos en pausa.")),
			("solo_error", _("Solo con &error"), _("Muestra solo los productos cuya última comprobación falló.")),
			("solo_agotados", _("Solo a&gotados"), _("Muestra solo los productos agotados.")),
		):
			casilla = wx.CheckBox(self.panel, label=etiqueta)
			casilla.SetValue(bool(self._config.obtener(f"lista.{clave}", False)))
			casilla.SetHelpText(ayuda)
			casilla.Bind(wx.EVT_CHECKBOX, lambda evento, c=clave: self.cambiar_filtro(c, evento.IsChecked()))
			self.casillas_filtro[clave] = casilla
			filtros.Add(casilla, 0, wx.ALL, 4)
		derecha.Add(filtros, 0)

		self.etiqueta_productos = wx.StaticText(self.panel, label=_("Pro&ductos:"))
		self.lista = ListaAccesible(
			self.panel, _("Productos"), columnas=[(_(n), self.FromDIP(a)) for n, a in COLUMNAS_PRODUCTOS],
			leer_preferencias=self._leer_preferencias,
		)
		self.lista.SetHelpText(_(
			"Lista de productos. Intro abre los detalles, Suprimir elimina, F2 edita, la tecla Aplicaciones abre el "
			"menú del producto. Izquierda y derecha recorren las columnas."
		))
		self.lista.Bind(wx.EVT_CONTEXT_MENU, self._al_menu_contextual)
		self.lista.Bind(wx.EVT_KEY_DOWN, self._al_tecla_lista)
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self._al_detalles(None))
		derecha.Add(self.etiqueta_productos, 0, wx.LEFT | wx.TOP, 4)
		derecha.Add(self.lista, 1, wx.EXPAND | wx.ALL, 4)

		self.etiqueta_avisos = wx.StaticText(self.panel, label=_("Avisos guar&dados:"))
		self.lista_avisos = ListaAccesible(
			self.panel, _("Avisos"), columnas=[(_(n), self.FromDIP(a)) for n, a in COLUMNAS_AVISOS],
			leer_preferencias=self._leer_preferencias,
		)
		self.lista_avisos.SetHelpText(_(
			"Avisos de cambios de precio, de los no leídos a los leídos y del más nuevo al más viejo. Intro abre el "
			"producto y marca el aviso como leído; Suprimir lo borra; la tecla Aplicaciones abre más acciones."
		))
		self.lista_avisos.Bind(wx.EVT_CONTEXT_MENU, self._al_menu_avisos)
		self.lista_avisos.Bind(wx.EVT_KEY_DOWN, self._al_tecla_avisos)
		self.lista_avisos.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self._abrir_aviso())
		derecha.Add(self.etiqueta_avisos, 0, wx.LEFT | wx.TOP, 4)
		derecha.Add(self.lista_avisos, 1, wx.EXPAND | wx.ALL, 4)
		principal.Add(derecha, 1, wx.EXPAND)
		self.panel.SetSizer(principal)

	# ════════════════════════════════════════════════════════════════════════
	# Mostrar, bandeja, geometría
	# ════════════════════════════════════════════════════════════════════════

	def mostrar(self) -> None:
		"""Muestra la ventana con el foco en la lista (la llama ``main.py``)."""
		self.Show()
		self.Raise()
		wx.CallAfter(self._enfocar_lista)

	def _poner_bandeja(self) -> None:
		if self.bandeja is not None:
			return
		self.bandeja = IconoBandeja(NOMBRE_APLICACION, self.restaurar, self.salir, lambda: self.comprobar())
		if not self.bandeja.mostrar():
			log.warning("No se pudo poner el icono en la bandeja.")
			self.bandeja.quitar()
			self.bandeja = None
			return
		self.notificador.asociar_icono(self.bandeja)

	def ocultar_en_bandeja(self) -> bool:
		"""Oculta la ventana (sigue el icono de la bandeja). ``False`` si no hay bandeja."""
		if self.bandeja is None:
			self._poner_bandeja()
		if self.bandeja is None:
			return False
		self.Hide()
		voz.hablar(_("{nombre} sigue en la bandeja del sistema.").format(nombre=NOMBRE_APLICACION))
		return True

	def restaurar(self) -> None:
		"""Muestra la ventana desde la bandeja, minimizada o detrás de otras."""
		if not self:
			return
		self.Show()
		if self.IsIconized():
			self.Iconize(False)
		self.Raise()
		dialogo = next(
			(v for v in wx.GetTopLevelWindows() if isinstance(v, wx.Dialog) and v.IsShown() and v.IsEnabled()),
			None,
		)
		if dialogo is not None:
			dialogo.Raise()
			dialogo.SetFocus()
		else:
			wx.CallAfter(self._enfocar_lista)
		if not traer_al_frente(self.GetHandle()):
			self.RequestUserAttention()

	def salir(self) -> None:
		"""Sale de verdad (aunque esté activado minimizar a la bandeja)."""
		self._forzar_salida = True
		self.Close()

	def _enfocar_lista(self) -> None:
		if not self:
			return
		lista = self.lista_avisos if self.seccion == vistas.AVISOS else self.lista
		lista.SetFocus()
		if lista.numero_filas() and lista.GetFocusedItem() < 0:
			lista.enfocar_fila(0, anunciar=False)

	def _restaurar_geometria(self) -> None:
		ancho = int(self._config.obtener("ventana.ancho", 1000))
		alto = int(self._config.obtener("ventana.alto", 650))
		if ancho < TAMANO_MINIMO[0] or alto < TAMANO_MINIMO[1]:
			ancho, alto = 1000, 650
		self.SetSize(wx.Size(ancho, alto))
		x = int(self._config.obtener("ventana.x", -1))
		y = int(self._config.obtener("ventana.y", -1))
		if x >= -50 and y >= -50 and wx.Display.GetFromPoint(wx.Point(x + 60, y + 15)) != wx.NOT_FOUND:
			self.SetPosition(wx.Point(x, y))
		else:
			self.Centre()
		if self._config.obtener("ventana.maximizada", False):
			self.Maximize(True)

	def _al_cambiar_geometria(self, evento: wx.Event) -> None:
		if self.IsShown() and not self.IsMaximized() and not self.IsIconized():
			self._rect_normal = self.GetRect()
		evento.Skip()

	def _guardar_geometria(self) -> None:
		rect = self._rect_normal or self.GetRect()
		self._config.establecer_varias({
			"ventana.x": rect.x, "ventana.y": rect.y, "ventana.ancho": rect.width, "ventana.alto": rect.height,
			"ventana.maximizada": bool(self.IsMaximized()),
		}, guardar=False)

	# ════════════════════════════════════════════════════════════════════════
	# Arranque y cierre
	# ════════════════════════════════════════════════════════════════════════

	def iniciar_servicios(self, actualizaciones: bool = True) -> None:
		"""Programador, comprobación al iniciar, copia diaria y actualizaciones (tras mostrarse)."""
		self._programador.Start(INTERVALO_PROGRAMADOR_MS)
		self.tareas.enviar(lambda _tarea: self._mantenimiento(), nombre="mantenimiento",
			al_fallar=lambda error: log.error("Falló el mantenimiento: %s", error))
		if self._config.obtener("precios.comprobar_al_iniciar", True) and self.nucleo.toca_comprobar():
			wx.CallLater(RETRASO_PRIMERA_COMPROBACION_MS, self._comprobar_si_toca)
		if actualizaciones:
			self._iniciar_actualizaciones()

	def _mantenimiento(self) -> str:
		"""Copia diaria de la base y limpieza de avisos viejos (en un hilo)."""
		try:
			copia = self.nucleo.copia_diaria_si_toca()
			if copia:
				log.info("Copia diaria: %s", copia.name)
			borrados = self.nucleo.purgar_avisos()
			if borrados:
				log.info("Avisos antiguos borrados: %d", borrados)
		finally:
			self.nucleo.bd.cerrar_lectura_del_hilo()
		return "ok"

	def _iniciar_actualizaciones(self) -> None:
		from app.services import actualizador
		from app.ui import dialogo_actualizacion

		self.actualizador = actualizador.configuracion_por_defecto(APP_VERSION)
		self._aplicar_origen_actualizaciones()
		dialogo_actualizacion.al_arrancar(self, self.actualizador, anunciar=voz.hablar)
		if self._config.obtener("precios.buscar_actualizaciones", True):
			self.comprobador_actualizaciones = dialogo_actualizacion.ComprobadorPeriodico(
				self, self.actualizador, intervalo_horas=24, anunciar=voz.hablar
			)
			self.comprobador_actualizaciones.iniciar()

	def _al_cerrar(self, evento: wx.CloseEvent) -> None:
		"""Cerrar la ventana la deja en la bandeja si así está configurado; si no, sale."""
		if (
			not self._forzar_salida
			and evento.CanVeto()
			and self._config.obtener("windows.minimizar_a_bandeja", True)
			and self.ocultar_en_bandeja()
		):
			evento.Veto()
			return
		self._saliendo = True
		self._temporizador_buzon.Stop()
		self._programador.Stop()
		if self.comprobador_actualizaciones is not None:
			self.comprobador_actualizaciones.detener()
		if self._desuscribir is not None:
			self._desuscribir()
		self.tareas.cancelar_todas(_("La aplicación se cierra"))
		self.tareas.apagar(espera=3.0)
		self._guardar_geometria()
		try:
			self._config.guardar_pendiente()
			self._config.guardar()
		except Exception:
			log.exception("No se pudo guardar la configuración al cerrar")
		self.notificador.desasociar()
		if self.bandeja is not None:
			self.bandeja.quitar()
			self.bandeja = None
		self.navegador.destruir()
		try:
			self.nucleo.cerrar()
		except Exception:
			log.exception("Error al cerrar la base de datos")
		log.info("Ventana principal cerrada.")
		self.Destroy()

	def _al_revisar_buzon(self, _evento: wx.TimerEvent) -> None:
		try:
			ordenes = self._instancia.recoger_ordenes() if self._instancia else []
			for orden in ordenes:
				if orden.orden in (ORDEN_MOSTRAR, ORDEN_ABRIR):
					self.restaurar()
				if orden.orden == ORDEN_ABRIR:
					url = next((extraer_primera_url(a) for a in orden.argumentos if extraer_primera_url(a)), None)
					if url:
						wx.CallAfter(self.anadir_producto, url)
		except Exception:
			log.exception("Error al atender las órdenes de otra instancia")

	# ════════════════════════════════════════════════════════════════════════
	# Secciones y lista
	# ════════════════════════════════════════════════════════════════════════

	@property
	def seccion(self) -> int:
		return int(self.lista_secciones.GetSelection()) if self.lista_secciones.GetSelection() >= 0 else 0

	def ir_a_seccion(self, seccion: int) -> None:
		"""Ctrl+1…Ctrl+7: cambia de sección y lleva el foco a donde se trabaja."""
		self._aplicar_seccion(seccion, enfocar=True)
		comunes.anunciar(_(vistas.SECCIONES[seccion]))

	def _aplicar_seccion(self, seccion: int, enfocar: bool) -> None:
		seccion = max(0, min(seccion, len(vistas.SECCIONES) - 1))
		if self.lista_secciones.GetSelection() != seccion:
			self.lista_secciones.SetSelection(seccion)
		self._config.establecer("lista.seccion", seccion, guardar=False)
		con_grupos = seccion in vistas.SECCIONES_CON_GRUPOS
		self.columna_grupos.ShowItems(con_grupos)
		es_avisos = seccion == vistas.AVISOS
		self.etiqueta_productos.Show(not es_avisos)
		self.lista.Show(not es_avisos)
		self.etiqueta_avisos.Show(es_avisos)
		self.lista_avisos.Show(es_avisos)
		etiquetas = {vistas.CATEGORIAS: _("Lista de catego&rías:"), vistas.TIENDAS: _("Lista de tiendas (&r):"),
			vistas.COMPARAR: _("Lista de g&rupos para comparar:")}
		if con_grupos:
			self.etiqueta_grupos.SetLabel(etiquetas[seccion])
		cabecera = _("Diferencia") if seccion == vistas.COMPARAR else _("Cambio")
		columna = self.lista.GetColumn(COLUMNA_CAMBIO)
		columna.SetText(cabecera)
		self.lista.SetColumn(COLUMNA_CAMBIO, columna)
		self.panel.Layout()
		self.recargar_datos()
		if enfocar:
			if con_grupos and self.lista_grupos.GetCount():
				self.lista_grupos.SetFocus()
			else:
				self._enfocar_lista()

	def recargar_datos(self, conservar_id: int | None = None) -> None:
		"""Vuelve a leer la base y repinta grupos y lista (rápido: unos cientos de filas)."""
		self._todos = self.nucleo.repositorio.productos()
		self._rellenar_grupos()
		self.refrescar_lista(conservar_id)

	def _rellenar_grupos(self) -> None:
		seccion = self.seccion
		previo = self._grupo_actual()
		grupos: list[tuple[Any, str]] = []
		if seccion == vistas.CATEGORIAS:
			for c in self.nucleo.repositorio.categorias():
				grupos.append((c["id"], self._texto_grupo(c["nombre"], c["productos"])))
			grupos.append((None, self._texto_grupo(SIN_CATEGORIA, self.nucleo.repositorio.sin_categoria())))
		elif seccion == vistas.TIENDAS:
			for t in self.nucleo.repositorio.tiendas():
				grupos.append((t["id"], self._texto_grupo(t["nombre"], t["productos"])))
		elif seccion == vistas.COMPARAR:
			for grupo, n in self.nucleo.repositorio.grupos():
				grupos.append((grupo, self._texto_grupo(grupo, n)))
		textos = [t for _c, t in grupos]
		if textos != [self.lista_grupos.GetString(i) for i in range(self.lista_grupos.GetCount())] or grupos != self._grupos:
			self._grupos = grupos
			self.lista_grupos.Set(textos)
			claves = [c for c, _t in grupos]
			if grupos:
				self.lista_grupos.SetSelection(claves.index(previo) if previo in claves else 0)

	@staticmethod
	def _texto_grupo(nombre: str, cantidad: int) -> str:
		return _("{nombre}, {n} producto").format(nombre=nombre, n=cantidad) if cantidad == 1 else \
			_("{nombre}, {n} productos").format(nombre=nombre, n=cantidad)

	def _grupo_actual(self) -> Any:
		indice = self.lista_grupos.GetSelection()
		if 0 <= indice < len(self._grupos):
			return self._grupos[indice][0]
		return "__ninguno__"

	def _productos_de_seccion(self) -> list[dict[str, Any]]:
		seccion = self.seccion
		todos = self._todos
		grupo = self._grupo_actual()
		self._comparacion = {}
		if seccion == vistas.CATEGORIAS:
			base = [p for p in todos if p.get("categoria_id") == grupo] if grupo != "__ninguno__" else []
		elif seccion == vistas.TIENDAS:
			base = [p for p in todos if p.get("tienda_id") == grupo] if grupo != "__ninguno__" else []
		elif seccion == vistas.OFERTAS:
			base = vistas.ofertas(todos)
		elif seccion == vistas.FAVORITOS:
			base = [p for p in todos if p.get("favorito")]
		elif seccion == vistas.COMPARAR:
			base = [p for p in todos if (p.get("grupo") or "") == grupo] if grupo != "__ninguno__" else []
		else:
			base = list(todos)
		filtrados = vistas.filtrar(
			base,
			self.campo_buscar.GetValue(),
			solo_activos=self.casillas_filtro["solo_activos"].GetValue(),
			solo_error=self.casillas_filtro["solo_error"].GetValue(),
			solo_agotados=self.casillas_filtro["solo_agotados"].GetValue(),
		)
		if seccion == vistas.COMPARAR:
			comparados = vistas.comparar(filtrados)
			self._comparacion = {int(p["id"]): texto for p, texto in comparados}
			return [dict(p) for p, _t in comparados]
		if seccion == vistas.OFERTAS:
			return [dict(p) for p in filtrados]
		return [dict(p) for p in vistas.ordenar(filtrados, str(self._config.obtener("lista.orden", "nombre")))]

	def refrescar_lista(self, conservar_id: int | None = None) -> None:
		"""Repinta la lista visible conservando el producto en el que está el usuario."""
		if self.seccion == vistas.AVISOS:
			self._refrescar_avisos(conservar_id)
			return
		actual = self.producto_actual()
		objetivo = conservar_id if conservar_id is not None else (actual["id"] if actual else None)
		self._productos = self._productos_de_seccion()
		ahora = datetime.now(timezone.utc)
		filas = []
		for p in self._productos:
			columnas = vistas.columnas_producto(p, ahora)
			if self._comparacion:
				columnas[COLUMNA_CAMBIO] = self._comparacion.get(int(p["id"]), columnas[COLUMNA_CAMBIO])
			filas.append(columnas)
		self.lista.reemplazar_filas(filas)
		ajustes = self._ajustes_colores()
		self.lista.colorear_filas([ajustes.pintura(colores.tipo_color(p, ahora)) for p in self._productos])
		if objetivo is not None:
			for indice, p in enumerate(self._productos):
				if p["id"] == objetivo:
					self.lista.enfocar_fila(indice, anunciar=False)
					break
		self._actualizar_menus_producto()

	def _refrescar_avisos(self, conservar_id: int | None = None) -> None:
		actual = self.aviso_actual()
		objetivo = conservar_id if conservar_id is not None else (actual["id"] if actual else None)
		self._avisos = self.nucleo.repositorio.avisos()
		texto = self.campo_buscar.GetValue()
		if texto.strip():
			self._avisos = [a for a in self._avisos if vistas.coincide({"nombre": f"{a.get('titulo')} {a.get('mensaje')}"}, texto)]
		filas = [
			[_("Leído") if a.get("leido") else _("Sin leer"), vistas.fecha_legible(a.get("fecha")), a.get("titulo") or "",
				a.get("mensaje") or ""]
			for a in self._avisos
		]
		self.lista_avisos.reemplazar_filas(filas)
		ajustes = self._ajustes_colores()
		self.lista_avisos.colorear_filas([ajustes.pintura(colores.tipo_color_aviso(a.get("tipo"))) for a in self._avisos])
		if objetivo is not None:
			for indice, a in enumerate(self._avisos):
				if a["id"] == objetivo:
					self.lista_avisos.enfocar_fila(indice, anunciar=False)
					break

	def producto_actual(self) -> dict[str, Any] | None:
		if self.seccion == vistas.AVISOS:
			aviso = self.aviso_actual()
			if aviso and aviso.get("producto_id"):
				return self.nucleo.repositorio.producto(int(aviso["producto_id"]))
			return None
		fila = self.lista.fila_actual()
		return self._productos[fila] if 0 <= fila < len(self._productos) else None

	def aviso_actual(self) -> dict[str, Any] | None:
		fila = self.lista_avisos.fila_actual()
		return self._avisos[fila] if 0 <= fila < len(self._avisos) else None

	def cambiar_orden(self, orden: str) -> None:
		self._config.establecer("lista.orden", orden)
		claves = [c for c, _t in vistas.ORDENES]
		if orden in claves and self.lista_orden.GetSelection() != claves.index(orden):
			self.lista_orden.SetSelection(claves.index(orden))
		if orden in self.elementos_orden:
			self.elementos_orden[orden].Check(True)
		self.refrescar_lista()

	def cambiar_filtro(self, clave: str, valor: bool) -> None:
		self._config.establecer(f"lista.{clave}", bool(valor))
		self.casillas_filtro[clave].SetValue(bool(valor))
		self.elementos_menu[clave].Check(bool(valor))
		self.refrescar_lista()
		comunes.anunciar(_("{n} productos").format(n=len(self._productos)))

	def _al_escribir_busqueda(self, _evento: wx.CommandEvent) -> None:
		if self._busqueda_pendiente is not None and self._busqueda_pendiente.IsRunning():
			self._busqueda_pendiente.Restart(RETRASO_BUSQUEDA_MS)
		else:
			self._busqueda_pendiente = wx.CallLater(RETRASO_BUSQUEDA_MS, self.refrescar_lista)

	def _al_tecla_buscar(self, evento: wx.KeyEvent) -> None:
		tecla = evento.GetKeyCode()
		if tecla in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_DOWN) and not evento.HasAnyModifiers():
			self.refrescar_lista()
			n = self.lista_avisos.numero_filas() if self.seccion == vistas.AVISOS else self.lista.numero_filas()
			comunes.anunciar(_("{n} resultados").format(n=n))
			self._enfocar_lista()
			return
		if tecla == wx.WXK_ESCAPE and self.campo_buscar.GetValue():
			self.campo_buscar.SetValue("")
			return
		evento.Skip()

	def _al_tecla_grupos(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not evento.HasAnyModifiers():
			self._enfocar_lista()
			return
		evento.Skip()

	def _al_tecla_lista(self, evento: wx.KeyEvent) -> None:
		# Suprimir aquí y no como atajo de menú: un atajo le robaría la tecla al campo de búsqueda.
		if evento.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and not evento.HasAnyModifiers():
			self._al_eliminar(None)
			return
		evento.Skip()

	def _al_tecla_avisos(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and not evento.HasAnyModifiers():
			self._borrar_aviso()
			return
		evento.Skip()

	def _mostrar_ultima_comprobacion(self) -> None:
		ultima = self._config.obtener("general.ultima_comprobacion") or self.nucleo.repositorio.ultima_comprobacion_global()
		if ultima:
			self.SetStatusText(_("Última comprobación: {fecha}.").format(fecha=vistas.fecha_legible(ultima)))
		else:
			self.SetStatusText(_("Todavía no se ha comprobado ningún precio. Pulse Control+N para añadir un producto."))

	# ════════════════════════════════════════════════════════════════════════
	# Menús dinámicos y contextuales
	# ════════════════════════════════════════════════════════════════════════

	def _actualizar_menus_producto(self) -> None:
		producto = self.producto_actual()
		hay = producto is not None
		for nombre in ("navegador", "detalles", "comprobar_producto", "editar", "mover", "favorito", "pausa", "copiar_enlace", "eliminar"):
			self.elementos_menu[nombre].Enable(hay)
		if hay:
			self.elementos_menu["favorito"].SetItemLabel(
				_("Quitar de &favoritos\tCtrl+D") if producto.get("favorito") else _("Marcar como &favorito\tCtrl+D"))
			self.elementos_menu["pausa"].SetItemLabel(
				_("&Reanudar la comprobación\tCtrl+P") if not producto.get("activo", 1) else _("&Pausar la comprobación\tCtrl+P"))

	def _al_abrir_menu(self, evento: wx.MenuEvent) -> None:
		self._actualizar_menus_producto()
		evento.Skip()

	def _posicion_menu(self, lista: ListaAccesible, evento: wx.ContextMenuEvent) -> wx.Point:
		posicion = evento.GetPosition()
		if posicion == wx.DefaultPosition:
			enfocado = max(lista.GetFocusedItem(), 0)
			rect = lista.GetItemRect(enfocado) if lista.numero_filas() else wx.Rect(0, 0, 0, 0)
			return wx.Point(rect.x + 20, rect.y + rect.height)
		return lista.ScreenToClient(posicion)

	def menu_producto(self) -> wx.Menu | None:
		"""Menú de acciones del producto actual, según su estado."""
		producto = self.producto_actual()
		menu = wx.Menu()
		if producto is None:
			item = menu.Append(wx.ID_ANY, _("&Añadir producto..."))
			menu.Bind(wx.EVT_MENU, self._al_anadir, item)
			return menu
		acciones = [
			("navegador", _("Abrir en el &navegador")),
			("detalles", _("Ver &detalles")),
			("comprobar_producto", _("&Comprobar ahora")),
			("editar", _("&Editar...")),
			("mover", _("&Mover a categoría...")),
			("favorito", _("Quitar de &favoritos") if producto.get("favorito") else _("Marcar como &favorito")),
			("pausa", _("&Reanudar la comprobación") if not producto.get("activo", 1) else _("&Pausar la comprobación")),
			("copiar_enlace", _("Copiar en&lace")),
			None,
			("eliminar", _("Elim&inar...")),
		]
		for accion in acciones:
			if accion is None:
				menu.AppendSeparator()
				continue
			nombre, etiqueta = accion
			item = menu.Append(wx.ID_ANY, etiqueta)
			menu.Bind(wx.EVT_MENU, getattr(self, f"_al_{nombre}"), item)
		return menu

	def _al_menu_contextual(self, evento: wx.ContextMenuEvent) -> None:
		menu = self.menu_producto()
		try:
			self.lista.PopupMenu(menu, self._posicion_menu(self.lista, evento))
		finally:
			menu.Destroy()

	def _al_menu_avisos(self, evento: wx.ContextMenuEvent) -> None:
		menu = wx.Menu()
		aviso = self.aviso_actual()
		if aviso is not None:
			if aviso.get("producto_id"):
				item = menu.Append(wx.ID_ANY, _("Abrir el &producto"))
				menu.Bind(wx.EVT_MENU, lambda _e: self._abrir_aviso(), item)
			item = menu.Append(wx.ID_ANY, _("Marcar como &no leído") if aviso.get("leido") else _("Marcar como &leído"))
			menu.Bind(wx.EVT_MENU, lambda _e: self._marcar_aviso(not aviso.get("leido")), item)
		item = menu.Append(wx.ID_ANY, _("Marcar &todos como leídos"))
		menu.Bind(wx.EVT_MENU, lambda _e: self._marcar_todos_leidos(), item)
		menu.AppendSeparator()
		if aviso is not None:
			item = menu.Append(wx.ID_ANY, _("&Borrar el aviso"))
			menu.Bind(wx.EVT_MENU, lambda _e: self._borrar_aviso(), item)
		item = menu.Append(wx.ID_ANY, _("Borrar t&odos los avisos..."))
		menu.Bind(wx.EVT_MENU, lambda _e: self._borrar_todos_avisos(), item)
		try:
			self.lista_avisos.PopupMenu(menu, self._posicion_menu(self.lista_avisos, evento))
		finally:
			menu.Destroy()

	# ════════════════════════════════════════════════════════════════════════
	# Avisos
	# ════════════════════════════════════════════════════════════════════════

	def _abrir_aviso(self) -> None:
		aviso = self.aviso_actual()
		if aviso is None:
			return
		if not aviso.get("leido"):
			self.nucleo.repositorio.marcar_avisos([aviso["id"]], True)
			self._refrescar_avisos(aviso["id"])
		if aviso.get("producto_id"):
			self.abrir_detalles(int(aviso["producto_id"]))
		else:
			comunes.mensaje(self, aviso.get("mensaje") or "", aviso.get("titulo") or _("Aviso"))

	def _marcar_aviso(self, leido: bool) -> None:
		aviso = self.aviso_actual()
		if aviso is not None:
			self.nucleo.repositorio.marcar_avisos([aviso["id"]], leido)
			self._refrescar_avisos(aviso["id"])
			comunes.anunciar(_("Marcado como leído") if leido else _("Marcado como no leído"))

	def _marcar_todos_leidos(self) -> None:
		self.nucleo.repositorio.marcar_todos_leidos()
		self._refrescar_avisos()
		comunes.anunciar(_("Todos los avisos marcados como leídos"))

	def _borrar_aviso(self) -> None:
		aviso = self.aviso_actual()
		if aviso is None:
			return
		fila = self.lista_avisos.fila_actual()
		self.nucleo.repositorio.borrar_avisos([aviso["id"]])
		self._refrescar_avisos(-1)
		if self.lista_avisos.numero_filas():
			self.lista_avisos.enfocar_fila(min(fila, self.lista_avisos.numero_filas() - 1), anunciar=False)
		comunes.anunciar(_("Aviso borrado"))

	def _borrar_todos_avisos(self) -> None:
		if comunes.preguntar(self, _("¿Borrar todos los avisos? No se puede deshacer."), _("Borrar avisos"), peligroso=True):
			self.nucleo.repositorio.borrar_avisos(None)
			self._refrescar_avisos()
			comunes.anunciar(_("Avisos borrados"))
		self.lista_avisos.SetFocus()

	# ════════════════════════════════════════════════════════════════════════
	# Acciones de producto
	# ════════════════════════════════════════════════════════════════════════

	def _requerir_producto(self) -> dict[str, Any] | None:
		producto = self.producto_actual()
		if producto is None:
			comunes.anunciar(_("No hay ningún producto seleccionado"))
		return producto

	def _al_navegador(self, _evento: wx.CommandEvent | None) -> None:
		producto = self._requerir_producto()
		if producto:
			self.abrir_navegador(int(producto["id"]))

	def abrir_navegador(self, producto_id: int) -> None:
		producto = self.nucleo.repositorio.producto(producto_id)
		if producto and not comunes.abrir_en_navegador(producto["url"]):
			comunes.error(self, _("No se pudo abrir el navegador."), _("Abrir en el navegador"))

	def _al_detalles(self, _evento: wx.CommandEvent | None) -> None:
		producto = self._requerir_producto()
		if producto:
			self.abrir_detalles(int(producto["id"]))

	def abrir_detalles(self, producto_id: int) -> None:
		"""Abre los detalles (modal). Al cerrar, el foco vuelve a la lista."""
		from app.ui.dialogo_detalles import DialogoDetalles

		if self._detalles is not None:
			self._detalles.Raise()
			return
		producto = self.nucleo.repositorio.producto(producto_id)
		if producto is None:
			comunes.mensaje(self, _("Ese producto ya no existe."), _("Detalles"), wx.ICON_WARNING)
			return
		historial = self.nucleo.repositorio.historial(producto_id)
		acciones = {
			"navegador": self.abrir_navegador,
			"comprobar": lambda pid: self.comprobar([pid]),
			"editar": self.editar_producto,
			"copiar": self.copiar_enlace,
			"elegir_precio": self.elegir_precio_producto,
			"variante": self.elegir_variante_producto,
			"abrir_tienda": self.abrir_tienda_de_producto,
		}
		dialogo = DialogoDetalles(self, producto, historial, acciones, self._leer_preferencias)
		self._detalles = dialogo
		try:
			dialogo.ShowModal()
		finally:
			self._detalles = None
			dialogo.Destroy()
		self.recargar_datos(producto_id)
		self._enfocar_lista()

	def _recargar_detalles(self) -> None:
		if self._detalles is None:
			return
		producto = self.nucleo.repositorio.producto(int(self._detalles.producto["id"]))
		if producto is not None:
			self._detalles.recargar(producto, self.nucleo.repositorio.historial(int(producto["id"])))

	def _al_comprobar_producto(self, _evento: wx.CommandEvent | None) -> None:
		producto = self._requerir_producto()
		if producto:
			self.comprobar([int(producto["id"])])

	def _al_editar(self, _evento: wx.CommandEvent | None) -> None:
		producto = self._requerir_producto()
		if producto:
			self.editar_producto(int(producto["id"]))

	def editar_producto(self, producto_id: int) -> None:
		from app.ui.dialogo_producto import DialogoProducto

		producto = self.nucleo.repositorio.producto(producto_id)
		if producto is None:
			return
		padre = self._detalles or self

		def al_elegir_precio() -> str | None:
			self.elegir_precio_producto(producto_id, comprobar_despues=False)
			nuevo = self.nucleo.repositorio.producto(producto_id) or {}
			return nuevo.get("selector_precio")

		dialogo = DialogoProducto(padre, self.nucleo, producto, al_elegir_precio=al_elegir_precio)
		try:
			if dialogo.ShowModal() != wx.ID_OK:
				return
			datos = dialogo.datos()
		finally:
			dialogo.Destroy()
		otro = self.nucleo.repositorio.producto_por_url(datos["url"])
		if otro is not None and otro["id"] != producto_id:
			comunes.error(padre, _("Ya sigue otro producto con esa dirección: {nombre}.").format(nombre=otro["nombre"]), _("Editar producto"))
			return
		cambio_pagina = datos["url"] != producto["url"] or (datos["selector_precio"] or "") != (producto.get("selector_precio") or "")
		if datos["url"] != producto["url"]:
			datos["tienda_id"], _nombre = self.nucleo.tienda_para(datos["url"])
		if not datos["nombre"]:
			datos.pop("nombre")
		self.nucleo.repositorio.actualizar_producto(producto_id, **datos)
		self.recargar_datos(producto_id)
		self._recargar_detalles()
		comunes.anunciar(_("Producto guardado"))
		if cambio_pagina:
			self.comprobar([producto_id])

	def _al_mover(self, _evento: wx.CommandEvent | None) -> None:
		producto = self._requerir_producto()
		if not producto:
			return
		categorias = self.nucleo.repositorio.categorias()
		opciones = [SIN_CATEGORIA] + [c["nombre"] for c in categorias]
		dialogo = wx.SingleChoiceDialog(self, _("Categoría de «{nombre}»:").format(nombre=producto["nombre"]),
			_("Mover a categoría"), opciones)
		actual = next((i for i, c in enumerate(categorias, start=1) if c["id"] == producto.get("categoria_id")), 0)
		dialogo.SetSelection(actual)
		try:
			if dialogo.ShowModal() != wx.ID_OK:
				return
			indice = dialogo.GetSelection()
		finally:
			dialogo.Destroy()
		categoria_id = categorias[indice - 1]["id"] if indice > 0 else None
		self.nucleo.repositorio.mover_a_categoria([int(producto["id"])], categoria_id)
		self.recargar_datos(int(producto["id"]))
		comunes.anunciar(_("Movido a {categoria}").format(categoria=opciones[indice]))
		self._enfocar_lista()

	def _al_favorito(self, _evento: wx.CommandEvent | None) -> None:
		producto = self._requerir_producto()
		if producto:
			nuevo = not producto.get("favorito")
			self.nucleo.repositorio.actualizar_producto(int(producto["id"]), favorito=nuevo)
			self.recargar_datos(int(producto["id"]))
			comunes.anunciar(_("Añadido a favoritos") if nuevo else _("Quitado de favoritos"))

	def _al_pausa(self, _evento: wx.CommandEvent | None) -> None:
		producto = self._requerir_producto()
		if producto:
			activo = not producto.get("activo", 1)
			self.nucleo.repositorio.actualizar_producto(int(producto["id"]), activo=activo)
			self.recargar_datos(int(producto["id"]))
			comunes.anunciar(_("Comprobación reanudada") if activo else _("Comprobación en pausa"))

	def _al_copiar_enlace(self, _evento: wx.CommandEvent | None) -> None:
		producto = self._requerir_producto()
		if producto:
			self.copiar_enlace(int(producto["id"]))

	def copiar_enlace(self, producto_id: int) -> None:
		producto = self.nucleo.repositorio.producto(producto_id)
		if producto and comunes.copiar_texto(producto["url"]):
			comunes.anunciar(_("Enlace copiado"))
			self.SetStatusText(_("Enlace copiado: {url}").format(url=producto["url"]))

	def _al_eliminar(self, _evento: wx.CommandEvent | None) -> None:
		producto = self._requerir_producto()
		if not producto:
			return
		texto = _("¿Eliminar «{nombre}» y su historial de precios?").format(nombre=producto.get("nombre") or producto["url"])
		if not comunes.preguntar(self, texto, _("Eliminar producto"), peligroso=True):
			self._enfocar_lista()
			return
		fila = self.lista.fila_actual()
		self.nucleo.repositorio.eliminar_productos([int(producto["id"])])
		self.recargar_datos(-1)
		if self.lista.numero_filas():
			self.lista.enfocar_fila(min(max(fila, 0), self.lista.numero_filas() - 1), anunciar=False)
		comunes.anunciar(_("Producto eliminado"))
		self._enfocar_lista()

	# ════════════════════════════════════════════════════════════════════════
	# Añadir producto
	# ════════════════════════════════════════════════════════════════════════

	def _al_anadir(self, _evento: wx.CommandEvent | None) -> None:
		texto = comunes.leer_portapapeles().strip()
		url = texto if es_url(texto) else (extraer_primera_url(texto) or "")
		self.anadir_producto(url)

	def anadir_producto(self, url_inicial: str = "") -> int | None:
		"""Añadir con comprobación inmediata: «Encontrado: ... ¿Guardar?»."""
		from app.ui.dialogo_producto import DialogoProducto

		valores: dict[str, Any] | None = None
		while True:
			dialogo = DialogoProducto(self, self.nucleo, None, url_inicial=url_inicial, valores=valores)
			try:
				if dialogo.ShowModal() != wx.ID_OK:
					self._enfocar_lista()
					return None
				datos = dialogo.datos()
			finally:
				dialogo.Destroy()
			valores = datos
			existente = self.nucleo.repositorio.producto_por_url(datos["url"])
			if existente is not None:
				eleccion = comunes.elegir(self, _("Ya sigue este producto: {nombre}. ¿Quiere abrirlo?").format(
					nombre=existente.get("nombre") or existente["url"]), _("Añadir producto"), [_("&Abrir el producto"), _("&Cancelar")])
				if eleccion == 0:
					self.abrir_detalles(int(existente["id"]))
				return None
			dominio = dominio_de(datos["url"])
			tienda = self.nucleo.repositorio.tienda_por_dominio(dominio) or {}

			def trabajo(cancelado: threading.Event, datos=datos, dominio=dominio, tienda=tienda):
				try:
					return self.nucleo.comprobador.analizar(
						datos["url"], dominio, nombre_tienda=tienda.get("nombre", ""),
						selector_producto=datos["selector_precio"], selector_tienda=tienda.get("selector_precio"),
						selector_titulo=tienda.get("selector_titulo"), selector_disponible=tienda.get("selector_disponible"),
						modo_descarga=tienda.get("modo_descarga") or "auto", cancelado=cancelado, lanzar=False,
					)
				finally:
					self.nucleo.bd.cerrar_lectura_del_hilo()

			try:
				resultado = espera.ejecutar(self, _("Añadir producto"), _("Comprobando la página de {dominio}...").format(dominio=dominio), trabajo)
			except espera.Cancelado:  # auditoria: ignorar except-silencioso - cancelar la espera vuelve al diálogo: es el flujo normal
				continue
			except ErrorComprobacion as error:
				resultado = Resultado()
				motivo = error.mensaje
			except Exception as error:  # noqa: BLE001 - se explica y se registra
				log.exception("Fallo inesperado al comprobar un producto nuevo")
				comunes.error(self, _("No se pudo comprobar la página: {error}").format(error=error), _("Añadir producto"))
				continue
			else:
				motivo = resultado.error or ""
			para_tienda = False
			if resultado.dudoso:
				# Selección asistida: el usuario elige el precio entre los candidatos.
				eleccion = self._elegir_candidato(resultado.candidatos, _(
					"No he encontrado el precio con seguridad. Elige el correcto:"))
				if eleccion is not None:
					candidato, selector, huella, para_tienda = eleccion
					datos.update(selector_precio=selector, huella_selector=huella)
					resultado.precio, resultado.origen_precio, resultado.confianza = candidato.valor, ORIGEN_ELEGIDO, "alta"
					resultado.disponible = True if resultado.disponible is None else resultado.disponible
			if resultado.valido:
				if resultado.desde and resultado.variantes:
					eleccion = comunes.elegir(
						self, _("Encontrado: {datos}. Este producto tiene variantes con precios distintos.").format(
							datos=describir_resultado(resultado)),
						_("Añadir producto"), [_("Guardar el precio «&desde»"), _("Elegir &variante"), _("&Editar"), _("&Cancelar")],
					)
					if eleccion == 1:
						variante = elegir_variante(self, resultado.variantes)
						if variante is None:
							continue
						datos["variante"] = variante.clave or variante.nombre
						resultado.precio, resultado.desde = variante.precio, False
						if variante.disponible is not None:
							resultado.disponible = variante.disponible
						eleccion = 0
				else:
					eleccion = comunes.elegir(
						self, _("Encontrado: {datos}. ¿Guardar?").format(datos=describir_resultado(resultado)),
						_("Añadir producto"), [_("&Guardar"), _("&Editar"), _("&Cancelar")],
					)
					if eleccion == 1:
						eleccion = 2
					elif eleccion == 2:
						eleccion = 3
				if eleccion in (1, 2):
					continue
				if eleccion != 0:
					self._enfocar_lista()
					return None
			else:
				opciones = [_("&Guardar igualmente"), _("&Editar el selector"), _("&Cancelar")]
				if resultado.bloqueo:
					opciones.insert(2, _("Abrir la tienda en la &app"))
				eleccion = comunes.elegir(
					self,
					_("No se encontró el precio: {motivo}\n\nPuede guardarlo igualmente (se volverá a intentar en cada "
						"comprobación) o editar el selector propio.").format(motivo=motivo or _("sin precio")),
					_("Añadir producto"), opciones,
				)
				if eleccion == 1:
					continue
				if resultado.bloqueo and eleccion == 2:
					self.abrir_tienda_en_app(datos["url"])
					continue
				if eleccion != 0:
					self._enfocar_lista()
					return None
				resultado = None
			campos = {k: v for k, v in datos.items() if k != "url"}
			try:
				producto_id = self.nucleo.anadir_producto(datos["url"], resultado, **campos)
			except ErrorDatos as error:
				comunes.error(self, str(error), _("Añadir producto"))
				return None
			if para_tienda and datos.get("selector_precio"):
				producto = self.nucleo.repositorio.producto(producto_id) or {}
				if producto.get("tienda_id"):
					self.nucleo.repositorio.actualizar_tienda(int(producto["tienda_id"]), selector_precio=datos["selector_precio"])
			if self.seccion not in (vistas.TODOS, vistas.FAVORITOS, vistas.OFERTAS):
				self._aplicar_seccion(vistas.TODOS, enfocar=False)
			self.recargar_datos(producto_id)
			self._enfocar_lista()
			comunes.anunciar(_("Producto añadido"))
			return producto_id

	# ════════════════════════════════════════════════════════════════════════
	# Selección asistida, variantes y navegador integrado
	# ════════════════════════════════════════════════════════════════════════

	def _elegir_candidato(self, candidatos: list, texto: str, permitir_tienda: bool = True):
		"""Lista accesible de candidatos → (candidato, selector, huella, para_tienda) o ``None``."""
		from app.services import seleccion

		generado: dict[str, Any] = {}

		def validar(candidato) -> str | None:
			try:
				generado["selector"], generado["huella"] = seleccion.selector_para(candidato)
			except seleccion.ErrorSeleccion as error:
				return str(error)
			return None

		elegido = elegir_precio(self._detalles or self, candidatos, texto, validar, permitir_tienda)
		if elegido is None:
			return None
		candidato, para_tienda = elegido
		comunes.anunciar(_("Precio guardado: {precio}. Se usará esta posición de la página en las próximas comprobaciones.").format(
			precio=formato_importe(candidato.valor)))
		return candidato, generado["selector"], generado["huella"], para_tienda

	def elegir_precio_producto(self, producto_id: int, comprobar_despues: bool = True) -> None:
		"""«Elegir el precio en la página» (detalles y Editar): descarga y enseña todos los candidatos."""
		producto = self.nucleo.repositorio.producto(producto_id)
		if producto is None:
			return
		padre = self._detalles or self

		def trabajo(cancelado: threading.Event):
			try:
				return self.nucleo.comprobador.pagina_para_elegir(
					producto["url"], producto.get("dominio") or "", producto.get("tienda_modo_descarga") or "auto", cancelado)
			finally:
				self.nucleo.bd.cerrar_lectura_del_hilo()

		try:
			candidatos = espera.ejecutar(padre, _("Elegir el precio"), _("Descargando la página..."), trabajo)
		except espera.Cancelado:
			return
		except ErrorComprobacion as error:
			comunes.error(padre, error.mensaje, _("Elegir el precio"))
			return
		if not candidatos:
			comunes.mensaje(padre, _("No se ha encontrado ningún importe en la página."), _("Elegir el precio"), wx.ICON_WARNING)
			return
		eleccion = self._elegir_candidato(candidatos, _("Elige el precio correcto de «{nombre}»:").format(nombre=producto.get("nombre") or ""))
		if eleccion is None:
			return
		candidato, selector, huella, para_tienda = eleccion
		self.nucleo.repositorio.actualizar_producto(producto_id, selector_precio=selector, huella_selector=huella)
		if para_tienda and producto.get("tienda_id"):
			self.nucleo.repositorio.actualizar_tienda(int(producto["tienda_id"]), selector_precio=selector)
		self.recargar_datos(producto_id)
		if comprobar_despues:
			self.comprobar([producto_id])

	def elegir_variante_producto(self, producto_id: int) -> None:
		"""«Elegir variante»: vuelve a leer la página y ofrece las variantes con su precio."""
		producto = self.nucleo.repositorio.producto(producto_id)
		if producto is None:
			return
		padre = self._detalles or self
		argumentos = self.nucleo.comprobador.argumentos(producto)
		argumentos["variante"] = None

		def trabajo(cancelado: threading.Event):
			try:
				return self.nucleo.comprobador.analizar(
					producto["url"], producto.get("dominio") or "", cancelado=cancelado, lanzar=False, **argumentos)
			finally:
				self.nucleo.bd.cerrar_lectura_del_hilo()

		try:
			resultado = espera.ejecutar(padre, _("Elegir variante"), _("Descargando la página..."), trabajo)
		except espera.Cancelado:
			return
		except ErrorComprobacion as error:
			comunes.error(padre, error.mensaje, _("Elegir variante"))
			return
		if not resultado.variantes:
			comunes.mensaje(padre, _("La página no ofrece variantes con precios distintos."), _("Elegir variante"))
			return
		variante = elegir_variante(padre, resultado.variantes)
		if variante is None:
			return
		self.nucleo.repositorio.actualizar_producto(producto_id, variante=variante.clave or variante.nombre, desde=False)
		comunes.anunciar(_("Variante elegida: {nombre}").format(nombre=variante.nombre))
		self.comprobar([producto_id])

	def abrir_tienda_en_app(self, url: str) -> None:
		"""«Abrir la tienda en la app»: la página en el navegador integrado, visible."""
		if not self.navegador.mostrar(url):
			eleccion = comunes.elegir(
				self._detalles or self, MENSAJE_SIN_MOTOR, _("Navegador integrado"),
				[_("Abrir la página de &descarga de WebView2"), _("&Cerrar")],
			)
			if eleccion == 0:
				comunes.abrir_en_navegador(URL_WEBVIEW2)
			return
		comunes.anunciar(_("Página de la tienda abierta. Escape la cierra y vuelve a la aplicación."))

	def abrir_tienda_de_producto(self, producto_id: int) -> None:
		producto = self.nucleo.repositorio.producto(producto_id)
		if producto is not None:
			self.abrir_tienda_en_app(producto["url"])

	# ════════════════════════════════════════════════════════════════════════
	# Comprobación de precios
	# ════════════════════════════════════════════════════════════════════════

	def comprobar(self, ids: list[int] | None = None, automatica: bool = False) -> bool:
		"""Comprueba en segundo plano (todos los activos si ``ids`` es ``None``)."""
		if self._comprobacion is not None:
			if not automatica:
				comunes.anunciar(_("Ya hay una comprobación en curso"))
				self.SetStatusText(_("Ya hay una comprobación en curso."))
			return False
		self._comprobacion_automatica = automatica
		self._hitos.reiniciar()
		uno = ids is not None and len(ids) == 1
		self.SetStatusText(_("Comprobando el producto...") if uno else _("Comprobando los precios..."))
		if not automatica:
			comunes.anunciar(_("Comprobando"))
		self.elementos_menu["cancelar_comprobacion"].Enable(True)

		def trabajo(tarea) -> Any:
			try:
				return self.nucleo.comprobador.comprobar(
					ids, cancelado=tarea.token, al_progresar=lambda hecho, total, nombre: tarea.progresar(hecho, total, nombre),
					incluir_pausados=ids is not None,
				)
			finally:
				self.nucleo.bd.cerrar_lectura_del_hilo()

		self._comprobacion = self.tareas.enviar(
			trabajo, al_terminar=lambda r: self._al_terminar_comprobacion(r, ids), al_fallar=self._al_fallar_comprobacion,
			al_progresar=self._al_progresar_comprobacion, clave_unica="comprobar", nombre="comprobar",
		)
		return self._comprobacion is not None

	def _al_progresar_comprobacion(self, progreso: Any) -> None:
		total = int(progreso.total or 0)
		self.SetStatusText(_("Comprobando: {hecho} de {total}. {nombre}").format(hecho=int(progreso.hecho), total=total, nombre=progreso.texto))
		if self.bandeja is not None:
			self.bandeja.mostrar(_("{app}: comprobando {hecho} de {total}").format(app=NOMBRE_APLICACION, hecho=int(progreso.hecho), total=total))
		hito = self._hitos.nuevo_hito(progreso.porcentaje)
		if hito is not None and hito < 100 and not self._comprobacion_automatica and total > 3:
			comunes.anunciar(_("{n} %").format(n=hito))

	def _fin_comprobacion(self) -> None:
		self._comprobacion = None
		self.elementos_menu["cancelar_comprobacion"].Enable(False)
		if self.bandeja is not None:
			self.bandeja.mostrar(NOMBRE_APLICACION)

	def _al_terminar_comprobacion(self, resumen: Any, ids: list[int] | None) -> None:
		self._fin_comprobacion()
		if ids is None and not resumen.cancelado:
			self.nucleo.anotar_comprobacion(resumen.fecha)
		texto = resumen.texto()
		if ids is not None and len(ids) == 1 and resumen.total == 1:
			producto = self.nucleo.repositorio.producto(ids[0])
			if producto is not None:
				texto = self._texto_resultado_producto(producto)
		self.SetStatusText(_("{texto} ({hora})").format(texto=texto, hora=datetime.now().strftime("%H:%M")))
		if not self._comprobacion_automatica:
			comunes.anunciar(texto)
		self._notificar(resumen.avisos)
		if resumen.avisos and self._config.obtener("windows.sonidos", True):
			sonar(True)
		self.recargar_datos()
		self._recargar_detalles()

	def _texto_resultado_producto(self, producto: dict[str, Any]) -> str:
		if producto.get("ultimo_error"):
			return _("{nombre}: {error}").format(nombre=producto.get("nombre") or "", error=producto["ultimo_error"])
		return _("{nombre}: {precio}, {cambio}.").format(
			nombre=producto.get("nombre") or "", precio=vistas.texto_precio(producto), cambio=vistas.texto_cambio(producto))

	def _al_fallar_comprobacion(self, error: BaseException) -> None:
		self._fin_comprobacion()
		if isinstance(error, TareaCancelada):
			self.SetStatusText(_("Comprobación cancelada."))
			comunes.anunciar(_("Comprobación cancelada"))
		elif isinstance(error, TareaDuplicada):
			self.SetStatusText(_("Ya hay una comprobación en curso."))
		else:
			log.error("La comprobación falló: %s", error)
			self.SetStatusText(_("La comprobación falló. Los detalles están en el registro."))
			if self._comprobacion_automatica:
				espera = self.nucleo.aplazar_tras_fallo()
				log.info("Se reintentará la comprobación automática dentro de %d minutos", espera.total_seconds() // 60)
		self.recargar_datos()

	def _notificar(self, avisos: list[Any]) -> None:
		"""Una notificación por aviso (hasta 3) y, si hay más, además un resumen."""
		if not avisos:
			return
		for aviso in avisos[:MAX_NOTIFICACIONES_INDIVIDUALES]:
			self.notificador.mostrar(aviso.titulo, aviso.mensaje, aviso.producto_id, error=aviso.tipo == logica.ERROR)
		if len(avisos) > MAX_NOTIFICACIONES_INDIVIDUALES:
			self.notificador.mostrar(NOMBRE_APLICACION, logica.texto_resumen(len(avisos)), None)

	def _al_pulsar_notificacion(self, producto_id: int | None) -> None:
		self.restaurar()
		if producto_id is not None:
			wx.CallAfter(self.abrir_detalles, producto_id)
		else:
			wx.CallAfter(self.ir_a_seccion, vistas.AVISOS)

	def _comprobar_si_toca(self) -> None:
		if self._saliendo or self._comprobacion is not None:
			return
		if self.nucleo.toca_comprobar():
			log.info("Toca comprobar los precios (intervalo de %s horas)", self._config.obtener("precios.intervalo_horas"))
			self.comprobar(automatica=True)

	def _al_programador(self, _evento: wx.TimerEvent) -> None:
		try:
			self._comprobar_si_toca()
		except Exception:
			log.exception("Error en el programador de comprobaciones")

	def _al_reanudar_equipo(self, evento: wx.Event) -> None:
		"""Al volver de la suspensión, se comprueba si toca (tras dar tiempo a la red)."""
		log.info("El equipo ha vuelto de la suspensión")
		wx.CallLater(30_000, self._comprobar_si_toca)
		evento.Skip()

	def _al_comprobar_todos(self, _evento: wx.CommandEvent | None) -> None:
		if not any(p.get("activo") for p in self._todos):
			comunes.mensaje(self, _("No hay productos activos que comprobar."), _("Comprobar todos"))
			return
		self.comprobar()

	def _al_cancelar_comprobacion(self, _evento: wx.CommandEvent | None) -> None:
		if self._comprobacion is not None:
			self.tareas.cancelar(self._comprobacion, _("Cancelada por el usuario"))
			self.SetStatusText(_("Cancelando la comprobación..."))
			comunes.anunciar(_("Cancelando"))

	# ════════════════════════════════════════════════════════════════════════
	# Archivo: importar y exportar
	# ════════════════════════════════════════════════════════════════════════

	def _al_importar(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.dialogo_importar import DialogoImportar

		with wx.FileDialog(self, _("Importar"), wildcard=_("Exportaciones de No Me Subas Los Precios (*.json)|*.json|Todos los archivos (*.*)|*.*"),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as selector:
			if selector.ShowModal() != wx.ID_OK:
				return
			ruta = selector.GetPath()
		try:
			datos = intercambio.leer_archivo(ruta)
			analisis = intercambio.analizar(self.nucleo.bd, datos)
		except intercambio.ErrorIntercambio as error:
			comunes.error(self, str(error), _("Importar"))
			return
		dialogo = DialogoImportar(self, analisis, os.path.basename(ruta))
		try:
			if dialogo.ShowModal() != wx.ID_OK:
				return
			opciones = dialogo.resultado()
		finally:
			dialogo.Destroy()
		if opciones["modo"] == intercambio.REEMPLAZAR and not comunes.preguntar(
			self, _("Se borrarán todos los productos, categorías, tiendas y avisos actuales y se cargará el archivo. "
				"Antes se guarda una copia de seguridad. ¿Continuar?"), _("Reemplazar todo"), peligroso=True):
			return
		try:
			from app.services import reglas

			resultado = espera.ejecutar(self, _("Importar"), _("Importando..."),
				lambda _c: intercambio.importar(self.nucleo.bd, datos, opciones["modo"], reglas.catalogo()))
		except espera.Cancelado:
			comunes.mensaje(self, _("La importación sigue en marcha o ya terminó; revise la lista."), _("Importar"))
			self.recargar_datos()
			return
		except Exception as error:  # noqa: BLE001 - la importación es atómica: se explica el motivo
			log.exception("Falló la importación")
			comunes.error(self, _("No se importó nada: {error}").format(error=error), _("Importar"))
			return
		texto = resultado.texto()
		if opciones["ajustes"] and resultado.ajustes:
			cambiados = self.nucleo.aplicar_ajustes_importados(resultado.ajustes)
			texto += " " + _("Ajustes importados: {n}.").format(n=cambiados)
		if resultado.copia is not None:
			texto += " " + _("Copia de seguridad previa: {nombre}.").format(nombre=resultado.copia.name)
		self.recargar_datos()
		comunes.mensaje(self, texto, _("Importar"))
		self._enfocar_lista()

	def _al_exportar(self, _evento: wx.CommandEvent | None) -> None:
		incluir = comunes.elegir(self, _("¿Incluir también los ajustes en el archivo?"), _("Exportar"),
			[_("&Sin ajustes"), _("&Con ajustes"), _("&Cancelar")])
		if incluir not in (0, 1):
			return
		with wx.FileDialog(self, _("Exportar"), defaultFile=intercambio.nombre_propuesto(),
				wildcard=_("Archivo JSON (*.json)|*.json"), style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as selector:
			if selector.ShowModal() != wx.ID_OK:
				return
			ruta = selector.GetPath()
		ajustes = self.nucleo.ajustes() if incluir == 1 else None
		try:
			datos = intercambio.exportar_json(self.nucleo.bd, ruta, ajustes)
		except intercambio.ErrorIntercambio as error:
			comunes.error(self, str(error), _("Exportar"))
			return
		texto = _("Exportados {n} productos a {archivo}.").format(n=len(datos["productos"]), archivo=os.path.basename(ruta))
		self.SetStatusText(texto)
		comunes.mensaje(self, texto, _("Exportar"))

	def _al_exportar_csv(self, _evento: wx.CommandEvent | None) -> None:
		with wx.FileDialog(self, _("Exportar a CSV"), defaultFile=intercambio.nombre_propuesto().replace(".json", ".csv"),
				wildcard=_("CSV para hojas de cálculo (*.csv)|*.csv"), style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as selector:
			if selector.ShowModal() != wx.ID_OK:
				return
			ruta = selector.GetPath()
		try:
			n = intercambio.exportar_csv(self.nucleo.repositorio.productos(), ruta)
		except intercambio.ErrorIntercambio as error:
			comunes.error(self, str(error), _("Exportar a CSV"))
			return
		texto = _("Exportados {n} productos a {archivo}.").format(n=n, archivo=os.path.basename(ruta))
		self.SetStatusText(texto)
		comunes.mensaje(self, texto, _("Exportar a CSV"))

	def _al_salir(self, _evento: wx.CommandEvent | None) -> None:
		self.salir()

	# ════════════════════════════════════════════════════════════════════════
	# Ver
	# ════════════════════════════════════════════════════════════════════════

	def _al_buscar(self, _evento: wx.CommandEvent | None) -> None:
		self.campo_buscar.SetFocus()
		self.campo_buscar.SelectAll()

	def _al_solo_activos(self, evento: wx.CommandEvent) -> None:
		self.cambiar_filtro("solo_activos", evento.IsChecked())

	def _al_solo_error(self, evento: wx.CommandEvent) -> None:
		self.cambiar_filtro("solo_error", evento.IsChecked())

	def _al_solo_agotados(self, evento: wx.CommandEvent) -> None:
		self.cambiar_filtro("solo_agotados", evento.IsChecked())

	def _al_barra_estado(self, evento: wx.CommandEvent) -> None:
		visible = evento.IsChecked()
		self._aplicar_barra_estado(visible)
		self._config.establecer("ventana.barra_estado", visible)

	def _aplicar_barra_estado(self, visible: bool) -> None:
		self.GetStatusBar().Show(visible)
		self.elementos_menu["barra_estado"].Check(visible)
		self.SendSizeEvent()

	# ════════════════════════════════════════════════════════════════════════
	# Herramientas
	# ════════════════════════════════════════════════════════════════════════

	def _al_categorias(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.dialogo_categorias import DialogoCategorias

		dialogo = DialogoCategorias(self, self.nucleo.repositorio, self._leer_preferencias)
		try:
			dialogo.ShowModal()
		finally:
			dialogo.Destroy()
		self.recargar_datos()
		self._enfocar_lista()

	def _al_tiendas(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.dialogo_tiendas import DialogoTiendas

		dialogo = DialogoTiendas(self, self.nucleo, self._leer_preferencias)
		try:
			dialogo.ShowModal()
		finally:
			dialogo.Destroy()
		self.recargar_datos()
		self._enfocar_lista()

	def _al_preferencias(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.dialogo_preferencias import DialogoPreferencias

		dialogo = DialogoPreferencias(
			self, self._config, anunciar=comunes.anunciar,
			botones_extra=((_("&Enviar una notificación de prueba"),
				_("Muestra una notificación de Windows para comprobar que llegan."), self.notificacion_de_prueba),),
		)
		try:
			dialogo.ShowModal()
		finally:
			dialogo.Destroy()
		self._enfocar_lista()

	def notificacion_de_prueba(self) -> None:
		mostrada = self.notificador.mostrar(
			_("Notificación de prueba"),
			_("Si lee esto, las notificaciones de {nombre} funcionan.").format(nombre=NOMBRE_APLICACION),
		)
		if not mostrada:
			comunes.mensaje(None, _("Windows no aceptó la notificación. Revise en Configuración de Windows, Sistema, "
				"Notificaciones, que estén activadas."), _("Notificación de prueba"), wx.ICON_WARNING)

	def _ajustes_colores(self) -> colores.Ajustes:
		"""Colores de la lista vigentes; con el contraste alto de Windows, ninguno."""
		if alto_contraste_activo():
			return colores.Ajustes(activos=False)
		return colores.leer_ajustes(self._config.obtener)

	def _programar_repintado(self) -> None:
		"""Repinta las listas una sola vez aunque cambien varias claves a la vez (hilo principal)."""
		if self._repintado_pendiente:
			return
		self._repintado_pendiente = True

		def repintar() -> None:
			self._repintado_pendiente = False
			if self:
				# En la sección Avisos repinta los avisos; la otra lista se pinta al entrar en ella.
				self.refrescar_lista()

		wx.CallAfter(repintar)

	def _al_cambiar_colores_sistema(self, evento: wx.SysColourChangedEvent) -> None:
		self._programar_repintado()
		evento.Skip()

	def _aplicar_origen_actualizaciones(self) -> None:
		"""Manifiestos del origen elegido en Preferencias (servidor, GitHub, los dos o una dirección)."""
		from app.services import actualizador

		if self.actualizador is None:
			return
		urls = actualizador.urls_de_origen(
			self._config.obtener("precios.origen_actualizaciones", "servidor"),
			self._config.obtener("precios.url_actualizaciones", ""),
		)
		self.actualizador.urls_manifiesto = urls
		self.actualizador.url_manifiesto = urls[0]
		log.info("Origen de las actualizaciones: %s", ", ".join(urls))

	def _al_cambiar_configuracion(self, clave: str, anterior: Any, nuevo: Any) -> None:
		"""Las preferencias se aplican al momento (llega desde cualquier hilo)."""
		if clave in ("precios.origen_actualizaciones", "precios.url_actualizaciones"):
			wx.CallAfter(self._aplicar_origen_actualizaciones)
		if clave.startswith("colores."):
			wx.CallAfter(self._programar_repintado)
		if clave == "windows.iniciar_con_windows":
			threading.Thread(target=self._aplicar_inicio_windows, args=(bool(nuevo),), name="inicio-windows", daemon=True).start()
		elif clave == "precios.buscar_actualizaciones" and nuevo and self.comprobador_actualizaciones is None and self.actualizador:
			wx.CallAfter(self._iniciar_actualizaciones)
		elif clave.startswith("precios.intervalo_horas"):
			wx.CallAfter(self._mostrar_ultima_comprobacion)

	def _aplicar_inicio_windows(self, activado: bool) -> None:
		from app.services import inicio_windows

		try:
			inicio_windows.aplicar(activado)
		except ErrorInicio as error:
			wx.CallAfter(comunes.error, self if self else None, str(error), _("Iniciar con Windows"))

	def _abrir_carpeta(self, carpeta: Any) -> None:
		if hasattr(os, "startfile"):
			try:
				os.startfile(carpeta)  # noqa: S606 - carpeta propia de la aplicación
			except OSError:
				log.exception("No se pudo abrir la carpeta %s", carpeta)

	def _al_carpeta_datos(self, _evento: wx.CommandEvent | None) -> None:
		self._abrir_carpeta(paths.ruta_datos())

	def _al_carpeta_registros(self, _evento: wx.CommandEvent | None) -> None:
		self._abrir_carpeta(paths.ruta_registros())

	# ════════════════════════════════════════════════════════════════════════
	# Ayuda
	# ════════════════════════════════════════════════════════════════════════

	def _al_manual(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui import visor_ayuda

		visor_ayuda.abrir_manual(self)

	def _al_teclas(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui import visor_ayuda

		visor_ayuda.abrir_teclas(self)

	def _al_novedades(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui import visor_ayuda

		visor_ayuda.abrir_novedades(self)

	def _al_ayuda_contextual(self, _evento: wx.CommandEvent | None) -> None:
		foco = wx.Window.FindFocus()
		texto = foco.GetHelpText() if foco else ""
		if not texto:
			texto = _("No hay ayuda para este control. Pulse F1 para abrir el manual.")
		comunes.mensaje(self, texto, _("Ayuda"))

	def _al_actualizaciones(self, _evento: wx.CommandEvent | None) -> None:
		from app.services import actualizador
		from app.ui import dialogo_actualizacion

		if self.actualizador is None:
			self.actualizador = actualizador.configuracion_por_defecto(APP_VERSION)
		self._aplicar_origen_actualizaciones()
		dialogo_actualizacion.comprobar_manualmente(self, self.actualizador, anunciar=voz.hablar)

	def _al_acerca_de(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.acerca_de import mostrar_acerca_de

		mostrar_acerca_de(self)
