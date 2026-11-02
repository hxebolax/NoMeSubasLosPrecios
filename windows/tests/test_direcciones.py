"""Limpieza de direcciones y dominio: vectores comunes (compartido/pruebas/direcciones.json)."""

from __future__ import annotations

import json

import pytest

from app.services.direcciones import dominio_de, es_url, extraer_primera_url, limpiar_url
from app.services.reglas import nombre_desde_dominio

from .conftest import PRUEBAS_COMUNES

VECTORES = json.loads((PRUEBAS_COMUNES / "direcciones.json").read_text(encoding="utf-8"))["direcciones"]


@pytest.mark.parametrize("caso", VECTORES, ids=[c["dominio"] for c in VECTORES])
def test_vectores_comunes(caso):
	assert limpiar_url(caso["entrada"]) == caso["limpia"]
	assert dominio_de(caso["entrada"]) == caso["dominio"]


def test_limpiar_es_idempotente():
	for caso in VECTORES:
		assert limpiar_url(caso["limpia"]) == caso["limpia"]


def test_parametros_de_seguimiento_y_resto():
	url = "https://tienda.es/p?id=7&utm_source=x&pd_rd_w=1&pf_rd_p=2&fbclid=3&keywords=a&color=azul#f"
	assert limpiar_url(url) == "https://tienda.es/p?id=7&color=azul"


def test_amazon_con_otro_tld_y_sin_www():
	assert limpiar_url("http://amazon.co.uk/x/dp/B000000001?tag=a") == "https://www.amazon.co.uk/dp/B000000001"
	assert dominio_de("https://www.amazon.co.uk/dp/B000000001") == "amazon.co.uk"


def test_portapapeles():
	assert es_url("https://www.tienda.es/p/1")
	assert es_url("www.tienda.es/p")
	assert not es_url("hola que tal")
	assert extraer_primera_url("Mira esto: https://t.es/p/1. ¡Barato!") == "https://t.es/p/1"
	assert extraer_primera_url("sin direcciones") is None


def test_nombre_de_tienda_desde_dominio():
	assert nombre_desde_dominio("tiendaejemplo.es") == "Tiendaejemplo"
	assert nombre_desde_dominio("tienda.co.uk") == "Tienda"
	assert nombre_desde_dominio("informatica.ejemplo.es") == "Ejemplo"
	assert nombre_desde_dominio("tienda.ejemplo.co.uk") == "Ejemplo"
	assert nombre_desde_dominio("deportes.ejemplo.com") == "Ejemplo"
