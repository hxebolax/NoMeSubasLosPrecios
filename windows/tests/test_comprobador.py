"""Comprobador con descargas y navegador simulados: pausas, paralelo, API, navegador, huella y recomprobación."""

from __future__ import annotations

import json
import threading
import time

import pytest

from app.core.configuracion import Configuracion
from app.services import comprobador as mod
from app.services import errores
from app.services.descargador import Pagina
from app.services.errores import ErrorComprobacion
from app.services.nucleo import Nucleo
from app.services.reglas import catalogo_desde_datos

JSONLD = '<script type="application/ld+json">{{"@type":"Product","name":"{nombre}","offers":{{"price":{precio}}}}}</script>'


class DescargadorFalso:
	"""Devuelve páginas preparadas por dirección y anota las peticiones (hora y hilo)."""

	def __init__(self, paginas):
		self.paginas = paginas
		self.peticiones = []
		self.tiempo_espera = 25

	def descargar(self, url, dominio="", cancelado=None, cabeceras=None):
		self.peticiones.append((url, time.monotonic(), threading.current_thread().name, cabeceras))
		respuesta = self.paginas[url]
		if isinstance(respuesta, Exception):
			raise respuesta
		if callable(respuesta):
			respuesta = respuesta()
		estado, html = respuesta if isinstance(respuesta, tuple) else (200, respuesta)
		return Pagina(html=html, estado=estado, url_final=url)

	def cerrar(self):
		pass


@pytest.fixture
def nucleo(data_temporal):
	config = Configuracion()
	config.establecer_varias({"precios.pausa_entre_peticiones": 0, "precios.avisar_errores": True})
	n = Nucleo(config)
	n.comprobador._catalogo = lambda: catalogo_desde_datos({
		"bloqueo_general": ["Just a moment"],
		"tiendas": [
			{"id": "m", "nombre": "Mercado", "dominios": ["mercado.es"], "api": {
				"id_desde_url": "/product/(\\d+)", "url": "https://mercado.es/api/{id}", "precio": ["p.precio"], "nombre": ["nombre"]}},
			{"id": "n", "nombre": "Nav", "dominios": ["nav.es"], "navegador": True},
		],
	})
	yield n
	n.cerrar()


def _anadir(nucleo, url, **campos):
	return nucleo.anadir_producto(url, None, **campos)


def test_comprueba_guarda_y_avisa(nucleo):
	precios = iter(["10", "8"])
	falso = DescargadorFalso({"https://a.es/p/1": lambda: JSONLD.format(nombre="Taza", precio=next(precios))})
	nucleo.comprobador.descargador = falso
	pid = _anadir(nucleo, "https://a.es/p/1")
	resumen = nucleo.comprobador.comprobar()
	producto = nucleo.repositorio.producto(pid)
	assert (resumen.comprobados, resumen.correctos, producto["precio_actual"], producto["nombre"]) == (1, 1, 10.0, "Taza")
	assert producto["origen_precio"] == "JSON-LD" and producto["confianza"] == "alta"
	resumen = nucleo.comprobador.comprobar()
	assert resumen.cambios_precio == 1 and [a.tipo for a in resumen.avisos] == ["minimo"]
	assert "Comprobados 1 de 1 productos" in resumen.texto()


def test_errores_y_estado_bloqueado(nucleo):
	falso = DescargadorFalso({"https://a.es/p/2": ErrorComprobacion(errores.BLOQUEADA, errores.MENSAJE_BLOQUEO)})
	nucleo.comprobador.descargador = falso
	pid = _anadir(nucleo, "https://a.es/p/2")
	for _ in range(3):
		resumen = nucleo.comprobador.comprobar()
	producto = nucleo.repositorio.producto(pid)
	assert producto["estado"] == errores.BLOQUEADA and producto["errores_seguidos"] == 3
	assert resumen.bloqueados == 1 and [a.tipo for a in resumen.avisos] == ["error"]


