"""Base de datos, repositorio, intercambio JSON/CSV y núcleo (sin red ni ventanas)."""

from __future__ import annotations

import json

import pytest

from app.core.base_datos import BaseDatos
from app.core.configuracion import Configuracion
from app.core.migraciones import MIGRACIONES
from app.services import intercambio
from app.services.avisos import Aviso, Cambios
from app.services.nucleo import Nucleo
from app.services.repositorio import ErrorDatos, Repositorio

from .conftest import PRUEBAS_COMUNES

EJEMPLO = PRUEBAS_COMUNES / "exportacion-ejemplo.json"


@pytest.fixture
def bd(data_temporal):
	base = BaseDatos(data_temporal / "db" / "precios.db", MIGRACIONES, carpeta_copias=data_temporal / "backups")
	yield base
	base.cerrar()


@pytest.fixture
def repo(bd):
	return Repositorio(bd)


def _columnas(bd, tabla):
	return {fila["name"] for fila in bd.consultar(f"PRAGMA table_info({tabla})")}


def test_esquema_del_contrato(bd):
	assert bd.version() == len(MIGRACIONES)
	assert {"id", "uuid", "nombre", "descripcion", "orden"} <= _columnas(bd, "categorias")
	assert {"uuid", "nombre", "dominio", "selector_precio", "selector_titulo", "selector_disponible", "notas", "modo_descarga"} <= _columnas(bd, "tiendas")
	productos = _columnas(bd, "productos")
	for columna in ("precio_actual", "precio_objetivo", "alerta_porcentaje", "avisar_disponible", "ultimo_error", "errores_seguidos",
		"variante", "origen_precio", "confianza", "huella_selector", "desde"):
		assert columna in productos
	assert {"producto_id", "fecha", "precio", "disponible"} <= _columnas(bd, "historial")
	assert {"producto_id", "fecha", "tipo", "titulo", "mensaje", "leido"} <= _columnas(bd, "avisos")


def test_categorias_unicas_sin_mayusculas_orden_y_borrado(repo):
	a = repo.crear_categoria("Hogar")
	b = repo.crear_categoria("Electrónica")
	with pytest.raises(ErrorDatos):
		repo.crear_categoria("hogar")
	with pytest.raises(ErrorDatos):
		repo.crear_categoria("Sin categoría")
	assert [c["nombre"] for c in repo.categorias()] == ["Hogar", "Electrónica"]
	assert repo.mover_categoria(b, -1) and not repo.mover_categoria(b, -1)
	assert [c["nombre"] for c in repo.categorias()] == ["Electrónica", "Hogar"]
	tienda = repo.obtener_o_crear_tienda("t.es", "T")
	producto = repo.crear_producto(url="https://t.es/1", tienda_id=tienda, categoria_id=a)
	repo.borrar_categoria(a)
	assert repo.producto(producto)["categoria"] == "Sin categoría"


def test_tiendas_solo_se_borran_vacias(repo):
	tienda = repo.obtener_o_crear_tienda("t.es", "T")
	assert repo.obtener_o_crear_tienda("t.es", "Otro") == tienda
	producto = repo.crear_producto(url="https://t.es/1", tienda_id=tienda)
	with pytest.raises(ErrorDatos):
		repo.borrar_tienda(tienda)
	repo.eliminar_productos([producto])
	repo.actualizar_tienda(tienda, modo_descarga="raro", nombre="Nueva")
	assert repo.tienda(tienda)["modo_descarga"] == "auto" and repo.tienda(tienda)["nombre"] == "Nueva"
	repo.borrar_tienda(tienda)
	assert repo.tiendas() == []


