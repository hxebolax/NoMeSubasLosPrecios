"""Lógica de una comprobación: campos, historial y avisos con los textos exactos del contrato."""

from __future__ import annotations

from app.services import avisos as logica
from app.services.avisos import aplicar_error, aplicar_resultado

AHORA = "2026-11-02T20:00:00Z"
MENOS = "−"


def _producto(**cambios):
	base = {
		"id": 1, "nombre": "Robot", "url": "https://t.es/r", "moneda": "EUR", "precio_actual": 100.0, "disponible": 1,
		"precio_inicial": 120.0, "precio_minimo": 90.0, "precio_maximo": 120.0, "precio_objetivo": None,
		"alerta_porcentaje": 0, "avisar_disponible": 1, "errores_seguidos": 0, "imagen_url": "",
	}
	base.update(cambios)
	return base


def _aviso(cambios):
	assert len(cambios.avisos) <= 1, "un solo aviso por producto y comprobación"
	return cambios.avisos[0] if cambios.avisos else None


def test_primera_lectura_sin_objetivo():
	producto = _producto(precio_actual=None, precio_inicial=None, precio_minimo=None, precio_maximo=None)
	cambios = aplicar_resultado(producto, 59.9, True, ahora=AHORA, tienda="T", hay_historial=False)
	campos = cambios.campos
	assert (campos["precio_actual"], campos["precio_inicial"], campos["precio_minimo"], campos["precio_maximo"]) == (59.9,) * 4
	assert campos["fecha_minimo"] == campos["fecha_maximo"] == AHORA
	assert cambios.historial == (AHORA, 59.9, True)
	assert not cambios.avisos and "precio_anterior" not in campos


def test_primera_lectura_con_objetivo_alcanzado():
	producto = _producto(precio_actual=None, precio_minimo=None, precio_maximo=None, precio_objetivo=60)
	aviso = _aviso(aplicar_resultado(producto, 59.9, True, ahora=AHORA, tienda="Amazon", hay_historial=False))
	assert aviso.tipo == "objetivo" and aviso.titulo == "¡Precio deseado alcanzado!"
	assert aviso.mensaje == "Robot: 59,90 € en Amazon (querías 60,00 € o menos)."


def test_objetivo_al_cruzarlo():
	aviso = _aviso(aplicar_resultado(_producto(precio_objetivo=95), 94.0, True, ahora=AHORA, tienda="T"))
	assert aviso.tipo == "objetivo"
	ya_debajo = _aviso(aplicar_resultado(_producto(precio_actual=94.0, precio_objetivo=95), 93.0, True, ahora=AHORA, tienda="T"))
	assert ya_debajo.tipo == "bajada", "si ya estaba por debajo del objetivo no se repite el aviso de objetivo"


def test_minimo_historico():
	cambios = aplicar_resultado(_producto(), 85.0, True, ahora=AHORA, tienda="Amazon")
	aviso = _aviso(cambios)
	assert aviso.tipo == "minimo" and aviso.titulo == "Mínimo histórico"
	assert aviso.mensaje == "Robot: 85,00 € en Amazon, el precio más bajo visto (antes 100,00 €)."
	assert cambios.campos["precio_minimo"] == 85.0 and cambios.campos["fecha_minimo"] == AHORA


def test_bajada_texto_exacto():
	producto = _producto(precio_actual=369.0, precio_minimo=339.0, nombre="Robot Aspirador Ejemplo R5")
	cambios = aplicar_resultado(producto, 349.9, True, ahora=AHORA, tienda="Amazon")
	aviso = _aviso(cambios)
	assert aviso.titulo == "Ha bajado de precio"
	assert aviso.mensaje == f"Robot Aspirador Ejemplo R5: de 369,00 € a 349,90 € en Amazon ({MENOS}19,10 €, {MENOS}5,2 %)."
	assert cambios.campos["precio_anterior"] == 369.0 and cambios.campos["fecha_cambio"] == AHORA
	assert cambios.historial == (AHORA, 349.9, True)


def test_bajada_con_alerta_porcentaje():
	producto = _producto(alerta_porcentaje=10, precio_minimo=50.0)
	assert _aviso(aplicar_resultado(producto, 95.0, True, ahora=AHORA, tienda="T")) is None
	assert _aviso(aplicar_resultado(producto, 90.0, True, ahora=AHORA, tienda="T")).tipo == "bajada"


def test_subida_texto_exacto():
	aviso = _aviso(aplicar_resultado(_producto(), 110.0, True, ahora=AHORA, tienda="PcComponentes"))
	assert aviso.tipo == "subida" and aviso.titulo == "¡Te han subido el precio!"
	assert aviso.mensaje == "Robot: de 100,00 € a 110,00 € en PcComponentes (+10,00 €, +10 %)."