def test_pausa_por_tienda_y_tres_en_paralelo(nucleo):
	nucleo.config.establecer("precios.pausa_entre_peticiones", 1)
	paginas = {}
	for tienda in ("a", "b", "c", "d"):
		for n in (1, 2):
			paginas[f"https://{tienda}.es/p/{n}"] = JSONLD.format(nombre=f"{tienda}{n}", precio=n)
	falso = DescargadorFalso(paginas)
	nucleo.comprobador.descargador = falso
	for url in paginas:
		_anadir(nucleo, url)
	mod_azar = mod.AZAR_PAUSA
	mod.AZAR_PAUSA = 0
	try:
		nucleo.comprobador.comprobar()
	finally:
		mod.AZAR_PAUSA = mod_azar
	horas = {url: momento for url, momento, _hilo, _c in falso.peticiones}
	for tienda in ("a", "b", "c", "d"):
		assert horas[f"https://{tienda}.es/p/2"] - horas[f"https://{tienda}.es/p/1"] >= 0.9, "pausa entre productos de la misma tienda"
	assert len({hilo for _u, _m, hilo, _c in falso.peticiones}) <= mod.MAX_TIENDAS_EN_PARALELO


def test_cancelar_detiene_pronto(nucleo):
	nucleo.config.establecer("precios.pausa_entre_peticiones", 30)
	paginas = {f"https://a.es/p/{n}": JSONLD.format(nombre="x", precio=n) for n in (1, 2, 3)}
	nucleo.comprobador.descargador = DescargadorFalso(paginas)
	for url in paginas:
		_anadir(nucleo, url)
	cancelado = threading.Event()
	threading.Timer(0.3, cancelado.set).start()
	inicio = time.monotonic()
	resumen = nucleo.comprobador.comprobar(cancelado=cancelado)
	assert time.monotonic() - inicio < 5 and resumen.cancelado and resumen.comprobados == 1


def test_api_de_la_tienda_antes_que_el_html(nucleo):
	falso = DescargadorFalso({"https://mercado.es/api/77": json.dumps({"p": {"precio": "3.45"}, "nombre": "Leche"})})
	nucleo.comprobador.descargador = falso
	resultado = nucleo.comprobador.analizar("https://mercado.es/product/77/leche", "mercado.es")
	assert (resultado.precio, resultado.origen_precio, resultado.nombre) == (3.45, "API de la tienda", "Leche")
	assert falso.peticiones[0][3] == {"Accept": "application/json"}


def test_navegador_para_tiendas_marcadas_y_en_auto(nucleo):
	visitas = []

	def navegador(url, cancelado=None, tiene_precio=None):
		visitas.append(url)
		html = JSONLD.format(nombre="Con JS", precio=9)
		assert tiene_precio is None or tiene_precio(html)
		return html

	nucleo.comprobador.navegador = navegador
	nucleo.comprobador.descargador = DescargadorFalso({
		"https://otra.es/p": '<html><body><div id="root"></div><script src="app.js"></script></body></html>',
		"https://otra.es/b": ErrorComprobacion(errores.BLOQUEADA, errores.MENSAJE_BLOQUEO),
	})
	assert nucleo.comprobador.analizar("https://nav.es/p", "nav.es").precio == 9.0, "tiendas.json: navegador true"
	assert nucleo.comprobador.analizar("https://otra.es/p", "otra.es").precio == 9.0, "página montada con JavaScript"
	assert nucleo.comprobador.analizar("https://otra.es/b", "otra.es").precio == 9.0, "bloqueo en la descarga normal"
	with pytest.raises(ErrorComprobacion):
		nucleo.comprobador.analizar("https://otra.es/b", "otra.es", modo_descarga="directo")
	assert visitas == ["https://nav.es/p", "https://otra.es/p", "https://otra.es/b"]


