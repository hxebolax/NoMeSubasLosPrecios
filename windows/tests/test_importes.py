"""Importes y formatos: vectores comunes con Android (compartido/pruebas/importes.json)."""

from __future__ import annotations

import json

import pytest

from app.services.importes import (
	analizar_importe,
	formato_importe,
	formato_porcentaje,
	importe_de_maquina,
	porcentaje_cambio,
	redondeo_comercial,
)

from .conftest import PRUEBAS_COMUNES

VECTORES = json.loads((PRUEBAS_COMUNES / "importes.json").read_text(encoding="utf-8"))["importes"]


@pytest.mark.parametrize("caso", VECTORES, ids=[repr(c["texto"]) for c in VECTORES])
def test_vectores_comunes(caso):
	assert analizar_importe(caso["texto"]) == caso["valor"]


@pytest.mark.parametrize(
	("valor", "esperado"),
	[
		(129.99, 129.99), (0, None), (-3, None), (True, None), (None, None),
		("1299.99", 1299.99), ("12.5", 12.5), ("1299", 1299.0), ("1.299", 1299.0), ("1.299,00", 1299.0),
		("129,99 €", 129.99), ("", None), ("0.00", None),
	],
)
def test_importe_de_maquina(valor, esperado):
	assert importe_de_maquina(valor) == esperado


def test_formato_importe_espanol():
	assert formato_importe(1299.99) == "1.299,99 €"
	assert formato_importe(5) == "5,00 €"
	assert formato_importe(1234567.5) == "1.234.567,50 €"
	assert formato_importe(24.99, "USD") == "24,99 $"
	assert formato_importe(10, "CHF") == "10,00 CHF"
	assert formato_importe(None) == "sin precio"


def test_formato_porcentaje():
	assert formato_porcentaje(7.5) == "7,5"
	assert formato_porcentaje(10.0) == "10"
	assert formato_porcentaje(-5.176) == "5,2"
	assert formato_porcentaje(9.96) == "10"
	assert formato_porcentaje(porcentaje_cambio(369.0, 349.9)) == "5,2"


def test_redondeo_comercial_mitad_hacia_arriba():
	assert redondeo_comercial(2.675) == 2.68
	assert redondeo_comercial(1999.999) == 2000.0
	assert redondeo_comercial(0.125, 2) == 0.13
