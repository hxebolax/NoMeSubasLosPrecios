package com.xebolax.nomesubaslosprecios.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Colores de la lista (1.1.0), con la paleta y el orden de ESPECIFICACION.md, «Colores de la lista». */
class ColoresTest {

	private val ahora = "2026-11-10T12:00:00Z"
	private val ahoraMs = Fechas.ms(ahora)!!
	private val hace2Dias = "2026-11-08T12:00:00Z"
	private val hace10Dias = "2026-10-31T12:00:00Z"

	/** Producto comprobado y sin cambios: 100 € siempre. */
	private fun producto(
		precio: Double? = 100.0,
		anterior: Double? = null,
		fechaCambio: String? = null,
		minimo: Double? = precio,
		maximo: Double? = precio,
		objetivo: Double? = null,
		disponible: Boolean = true,
		activo: Boolean = true,
		comprobado: Boolean = true,
		error: String? = null,
	) = Producto(
		uuid = "u", nombre = "Robot", url = "https://tienda.es/robot", precioActual = precio, precioAnterior = anterior,
		fechaCambio = fechaCambio, precioMinimo = minimo, precioMaximo = maximo, precioObjetivo = objetivo,
		disponible = disponible, activo = activo, ultimaComprobacion = if (comprobado) hace2Dias else null, ultimoError = error,
	)

	private fun tipo(p: Producto) = Colores.tipoColor(p, ahoraMs)

	@Test
	fun paletaExacta() {
		assertEquals(
			listOf("ninguno", "verde", "azul", "celeste", "turquesa", "morado", "rosa", "rojo", "naranja", "amarillo", "marron", "gris"),
			Colores.IDS,
		)
		val nombres = Colores.PALETA.map { it.nombre }
		assertEquals(
			listOf("Sin color", "Verde", "Azul", "Celeste", "Turquesa", "Morado", "Rosa", "Rojo", "Naranja", "Amarillo", "Marrón", "Gris"),
			nombres,
		)
		val esperados = mapOf(
			"verde" to listOf("#C8E6C9", "#1B5E20", "#1E4620", "#A5D6A7"),
			"azul" to listOf("#BBDEFB", "#0D47A1", "#0D3260", "#90CAF9"),
			"celeste" to listOf("#B3E5FC", "#01579B", "#0A3D5C", "#81D4FA"),
			"turquesa" to listOf("#B2DFDB", "#004D40", "#0B3D38", "#80CBC4"),
			"morado" to listOf("#E1BEE7", "#4A148C", "#3B1D4A", "#CE93D8"),
			"rosa" to listOf("#F8BBD0", "#880E4F", "#4A1830", "#F48FB1"),
			"rojo" to listOf("#FFCDD2", "#B71C1C", "#5C1A1A", "#EF9A9A"),
			"naranja" to listOf("#FFE0B2", "#BF360C", "#5A3210", "#FFCC80"),
			"amarillo" to listOf("#FFF9C4", "#7A5C00", "#4D4410", "#FFF59D"),
			"marron" to listOf("#D7CCC8", "#4E342E", "#3E2C26", "#BCAAA4"),
			"gris" to listOf("#E0E0E0", "#424242", "#3A3A3A", "#BDBDBD"),
		)
		for ((id, hex) in esperados) {
			val c = Colores.color(id)
			assertEquals(id, hex.map { Colores.hex(it) }, listOf(c.fondo, c.texto, c.fondoOscuro, c.textoClaro))
		}
		val ninguno = Colores.color("ninguno")
		assertTrue(ninguno.sinColor)
		assertNull(ninguno.pintura(ModoColores.FONDO, false))
		assertEquals(0xFFC8E6C9.toInt(), Colores.hex("#C8E6C9"))
	}

	@Test
	fun desconocidoEsElDePorDefecto() {
		assertEquals("verde", Colores.color("fucsia", TipoColor.BAJADA).id)
		assertEquals("rojo", Colores.color(null, TipoColor.SUBIDA).id)
		assertEquals("azul", Colores.color("", TipoColor.OBJETIVO).id)
		assertEquals("gris", Colores.color("Verde", TipoColor.PROBLEMA).id)
		assertEquals("ninguno", Colores.color("fucsia").id)
		assertEquals(ModoColores.FONDO, ModoColores.de("lienzo"))
		assertEquals(ModoColores.FONDO, ModoColores.de(null))
		assertEquals(ModoColores.TEXTO, ModoColores.de("texto"))
		assertEquals(listOf("color_bajada", "color_subida", "color_objetivo", "color_problema"), TipoColor.entries.map { it.clave })
		assertEquals(listOf("verde", "rojo", "azul", "gris"), TipoColor.entries.map { it.porDefecto })
	}

	@Test
	fun enPausaNada() {
		assertNull(tipo(producto(activo = false, error = MensajesError.BLOQUEO)))
		assertNull(tipo(producto(activo = false, disponible = false)))
	}