def test_descarga_colgada_prueba_el_navegador(nucleo):
	"""1.1.0: Akamai (G2A) deja la descarga sin respuesta; en auto se repite con el navegador."""
	visitas = []
	falla_navegador = {"si": False}

	def navegador(url, cancelado=None, tiene_precio=None):
		visitas.append(url)
		if falla_navegador["si"]:
			raise ErrorComprobacion(errores.ERROR, "El navegador integrado no pudo leer la página.")
		return JSONLD.format(nombre="Clave", precio=12.55)

	nucleo.comprobador.navegador = navegador
	nucleo.comprobador.descargador = DescargadorFalso({
		"https://lenta.es/p": ErrorComprobacion(errores.SIN_CONEXION, errores.MENSAJE_TIEMPO),
		"https://sinred.es/p": ErrorComprobacion(errores.SIN_CONEXION, errores.MENSAJE_SIN_CONEXION),
	})
	assert nucleo.comprobador.analizar("https://lenta.es/p", "lenta.es").precio == 12.55
	with pytest.raises(ErrorComprobacion) as sin_red:
		nucleo.comprobador.analizar("https://sinred.es/p", "sinred.es")
	assert sin_red.value.mensaje == errores.MENSAJE_SIN_CONEXION, "sin conexión no prueba el navegador"
	with pytest.raises(ErrorComprobacion):
		nucleo.comprobador.analizar("https://lenta.es/p", "lenta.es", modo_descarga="directo")
	falla_navegador["si"] = True
	with pytest.raises(ErrorComprobacion) as error:
		nucleo.comprobador.analizar("https://lenta.es/p", "lenta.es")
	assert error.value.mensaje == errores.MENSAJE_TIEMPO, "si el navegador tampoco puede, el error de la descarga"
	assert visitas == ["https://lenta.es/p", "https://lenta.es/p"]


def test_sin_navegador_se_explica(nucleo):
	nucleo.comprobador.navegador = None
	with pytest.raises(ErrorComprobacion, match="WebView2"):
		nucleo.comprobador.analizar("https://nav.es/p", "nav.es")


def test_desafio_202_y_400_de_bloqueo(nucleo):
	nucleo.comprobador.navegador = None
	nucleo.comprobador.descargador = DescargadorFalso({
		"https://a.es/202": (202, "<html><body>espera</body></html>"),
		"https://a.es/400": (400, "<p>Just a moment</p>"),
	})
	for url in ("https://a.es/202", "https://a.es/400"):
		with pytest.raises(ErrorComprobacion) as error:
			nucleo.comprobador.analizar(url, "a.es", modo_descarga="directo")
		assert error.value.estado == errores.BLOQUEADA


def test_selector_elegido_con_huella(nucleo):
	html_bueno = '<span id="precio">39,99 €</span>'
	html_movido = '<span id="otro">39,99 €</span><script type="application/ld+json">{"@type":"Product","offers":{"price":39.99}}</script>'
	html_otro = '<span id="otro">5,00 €</span><script type="application/ld+json">{"@type":"Product","offers":{"price":12}}</script>'
	paginas = {"https://a.es/x": html_bueno}
	nucleo.comprobador.descargador = DescargadorFalso(paginas)
	huella = mod.crear_huella(39.99, "Precio")
	argumentos = {"selector_producto": "#precio", "huella": huella, "precio_conocido": 39.99}
	assert nucleo.comprobador.analizar("https://a.es/x", "a.es", **argumentos).precio == 39.99
	paginas["https://a.es/x"] = html_movido
	assert nucleo.comprobador.analizar("https://a.es/x", "a.es", **argumentos).precio == 39.99, "el automático da el mismo precio"
	paginas["https://a.es/x"] = html_otro
	with pytest.raises(ErrorComprobacion, match="posición del precio"):
		nucleo.comprobador.analizar("https://a.es/x", "a.es", **argumentos)


def test_confianza_media_y_cambio_grande_se_recomprueba(nucleo, monkeypatch):
	monkeypatch.setattr(mod, "ESPERA_RECOMPROBACION", 0)
	visible = '<main><h1>Robot</h1><div class="product-price">{p} €</div><form><button>Añadir al carrito</button></form></main>'
	respuestas = iter([visible.format(p="100,00"), visible.format(p="20,00"), visible.format(p="99,00")])
	falso = DescargadorFalso({"https://a.es/r": lambda: next(respuestas)})
	nucleo.comprobador.descargador = falso
	pid = _anadir(nucleo, "https://a.es/r")
	nucleo.comprobador.comprobar()
	assert nucleo.repositorio.producto(pid)["confianza"] == "media"
	nucleo.comprobador.comprobar()
	assert len(falso.peticiones) == 3, "el cambio del 80 % se volvió a comprobar"
	assert nucleo.repositorio.producto(pid)["precio_actual"] == 99.0