def test_maximo_al_subir():
	cambios = aplicar_resultado(_producto(), 130.0, True, ahora=AHORA, tienda="T")
	assert cambios.campos["precio_maximo"] == 130.0 and cambios.campos["fecha_maximo"] == AHORA


def test_cambio_minimo_porcentaje():
	ajustes = {"cambio_minimo_porcentaje": 5.0}
	cambios = aplicar_resultado(_producto(), 97.0, True, ahora=AHORA, tienda="T", ajustes=ajustes)
	assert not cambios.avisos and cambios.campos["precio_actual"] == 97.0 and cambios.historial is not None
	assert _aviso(aplicar_resultado(_producto(), 94.0, True, ahora=AHORA, tienda="T", ajustes=ajustes)) is not None


def test_avisos_desactivados_en_ajustes():
	ajustes = {"avisar_bajadas": False, "avisar_minimo": False, "avisar_subidas": False}
	assert not aplicar_resultado(_producto(), 80.0, True, ahora=AHORA, tienda="T", ajustes=ajustes).avisos
	assert not aplicar_resultado(_producto(), 120.0, True, ahora=AHORA, tienda="T", ajustes=ajustes).avisos


def test_vuelve_a_estar_disponible_y_agotado():
	cambios = aplicar_resultado(_producto(disponible=0), 100.0, True, ahora=AHORA, tienda="Amazon")
	aviso = _aviso(cambios)
	assert aviso.tipo == "disponible" and aviso.titulo == "Vuelve a estar disponible"
	assert aviso.mensaje == "Robot vuelve a estar disponible en Amazon a 100,00 €."
	assert cambios.campos["disponible"] == 1 and cambios.historial == (AHORA, 100.0, True)
	assert not aplicar_resultado(_producto(disponible=0, avisar_disponible=0), 100.0, True, ahora=AHORA, tienda="T").avisos
	agotado = aplicar_resultado(_producto(), None, False, ahora=AHORA, tienda="Amazon")
	assert not agotado.avisos, "avisar_agotado está desactivado por defecto"
	assert agotado.historial == (AHORA, 100.0, False) and "precio_actual" not in agotado.campos
	aviso = _aviso(aplicar_resultado(_producto(), None, False, ahora=AHORA, tienda="Amazon", ajustes={"avisar_agotado": True}))
	assert aviso.tipo == "agotado" and aviso.mensaje == "Robot se ha agotado en Amazon."


def test_precio_y_disponibilidad_en_el_mismo_mensaje():
	aviso = _aviso(aplicar_resultado(_producto(disponible=0), 110.0, True, ahora=AHORA, tienda="T"))
	assert aviso.tipo == "subida"
	assert aviso.mensaje.endswith("(+10,00 €, +10 %). Robot vuelve a estar disponible en T a 110,00 €.")


def test_sin_cambios_no_hay_historial_ni_aviso():
	cambios = aplicar_resultado(_producto(), 100.0, True, ahora=AHORA, tienda="T")
	assert cambios.historial is None and not cambios.avisos
	assert cambios.campos["errores_seguidos"] == 0 and cambios.campos["ultimo_error"] == ""


def test_nombre_vacio_se_rellena_y_imagen():
	cambios = aplicar_resultado(_producto(nombre=""), 100.0, True, ahora=AHORA, tienda="T", nombre_pagina="Robot X", imagen="i.jpg")
	assert cambios.campos["nombre"] == "Robot X" and cambios.campos["imagen_url"] == "i.jpg"


def test_tres_errores_seguidos():
	segundo = aplicar_error(_producto(errores_seguidos=1), "Fallo", ahora=AHORA, tienda="T", ajustes={"avisar_errores": True})
	assert segundo.campos["errores_seguidos"] == 2 and not segundo.avisos
	tercero = aplicar_error(_producto(errores_seguidos=2), "Fallo", ahora=AHORA, tienda="Amazon", ajustes={"avisar_errores": True})
	aviso = _aviso(tercero)
	assert aviso.tipo == "error" and aviso.titulo == "No se puede leer el precio"
	assert aviso.mensaje == "Robot (Amazon): Fallo"
	assert set(tercero.campos) == {"ultimo_error", "errores_seguidos", "ultima_comprobacion", "estado"}
	assert not aplicar_error(_producto(errores_seguidos=2), "F", ahora=AHORA, tienda="T").avisos, "avisar_errores es false por defecto"
	assert not aplicar_error(_producto(errores_seguidos=3), "F", ahora=AHORA, tienda="T", ajustes={"avisar_errores": True}).avisos


def test_resumen_y_confianza():
	assert logica.texto_resumen(5) == "5 productos han cambiado de precio"
	cambios = aplicar_resultado(
		_producto(), 100.0, True, ahora=AHORA, tienda="T", confianza="media", desde=True, origen_precio="JSON-LD"
	)
	assert (cambios.campos["confianza"], cambios.campos["desde"], cambios.campos["origen_precio"]) == ("media", 1, "JSON-LD")
