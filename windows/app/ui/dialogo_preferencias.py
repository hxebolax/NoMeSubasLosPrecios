"""Diálogo de preferencias accesible y declarativo.

Añadir una opción nueva es añadir un ``Opcion(...)`` a ``PAGINAS`` (y su valor
por defecto en ``configuracion.VALORES_POR_DEFECTO``); el diálogo crea el
control, su etiqueta, su ayuda, la carga y el guardado.

Accesibilidad (por qué está hecho así):

- Una página de ``wx.Notebook`` por categoría: el lector anuncia el nombre de
  la pestaña y Ctrl+Tab / Ctrl+Mayús+Tab cambian de página.
- Cada control va PRECEDIDO por su ``wx.StaticText``, creado justo antes: en
  Windows el lector toma de ahí el nombre del control (``name=`` o ``SetName``
  no nombran los controles nativos). Las casillas llevan su propio texto.
- La etiqueta puede llevar ``&`` para saltar al control con Alt+letra.
- Ctrl+H lee la ayuda del control con el foco (``SetHelpText``) en un cuadro de
  texto de solo lectura que se puede recorrer línea a línea.
- Botones en español con acelerador: &Aceptar, &Cancelar, A&plicar y
  &Restablecer valores de fábrica. Escape cancela. El foco empieza en la
  primera opción.
- Cancelar no cambia nada: los valores solo se escriben al Aplicar o Aceptar.
  Lo ya aplicado no se deshace al cancelar después (comportamiento estándar).
- Aplicar/Aceptar validan TODO antes de guardar; si algo no vale, se avisa, se
  lleva el foco a ese control y no se guarda nada.
- Al guardar, la configuración avisa a sus suscriptores: las ventanas abiertas
  aplican la preferencia al momento.

PLANTILLA del agente «configuracion».
"""

from __future__ import annotations

import builtins
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import wx
import wx.adv
import wx.lib.scrolledpanel as scrolled

from app.core.configuracion import Configuracion, ErrorValidacion
from app.services import actualizador, colores
from app.services.importes import porcentaje_para_campo
from app.ui.accesibilidad.visual import alto_contraste_activo

log = logging.getLogger(__name__)


def _(texto: str) -> str:
	"""Traduce con gettext si está instalado en builtins; si no, devuelve el texto."""
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


def N_(texto: str) -> str:  # noqa: N802 - convención de gettext
	"""Marca un texto para traducir SIN traducirlo aún.

	Los descriptores se crean al importar el módulo, antes de que gettext esté
	listo; se traducen al construir el diálogo con ``_()``.
	"""
	return texto


# Tipos de opción admitidos. COLOR (1.1.0): lista desplegable nativa de solo
# lectura en la que cada elemento lleva una muestra del color y su nombre (el
# lector lee el nombre).
BOOL, ENTERO, DECIMAL, TEXTO, OPCION, CARPETA, SECRETO, COLOR = (
	"bool", "entero", "decimal", "texto", "opcion", "carpeta", "secreto", "color",
)
_PALETA = tuple((c.id, c.nombre) for c in colores.PALETA)


