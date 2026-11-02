"""Textos de la lista y los detalles, descargador con servidor local, inicio con Windows."""

from __future__ import annotations

import http.server
import socket
import subprocess
import threading
from datetime import datetime, timezone

import pytest

from app.services import errores, inicio_windows, vistas
from app.services.descargador import Descargador
from app.services.errores import ErrorComprobacion

AHORA = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)


def _p(**cambios):
	base = {"id": 1, "nombre": "Robot", "tienda": "Amazon", "categoria": "Hogar", "moneda": "EUR", "precio_actual": 90.0,
		"precio_anterior": 100.0, "precio_minimo": 90.0, "precio_maximo": 120.0, "fecha_cambio": "2026-11-01T10:00:00Z",
		"activo": 1, "disponible": 1, "ultima_comprobacion": "2026-11-02T19:00:00Z", "ultimo_error": "", "estado": "correcta"}
	base.update(cambios)
	return base


def test_fila_de_la_lista_con_estado_primero():
	columnas = vistas.columnas_producto(_p(), AHORA)
	assert columnas[:4] == ["En oferta", "Robot", "90,00 €", "bajó 10,00 € (10 %)"]
	assert vistas.texto_estado(_p(activo=0)) == "En pausa"
	assert vistas.texto_estado(_p(disponible=0, precio_anterior=None)) == "Agotado"
	bloqueado = _p(ultimo_error=errores.MENSAJE_BLOQUEO, estado=errores.BLOQUEADA, disponible=0)
	assert vistas.texto_estado(bloqueado) == "Bloqueada por la tienda", "un bloqueo nunca se confunde con agotado"
	assert vistas.texto_estado(_p(ultimo_error=errores.MENSAJE_SIN_PRECIO, estado=None)) == "Sin precio"
	assert vistas.texto_estado(_p(ultimo_error=errores.MENSAJE_SIN_CONEXION, estado=errores.SIN_CONEXION)) == "Sin conexión"
	assert vistas.texto_cambio(_p(precio_anterior=None)) == "sin cambios"
	assert vistas.texto_cambio(_p(precio_objetivo=95)) == "bajó 10,00 € (10 %), precio deseado alcanzado"
	assert vistas.texto_precio(_p(desde=1)) == "desde 90,00 €"


def test_ofertas_orden_busqueda_y_filtros():
	productos = [
		_p(id=1, nombre="Árbol", precio_actual=50.0, precio_anterior=100.0, tienda="Zeta"),
		_p(id=2, nombre="bote", precio_actual=95.0, precio_anterior=100.0, notas="para la cocina"),
		_p(id=3, nombre="Caja", precio_actual=10.0, precio_anterior=None, precio_minimo=10.0, precio_maximo=10.0, activo=0),
	]
	assert [p["id"] for p in vistas.ofertas(productos, AHORA)] == [1, 2]
	assert [p["nombre"] for p in vistas.ordenar(productos, "nombre")] == ["Árbol", "bote", "Caja"]
	assert [p["id"] for p in vistas.ordenar(productos, "precio")] == [3, 1, 2]
	assert [p["id"] for p in vistas.ordenar(productos, "bajada")][0] == 1
	assert [p["id"] for p in vistas.filtrar(productos, "COCINA")] == [2]
	assert [p["id"] for p in vistas.filtrar(productos, "arbol zeta")] == [1]
	assert [p["id"] for p in vistas.filtrar(productos, solo_activos=True)] == [1, 2]


def test_comparar_con_el_mas_barato():
	filas = vistas.comparar([_p(id=1, precio_actual=359.0), _p(id=2, precio_actual=349.9), _p(id=3, precio_actual=None)])
	assert [(p["id"], t) for p, t in filas] == [(2, "el más barato"), (1, "9,10 € más (2,6 %)"), (3, "sin precio")]


def test_resumen_hablado_e_historial():
	producto = _p(precio_actual=129.99, precio_minimo=119.0, fecha_minimo="2026-10-03T10:00:00Z", precio_maximo=149.0)
	assert vistas.resumen_hablado(producto) == (
		"Ahora 129,99 €. Mínimo 119,00 € el 3 de octubre. Máximo 149,00 €. Está un 9,2 % por encima del mínimo.")
	filas = vistas.filas_historial([
		{"fecha": "2026-10-01T10:00:00Z", "precio": 100.0, "disponible": 1},
		{"fecha": "2026-10-05T10:00:00Z", "precio": 90.0, "disponible": 1},
	], "EUR")
	assert filas[0][1:] == ["90,00 €", "bajó 10,00 € (10 %)", "disponible"] and filas[1][2] == "primera lectura"
	etiquetas = [e for e, _v in vistas.lineas_detalles(producto, [])]
	assert {"Origen del precio", "Confianza", "Media del historial", "Diferencia con el mínimo"} <= set(etiquetas)


