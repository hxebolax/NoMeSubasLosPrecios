package com.xebolax.nomesubaslosprecios.nucleo

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** limpiarUrl y dominioDe con compartido/pruebas/direcciones.json. */
class DireccionesTest {

	@Test
	fun vectoresComunes() {
		val lista = JSONObject(Comun.leer("direcciones.json")).getJSONArray("direcciones")
		assertTrue(lista.length() > 0)
		val fallos = mutableListOf<String>()
		for (i in 0 until lista.length()) {
			val caso = lista.getJSONObject(i)
			val entrada = caso.getString("entrada")
			val limpia = limpiarUrl(entrada)
			if (limpia != caso.getString("limpia")) fallos += "limpiarUrl(«$entrada») = «$limpia», se esperaba «${caso.getString("limpia")}»"
			val dominio = dominioDe(limpia)
			if (dominio != caso.getString("dominio")) fallos += "dominioDe(«$limpia») = «$dominio», se esperaba «${caso.getString("dominio")}»"
		}
		assertTrue("Direcciones que no coinciden:\n" + fallos.joinToString("\n"), fallos.isEmpty())
	}

	@Test
	fun nombreDeTienda() {
		assertEquals("Tiendaejemplo", nombreTiendaPorDominio("tiendaejemplo.es"))
		assertEquals("Ejemplo", nombreTiendaPorDominio("informatica.ejemplo.es"))
		assertEquals("Ejemplo", nombreTiendaPorDominio("tienda.ejemplo.co.uk"))
		assertEquals("Ejemplo", nombreTiendaPorDominio("ejemplo.co.uk"))
		assertEquals("Ejemplo", nombreTiendaPorDominio("deportes.ejemplo.com"))
		assertEquals("Tienda", nombreTiendaPorDominio("tienda.com.mx"))
		assertEquals("Amazon", Comun.reglas.nombrePara("amazon.es"))
		assertEquals("Amazon", Comun.reglas.nombrePara("smile.amazon.de"))
		assertEquals("Tiendaejemplo", Comun.reglas.nombrePara("tiendaejemplo.es"))
	}

	@Test
	fun primeraUrlDeTextoCompartido() {
		assertEquals("https://www.amazon.es/dp/B0EJEMPLO1", primeraUrl("Mira esto: https://www.amazon.es/dp/B0EJEMPLO1 está barato"))
		assertEquals(null, primeraUrl("sin enlace"))
	}
}