def test_aplicar_cambios_es_atomico_e_historial_y_avisos_en_cascada(repo, bd):
	tienda = repo.obtener_o_crear_tienda("t.es", "T")
	producto = repo.crear_producto(url="https://t.es/1", tienda_id=tienda, nombre="X")
	cambios = Cambios(campos={"precio_actual": 10.0}, historial=("2026-11-02T10:00:00Z", 10.0, True),
		avisos=[Aviso("bajada", "Ha bajado de precio", "X")])
	ids = repo.aplicar_cambios(producto, cambios, "2026-11-02T10:00:00Z")
	assert len(ids) == 1 and repo.avisos_sin_leer() == 1
	assert repo.historial(producto) == [{"fecha": "2026-11-02T10:00:00Z", "precio": 10.0, "disponible": 1}]
	repo.eliminar_productos([producto])
	assert bd.valor("SELECT COUNT(*) FROM historial") == 0, "el historial se borra en cascada"
	assert repo.avisos()[0]["producto_id"] is None, "el aviso se conserva sin producto"


def test_avisos_orden_marcar_y_purgar(repo):
	viejo = repo.crear_aviso(None, "2020-01-01T00:00:00Z", "bajada", "A", "viejo")
	nuevo = repo.crear_aviso(None, "2026-11-02T00:00:00Z", "subida", "B", "nuevo")
	repo.marcar_avisos([nuevo])
	assert [a["id"] for a in repo.avisos()] == [viejo, nuevo], "los no leídos primero"
	assert repo.purgar_avisos(90) == 1
	assert repo.purgar_avisos(0) == 0


def test_copia_de_seguridad_diaria_y_rotacion(data_temporal):
	config = Configuracion()
	nucleo = Nucleo(config)
	try:
		assert nucleo.copia_diaria_si_toca() is not None
		assert nucleo.copia_diaria_si_toca() is None, "una al día"
		for _ in range(9):
			nucleo.bd.copia_seguridad("prueba")
		assert len(list((data_temporal / "backups").glob("precios-*.db"))) == 7
	finally:
		nucleo.cerrar()


def test_importar_ejemplo_exportar_y_comparar(bd):
	original = json.loads(EJEMPLO.read_text(encoding="utf-8"))
	analisis = intercambio.analizar(bd, intercambio.leer_archivo(EJEMPLO))
	assert analisis.texto() == "El archivo tiene 3 productos, 2 categorías y 2 tiendas. Se añadirán 3 productos y se actualizarán 0."
	resultado = intercambio.importar(bd, intercambio.leer_archivo(EJEMPLO))
	assert (resultado.nuevos, resultado.actualizados, resultado.ajustes) == (3, 0, {"intervalo_horas": 6, "avisar_subidas": True})
	exportado = intercambio.construir_exportacion(bd)
	assert list(exportado)[:8] == ["formato", "version_formato", "app", "version_app", "exportado", "categorias", "tiendas", "productos"]
	assert exportado["categorias"] == original["categorias"]
	assert [{k: t[k] for k in original["tiendas"][0]} for t in exportado["tiendas"]] == original["tiendas"]
	por_uuid = {p["uuid"]: p for p in exportado["productos"]}
	for producto in original["productos"]:
		assert {k: por_uuid[producto["uuid"]][k] for k in producto} == producto
	assert sorted(json.dumps(a, sort_keys=True) for a in exportado["avisos"]) == sorted(
		json.dumps(a, sort_keys=True) for a in original["avisos"])


def test_combinar_dos_veces_no_duplica(bd):
	datos = intercambio.leer_archivo(EJEMPLO)
	intercambio.importar(bd, datos)
	segundo = intercambio.importar(bd, datos)
	assert (segundo.nuevos, segundo.actualizados) == (0, 3)
	assert bd.valor("SELECT COUNT(*) FROM productos") == 3
	assert bd.valor("SELECT COUNT(*) FROM historial") == 8
	assert bd.valor("SELECT COUNT(*) FROM avisos") == 2
	assert bd.valor("SELECT COUNT(*) FROM tiendas") == 2


def test_combinar_por_url_y_dato_mas_reciente(bd, repo):
	tienda = repo.obtener_o_crear_tienda("amazon.es", "Amazon")
	propio = repo.crear_producto(url="https://www.amazon.es/dp/B0EJEMPLO1", tienda_id=tienda, nombre="Mío", precio_actual=1.0,
		ultima_comprobacion="2030-01-01T00:00:00Z")
	intercambio.importar(bd, intercambio.leer_archivo(EJEMPLO))
	producto = repo.producto(propio)
	assert producto["nombre"] == "Robot Aspirador Ejemplo R5", "lo que puso el usuario viene del archivo"
	assert producto["precio_actual"] == 1.0, "el precio local es más reciente"
	assert bd.valor("SELECT COUNT(*) FROM productos") == 3