class _Manejador(http.server.BaseHTTPRequestHandler):
	contador: dict[str, int] = {}

	def log_message(self, *argumentos):
		return

	def do_GET(self):  # noqa: N802 - nombre impuesto por http.server
		_Manejador.contador[self.path] = _Manejador.contador.get(self.path, 0) + 1
		if self.path == "/redirige":
			self.send_response(307)
			self.send_header("Set-Cookie", "sesion=1; Path=/")
			self.send_header("Location", "/con-cookie")
			self.end_headers()
			return
		if self.path == "/con-cookie":
			ok = "sesion=1" in (self.headers.get("Cookie") or "")
			self._responder(200 if ok else 403, "<p>bien</p>" if ok else "no")
			return
		codigos = {"/403": 403, "/429": 429, "/404": 404, "/500": 500}
		if self.path in codigos:
			self._responder(codigos[self.path], "x")
			return
		self._responder(200, "<p>Hola ñ</p>", "text/html; charset=utf-8")

	def _responder(self, codigo, texto, tipo="text/html"):
		datos = texto.encode("utf-8")
		self.send_response(codigo)
		self.send_header("Content-Type", tipo)
		self.send_header("Content-Length", str(len(datos)))
		self.end_headers()
		self.wfile.write(datos)


@pytest.fixture
def servidor(monkeypatch):
	from app.services import descargador

	monkeypatch.setattr(descargador, "ESPERA_REINTENTO", 0.05)
	_Manejador.contador = {}
	# Como en el servidor de pruebas del actualizador: en este equipo un filtro de
	# red corta las conexiones a 127.0.0.1; con IPv6 (::1) no pasa.
	if socket.has_ipv6:
		class Servidor(http.server.ThreadingHTTPServer):
			address_family = socket.AF_INET6

		httpd = Servidor(("::1", 0), _Manejador)
		base = f"http://[::1]:{httpd.server_address[1]}"
	else:
		httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Manejador)
		base = f"http://127.0.0.1:{httpd.server_address[1]}"
	hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
	hilo.start()
	yield base
	httpd.shutdown()
	httpd.server_close()


def test_descargador_cookies_errores_y_reintento(servidor):
	descargador = Descargador(5)
	pagina = descargador.descargar(servidor + "/", "local")
	assert pagina.estado == 200 and "Hola ñ" in pagina.html
	assert "bien" in descargador.descargar(servidor + "/redirige", "local").html, "cookies entre la 307 y la página"
	for ruta, estado in (("/403", errores.BLOQUEADA), ("/429", errores.BLOQUEADA)):
		with pytest.raises(ErrorComprobacion) as error:
			descargador.descargar(servidor + ruta, "local")
		assert error.value.estado == estado and "robot" in error.value.mensaje
	with pytest.raises(ErrorComprobacion, match="404"):
		descargador.descargar(servidor + "/404", "local")
	with pytest.raises(ErrorComprobacion, match="500"):
		descargador.descargar(servidor + "/500", "local")
	assert _Manejador.contador["/500"] == 2, "un solo reintento con 5xx"
	assert _Manejador.contador["/404"] == 1
	with pytest.raises(ErrorComprobacion) as error:
		descargador.descargar("http://127.0.0.1:9/", "nada")
	assert error.value.estado == errores.SIN_CONEXION
	descargador.cerrar()


def test_inicio_con_windows_por_powershell():
	ordenes = []

	def falso(script):
		ordenes.append(script)
		return subprocess.CompletedProcess([], 0, stdout="True\n" if "Test-Path" in script and "Remove" not in script else "", stderr="")

	inicio_windows.establecer_ejecutor(falso)
	try:
		inicio_windows.activar()
		assert "GetFolderPath('Startup')" in ordenes[-1] and "--bandeja" in ordenes[-1] and "WScript.Shell" in ordenes[-1]
		assert inicio_windows.esta_activado()
		inicio_windows.desactivar()
		assert "Remove-Item" in ordenes[-1]
		inicio_windows.establecer_ejecutor(lambda s: subprocess.CompletedProcess([], 1, stdout="", stderr="mal"))
		with pytest.raises(inicio_windows.ErrorInicio):
			inicio_windows.activar()
	finally:
		inicio_windows.establecer_ejecutor(None)
