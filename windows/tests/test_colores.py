"""Colores de la lista (1.1.0): paleta, regla de cada producto, preferencias y lista."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from app.core import configuracion
from app.core.configuracion import Configuracion
from app.services import colores, errores, intercambio

from .conftest import COMPARTIDO, procesar_eventos

AHORA = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)


def _iso(dias: float) -> str:
	return (AHORA - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _producto(**cambios) -> dict:
	base = {
		"activo": 1, "disponible": 1, "ultima_comprobacion": _iso(0.1), "ultimo_error": "",
		"precio_actual": 50.0, "precio_anterior": None, "fecha_cambio": None,
		"precio_minimo": 50.0, "precio_maximo": 50.0, "precio_objetivo": None,
	}
	base.update(cambios)
	return base


# ── Paleta: la misma que la tabla de la especificación común ─────────────────


def test_paleta_igual_que_la_especificacion():
	texto = (COMPARTIDO / "ESPECIFICACION.md").read_text(encoding="utf-8")
	filas = re.findall(r"^\| `(\w+)` \| ([^|]+) \| (.+) \|$", texto, re.M)
	tabla = {}
	for identificador, nombre, resto in filas:
		celdas = [c.strip().strip("`") for c in resto.split("|")]
		if len(celdas) == 4:
			tabla[identificador] = (nombre.strip(), *[None if c == "—" else c for c in celdas])
	assert tabla, "no se encontró la tabla de la paleta en la especificación"
	assert {c.id: (c.nombre, c.fondo, c.texto, c.fondo_oscuro, c.texto_claro) for c in colores.PALETA} == tabla
	assert configuracion._IDS_COLORES == colores.IDS


def test_ajustes_de_colores_en_la_especificacion_y_la_exportacion():
	por_defecto = configuracion.VALORES_POR_DEFECTO["colores"]
	assert por_defecto == {
		"colores_lista": True, "colores_modo": "fondo", "color_bajada": "verde", "color_subida": "rojo",
		"color_objetivo": "azul", "color_problema": "gris",
	}
	for clave in por_defecto:
		assert clave in intercambio.CLAVES_AJUSTES
		assert configuracion.CLAVES_ESPECIFICACION[clave] == f"colores.{clave}"
	assert {f"color_{t}": v for t, v in colores.POR_DEFECTO.items()} == {
		k: v for k, v in por_defecto.items() if k.startswith("color_")}


# ── Qué color lleva cada producto ────────────────────────────────────────────


@pytest.mark.parametrize(("cambios", "esperado"), [
	({"activo": 0, "disponible": 0}, None),
	({"ultimo_error": "La tienda ha pedido comprobar que no eres un robot.", "estado": errores.BLOQUEADA}, colores.PROBLEMA),
	({"disponible": 0}, colores.PROBLEMA),
	({"ultima_comprobacion": None}, None),
	({"precio_objetivo": 55.0, "precio_anterior": 60.0, "fecha_cambio": _iso(1)}, colores.OBJETIVO),
	({"precio_anterior": 60.0, "fecha_cambio": _iso(2), "precio_maximo": 60.0}, colores.BAJADA),
	({"precio_anterior": 60.0, "fecha_cambio": _iso(30), "precio_minimo": 45.0, "precio_maximo": 60.0}, None),
	({"precio_anterior": 60.0, "fecha_cambio": _iso(30), "precio_minimo": 50.0, "precio_maximo": 60.0}, colores.BAJADA),
	({"precio_anterior": 40.0, "fecha_cambio": _iso(3), "precio_minimo": 40.0}, colores.SUBIDA),
	({"precio_anterior": 40.0, "fecha_cambio": _iso(8), "precio_minimo": 40.0}, None),
	({}, None),
])
def test_tipo_color(cambios, esperado):
	assert colores.tipo_color(_producto(**cambios), AHORA) == esperado


def test_tipo_color_de_los_avisos():
	assert [colores.tipo_color_aviso(t) for t in ("objetivo", "minimo", "bajada", "subida", "agotado", "error",
		"disponible", None)] == ["objetivo", "bajada", "bajada", "subida", "problema", "problema", None, None]


def test_pintura_segun_modo_y_valores_desconocidos():
	valores = {"colores.colores_lista": True, "colores.colores_modo": "fondo", "colores.color_bajada": "morado",
		"colores.color_subida": "inventado", "colores.color_objetivo": "ninguno"}
	ajustes = colores.leer_ajustes(lambda clave, defecto: valores.get(clave, defecto))
	assert ajustes.pintura(colores.BAJADA) == ("#E1BEE7", None)
	assert ajustes.pintura(colores.SUBIDA) == ("#FFCDD2", None), "desconocido → el de por defecto (rojo)"
	assert ajustes.pintura(colores.OBJETIVO) == (None, None)
	assert ajustes.pintura(None) == (None, None)
	valores["colores.colores_modo"] = "texto"
	assert colores.leer_ajustes(lambda c, d: valores.get(c, d)).pintura(colores.BAJADA) == (None, "#4A148C")
	valores["colores.colores_lista"] = False
	assert colores.leer_ajustes(lambda c, d: valores.get(c, d)).pintura(colores.BAJADA) == (None, None)


# ── Interfaz ─────────────────────────────────────────────────────────────────


def test_preferencias_colores_con_muestra_vista_previa_y_aplicar(app_wx, data_temporal):
	import wx
	import wx.adv

	from app.ui.dialogo_preferencias import DialogoPreferencias

	from . import msaa

	config = Configuracion()
	avisos = []
	config.suscribir(lambda clave, anterior, nuevo: avisos.append(clave))
	dialogo = DialogoPreferencias(None, config)
	try:
		titulos = [dialogo.libro.GetPageText(i) for i in range(dialogo.libro.GetPageCount())]
		assert "Colores" in titulos
		combo = dialogo.control_de("colores.color_bajada")
		assert isinstance(combo, wx.adv.BitmapComboBox) and combo.HasFlag(wx.CB_READONLY)
		assert [combo.GetString(i) for i in range(combo.GetCount())] == [c.nombre for c in colores.PALETA]
		assert combo.GetItemBitmap(1).IsOk(), "cada color lleva su muestra"
		assert combo.GetStringSelection() == "Verde"
		propiedades = msaa.propiedades(combo)
		assert propiedades["nombre"].rstrip(":") == "Color de bajada u oferta"
		assert propiedades["valor"] == "Verde" and propiedades["atajo"] == "Alt+b"
		# Vista previa: se repinta al elegir otro color, sin guardar nada todavía.
		combo.SetSelection(colores.IDS.index("naranja"))
		evento = wx.CommandEvent(wx.wxEVT_COMBOBOX, combo.GetId())
		evento.SetEventObject(combo)
		combo.GetEventHandler().ProcessEvent(evento)
		if not colores_desactivados_por_contraste():
			assert dialogo._muestras[colores.BAJADA].GetBackgroundColour() == wx.Colour("#FFE0B2")
		assert config.obtener("colores.color_bajada") == "verde"
		# La casilla general activa o desactiva el resto.
		casilla = dialogo.control_de("colores.colores_lista")
		casilla.SetValue(False)
		evento = wx.CommandEvent(wx.wxEVT_CHECKBOX, casilla.GetId())
		evento.SetEventObject(casilla)
		casilla.GetEventHandler().ProcessEvent(evento)
		assert not combo.IsEnabled()
		casilla.SetValue(True)
		casilla.GetEventHandler().ProcessEvent(evento)
		assert combo.IsEnabled()
		assert dialogo.aplicar()
		assert Configuracion().obtener("colores.color_bajada") == "naranja"
		assert "colores.color_bajada" in avisos, "las ventanas abiertas se enteran al momento"
		dialogo.restablecer_controles()
		assert combo.GetStringSelection() == "Verde"
	finally:
		dialogo.Destroy()


def colores_desactivados_por_contraste() -> bool:
	from app.ui.accesibilidad.visual import alto_contraste_activo

	return alto_contraste_activo()


def test_lista_pinta_filas_en_modo_normal_y_virtual(app_wx):
	import wx

	from app.ui.accesibilidad.lista import ListaAccesible

	marco = wx.Frame(None)
	try:
		for virtual in (False, True):
			lista = ListaAccesible(marco, "Productos", [("Estado", 80), ("Nombre", 120)], virtual=virtual)
			lista.reemplazar_filas([["En oferta", "Mando"], ["Correcto", "Cascos"], ["Agotado", "Consola"]])
			lista.colorear_filas([("#C8E6C9", None), (None, None), (None, "#424242")])
			assert lista.pintura_fila(0) == ("#C8E6C9", None) and lista.pintura_fila(1) == (None, None)
			if virtual:
				assert lista.OnGetItemAttr(0).GetBackgroundColour() == wx.Colour("#C8E6C9")
				assert lista.OnGetItemAttr(1) is None
				assert lista.OnGetItemAttr(2).GetTextColour() == wx.Colour("#424242")
				lista.eliminar_fila(0)
				assert lista.pintura_fila(1) == (None, "#424242"), "los colores siguen a su fila"
			else:
				assert lista.GetItemBackgroundColour(0) == wx.Colour("#C8E6C9")
				assert lista.GetItemTextColour(2) == wx.Colour("#424242")
			lista.reemplazar_filas([["Correcto", "Mando"]])
			assert lista.pintura_fila(0) == (None, None), "recargar borra los colores"
			procesar_eventos()
	finally:
		marco.Destroy()