def test_candidatos_para_elegir_desde_el_comprobador(nucleo):
	nucleo.comprobador.descargador = DescargadorFalso({
		"https://a.es/c": '<main><h1>Planta</h1><p class="shipping">Envío gratis a partir de 49 €</p></main>'})
	resultado = nucleo.comprobador.analizar("https://a.es/c", "a.es", lanzar=False)
	assert resultado.dudoso and resultado.error == "No se pudo decidir cuál es el precio. Abre el producto y elige el precio correcto."
	candidatos = nucleo.comprobador.pagina_para_elegir("https://a.es/c", "a.es")
	assert candidatos and "envío" in candidatos[0].descripcion


def test_parece_javascript():
	assert mod.parece_javascript('<html><body><app-root></app-root></body></html>')
	assert mod.parece_javascript("<p>poco</p>")
	assert not mod.parece_javascript("<p>" + "texto de producto " * 30 + "</p>")


def test_comprobar_con_el_token_del_gestor_de_tareas(nucleo):
	"""Como lo hace la ventana: con un TokenCancelacion, no con un threading.Event.

	En la 1.0.1 «Comprobar todos» fallaba siempre con «'TokenCancelacion' object has
	no attribute 'wait'» en cuanto había dos productos de la misma tienda (la pausa).
	"""
	from app.core.tareas import TokenCancelacion

	paginas = {f"https://a.es/p/{n}": JSONLD.format(nombre=f"Taza {n}", precio=n) for n in (1, 2)}
	nucleo.comprobador.descargador = DescargadorFalso(paginas)
	for url in paginas:
		_anadir(nucleo, url)
	mod_azar = mod.AZAR_PAUSA
	mod.AZAR_PAUSA = 0
	try:
		resumen = nucleo.comprobador.comprobar(cancelado=TokenCancelacion())
	finally:
		mod.AZAR_PAUSA = mod_azar
	assert (resumen.comprobados, resumen.correctos) == (2, 2)


def test_comprobar_con_token_cancelado_se_detiene(nucleo):
	from app.core.tareas import TokenCancelacion

	paginas = {f"https://a.es/p/{n}": JSONLD.format(nombre=f"Taza {n}", precio=n) for n in (1, 2, 3)}
	nucleo.comprobador.descargador = DescargadorFalso(paginas)
	for url in paginas:
		_anadir(nucleo, url)
	token = TokenCancelacion()
	token.cancelar()
	resumen = nucleo.comprobador.comprobar(cancelado=token)
	assert resumen.cancelado and resumen.comprobados == 0


def test_tras_un_fallo_automatico_no_se_reintenta_cada_minuto(nucleo):
	from datetime import datetime, timedelta, timezone

	ahora = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)
	assert nucleo.toca_comprobar(ahora)
	assert nucleo.aplazar_tras_fallo(ahora) == timedelta(minutes=15)
	assert not nucleo.toca_comprobar(ahora + timedelta(minutes=1))
	assert nucleo.toca_comprobar(ahora + timedelta(minutes=16))
	assert nucleo.aplazar_tras_fallo(ahora) == timedelta(minutes=30), "la espera crece con cada fallo"
	for _ in range(10):
		espera = nucleo.aplazar_tras_fallo(ahora)
	assert espera == timedelta(hours=int(nucleo.config.obtener("precios.intervalo_horas"))), "nunca más que el intervalo"
	nucleo.anotar_comprobacion()
	assert nucleo.aplazar_tras_fallo(ahora) == timedelta(minutes=15), "una comprobación buena olvida los fallos"
