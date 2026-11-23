package com.xebolax.nomesubaslosprecios.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Origen de las actualizaciones (1.2.0), con los casos de ESPECIFICACION.md (los mismos que en Windows). */
class OrigenActualizacionesTest {

	private val servidor = "https://xebolax.synology.me/NoMeSubasLosPrecios/version.json"

	@Test
	fun basePersonalizada() {
		val casos = listOf(
			"https://x.es/carpeta" to "https://x.es/carpeta/",
			"https://x.es/c/version.json" to "https://x.es/c/",
			"https://x.es/c/windows/version.json" to "https://x.es/c/",
			"http://x.es/" to "",
			"ftp://x" to "",
			"" to "",
			"http://localhost:8000/a" to "http://localhost:8000/a/",
			// Más casos
			"  https://x.es/c/  " to "https://x.es/c/",
			"https://x.es/c/" to "https://x.es/c/",
			"https://x.es" to "https://x.es/",
			"HTTPS://X.es/C/VERSION.JSON" to "HTTPS://X.es/C/",
			"http://127.0.0.1/espejo" to "http://127.0.0.1/espejo/",
			"http://localhost.ejemplo.es/a" to "",
			"https://" to "",
			"https:///version.json" to "",
			"x.es/carpeta" to "",
			"   " to "",
		)
		for ((entrada, esperado) in casos) assertEquals("«$entrada»", esperado, OrigenActualizaciones.basePersonalizada(entrada))
		assertEquals("", OrigenActualizaciones.basePersonalizada(null))
	}

	@Test
	fun origenDesconocidoEsServidor() {
		assertEquals("servidor", OrigenActualizaciones.origen(null))
		assertEquals("servidor", OrigenActualizaciones.origen("gitlab"))
		assertEquals("github", OrigenActualizaciones.origen("github"))
		assertEquals("ambos", OrigenActualizaciones.origen(" Ambos "))
		assertEquals(listOf("servidor", "github", "ambos", "personalizada"), OrigenActualizaciones.VALORES)
	}

	@Test
	fun manifiestos() {
		val github = "https://github.com/hxebolax/NoMeSubasLosPrecios/releases/latest/download/version.json"
		assertEquals(listOf(servidor), OrigenActualizaciones.manifiestos("servidor", "", servidor))
		assertEquals(listOf(github), OrigenActualizaciones.manifiestos("github", "", servidor))
		// Con empate de versión gana el primero: el servidor del autor
		assertEquals(listOf(servidor, github), OrigenActualizaciones.manifiestos("ambos", "", servidor))
		assertEquals(
			listOf("https://espejo.es/nmslp/version.json"),
			OrigenActualizaciones.manifiestos("personalizada", "https://espejo.es/nmslp/windows/version.json", servidor),
		)
		// Dirección personalizada no válida (por ejemplo, importada): el servidor del autor
		assertEquals(listOf(servidor), OrigenActualizaciones.manifiestos("personalizada", "http://espejo.es/", servidor))
		assertEquals(listOf(servidor), OrigenActualizaciones.manifiestos("otro", "", servidor))
	}

	@Test
	fun carpetaDelManifiesto() {
		assertEquals("https://xebolax.synology.me/NoMeSubasLosPrecios/", OrigenActualizaciones.carpeta(servidor))
		assertEquals(
			"https://github.com/hxebolax/NoMeSubasLosPrecios/releases/latest/download/",
			OrigenActualizaciones.carpeta(OrigenActualizaciones.MANIFIESTO_GITHUB),
		)
		assertEquals("https://x.es/c/", OrigenActualizaciones.carpeta("https://x.es/c/version.json?t=123"))
	}

	@Test
	fun clavesDeAjustesExportables() {
		val claves = Intercambio.CLAVES_AJUSTES
		assertTrue(claves.takeLast(2) == listOf("origen_actualizaciones", "url_actualizaciones"))
	}
}
