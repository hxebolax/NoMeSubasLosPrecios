"""Origen de las actualizaciones (1.2.0): servidor del autor, GitHub, los dos o una dirección propia."""

from __future__ import annotations

import sys

import pytest

pytest.importorskip("cryptography")

from apoyo_actualizador import Servidor, cargar_firmador, publicar  # noqa: E402

from app.core import configuracion  # noqa: E402
from app.core.configuracion import Configuracion  # noqa: E402
from app.services import actualizador, intercambio  # noqa: E402

ARCHIVOS = {"NoMeSubasLosPrecios.exe": b"EXE nuevo"}


@pytest.mark.parametrize(("entrada", "esperado"), [
	("https://x.es/carpeta", "https://x.es/carpeta/"),
	("  https://x.es/carpeta/  ", "https://x.es/carpeta/"),
	("https://x.es/c/version.json", "https://x.es/c/"),
	("https://x.es/c/windows/version.json", "https://x.es/c/"),
	("http://localhost:8000/a", "http://localhost:8000/a/"),
	("http://127.0.0.1/a/", "http://127.0.0.1/a/"),
	("http://x.es/", ""),
	("ftp://x.es/", ""),
	("x.es/carpeta", ""),
	("https://x.es/c/?t=1", ""),
	("", ""),
	(None, ""),
])
def test_base_personalizada(entrada, esperado):
	assert actualizador.base_personalizada(entrada) == esperado


def test_urls_de_cada_origen():
	servidor = "https://xebolax.synology.me/NoMeSubasLosPrecios/windows/version.json"
	github = "https://github.com/hxebolax/NoMeSubasLosPrecios/releases/latest/download/version-windows.json"
	assert actualizador.urls_de_origen("servidor") == (servidor,)
	assert actualizador.urls_de_origen("github") == (github,)
	assert actualizador.urls_de_origen("ambos") == (servidor, github)
	assert actualizador.urls_de_origen("personalizada", "https://mi.es/nmslp") == ("https://mi.es/nmslp/windows/version.json",)
	assert actualizador.urls_de_origen("personalizada", "http://mi.es/") == (servidor,), "no válida: el del autor"
	assert actualizador.urls_de_origen("inventado") == (servidor,)
	assert [valor for valor, _texto in actualizador.ORIGENES] == list(
		configuracion.REGLAS["precios.origen_actualizaciones"].opciones)


def test_ajustes_en_la_exportacion():
	assert configuracion.VALORES_POR_DEFECTO["precios"]["origen_actualizaciones"] == "servidor"
	assert configuracion.VALORES_POR_DEFECTO["precios"]["url_actualizaciones"] == ""
	for clave in ("origen_actualizaciones", "url_actualizaciones"):
		assert clave in intercambio.CLAVES_AJUSTES
		assert configuracion.CLAVES_ESPECIFICACION[clave] == f"precios.{clave}"


@pytest.fixture
def dos_servidores(tmp_path):
	a, b = Servidor(tmp_path / "a"), Servidor(tmp_path / "b")
	yield a, b
	a.cerrar()
	b.cerrar()


@pytest.fixture
def clave(tmp_path, monkeypatch):
	firmador = cargar_firmador()
	monkeypatch.delenv(firmador.VARIABLE_CONTRASENA, raising=False)
	ruta = tmp_path / "claves" / "firma.key"
	return ruta, firmador.generar(ruta)


def _config(tmp_path, clave, urls):
	instalacion = tmp_path / "App"
	(instalacion / "data" / "config").mkdir(parents=True, exist_ok=True)
	return actualizador.Configuracion(
		version_actual="1.0.0", carpeta_app=instalacion, url_manifiesto=urls[0], urls_manifiesto=tuple(urls),
		claves_publicas=(clave[1],), comando=[sys.executable, "main.py"], permitir_desde_codigo=True,
	)


def test_ambos_gana_la_version_mas_nueva_y_el_zip_es_de_su_carpeta(tmp_path, dos_servidores, clave):
	a, b = dos_servidores
	publicar(a.carpeta, "1.1.0", ARCHIVOS, clave[0])
	publicar(b.carpeta, "1.2.0", ARCHIVOS, clave[0])
	info = actualizador.comprobar(_config(tmp_path, clave, [a.url("version.json"), b.url("version.json")]))
	assert info.version == "1.2.0" and info.url_zip == b.url("NoMeSubasLosPrecios_v1.2.0.zip")