def muestra_color(ventana: wx.Window, identificador: str) -> wx.Bitmap:
	"""Cuadradito con el color: fondo claro, borde y franja del tono de texto.

	«Sin color» es un cuadrado blanco tachado en diagonal.
	"""
	lado = ventana.FromDIP(16)
	mapa = wx.Bitmap(lado, lado)
	dc = wx.MemoryDC(mapa)
	try:
		elegido = colores.color(identificador)
		borde = wx.Colour(elegido.texto) if elegido.texto else wx.Colour(96, 96, 96)
		dc.SetBackground(wx.Brush(wx.Colour(elegido.fondo) if elegido.fondo else wx.WHITE))
		dc.Clear()
		dc.SetPen(wx.Pen(borde, max(1, ventana.FromDIP(1))))
		if elegido.texto:
			dc.SetBrush(wx.Brush(borde))
			dc.DrawRectangle(lado * 2 // 3, 0, lado - lado * 2 // 3, lado)
		else:
			dc.DrawLine(0, lado - 1, lado - 1, 0)
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		dc.DrawRectangle(0, 0, lado, lado)
	finally:
		dc.SelectObject(wx.NullBitmap)
	return mapa


@dataclass(frozen=True)
class Opcion:
	"""Descriptor de una preferencia.

	:param clave: «seccion.clave» en la configuración (o nombre del secreto).
	:param etiqueta: texto visible y nombre para el lector (con ``&`` opcional).
	:param tipo: ``bool``, ``entero``, ``decimal``, ``texto``, ``opcion``, ``color``,
		``carpeta`` o ``secreto``.
	:param ayuda: explicación que se lee con Ctrl+H.
	:param minimo, maximo: límites numéricos (si faltan, se toman de la regla
		de la configuración).
	:param incremento: paso de los decimales.
	:param opciones: pares ``(valor, etiqueta)`` para el tipo ``opcion``.
	:param activa_si: ``(clave, valor)``: el control solo está activo si esa otra
		opción vale eso (se actualiza al momento).
	:param validar: ``validar(valor) -> mensaje o None`` además de las reglas de la
		configuración; solo se aplica si el control está activo.
	"""

	clave: str
	etiqueta: str
	tipo: str
	ayuda: str = ""
	minimo: float | None = None
	maximo: float | None = None
	incremento: float = 0.1
	opciones: tuple[tuple[Any, str], ...] = ()
	activa_si: tuple[str, Any] | None = None
	validar: Callable[[Any], str | None] | None = None


def _validar_url_actualizaciones(valor: Any) -> str | None:
	if actualizador.base_personalizada(str(valor or "")):
		return None
	return N_("Escribe la dirección de una carpeta que empiece por https:// (por ejemplo, "
		"https://mi-servidor.es/NoMeSubasLosPrecios/), o elige otro origen.")


@dataclass(frozen=True)
class Pagina:
	"""Una pestaña del diálogo."""

	titulo: str
	opciones: tuple[Opcion, ...]


# ── Preferencias de No Me Subas Los Precios ──────────────────────────────────
# Aceleradores: únicos en cada página y distintos de los botones (Restablecer,
# Enviar una notificación de prueba, Aceptar, Cancelar, Aplicar: R, E, A, C, P).
PAGINAS: tuple[Pagina, ...] = (
	Pagina(N_("Comprobación"), (
		Opcion("precios.intervalo_horas", N_("Comprobar los precios ca&da:"), OPCION,
			N_("Cada cuánto se comprueban todos los productos activos mientras la aplicación está abierta "
				"(también en la bandeja)."),
			opciones=((1, N_("1 hora")), (2, N_("2 horas")), (3, N_("3 horas")), (6, N_("6 horas")),
				(12, N_("12 horas")), (24, N_("24 horas")))),
		Opcion("precios.comprobar_al_iniciar", N_("Comprobar al &iniciar la aplicación si toca"), BOOL,
			N_("Al abrir la aplicación, si la última comprobación es más vieja que el intervalo, comprueba en segundo plano.")),
		Opcion("precios.pausa_entre_peticiones", N_("Pa&usa entre páginas de la misma tienda (segundos):"), ENTERO,
			N_("Segundos de espera entre un producto y el siguiente de la misma tienda, más un poco al azar. "
				"Con pausas cortas, algunas tiendas bloquean las comprobaciones.")),
		Opcion("precios.tiempo_espera", N_("&Tiempo máximo de espera por página (segundos):"), ENTERO,
			N_("Si una tienda tarda más en responder, la comprobación de ese producto falla y se reintenta la próxima vez.")),
		Opcion("precios.buscar_actualizaciones", N_("&Buscar actualizaciones de la aplicación al iniciar"), BOOL,
			N_("Como mucho una vez al día. Si no hay conexión, no molesta.")),
		Opcion("precios.origen_actualizaciones", N_("Descargar &las actualizaciones de:"), OPCION,
			N_("De dónde se descargan las versiones nuevas: del servidor del autor, de GitHub, de los dos (se usa el "
				"que tenga la versión más nueva y, si uno falla, el otro) o de una dirección tuya. Venga de donde venga, "
				"solo se instala una versión firmada por el autor."),
			opciones=tuple((valor, nombre) for valor, nombre in actualizador.ORIGENES)),
		Opcion("precios.url_actualizaciones", N_("Dirección personali&zada (https):"), TEXTO,
			N_("Solo con «Dirección personalizada»: la carpeta con la misma estructura que el servidor del autor "
				"(windows/version.json y el ZIP dentro de windows). Sirve, por ejemplo, para una copia en tu red."),
			activa_si=("precios.origen_actualizaciones", "personalizada"), validar=_validar_url_actualizaciones),
	)),
	Pagina(N_("Avisos"), (
		Opcion("precios.avisar_bajadas", N_("Avisar cuando &baje el precio"), BOOL,
			N_("Notificación cuando un producto baja de precio (respetando la alerta por porcentaje de cada producto).")),
		Opcion("precios.avisar_subidas", N_("Avisar cuando &suba el precio"), BOOL,
			N_("Notificación «¡Te han subido el precio!» cuando un producto sube.")),
		Opcion("precios.avisar_objetivo", N_("Avisar al llegar al precio &deseado"), BOOL,
			N_("Notificación cuando el precio llega al precio deseado del producto o lo baja.")),
		Opcion("precios.avisar_minimo", N_("Avisar de un &mínimo histórico"), BOOL,
			N_("Notificación cuando un producto marca el precio más bajo visto.")),
		Opcion("precios.avisar_disponible", N_("Avisar cuando &vuelva a estar disponible"), BOOL,
			N_("Notificación cuando un producto agotado vuelve a estar disponible (si el producto también lo pide).")),
		Opcion("precios.avisar_agotado", N_("Avisar cuando se ag&ote"), BOOL,
			N_("Notificación cuando un producto se agota.")),
		Opcion("precios.avisar_errores", N_("Avisar tras 3 errores se&guidos"), BOOL,
			N_("Notificación cuando un producto falla tres comprobaciones seguidas.")),
		Opcion("precios.cambio_minimo_porcentaje", N_("&Ignorar bajadas y subidas menores de (%):"), DECIMAL,
			N_("Los cambios más pequeños se guardan en el historial pero no avisan. 0 avisa de todos."), incremento=0.5),
		Opcion("precios.conservar_avisos_dias", N_("Conservar los avisos &hasta (días, 0 = siempre):"), ENTERO,
			N_("Los avisos más viejos se borran solos de la sección Avisos.")),
	)),
	Pagina(N_("Windows"), (
		Opcion("windows.iniciar_con_windows", N_("Iniciar con &Windows (en la bandeja)"), BOOL,
			N_("Crea un acceso directo en la carpeta Inicio de su usuario que abre la aplicación en la bandeja. "
				"Al desactivarlo se borra.")),
		Opcion("windows.minimizar_a_bandeja", N_("&Minimizar a la bandeja al cerrar la ventana"), BOOL,
			N_("Al cerrar la ventana, la aplicación sigue en la bandeja del sistema y sigue comprobando. "
				"Para salir de verdad, Archivo, Salir. Windows+B lleva a la bandeja.")),
		Opcion("windows.sonidos", N_("&Sonidos al terminar una comprobación con cambios"), BOOL,
			N_("Un sonido corto del sistema cuando una comprobación encuentra cambios.")),
		Opcion("general.anunciar_arranque", N_("Anunciar el arranque por &voz"), BOOL,
			N_("Dice el nombre de la aplicación al abrirla, antes de que aparezca la ventana.")),
	)),
	# Colores de la lista (1.1.0). Aceleradores: o, q, b, s, d, g (sin R, E, A, C, P de los botones).
	Pagina(N_("Colores"), (
		Opcion("colores.colores_lista", N_("C&olorear la lista según el estado"), BOOL,
			N_("Pinta de un color las filas de los productos que han bajado, subido, llegado al precio deseado o "
				"tienen algún problema, y los avisos de cada tipo. Es solo visual: la fila ya dice su estado al leerla. "
				"Con el contraste alto de Windows no se colorea nada.")),
		Opcion("colores.colores_modo", N_("&Qué se colorea:"), OPCION,
			N_("Fondo de la fila: un tono claro detrás del texto, que se ve más. Texto: las letras de la fila en un "
				"tono oscuro del color."),
			opciones=tuple((valor, nombre) for valor, nombre in colores.MODOS)),
		Opcion("colores.color_bajada", N_("Color de &bajada u oferta:"), COLOR,
			N_("Productos en oferta: han bajado en los últimos 7 días o están en su precio mínimo. "
				"También los avisos de bajada y de mínimo histórico."), opciones=_PALETA),
		Opcion("colores.color_subida", N_("Color de &subida:"), COLOR,
			N_("Productos que han subido de precio en los últimos 7 días, y los avisos de subida."), opciones=_PALETA),
		Opcion("colores.color_objetivo", N_("Color de precio &deseado alcanzado:"), COLOR,
			N_("Productos que han llegado al precio deseado o lo han bajado, y esos avisos."), opciones=_PALETA),
		Opcion("colores.color_problema", N_("Color de a&gotado o con problemas:"), COLOR,
			N_("Productos agotados, bloqueados por la tienda, sin precio, sin conexión o con error, y esos avisos."),
			opciones=_PALETA),
	)),
	Pagina(N_("Lectura de listas"), (
		Opcion("lectura.numero_fila", N_("Decir el &número de fila"), BOOL,
			N_("Al recorrer las columnas con izquierda y derecha, dice el número de fila. "
				"Si desactiva las tres opciones, se lee el contenido.")),
		Opcion("lectura.cabecera", N_("Decir el nombre de la co&lumna"), BOOL,
			N_("Al recorrer las columnas con izquierda y derecha, dice el nombre de la columna.")),
		Opcion("lectura.contenido", N_("Decir el con&tenido"), BOOL,
			N_("Al recorrer las columnas con izquierda y derecha, dice el contenido de la celda.")),
	)),
)


# ── Avisos modales (funciones de módulo para poder sustituirlas en pruebas) ──

def mostrar_aviso(padre: wx.Window | None, texto: str, titulo: str) -> None:
	"""Mensaje de error o aviso con botón en español."""
	dialogo = wx.MessageDialog(padre, texto, titulo, wx.OK | wx.ICON_WARNING)
	dialogo.SetOKLabel(_("&Aceptar"))
	try:
		dialogo.ShowModal()
	finally:
		dialogo.Destroy()


def confirmar(padre: wx.Window | None, texto: str, titulo: str) -> bool:
	"""Pregunta Sí/No (con «No» por defecto para las acciones que borran)."""
	dialogo = wx.MessageDialog(padre, texto, titulo, wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
	dialogo.SetYesNoLabels(_("&Sí"), _("&No"))
	try:
		return dialogo.ShowModal() == wx.ID_YES
	finally:
		dialogo.Destroy()


class DialogoAyuda(wx.Dialog):
	"""Muestra un texto de ayuda en un campo de solo lectura (navegable con flechas)."""

	def __init__(self, padre: wx.Window | None, titulo: str, texto: str) -> None:
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		sizer = wx.BoxSizer(wx.VERTICAL)
		etiqueta = wx.StaticText(self, label=_("&Ayuda:"))
		self.texto = wx.TextCtrl(self, value=texto, size=(420, 140),
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
		# Escape y el botón comparten ID_CANCEL: Escape cierra el cuadro.
		cerrar = wx.Button(self, wx.ID_CANCEL, _("&Cerrar"))
		sizer.Add(etiqueta, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
		sizer.Add(self.texto, 1, wx.EXPAND | wx.ALL, 10)
		sizer.Add(cerrar, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		self.SetSizerAndFit(sizer)
		self.SetEscapeId(wx.ID_CANCEL)
		self.Bind(wx.EVT_INIT_DIALOG, self._al_iniciar)

	def _al_iniciar(self, evento: wx.InitDialogEvent) -> None:
		self.texto.SetFocus()
		self.texto.SetInsertionPoint(0)
		evento.Skip()


def mostrar_ayuda(padre: wx.Window | None, titulo: str, texto: str) -> None:
	"""Abre ``DialogoAyuda`` de forma modal."""
	dialogo = DialogoAyuda(padre, titulo, texto)
	try:
		dialogo.ShowModal()
	finally:
		dialogo.Destroy()


class DialogoPreferencias(wx.Dialog):
	"""Diálogo de preferencias generado a partir de descriptores.

	:param padre: ventana padre.
	:param config: configuración de la aplicación.
	:param paginas: descriptores (por defecto ``PAGINAS``).
	:param secretos: almacén de secretos (``obtener``/``guardar_varios``) para
		las opciones de tipo ``secreto``; sin él, esas opciones no se muestran.
	:param anunciar: función opcional que dice un texto por el lector.
	:param botones_extra: ``(etiqueta, ayuda, acción)`` de botones propios junto a «Restablecer».
	"""

	def __init__(
		self,
		padre: wx.Window | None,
		config: Configuracion,
		paginas: tuple[Pagina, ...] | None = None,
		secretos: Any | None = None,
		anunciar: Callable[[str], None] | None = None,
		titulo: str | None = None,
		botones_extra: tuple[tuple[str, str, Callable[[], None]], ...] = (),
	) -> None:
		# Sin proveedor de ayuda, SetHelpText no guarda nada. Se instala uno si falta.
		if wx.HelpProvider.Get() is None:
			wx.HelpProvider.Set(wx.SimpleHelpProvider())
		super().__init__(padre, title=titulo or _("Preferencias"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._config = config
		self._secretos = secretos
		self._anunciar = anunciar
		# clave → (opción, control, índice de página)
		self._controles: dict[str, tuple[Opcion, wx.Window, int]] = {}
		# id de control (y de sus hijos, p. ej. el texto de un SpinCtrl) → clave
		self._clave_por_id: dict[int, str] = {}
		self._valores_secretos: dict[str, str] = {}
		# Filas de la vista previa de colores (tipo → texto pintado).
		self._muestras: dict[str, wx.StaticText] = {}

		sizer = wx.BoxSizer(wx.VERTICAL)
		self.libro = wx.Notebook(self)
		for indice, pagina in enumerate(paginas if paginas is not None else PAGINAS):
			panel = self._crear_pagina(pagina, indice)
			self.libro.AddPage(panel, _(pagina.titulo))
		sizer.Add(self.libro, 1, wx.EXPAND | wx.ALL, 8)

		botones = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_restablecer = wx.Button(self, label=_("&Restablecer valores de fábrica"))
		self.boton_aceptar = wx.Button(self, wx.ID_OK, _("&Aceptar"))
		self.boton_cancelar = wx.Button(self, wx.ID_CANCEL, _("&Cancelar"))
		self.boton_aplicar = wx.Button(self, wx.ID_APPLY, _("A&plicar"))
		self.boton_restablecer.SetHelpText(_("Pone todas las opciones con sus valores de fábrica. "
			"No se guarda nada hasta pulsar Aplicar o Aceptar."))
		botones.Add(self.boton_restablecer, 0, wx.ALL, 4)
		# Botones propios de la aplicación (por ejemplo, «Enviar una notificación de prueba»).
		self.botones_extra: list[wx.Button] = []
		for etiqueta, ayuda, accion in botones_extra:
			extra = wx.Button(self, label=etiqueta)
			extra.SetHelpText(ayuda)
			extra.Bind(wx.EVT_BUTTON, lambda _evento, accion=accion: accion())
			botones.Add(extra, 0, wx.ALL, 4)
			self.botones_extra.append(extra)
		botones.AddStretchSpacer()
		for boton in (self.boton_aceptar, self.boton_cancelar, self.boton_aplicar):
			botones.Add(boton, 0, wx.ALL, 4)
		sizer.Add(botones, 0, wx.EXPAND | wx.ALL, 4)
		self.SetSizerAndFit(sizer)
		# Alto suficiente para ver la vista previa de la pestaña Colores sin desplazarse.
		self.SetMinSize(self.FromDIP(wx.Size(560, 640)))

		self.boton_aceptar.SetDefault()
		self.SetEscapeId(wx.ID_CANCEL)
		self.boton_aceptar.Bind(wx.EVT_BUTTON, self._al_aceptar)
		self.boton_cancelar.Bind(wx.EVT_BUTTON, self._al_cancelar)
		self.boton_aplicar.Bind(wx.EVT_BUTTON, self._al_aplicar)
		self.boton_restablecer.Bind(wx.EVT_BUTTON, self._al_restablecer)
		# EVT_CHAR_HOOK ve la tecla antes que el control: en un cuadro de texto de
		# Windows, Ctrl+H sería «borrar hacia atrás».
		self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
		self.Bind(wx.EVT_INIT_DIALOG, self._al_iniciar)
		self.CentreOnParent()

	# ── Construcción ─────────────────────────────────────────────────────────

	def _crear_pagina(self, pagina: Pagina, indice: int) -> wx.Window:
		"""Crea el panel de una página, con la etiqueta de cada control justo antes."""
		panel = scrolled.ScrolledPanel(self.libro)
		sizer = wx.BoxSizer(wx.VERTICAL)
		for opcion in pagina.opciones:
			if opcion.tipo == SECRETO and self._secretos is None:
				log.warning("Opción secreta «%s» omitida: no se pasó almacén de secretos", opcion.clave)
				continue
			control = self._crear_opcion(panel, sizer, opcion)
			ayuda = _(opcion.ayuda)
			if ayuda:
				control.SetHelpText(ayuda)
			self._controles[opcion.clave] = (opcion, control, indice)
			self._registrar_ids(control, opcion.clave)
			self._escribir_control(opcion, control, self._valor_guardado(opcion))
		if any(opcion.tipo == COLOR for opcion in pagina.opciones):
			self._crear_vista_previa(panel, sizer)
		for opcion in pagina.opciones:
			if opcion.activa_si and opcion.activa_si[0] in self._controles:
				origen = self._controles[opcion.activa_si[0]][1]
				for evento in (wx.EVT_CHECKBOX, wx.EVT_CHOICE, wx.EVT_COMBOBOX):
					origen.Bind(evento, self._al_cambiar_dependencia)
		self._actualizar_dependencias()
		panel.SetSizer(sizer)
		# Desplaza la vista hasta el control enfocado (útil con muchas opciones).
		panel.SetupScrolling(scroll_x=False)
		return panel

	# ── Colores: vista previa y casilla que activa las demás opciones ─────────

	def _crear_vista_previa(self, panel: wx.Window, sizer: wx.Sizer) -> None:
		"""Una fila de ejemplo por estado, pintada como quedará en la lista (solo visual).

		Son ``StaticText``: no reciben el foco, así que no estorban al recorrer
		el diálogo con el tabulador. Se repinta al cambiar cualquier opción.
		"""
		titulo = wx.StaticText(panel, label=_("Vista previa (solo visual; la lista dice su estado al leerla):"))
		sizer.Add(titulo, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
		ejemplos = {
			colores.BAJADA: _("En oferta, Mando inalámbrico, 49,99 €, bajó 10,00 € (17 %)"),
			colores.SUBIDA: _("Correcto, Auriculares, 89,90 €, subió 5,00 € (6 %)"),
			colores.OBJETIVO: _("En oferta, Robot aspirador, 199,00 €, precio deseado alcanzado"),
			colores.PROBLEMA: _("Agotado, Consola portátil, 349,00 €, sin cambios"),
		}
		caja = wx.BoxSizer(wx.VERTICAL)
		for tipo in colores.TIPOS:
			muestra = wx.StaticText(panel, label=f"  {ejemplos[tipo]}  ")
			self._muestras[tipo] = muestra
			caja.Add(muestra, 0, wx.EXPAND | wx.BOTTOM, 2)
		sizer.Add(caja, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
		if alto_contraste_activo():
			aviso = wx.StaticText(panel, label=_(
				"El contraste alto de Windows está activado: la lista no se colorea, para respetar sus colores."))
			sizer.Add(aviso, 0, wx.ALL, 6)
		for clave, (_opcion, control, _pagina) in self._controles.items():
			if clave.startswith("colores."):
				for evento in (wx.EVT_CHECKBOX, wx.EVT_CHOICE, wx.EVT_COMBOBOX):
					control.Bind(evento, self._al_cambiar_color)
		self._actualizar_colores()

	def _al_cambiar_dependencia(self, evento: wx.Event) -> None:
		self._actualizar_dependencias()
		evento.Skip()

	def _activa(self, opcion: Opcion) -> bool:
		"""¿Cumple la condición ``activa_si`` con lo que hay ahora en los controles?"""
		if not opcion.activa_si or opcion.activa_si[0] not in self._controles:
			return True
		clave, valor = opcion.activa_si
		otra, control, _pagina = self._controles[clave]
		return self._leer_control(otra, control) == valor

	def _actualizar_dependencias(self) -> None:
		for opcion, control, _pagina in self._controles.values():
			if opcion.activa_si:
				control.Enable(self._activa(opcion))

	def _al_cambiar_color(self, evento: wx.Event) -> None:
		self._actualizar_colores()
		evento.Skip()

	def _actualizar_colores(self) -> None:
		"""Activa o desactiva las opciones según la casilla y repinta la vista previa."""
		if not self._muestras:
			return
		valores = {clave: self._leer_control(opcion, control)
			for clave, (opcion, control, _pagina) in self._controles.items() if clave.startswith("colores.")}
		activos = bool(valores.get("colores.colores_lista", True))
		for clave, (_opcion, control, _pagina) in self._controles.items():
			if clave.startswith("colores.") and clave != "colores.colores_lista":
				control.Enable(activos)
		ajustes = colores.leer_ajustes(lambda clave, defecto: valores.get(clave, defecto))
		fondo_normal = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
		texto_normal = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
		for tipo, muestra in self._muestras.items():
			fondo, texto = ajustes.pintura(tipo)
			muestra.SetBackgroundColour(wx.Colour(fondo) if fondo else fondo_normal)
			muestra.SetForegroundColour(wx.Colour(texto) if texto else texto_normal)
			muestra.Refresh()

	def _registrar_ids(self, control: wx.Window, clave: str) -> None:
		self._clave_por_id[control.GetId()] = clave
		for hijo in control.GetChildren():
			self._registrar_ids(hijo, clave)

	def _crear_opcion(self, panel: wx.Window, sizer: wx.Sizer, opcion: Opcion) -> wx.Window:
		"""Crea (etiqueta +) control según el tipo."""
		etiqueta = _(opcion.etiqueta)
		if opcion.tipo == BOOL:
			# La casilla lleva su propio texto: no necesita StaticText.
			control = wx.CheckBox(panel, label=etiqueta)
			sizer.Add(control, 0, wx.ALL, 6)
			return control
		# La etiqueta se crea ANTES que el control: así la enlaza el lector.
		texto = wx.StaticText(panel, label=etiqueta)
		sizer.Add(texto, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
		minimo, maximo = self._limites(opcion)
		if opcion.tipo == ENTERO:
			control = wx.SpinCtrl(panel, min=int(minimo), max=int(maximo))
		elif opcion.tipo == DECIMAL:
			# Campo de texto normal y no SpinCtrlDouble: este es genérico en Windows
			# y NVDA no leía su etiqueta al llegar con Tabulador (1.0.1).
			control = wx.TextCtrl(panel)
		elif opcion.tipo == OPCION:
			control = wx.Choice(panel, choices=[_(nombre) for _valor, nombre in opcion.opciones])
		elif opcion.tipo == COLOR:
			# ComboBoxEx nativo de solo lectura: se maneja como un Choice (flechas,
			# letra inicial) y el lector lee el nombre de cada color.
			control = wx.adv.BitmapComboBox(panel, style=wx.CB_READONLY)
			for valor, nombre in opcion.opciones:
				control.Append(_(nombre), muestra_color(control, valor))
		elif opcion.tipo == SECRETO:
			control = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
		elif opcion.tipo in (TEXTO, CARPETA):
			control = wx.TextCtrl(panel)
		else:
			raise ValueError(f"Tipo de opción desconocido: {opcion.tipo}")
		if opcion.tipo == CARPETA:
			fila = wx.BoxSizer(wx.HORIZONTAL)
			fila.Add(control, 1, wx.EXPAND)
			boton = wx.Button(panel, label=_("E&xaminar..."))
			boton.SetHelpText(_("Elige la carpeta en una ventana de selección."))
			boton.Bind(wx.EVT_BUTTON, lambda _evento, c=control: self._elegir_carpeta(c))
			fila.Add(boton, 0, wx.LEFT, 6)
			sizer.Add(fila, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
		else:
			sizer.Add(control, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
		return control

	def _limites(self, opcion: Opcion) -> tuple[float, float]:
		"""Límites del descriptor o, si faltan, de la regla de la configuración."""
		regla = self._config.regla(opcion.clave) if opcion.tipo in (ENTERO, DECIMAL) else None
		minimo = opcion.minimo if opcion.minimo is not None else (regla.minimo if regla and regla.minimo is not None else 0)
		maximo = opcion.maximo if opcion.maximo is not None else (
			regla.maximo if regla and regla.maximo is not None else 1_000_000)
		return minimo, maximo

	def _elegir_carpeta(self, control: wx.TextCtrl) -> None:
		dialogo = wx.DirDialog(self, _("Elige una carpeta"), control.GetValue())
		try:
			if dialogo.ShowModal() == wx.ID_OK:
				control.SetValue(dialogo.GetPath())
		finally:
			dialogo.Destroy()
		control.SetFocus()

	# ── Valores ──────────────────────────────────────────────────────────────

	def _valor_guardado(self, opcion: Opcion) -> Any:
		if opcion.tipo == SECRETO:
			valor = self._secretos.obtener(opcion.clave) or ""
			self._valores_secretos[opcion.clave] = valor
			return valor
		return self._config.obtener(opcion.clave)

	def _escribir_control(self, opcion: Opcion, control: wx.Window, valor: Any) -> None:
		if opcion.tipo == BOOL:
			control.SetValue(bool(valor))
		elif opcion.tipo == ENTERO:
			control.SetValue(valor)
		elif opcion.tipo == DECIMAL:
			control.ChangeValue(porcentaje_para_campo(float(valor or 0)))
		elif opcion.tipo in (OPCION, COLOR):
			valores = [v for v, _nombre in opcion.opciones]
			control.SetSelection(valores.index(valor) if valor in valores else 0)
		else:
			control.ChangeValue("" if valor is None else str(valor))

	def _leer_control(self, opcion: Opcion, control: wx.Window) -> Any:
		if opcion.tipo == BOOL:
			return bool(control.GetValue())
		if opcion.tipo == ENTERO:
			return int(control.GetValue())
		if opcion.tipo == DECIMAL:
			texto = control.GetValue().replace("%", "").strip().replace(",", ".") or "0"
			try:
				return round(float(texto), 6)
			except ValueError:
				# La validación de la configuración lo rechaza con un mensaje claro
				return control.GetValue()
		if opcion.tipo in (OPCION, COLOR):
			indice = control.GetSelection()
			return opcion.opciones[indice][0] if indice != wx.NOT_FOUND else None
		return control.GetValue()

	def control_de(self, clave: str) -> wx.Window:
		"""Control asociado a una clave (para pruebas y para dar el foco)."""
		return self._controles[clave][1]

	def valores(self) -> dict[str, Any]:
		"""Valores actuales de los controles (sin secretos)."""
		return {
			clave: self._leer_control(opcion, control)
			for clave, (opcion, control, _pagina) in self._controles.items()
			if opcion.tipo != SECRETO
		}

	# ── Acciones ─────────────────────────────────────────────────────────────

	def aplicar(self) -> bool:
		"""Valida todo y guarda lo que cambió. ``False`` si algo no es válido."""
		cambios: dict[str, Any] = {}
		for clave, valor in self.valores().items():
			try:
				self._config.validar(clave, valor)
			except ErrorValidacion as error:
				self._senalar(clave, str(error))
				return False
			opcion = self._controles[clave][0]
			if opcion.validar is not None and self._activa(opcion):
				mensaje = opcion.validar(valor)
				if mensaje:
					self._senalar(clave, _(mensaje))
					return False
			if valor != self._config.obtener(clave, None):
				cambios[clave] = valor
		cambios_secretos = {
			clave: (control.GetValue() or None)
			for clave, (opcion, control, _pagina) in self._controles.items()
			if opcion.tipo == SECRETO and control.GetValue() != self._valores_secretos.get(clave, "")
		}
		try:
			if cambios:
				self._config.establecer_varias(cambios)
			if cambios_secretos:
				self._secretos.guardar_varios(cambios_secretos)
				self._valores_secretos.update({c: v or "" for c, v in cambios_secretos.items()})
		except Exception as error:  # noqa: BLE001 - ErrorConfiguracion, ErrorSecretos, OSError...: se informa al usuario
			log.exception("No se pudieron guardar las preferencias")
			mostrar_aviso(self, _("No se pudieron guardar las preferencias: %s") % error, _("Error"))
			return False
		log.info("Preferencias aplicadas: %d cambios, %d secretos", len(cambios), len(cambios_secretos))
		if self._anunciar is not None and (cambios or cambios_secretos):
			self._anunciar(_("Preferencias guardadas."))
		return True

	def _senalar(self, clave: str, mensaje: str) -> None:
		"""Avisa de un valor no válido y lleva el foco a su control."""
		opcion, control, pagina = self._controles[clave]
		self.libro.SetSelection(pagina)
		nombre = _(opcion.etiqueta).replace("&", "").rstrip(":")
		mostrar_aviso(self, f"{nombre}\n\n{mensaje}", _("Valor no válido"))
		control.SetFocus()

	def restablecer_controles(self) -> None:
		"""Pone los valores de fábrica en los controles (sin guardar)."""
		for clave, (opcion, control, _pagina) in self._controles.items():
			if opcion.tipo == SECRETO:
				continue  # los secretos no tienen valor de fábrica: no se borran por esto
			self._escribir_control(opcion, control, self._config.valor_por_defecto(clave))
		self._actualizar_colores()
		self._actualizar_dependencias()

	def _cerrar(self, codigo: int) -> None:
		if self.IsModal():
			self.EndModal(codigo)
		else:
			self.SetReturnCode(codigo)
			self.Hide()

	# ── Eventos ──────────────────────────────────────────────────────────────

	def control_inicial(self) -> wx.Window | None:
		"""Primer control de la primera página (foco inicial)."""
		for _opcion, control, pagina in self._controles.values():
			if pagina == 0:
				return control
		return None

	def _al_iniciar(self, evento: wx.InitDialogEvent) -> None:
		control = self.control_inicial()
		if control is not None:
			control.SetFocus()
		evento.Skip()

	def _al_aceptar(self, _evento: wx.CommandEvent) -> None:
		if self.aplicar():
			self._cerrar(wx.ID_OK)

	def _al_cancelar(self, _evento: wx.CommandEvent) -> None:
		log.debug("Preferencias canceladas; no se guarda nada")
		self._cerrar(wx.ID_CANCEL)

	def _al_aplicar(self, _evento: wx.CommandEvent) -> None:
		self.aplicar()

	def _al_restablecer(self, _evento: wx.CommandEvent) -> None:
		if not confirmar(self, _("¿Poner todas las opciones con sus valores de fábrica? "
				"No se guardará nada hasta que pulses Aplicar o Aceptar."), _("Restablecer valores de fábrica")):
			return
		self.restablecer_controles()
		self.libro.SetSelection(0)
		control = self.control_inicial()
		if control is not None:
			control.SetFocus()
		if self._anunciar is not None:
			self._anunciar(_("Valores de fábrica puestos. Pulsa Aceptar para guardarlos."))

	def _al_tecla(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() in (ord("H"), ord("h")) and evento.GetModifiers() == wx.MOD_CONTROL:
			self.mostrar_ayuda_de(wx.Window.FindFocus())
			return
		evento.Skip()

	def texto_ayuda(self, ventana: wx.Window | None) -> str:
		"""Ayuda del control (o de su antecesor con ayuda) para Ctrl+H."""
		actual = ventana
		while actual is not None and actual is not self:
			clave = self._clave_por_id.get(actual.GetId())
			if clave is not None:
				opcion = self._controles[clave][0]
				nombre = _(opcion.etiqueta).replace("&", "").rstrip(":")
				return f"{nombre}. {_(opcion.ayuda)}" if opcion.ayuda else nombre
			ayuda = actual.GetHelpText()
			if ayuda:
				return ayuda
			actual = actual.GetParent()
		return _("No hay ayuda para este elemento.")

	def mostrar_ayuda_de(self, ventana: wx.Window | None) -> None:
		mostrar_ayuda(self, _("Ayuda"), self.texto_ayuda(ventana))
