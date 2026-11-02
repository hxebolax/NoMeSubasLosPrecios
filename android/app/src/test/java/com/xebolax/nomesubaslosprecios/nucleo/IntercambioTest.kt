package com.xebolax.nomesubaslosprecios.nucleo

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/** Formato de intercambio: leer compartido/pruebas/exportacion-ejemplo.json, volver a escribirlo y que tenga lo mismo. */
class IntercambioTest {

	private val original by lazy { Intercambio.leer(Comun.leer("exportacion-ejemplo.json")) }

	@Test
	fun leeElEjemplo() {
		val d = original
		assertEquals("windows", d.app)
		assertEquals(2, d.categorias.size)
		assertEquals(2, d.tiendas.size)
		assertEquals(3, d.productos.size)
		assertEquals(2, d.avisos.size)
		assertEquals(0, d.noValidos)
		val robot = d.productos.first { it.producto.uuid == "d4e5f6a7-b8c9-4d0e-9f1a-2b3c4d5e6f01" }
		assertEquals("a3b9d0c2-7e4f-4a1b-8c6d-2e9f0a1b3c01", robot.tiendaUuid)
		assertEquals("6f1c2a8e-0b1d-4c55-9a3e-5d2f7c1b9e02", robot.categoriaUuid)
		assertEquals(349.9, robot.producto.precioActual!!, 0.0)
		assertEquals(320.0, robot.producto.precioObjetivo!!, 0.0)
		assertTrue(robot.producto.favorito)
		assertEquals(4, robot.historial.size)
		assertEquals("Esperar al Black Friday", robot.producto.notas)
		assertNull(robot.producto.ultimoError)
		val pc = d.productos.first { it.producto.uuid.endsWith("02") }
		assertEquals(5.0, pc.producto.alertaPorcentaje, 0.0)
		assertNull(pc.producto.precioAnterior)
		val consola = d.productos.first { it.producto.uuid.endsWith("03") }
		assertFalse(consola.producto.disponible)
		assertEquals(false, consola.historial.last().disponible)
		assertEquals(mapOf<String, Any?>("intervalo_horas" to 6, "avisar_subidas" to true), d.ajustes)
		assertEquals("Revisar si cambia el diseño", d.tiendas[1].notas)
		assertNull(d.categorias[1].descripcion)
	}

	@Test
	fun escribirYVolverALeerDaLoMismo() {
		val texto = Intercambio.escribir(original)
		val vuelta = Intercambio.leer(texto)
		assertEquals(original.categorias, vuelta.categorias)
		assertEquals(original.tiendas, vuelta.tiendas)
		assertEquals(original.productos, vuelta.productos)
		assertEquals(original.avisos, vuelta.avisos)
		assertEquals(original.ajustes, vuelta.ajustes)
		// Lo escrito es JSON válido con las claves obligatorias, sangría de 2 espacios y sin ids internos
		val raiz = JSONObject(texto)
		assertEquals("NoMeSubasLosPrecios", raiz.getString("formato"))
		assertEquals(1, raiz.getInt("version_formato"))
		assertTrue(texto.startsWith("{\n  \"formato\": \"NoMeSubasLosPrecios\",\n  \"version_formato\": 1,"))
		assertFalse(texto.contains("\"id\""))
		val clavesProducto = raiz.getJSONArray("productos").getJSONObject(0).keys().asSequence().toSet()
		val clavesEjemplo = JSONObject(Comun.leer("exportacion-ejemplo.json")).getJSONArray("productos").getJSONObject(0).keys().asSequence().toSet()
		// Las del ejemplo y las nuevas de la migración 2 (opcionales al leer)
		assertEquals(clavesEjemplo + setOf("variante", "origen_precio", "confianza", "huella_selector", "desde"), clavesProducto)
		assertEquals("auto", raiz.getJSONArray("tiendas").getJSONObject(0).getString("modo_descarga"))
		// El orden de las claves es el del documento
		val orden = listOf("\"uuid\"", "\"nombre\"", "\"url\"", "\"tienda\"", "\"categoria\"", "\"grupo\"", "\"moneda\"", "\"precio_actual\"", "\"historial\"")
		val primerProducto = texto.substring(texto.indexOf("\"productos\""))
		val posiciones = orden.map { primerProducto.indexOf(it) }
		assertEquals(posiciones.sorted(), posiciones)
	}

	@Test
	fun rechazaOtrosArchivos() {
		try {
			Intercambio.leer("{\"formato\":\"otro\"}")
			fail("Debería rechazarlo")
		} catch (e: ArchivoNoValido) {
			assertEquals(Intercambio.ERROR_FORMATO, e.message)
		}
		try {
			Intercambio.leer("{\"formato\":\"NoMeSubasLosPrecios\",\"version_formato\":2}")
			fail("Debería rechazarlo")
		} catch (e: ArchivoNoValido) {
			assertEquals(Intercambio.ERROR_VERSION, e.message)
		}
		try {
			Intercambio.leer("no es json")
			fail("Debería rechazarlo")
		} catch (e: ArchivoNoValido) {
			assertEquals(Intercambio.ERROR_FORMATO, e.message)
		}
	}

	@Test
	fun productosSinUrlOUuidSeCuentan() {
		val d = Intercambio.leer(
			"""{"formato":"NoMeSubasLosPrecios","version_formato":1,"app":"windows","version_app":"1.0.0","exportado":"2026-11-02T20:15:00Z",
			"categorias":[],"tiendas":[],"productos":[{"uuid":"a","nombre":"x"},{"url":"https://a.es/p"},{"uuid":"b","url":"https://a.es/q","campo_futuro":1}]}""",
		)
		assertEquals(2, d.noValidos)
		assertEquals(1, d.productos.size)
		assertEquals("EUR", d.productos[0].producto.moneda)
		assertTrue(d.productos[0].producto.activo)
	}

	@Test
	fun csv() {
		val texto = Csv.escribir(original.productos.map { ProductoConNombres(it.producto, "Amazon", "Hogar") })
		assertTrue(texto.startsWith("﻿"))
		assertTrue(texto.contains(";349,90;"))
	}
}