def test_ambos_con_empate_gana_el_primero(tmp_path, dos_servidores, clave):
	a, b = dos_servidores
	publicar(a.carpeta, "1.2.0", ARCHIVOS, clave[0])
	publicar(b.carpeta, "1.2.0", ARCHIVOS, clave[0])
	info = actualizador.comprobar(_config(tmp_path, clave, [a.url("version.json"), b.url("version.json")]))
	assert info.url_zip == a.url("NoMeSubasLosPrecios_v1.2.0.zip")


def test_ambos_si_uno_falla_vale_el_otro(tmp_path, dos_servidores, clave):
	a, b = dos_servidores
	publicar(b.carpeta, "1.2.0", ARCHIVOS, clave[0])  # el primero no tiene nada: 404
	info = actualizador.comprobar(_config(tmp_path, clave, [a.url("version.json"), b.url("version.json")]))
	assert info.version == "1.2.0"
	publicar(a.carpeta, "1.0.0", ARCHIVOS, clave[0])
	(b.carpeta / "version.json").unlink()
	assert actualizador.comprobar(_config(tmp_path, clave, [a.url("version.json"), b.url("version.json")])) is None


def test_ambos_fallan_da_el_primer_error(tmp_path, dos_servidores, clave):
	a, b = dos_servidores
	publicar(b.carpeta, "1.2.0", ARCHIVOS, None)  # sin firma
	with pytest.raises(actualizador.ErrorRed):
		actualizador.comprobar(_config(tmp_path, clave, [a.url("version.json"), b.url("version.json")]))


def test_una_firma_ajena_nunca_gana(tmp_path, dos_servidores, clave):
	a, b = dos_servidores
	publicar(a.carpeta, "1.1.0", ARCHIVOS, clave[0])
	otra = tmp_path / "otra" / "firma.key"
	cargar_firmador().generar(otra)
	publicar(b.carpeta, "9.9.9", ARCHIVOS, otra)
	info = actualizador.comprobar(_config(tmp_path, clave, [a.url("version.json"), b.url("version.json")]))
	assert info.version == "1.1.0"


def test_preferencias_origen_y_direccion(app_wx, data_temporal, monkeypatch):
	import wx

	from app.ui import dialogo_preferencias as mod

	avisos = []
	monkeypatch.setattr(mod, "mostrar_aviso", lambda padre, texto, titulo: avisos.append(texto))
	config = Configuracion()
	dialogo = mod.DialogoPreferencias(None, config)
	try:
		origen = dialogo.control_de("precios.origen_actualizaciones")
		campo = dialogo.control_de("precios.url_actualizaciones")
		assert origen.GetStrings() == [texto for _valor, texto in actualizador.ORIGENES]
		assert not campo.IsEnabled(), "la dirección solo con «Dirección personalizada»"
		origen.SetSelection(3)
		evento = wx.CommandEvent(wx.wxEVT_CHOICE, origen.GetId())
		evento.SetEventObject(origen)
		origen.GetEventHandler().ProcessEvent(evento)
		assert campo.IsEnabled()
		campo.SetValue("http://inseguro.es/")
		assert not dialogo.aplicar() and "https://" in avisos[-1]
		assert config.obtener("precios.origen_actualizaciones") == "servidor", "no se guarda nada"
		campo.SetValue("https://mi-servidor.es/NoMeSubasLosPrecios")
		assert dialogo.aplicar()
		assert config.obtener("precios.origen_actualizaciones") == "personalizada"
		assert config.obtener("precios.url_actualizaciones") == "https://mi-servidor.es/NoMeSubasLosPrecios"
		origen.SetSelection(1)
		origen.GetEventHandler().ProcessEvent(evento)
		campo.SetValue("cualquier cosa")
		assert dialogo.aplicar(), "con GitHub no se valida la dirección (está desactivada)"
	finally:
		dialogo.Destroy()
