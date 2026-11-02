"""Navegador integrado: carga páginas con el motor Edge (WebView2) del sistema.

Para las tiendas que no dan la página a una descarga normal o que montan el
precio con JavaScript. Reglas (especificación, «Navegador integrado»):

- ``wx.html2.WebView`` con el motor Edge en una ventana OCULTA. Todo lo de
  wx se hace en el hilo principal; el hilo de comprobación pide la página con
  ``wx.CallAfter`` y espera el resultado con un ``threading.Event``.
- Carga la dirección, espera al final de la carga y después hasta 8 segundos
  más mientras no haya precio, mirando cada segundo
  ``document.documentElement.outerHTML``. Máximo 30 segundos. Uno a la vez.
- Mismo User-Agent del motor y sus propias cookies, que se conservan (la
  carpeta de datos del motor va en ``data/cache/webview``: portable).
- Nada para engañar a la tienda: ni huellas cambiadas, ni ocultar que es un
  navegador automatizado, ni resolver verificaciones solo.
- «Abrir la tienda en la app» muestra esa misma ventana para que el usuario
  resuelva una verificación o acepte las cookies; Escape la oculta.
"""

from __future__ import annotations

import builtins
import logging
import os
import threading
import time
from collections.abc import Callable

import wx

from app.core import paths
from app.services import errores
from app.services.errores import ErrorComprobacion

log = logging.getLogger(__name__)

TIEMPO_MAXIMO = 30.0
ESPERA_PRECIO = 8
URL_WEBVIEW2 = "https://developer.microsoft.com/microsoft-edge/webview2/"
MENSAJE_SIN_MOTOR = (
	"El navegador integrado necesita el runtime WebView2 de Microsoft, que no está instalado. "
	"Puede descargarlo de " + URL_WEBVIEW2
)


def _(texto: str) -> str:
	traducir = getattr(builtins, "_", None)
	return traducir(texto) if callable(traducir) else texto


def motor_disponible() -> bool:
	"""¿Está el runtime WebView2 (motor Edge)?"""
	try:
		import wx.html2

		return bool(wx.html2.WebView.IsBackendAvailable(wx.html2.WebViewBackendEdge))
	except (ImportError, AttributeError, RuntimeError):
		log.info("wx.html2 no está disponible", exc_info=True)
		return False