def test_reemplazar_hace_copia_y_es_atomico(bd, repo, data_temporal):
	repo.obtener_o_crear_tienda("t.es", "T")
	resultado = intercambio.importar(bd, intercambio.leer_archivo(EJEMPLO), intercambio.REEMPLAZAR)
	assert resultado.copia is not None and resultado.copia.is_file()
	assert repo.tienda_por_dominio("t.es") is None
	roto = intercambio.leer_archivo(EJEMPLO)
	roto["productos"].append({"uuid": "x", "url": "https://t.es/1", "historial": [{"fecha": "2026-01-01T00:00:00Z", "precio": "no"}],
		"precio_actual": 5, "errores_seguidos": 0, "tienda": "no-existe"})
	roto["categorias"].append({"uuid": "c", "nombre": "Nueva", "orden": 0})
	antes = bd.valor("SELECT COUNT(*) FROM categorias")
	intercambio.importar(bd, roto)
	assert bd.valor("SELECT COUNT(*) FROM categorias") == antes + 1


def test_errores_de_formato(tmp_path):
	otro = tmp_path / "otro.json"
	otro.write_text('{"formato": "otro"}', encoding="utf-8")
	with pytest.raises(intercambio.ErrorIntercambio, match="no es una exportación"):
		intercambio.leer_archivo(otro)
	nuevo = tmp_path / "nuevo.json"
	nuevo.write_text('{"formato": "NoMeSubasLosPrecios", "version_formato": 9}', encoding="utf-8")
	with pytest.raises(intercambio.ErrorIntercambio, match="versión más nueva"):
		intercambio.leer_archivo(nuevo)


def test_producto_sin_url_no_valido(bd):
	datos = intercambio.leer_archivo(EJEMPLO)
	datos["productos"].append({"uuid": "sin-url"})
	assert intercambio.analizar(bd, datos).no_validos == 1
	assert intercambio.importar(bd, datos).no_validos == 1


def test_exportar_json_atomico_y_csv(bd, repo, tmp_path):
	intercambio.importar(bd, intercambio.leer_archivo(EJEMPLO))
	ruta = tmp_path / intercambio.nombre_propuesto("2026-11-02T00:00:00Z")
	assert ruta.name == "NoMeSubasLosPrecios-2026-11-02.json"
	intercambio.exportar_json(bd, ruta, {"intervalo_horas": 12, "sonidos": False})
	texto = ruta.read_text(encoding="utf-8")
	assert not texto.startswith("﻿") and '\n  "formato": "NoMeSubasLosPrecios"' in texto
	assert json.loads(texto)["ajustes"] == {"intervalo_horas": 12, "sonidos": False}
	csv = tmp_path / "p.csv"
	assert intercambio.exportar_csv(repo.productos(), csv) == 3
	contenido = csv.read_bytes()
	assert contenido.startswith(b"\xef\xbb\xbf")
	lineas = contenido.decode("utf-8-sig").splitlines()
	assert lineas[0].startswith("Nombre;Tienda;Categoría")
	assert any(";349,90;" in linea for linea in lineas)


def test_nucleo_ajustes_y_calendario(data_temporal):
	config = Configuracion()
	nucleo = Nucleo(config)
	try:
		ajustes = nucleo.ajustes()
		assert ajustes["intervalo_horas"] == 6 and ajustes["avisar_agotado"] is False and ajustes["minimizar_a_bandeja"] is True
		assert nucleo.toca_comprobar()
		nucleo.anotar_comprobacion()
		assert not nucleo.toca_comprobar()
		assert nucleo.aplicar_ajustes_importados({"intervalo_horas": 12, "cambio_minimo_porcentaje": 2, "raro": 1, "tiempo_espera": "x"}) == 2
		assert config.obtener("precios.intervalo_horas") == 12 and config.obtener("precios.cambio_minimo_porcentaje") == 2.0
	finally:
		nucleo.cerrar()
