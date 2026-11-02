package com.xebolax.nomesubaslosprecios.nucleo

import org.junit.Assert.assertEquals
import org.junit.Test

/** Importes con formato español y porcentajes con una decimal. */
class FormatoTest {

	@Test
	fun importes() {
		assertEquals("1.299,99 €", formatearImporte(1299.99))
		assertEquals("129,99 €", formatearImporte(129.99))
		assertEquals("0,99 €", formatearImporte(0.99))
		assertEquals("12.345.678,90 €", formatearImporte(12345678.9))
		assertEquals("349,90 €", formatearImporte(349.9, "EUR"))
		assertEquals("24,99 $", formatearImporte(24.99, "USD"))
		assertEquals("1.049,00 £", formatearImporte(1049.0, "GBP"))
		assertEquals("1.299,50 CHF", formatearImporte(1299.5, "CHF"))
		assertEquals("1.000,00 €", formatearImporte(999.999))
	}

	@Test
	fun porcentajes() {
		assertEquals("7,5", formatearPorcentaje(7.5))
		assertEquals("10", formatearPorcentaje(10.0))
		assertEquals("10", formatearPorcentaje(9.96))
		assertEquals("5,2", formatearPorcentaje(cambioPorcentaje(369.0, 349.9)))
		assertEquals("9,2", formatearPorcentaje(9.24))
		assertEquals("0,1", formatearPorcentaje(-0.05))
	}

	@Test
	fun redondeo() {
		assertEquals(2000.0, redondear(1999.999), 0.0)
		assertEquals(0.13, redondear(0.125), 0.0)
	}
}