class NavegadorIntegrado:
	"""Ventana oculta con un WebView; se usa desde hilos con :meth:`obtener_html`."""

	def __init__(self, padre: wx.Window | None) -> None:
		self._padre = padre
		self._marco: wx.Frame | None = None
		self._web = None
		self._uno_a_la_vez = threading.Lock()
		self._cargada = threading.Event()
		self._respuesta: dict[str, object] = {}
		self._listo_script = threading.Event()
		self._foco_previo: wx.Window | None = None

	# ── Hilo principal ───────────────────────────────────────────────────────

	def _asegurar(self) -> bool:
		"""Crea la ventana y el WebView la primera vez (hilo principal)."""
		if self._web is not None:
			return True
		if not motor_disponible():
			return False
		import wx.html2

		# Datos del motor (cookies, caché) dentro de data/: la aplicación es portable.
		os.environ.setdefault("WEBVIEW2_USER_DATA_FOLDER", str(paths.subcarpeta("cache") / "webview"))
		self._marco = wx.Frame(self._padre, title=_("Tienda en el navegador integrado"), size=(1100, 800))
		self._web = wx.html2.WebView.New(self._marco, backend=wx.html2.WebViewBackendEdge)
		self._web.SetName(_("Página de la tienda"))
		self._web.Bind(wx.html2.EVT_WEBVIEW_LOADED, self._al_cargar)
		self._web.Bind(wx.html2.EVT_WEBVIEW_ERROR, self._al_cargar)
		self._web.Bind(wx.html2.EVT_WEBVIEW_SCRIPT_RESULT, self._al_resultado_script)
		self._marco.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
		self._marco.Bind(wx.EVT_CLOSE, self._al_cerrar_marco)
		return True

	def _al_cargar(self, evento: wx.Event) -> None:
		self._cargada.set()
		evento.Skip()

	def _al_resultado_script(self, evento: wx.Event) -> None:
		self._respuesta["html"] = "" if evento.IsError() else (evento.GetString() or "")
		self._listo_script.set()

	def _al_tecla(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() == wx.WXK_ESCAPE:
			self.ocultar()
			return
		evento.Skip()

	def _al_cerrar_marco(self, evento: wx.CloseEvent) -> None:
		# Cerrar con Alt+F4 solo oculta: el WebView (y sus cookies) se reutiliza.
		if evento.CanVeto():
			evento.Veto()
			self.ocultar()
			return
		evento.Skip()

	def _cargar_en_interfaz(self, url: str, creado: threading.Event, estado: dict) -> None:
		try:
			if not self._asegurar():
				estado["error"] = MENSAJE_SIN_MOTOR
			else:
				self._cargada.clear()
				self._web.LoadURL(url)
		except Exception as error:  # noqa: BLE001 - se informa al hilo que espera
			log.exception("No se pudo cargar la página en el navegador integrado")
			estado["error"] = str(error)
		finally:
			creado.set()

	def _pedir_html_en_interfaz(self) -> None:
		try:
			self._web.RunScriptAsync("document.documentElement.outerHTML")
		except Exception:  # noqa: BLE001 - se responde vacío y el hilo sigue
			log.exception("No se pudo leer el HTML del navegador integrado")
			self._respuesta["html"] = ""
			self._listo_script.set()

	def mostrar(self, url: str | None = None) -> bool:
		"""«Abrir la tienda en la app»: la ventana visible (hilo principal)."""
		if not self._asegurar():
			return False
		self._foco_previo = wx.Window.FindFocus()
		if url:
			self._web.LoadURL(url)
		# Si hay un diálogo modal abierto (detalles, tiendas), wx desactivó esta
		# ventana al abrirlo: se reactiva para poder usarla.
		self._marco.Enable(True)
		self._marco.Show()
		self._marco.Raise()
		self._web.SetFocus()
		return True

	def ocultar(self) -> None:
		"""Oculta la ventana y devuelve el foco a donde estaba (las cookies se quedan)."""
		if self._marco is not None:
			self._marco.Hide()
			previo = getattr(self, "_foco_previo", None)
			if previo:
				wx.GetTopLevelParent(previo).Raise()
				previo.SetFocus()
			elif self._padre:
				self._padre.Raise()

	def destruir(self) -> None:
		if self._marco is not None:
			self._marco.Unbind(wx.EVT_CLOSE)
			self._marco.Destroy()
			self._marco = None
			self._web = None

	# ── Desde el hilo de comprobación ────────────────────────────────────────

	def obtener_html(
		self, url: str, cancelado: threading.Event | None = None, tiene_precio: Callable[[str], bool] | None = None
	) -> str:
		"""Carga ``url`` y devuelve su HTML. Lanza :class:`ErrorComprobacion` si no se puede."""
		if threading.current_thread() is threading.main_thread():
			raise RuntimeError("obtener_html no puede llamarse desde el hilo de la interfaz")
		with self._uno_a_la_vez:
			inicio = time.monotonic()
			creado, estado = threading.Event(), {}
			wx.CallAfter(self._cargar_en_interfaz, url, creado, estado)
			if not creado.wait(10) or estado.get("error"):
				raise ErrorComprobacion(errores.ERROR, str(estado.get("error") or MENSAJE_SIN_MOTOR))
			while not self._cargada.wait(0.5):
				if cancelado is not None and cancelado.is_set():
					raise ErrorComprobacion(errores.ERROR, "Comprobación cancelada.")
				if time.monotonic() - inicio > TIEMPO_MAXIMO:
					raise ErrorComprobacion(errores.SIN_CONEXION, errores.MENSAJE_TIEMPO)
			html = ""
			for intento in range(ESPERA_PRECIO + 1):
				self._listo_script.clear()
				self._respuesta.clear()
				wx.CallAfter(self._pedir_html_en_interfaz)
				if not self._listo_script.wait(10):
					break
				html = str(self._respuesta.get("html") or "")
				if tiene_precio is None or tiene_precio(html) or intento == ESPERA_PRECIO:
					break
				if time.monotonic() - inicio > TIEMPO_MAXIMO:
					break
				if cancelado is not None and cancelado.wait(1.0):
					raise ErrorComprobacion(errores.ERROR, "Comprobación cancelada.")
				if cancelado is None:
					time.sleep(1.0)
			if not html:
				raise ErrorComprobacion(errores.ERROR, _("El navegador integrado no pudo leer la página."))
			return html
