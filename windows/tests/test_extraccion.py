"""Extracción: páginas de ejemplo comunes, extractor ampliado, API de la tienda y selectores."""

from __future__ import annotations

import json

import pytest
from bs4 import BeautifulSoup

from app.services import api_tienda, extractor, reglas, selector_css, seleccion
from app.services.direcciones import dominio_de
from app.services.extractor import extraer

from .conftest import PRUEBAS_COMUNES, TIENDAS_JSON

PAGINAS = json.loads((PRUEBAS_COMUNES / "paginas.json").read_text(encoding="utf-8"))["paginas"]
GENERICO = json.loads((PRUEBAS_COMUNES / "extractor_generico.json").read_text(encoding="utf-8"))["casos"]


@pytest.fixture(scope="module")
def catalogo():
	return reglas.cargar_catalogo(TIENDAS_JSON)


@pytest.mark.parametrize("caso", PAGINAS, ids=[c["archivo"] for c in PAGINAS])
def test_paginas_comunes(caso, catalogo):
	html = (PRUEBAS_COMUNES / "paginas" / caso["archivo"]).read_text(encoding="utf-8")
	dominio = dominio_de(caso["url"])
	tienda = catalogo.buscar(dominio)
	if caso["archivo"] == "selector_tienda.html" and tienda is not None and not tienda.precio:
		# Esta página prueba la regla CSS de la tienda; si tiendas.json se queda sin
		# reglas de precio para ella, el caso no puede pasar (avisado en el informe).
		pytest.xfail(f"tiendas.json no tiene reglas de precio para {dominio}: el caso de prueba depende de ellas")
	resultado = extraer(html, dominio, catalogo, url=caso["url"], nombre_tienda=catalogo.nombre_tienda(dominio))
	for campo in ("precio", "moneda", "nombre", "disponible", "imagen", "bloqueo"):
		if campo in caso:
			assert getattr(resultado, campo) == caso[campo], campo
	if caso.get("error"):
		assert not resultado.valido and resultado.error
	else:
		assert resultado.valido


@pytest.mark.parametrize("caso", GENERICO, ids=[c["nombre"] for c in GENERICO])
def test_extractor_generico_comun(caso, catalogo):
	resultado = extraer(caso["html"], dominio_de(caso["url"]), catalogo, url=caso["url"])
	assert resultado.precio == caso["precio"]
	if caso.get("origen"):
		assert resultado.origen_precio == caso["origen"]
	if caso.get("plataforma"):
		assert resultado.plataforma == caso["plataforma"]
	decision = "acepta" if resultado.precio is not None else ("error" if resultado.categoria else "pregunta")
	assert decision == caso["decision"]
	if "nombre_producto" in caso:
		assert resultado.nombre == caso["nombre_producto"]
	for campo in ("desde", "disponible", "bloqueo", "categoria"):
		if campo in caso:
			assert getattr(resultado, campo) == caso[campo], campo


def test_catalogo_busca_por_dominio_y_subdominio(catalogo):
	assert catalogo.buscar("amazon.es").nombre == "Amazon"
	assert catalogo.buscar("www.amazon.es") is None or catalogo.buscar("www.amazon.es").nombre == "Amazon"
	assert catalogo.buscar("es.aliexpress.com").id == "aliexpress"
	assert catalogo.buscar("noexiste.invalid") is None
	assert catalogo.nombre_tienda("tiendaejemplo.es") == "Tiendaejemplo"


def test_selector_del_producto_gana_y_origen(catalogo):
	html = '<span id="mio">10,00 €</span><script type="application/ld+json">{"@type":"Product","offers":{"price":20}}</script>'
	resultado = extraer(html, "t.es", catalogo, selector_producto="#mio")
	assert (resultado.precio, resultado.origen_precio, resultado.confianza) == (10.0, extractor.ORIGEN_PRODUCTO, "alta")
	sin_selector = extraer(html, "t.es", catalogo)
	assert (sin_selector.precio, sin_selector.origen_precio) == (20.0, extractor.ORIGEN_JSONLD)


def test_selector_no_valido_no_rompe(catalogo):
	html = '<meta property="og:price:amount" content="5.5">'
	assert extraer(html, "t.es", catalogo, selector_producto="##mal[").precio == 5.5


def test_selector_a_un_meta_lee_content(catalogo):
	html = '<div id="p"><meta itemprop="price" content="12.90"></div>'
	assert extraer(html, "t.es", catalogo, selector_producto="#p meta").precio == 12.9


def test_variante_elegida_por_el_usuario(catalogo):
	html = ('<script type="application/ld+json">{"@type":"ProductGroup","name":"Café","hasVariant":['
		'{"@type":"Product","sku":"C250","name":"Café 250 g","offers":{"price":12}},'
		'{"@type":"Product","sku":"C1K","name":"Café 1 kg","offers":{"price":40}}]}</script>')
	desde = extraer(html, "t.es", catalogo, url="https://t.es/cafe")
	assert desde.desde and [v.clave for v in desde.variantes] == ["C250", "C1K"]
	elegida = extraer(html, "t.es", catalogo, url="https://t.es/cafe", variante="C1K")
	assert (elegida.precio, elegida.desde, elegida.nombre) == (40.0, False, "Café")