	@Test
	fun problemas() {
		assertEquals(TipoColor.PROBLEMA, tipo(producto(error = MensajesError.BLOQUEO)))
		assertEquals(TipoColor.PROBLEMA, tipo(producto(error = MensajesError.SIN_CONEXION)))
		assertEquals(TipoColor.PROBLEMA, tipo(producto(error = MensajesError.TIEMPO_AGOTADO)))
		assertEquals(TipoColor.PROBLEMA, tipo(producto(error = "Algo raro pasó.")))
		assertEquals(TipoColor.PROBLEMA, tipo(producto(precio = null, error = MensajesError.SIN_PRECIO)))
		// Agotado gana a precio deseado y a oferta
		assertEquals(TipoColor.PROBLEMA, tipo(producto(disponible = false, objetivo = 200.0)))
		// Un error sin haber comprobado nunca bien también es problema (no pendiente)
		assertEquals(TipoColor.PROBLEMA, tipo(producto(precio = null, comprobado = false, error = MensajesError.SIN_CONEXION)))
	}

	@Test
	fun pendienteNada() {
		assertNull(tipo(producto(precio = null, comprobado = false)))
	}

	@Test
	fun objetivoAntesQueOferta() {
		assertEquals(TipoColor.OBJETIVO, tipo(producto(objetivo = 100.0)))
		assertEquals(TipoColor.OBJETIVO, tipo(producto(precio = 80.0, anterior = 100.0, fechaCambio = hace2Dias, minimo = 80.0, maximo = 100.0, objetivo = 90.0)))
	}

	@Test
	fun ofertaEsBajada() {
		// Bajó en los últimos 7 días
		assertEquals(TipoColor.BAJADA, tipo(producto(precio = 90.0, anterior = 100.0, fechaCambio = hace2Dias, minimo = 80.0, maximo = 120.0)))
		// En su mínimo y el precio ha variado alguna vez, aunque la bajada sea vieja
		assertEquals(TipoColor.BAJADA, tipo(producto(precio = 90.0, anterior = 100.0, fechaCambio = hace10Dias, minimo = 90.0, maximo = 100.0)))
		// Bajó hace más de 7 días y no está en su mínimo: nada
		assertNull(tipo(producto(precio = 90.0, anterior = 100.0, fechaCambio = hace10Dias, minimo = 80.0, maximo = 120.0)))
	}

	@Test
	fun subida() {
		assertEquals(TipoColor.SUBIDA, tipo(producto(precio = 110.0, anterior = 100.0, fechaCambio = hace2Dias, minimo = 100.0, maximo = 110.0)))
		// Subida de hace más de 7 días: nada
		assertNull(tipo(producto(precio = 110.0, anterior = 100.0, fechaCambio = hace10Dias, minimo = 100.0, maximo = 110.0)))
		// Sin fecha de cambio: nada
		assertNull(tipo(producto(precio = 110.0, anterior = 100.0, minimo = 100.0, maximo = 110.0)))
	}

	@Test
	fun sinCambiosNada() {
		assertNull(tipo(producto()))
	}

	@Test
	fun avisos() {
		assertEquals(TipoColor.OBJETIVO, Colores.tipoColorAviso("objetivo"))
		assertEquals(TipoColor.BAJADA, Colores.tipoColorAviso("minimo"))
		assertEquals(TipoColor.BAJADA, Colores.tipoColorAviso("bajada"))
		assertEquals(TipoColor.SUBIDA, Colores.tipoColorAviso("subida"))
		assertEquals(TipoColor.PROBLEMA, Colores.tipoColorAviso("agotado"))
		assertEquals(TipoColor.PROBLEMA, Colores.tipoColorAviso("error"))
		assertNull(Colores.tipoColorAviso("disponible"))
		assertNull(Colores.tipoColorAviso(null))
		assertNull(Colores.tipoColorAviso("otro"))
	}

	@Test
	fun ajustes() {
		val porDefecto = AjustesColores()
		assertEquals(Colores.hex("#C8E6C9"), porDefecto.pintura(TipoColor.BAJADA, temaOscuro = false))
		assertEquals(Colores.hex("#1E4620"), porDefecto.pintura(TipoColor.BAJADA, temaOscuro = true))
		assertNull(porDefecto.pintura(null, false))
		val texto = AjustesColores(modo = ModoColores.TEXTO, elegidos = mapOf(TipoColor.SUBIDA to "naranja", TipoColor.PROBLEMA to "ninguno"))
		assertEquals(Colores.hex("#BF360C"), texto.pintura(TipoColor.SUBIDA, false))
		assertEquals(Colores.hex("#FFCC80"), texto.pintura(TipoColor.SUBIDA, true))
		assertNull(texto.pintura(TipoColor.PROBLEMA, false))
		assertEquals(Colores.hex("#0D47A1"), texto.pintura(TipoColor.OBJETIVO, false))
		assertNull(AjustesColores(activos = false).pintura(TipoColor.BAJADA, false))
		assertEquals("verde", AjustesColores(elegidos = mapOf(TipoColor.BAJADA to "fucsia")).colorDe(TipoColor.BAJADA)?.id)
	}

	@Test
	fun clavesDeAjustesExportables() {
		for (clave in listOf("colores_lista", "colores_modo", "color_bajada", "color_subida", "color_objetivo", "color_problema")) {
			assertTrue(clave, clave in Intercambio.CLAVES_AJUSTES)
		}
	}
}
