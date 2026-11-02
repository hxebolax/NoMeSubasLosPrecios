"""Coherencia del proyecto: versión única, data limpia, rutas portables y .bat correcto."""

from __future__ import annotations

import ast
import re

from app.core import paths
from app.core.version import APP_VERSION, ID_APLICACION

from .conftest import RAIZ


def _constantes_de(archivo):
	arbol = ast.parse(archivo.read_text(encoding="utf-8"))
	valores = {}
	for nodo in arbol.body:
		if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1 and isinstance(nodo.targets[0], ast.Name):
			try:
				valores[nodo.targets[0].id] = ast.literal_eval(nodo.value)
			except ValueError:
				continue
	return valores


def test_version_unica():
	texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
	coincidencia = re.search(r'^version\s*=\s*"([^"]+)"', texto, re.MULTILINE)
	assert coincidencia and coincidencia.group(1) == APP_VERSION


def test_setup_cx_coherente_y_limpio():
	setup = RAIZ / "setup_cx.py"
	constantes = _constantes_de(setup)
	assert constantes["NOMBRE_APP"] == ID_APLICACION
	assert constantes["EJECUTABLE"] == f"{ID_APLICACION}.exe"
	assert not set(constantes["DATA_DISTRIBUIBLE"]) & constantes["DATA_PROHIBIDO"]
	assert '"include_msvcr": True' in setup.read_text(encoding="utf-8")


def test_data_del_proyecto_solo_tiene_lo_distribuible():
	distribuible = set(_constantes_de(RAIZ / "setup_cx.py")["DATA_DISTRIBUIBLE"])
	carpetas = {p.name for p in (RAIZ / "data").iterdir() if p.is_dir()}
	assert carpetas <= distribuible, f"data/ contiene carpetas personales: {carpetas - distribuible}"


def test_rutas_portables(datos_temporales):
	assert paths.ruta_base() == RAIZ
	assert paths.ruta_datos() == datos_temporales
	assert paths.ruta_registros() == datos_temporales / "logs"


def test_bat_crlf_sin_bom():
	datos = (RAIZ / "entorno.bat").read_bytes()
	assert not datos.startswith(b"\xef\xbb\xbf")
	assert b"\n" not in datos.replace(b"\r\n", b"")
	assert f'set "NOMBRE_APP={ID_APLICACION}"'.encode() in datos


def test_recursos_comunes_se_distribuyen():
	distribuible = set(_constantes_de(RAIZ / "setup_cx.py")["DATA_DISTRIBUIBLE"])
	assert "recursos" in distribuible
	from app.services import actualizador

	assert "recursos" in actualizador.DATA_ACTUALIZABLE


def test_nombre_del_zip_y_clave_fuera_del_proyecto():
	import sys

	sys.path.insert(0, str(RAIZ / "tools"))
	try:
		import empaquetar
	finally:
		sys.path.pop(0)
	assert empaquetar.nombre_zip("1.0.0") == "NoMeSubasLosPrecios-1.0.0-win64.zip"
	assert empaquetar.DESTINO == RAIZ / "dist"
	assert RAIZ not in empaquetar.CLAVE_FIRMA.parents, "la clave privada nunca dentro de windows/"


def test_bat_tiene_las_ordenes_sin_menu():
	texto = (RAIZ / "entorno.bat").read_bytes().decode("utf-8")
	for orden in ("crear", "instalar", "pruebas", "ejecutar", "compilar", "publicar", "recursos", "comprobar", "auditoria"):
		assert f'if /i "%ORDEN%"=="{orden}"' in texto, orden
	assert r"..\entorno\python\python.exe" in texto and "py -%VERSION_PY%" in texto
	assert r"..\compartido\recursos" in texto


def test_sin_rutas_fuera_de_la_aplicacion():
	"""El código no guarda nada en carpetas del perfil de Windows (portable)."""
	prohibidas = re.compile(r"(environ|getenv)\W+[\"'](LOCAL)?APPDATA|tempfile\.gettempdir\(", re.IGNORECASE)
	culpables = [
		str(archivo.relative_to(RAIZ)) for archivo in (RAIZ / "app").rglob("*.py")
		if prohibidas.search(archivo.read_text(encoding="utf-8", errors="replace"))
	]
	assert not culpables, f"Rutas fuera de data/: {culpables}"