def test_bloqueo_sin_palabra_captcha_suelta(catalogo):
	html = "<html><body>Para continuar resuelve el captcha</body></html>"
	resultado = extraer(html, "t.es", catalogo)
	assert not resultado.bloqueo and resultado.error


def test_bloqueo_sin_distinguir_mayusculas(catalogo):
	resultado = extraer("<p>ACCESS DENIED</p>", "t.es", catalogo)
	assert resultado.bloqueo and resultado.estado == "bloqueada"


def test_candidatos_para_elegir_y_selector_valido():
	html = (
		'<main><h1>Robot</h1><span class="price old">249,00 €</span><span class="price current-price">199,00 €</span>'
		'<form><button>Añadir al carrito</button></form></main><ul class="related"><li><span class="price">5,00 €</span></li></ul>'
	)
	candidatos, _sopa = extractor.candidatos_para_elegir(html, "https://t.es/robot")
	assert candidatos[0].valor == 199.0
	assert "junto al botón de compra" in candidatos[0].descripcion
	assert any("tachado" in c.descripcion for c in candidatos if c.valor == 249.0)
	selector, huella = seleccion.selector_para(candidatos[0])
	assert extraer(html, "t.es", None, selector_producto=selector).precio == 199.0
	assert json.loads(huella)["importe"] == 199.0


def test_selector_css_estable():
	for nombre in ("product-price", "current-price", "price__current", "js-product-price", "woocommerce-Price-amount"):
		assert selector_css.palabra_estable(nombre), nombre
	for nombre in ("css-1x2y3z", "sc-abc123", "Price_price__a1B2c", "md:text-lg", "is-active"):
		assert not selector_css.palabra_estable(nombre), nombre
	sopa = BeautifulSoup('<div><span data-test="product-price">19,99 €</span></div>', "html.parser")
	elemento = sopa.find("span")
	selector, atributo = selector_css.generar_selector(elemento, sopa)
	assert selector == 'span[data-test="product-price"]' and atributo is None


def test_api_de_la_tienda_rutas_y_resultado(catalogo):
	api = catalogo.buscar("tienda.mercadona.es").api
	assert api_tienda.url_api(api, "https://tienda.mercadona.es/product/12345/aceite") == "https://tienda.mercadona.es/api/products/12345/"
	assert api_tienda.url_api(api, "https://tienda.mercadona.es/categories/1") is None
	datos = {"display_name": "Aceite  1 l", "price_instructions": {"unit_price": "8.45"}, "photos": [{"regular": "f.jpg"}],
		"published": True}
	resultado = api_tienda.resultado_de_api(api, json.dumps(datos))
	assert (resultado.precio, resultado.nombre, resultado.imagen, resultado.disponible) == (8.45, "Aceite 1 l", "f.jpg", True)
	assert resultado.origen_precio == extractor.ORIGEN_API and resultado.confianza == "alta"
	consum = catalogo.buscar("tienda.consum.es").api
	respuesta = {"productData": {"name": "Leche", "availability": "1"},
		"priceData": {"prices": [{"id": "PRICE", "value": {"centAmount": 0.96}}, {"id": "OFFER_PRICE", "value": {"centAmount": 0.89}}]}}
	resultado = api_tienda.resultado_de_api(consum, json.dumps(respuesta))
	assert (resultado.precio, resultado.disponible) == (0.89, True)
	assert api_tienda.leer_ruta({"a": [{"b": 1}, {"b": 2}]}, "a.1.b") == 2
	assert api_tienda.leer_ruta({"a": [{"k": "x", "v": 1}]}, "a[k=y].v") is None
	assert not api_tienda.resultado_de_api(api, "no es json").valido


def test_regla_css_de_la_tienda_con_catalogo_propio():
	"""La página «selector_tienda.html» con una regla de precio como la que tenía Carrefour."""
	propio = reglas.catalogo_desde_datos({"tiendas": [{
		"id": "carrefour", "nombre": "Carrefour", "dominios": ["carrefour.es"],
		"precio": [{"css": ".buybox__price--current"}, {"css": ".buybox__price"}],
		"titulo": [{"css": "h1.product-header__name"}],
		"disponible": [{"css": ".buybox", "agotado": ["agotado"]}],
	}]})
	html = (PRUEBAS_COMUNES / "paginas" / "selector_tienda.html").read_text(encoding="utf-8")
	resultado = extraer(html, "carrefour.es", propio, url="https://www.carrefour.es/supermercado/aceite/R-1234/p")
	assert (resultado.precio, resultado.origen_precio, resultado.disponible) == (8.49, extractor.ORIGEN_REGLA, True)
	assert resultado.nombre == "Aceite de oliva virgen extra 1 l"
