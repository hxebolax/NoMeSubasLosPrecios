package com.xebolax.nomesubaslosprecios.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Lógica de la comprobación y de los avisos, con los casos de ESPECIFICACION.md. */
class AvisosTest {

	private val ahora = "2026-11-02T20:15:00Z"
	private val antes = "2026-11-01T20:15:00Z"
	private val todos = AjustesAvisos(avisarAgotado = true, avisarErrores = true)

	private fun producto(
		precio: Double? = 100.0,
		minimo: Double? = precio,
		maximo: Double? = precio,
		objetivo: Double? = null,
		alerta: Double = 0.0,
		disponible: Boolean = true,
		avisarDisponible: Boolean = true,
	) = Producto(
		uuid = "u", nombre = "Robot", url = "https://www.amazon.es/dp/B0EJEMPLO1", precioActual = precio, precioInicial = precio,
		precioMinimo = minimo, precioMaximo = maximo, precioObjetivo = objetivo, alertaPorcentaje = alerta, disponible = disponible,
		avisarDisponible = avisarDisponible, ultimaComprobacion = if (precio != null) antes else null,
	)

	private fun leer(p: Producto, precio: Double?, disponible: Boolean = true, ajustes: AjustesAvisos = todos) =
		LogicaAvisos.aplicarLectura(p, Lectura(precio, disponible), ajustes, ahora, "Amazon")

	@Test
	fun primeraLectura() {
		val r = leer(producto(precio = null), 129.99)
		assertEquals(129.99, r.producto.precioActual!!, 0.0)
		assertEquals(129.99, r.producto.precioInicial!!, 0.0)
		assertEquals(129.99, r.producto.precioMinimo!!, 0.0)
		assertEquals(129.99, r.producto.precioMaximo!!, 0.0)
		assertEquals(ahora, r.producto.fechaMinimo)
		assertEquals(ahora, r.producto.fechaMaximo)
		assertEquals(PuntoHistorial(ahora, 129.99, true), r.historial)
		assertTrue(r.avisos.isEmpty())
	}

	@Test
	fun primeraLecturaConObjetivo() {
		val r = leer(producto(precio = null, objetivo = 130.0), 129.99)
		assertEquals(1, r.avisos.size)
		assertEquals(TipoAviso.OBJETIVO, r.avisos[0].tipo)
		assertEquals("¡Precio deseado alcanzado!", r.avisos[0].titulo)
		assertEquals("Robot: 129,99 € en Amazon (querías 130,00 € o menos).", r.avisos[0].mensaje)
	}

	@Test
	fun objetivoGanaAMinimoYBajada() {
		val r = leer(producto(precio = 150.0, minimo = 140.0, objetivo = 120.0), 119.0)
		assertEquals(TipoAviso.OBJETIVO, r.avisos.single().tipo)
		assertEquals("Robot: 119,00 € en Amazon (querías 120,00 € o menos).", r.avisos.single().mensaje)
		assertEquals(150.0, r.producto.precioAnterior!!, 0.0)
		assertEquals(119.0, r.producto.precioMinimo!!, 0.0)
		assertNotNull(r.historial)
	}

	@Test
	fun objetivoNoSeRepiteSiYaEstabaPorDebajo() {
		val r = leer(producto(precio = 110.0, minimo = 100.0, objetivo = 120.0), 105.0)
		assertEquals(TipoAviso.BAJADA, r.avisos.single().tipo)
	}

	@Test
	fun minimoHistorico() {
		val r = leer(producto(precio = 129.99, minimo = 120.0, maximo = 150.0), 119.0)
		val a = r.avisos.single()
		assertEquals(TipoAviso.MINIMO, a.tipo)
		assertEquals("Mínimo histórico", a.titulo)
		assertEquals("Robot: 119,00 € en Amazon, el precio más bajo visto (antes 129,99 €).", a.mensaje)
		assertEquals(119.0, r.producto.precioMinimo!!, 0.0)
		assertEquals(ahora, r.producto.fechaMinimo)
	}

	@Test
	fun bajadaSinPorcentaje() {
		val r = leer(producto(precio = 369.0, minimo = 339.0, maximo = 399.0), 349.9)
		val a = r.avisos.single()
		assertEquals(TipoAviso.BAJADA, a.tipo)
		assertEquals("Ha bajado de precio", a.titulo)
		assertEquals("Robot: de 369,00 € a 349,90 € en Amazon (−19,10 €, −5,2 %).", a.mensaje)
		assertEquals(369.0, r.producto.precioAnterior!!, 0.0)
		assertEquals(ahora, r.producto.fechaCambio)
	}

	@Test
	fun bajadaConPorcentaje() {
		// Alerta del 10 %: una bajada del 5 % se guarda pero no avisa; una del 10 % sí
		val pequena = leer(producto(precio = 100.0, minimo = 90.0, alerta = 10.0), 95.0)
		assertTrue(pequena.avisos.isEmpty())
		assertEquals(95.0, pequena.producto.precioActual!!, 0.0)
		assertNotNull(pequena.historial)
		val grande = leer(producto(precio = 100.0, minimo = 80.0, alerta = 10.0), 90.0)
		assertEquals(TipoAviso.BAJADA, grande.avisos.single().tipo)
		assertEquals("Robot: de 100,00 € a 90,00 € en Amazon (−10,00 €, −10 %).", grande.avisos.single().mensaje)
	}

	@Test
	fun subida() {
		val r = leer(producto(precio = 100.0, minimo = 90.0, maximo = 110.0), 107.5)
		val a = r.avisos.single()
		assertEquals(TipoAviso.SUBIDA, a.tipo)
		assertEquals("¡Te han subido el precio!", a.titulo)
		assertEquals("Robot: de 100,00 € a 107,50 € en Amazon (+7,50 €, +7,5 %).", a.mensaje)
		val sinAviso = leer(producto(precio = 100.0, minimo = 90.0, maximo = 110.0), 107.5, ajustes = todos.copy(avisarSubidas = false))
		assertTrue(sinAviso.avisos.isEmpty())
	}

	@Test
	fun nuevoMaximo() {
		val r = leer(producto(precio = 100.0, minimo = 90.0, maximo = 110.0), 120.0)
		assertEquals(120.0, r.producto.precioMaximo!!, 0.0)
		assertEquals(ahora, r.producto.fechaMaximo)
	}

	@Test
	fun cambioMinimoPorcentaje() {
		val ajustes = todos.copy(cambioMinimoPorcentaje = 5.0)
		val pequena = leer(producto(precio = 100.0, minimo = 90.0), 97.0, ajustes = ajustes)
		assertTrue(pequena.avisos.isEmpty())
		assertEquals(97.0, pequena.producto.precioActual!!, 0.0)
		assertNotNull(pequena.historial)
		val subidaPequena = leer(producto(precio = 100.0, minimo = 90.0), 104.0, ajustes = ajustes)
		assertTrue(subidaPequena.avisos.isEmpty())
		val grande = leer(producto(precio = 100.0, minimo = 90.0), 95.0, ajustes = ajustes)
		assertEquals(TipoAviso.BAJADA, grande.avisos.single().tipo)
	}

	@Test
	fun sinCambiosNoHayHistorialNiAvisos() {
		val r = leer(producto(precio = 100.0), 100.0)
		assertNull(r.historial)
		assertTrue(r.avisos.isEmpty())
		assertEquals("", r.producto.ultimoError)
		assertEquals(0, r.producto.erroresSeguidos)
		assertEquals(ahora, r.producto.ultimaComprobacion)
	}

	@Test
	fun vuelveAEstarDisponible() {
		val r = leer(producto(precio = 100.0, disponible = false), 100.0, disponible = true)
		val a = r.avisos.single()
		assertEquals(TipoAviso.DISPONIBLE, a.tipo)
		assertEquals("Vuelve a estar disponible", a.titulo)
		assertEquals("Robot vuelve a estar disponible en Amazon a 100,00 €.", a.mensaje)
		assertEquals(PuntoHistorial(ahora, 100.0, true), r.historial)
		// Sin avisar_disponible en el producto o en los ajustes, no hay aviso
		assertTrue(leer(producto(precio = 100.0, disponible = false, avisarDisponible = false), 100.0).avisos.isEmpty())
		assertTrue(leer(producto(precio = 100.0, disponible = false), 100.0, ajustes = todos.copy(avisarDisponible = false)).avisos.isEmpty())
	}

	@Test
	fun agotado() {
		// Agotado sin precio: se conserva el último precio conocido
		val r = leer(producto(precio = 100.0), null, disponible = false)
		val a = r.avisos.single()
		assertEquals(TipoAviso.AGOTADO, a.tipo)
		assertEquals("Agotado", a.titulo)
		assertEquals("Robot se ha agotado en Amazon.", a.mensaje)
		assertEquals(100.0, r.producto.precioActual!!, 0.0)
		assertEquals(false, r.producto.disponible)
		assertEquals(PuntoHistorial(ahora, 100.0, false), r.historial)
		// avisar_agotado está desactivado por defecto
		assertTrue(leer(producto(precio = 100.0), null, disponible = false, ajustes = AjustesAvisos()).avisos.isEmpty())
	}

	@Test
	fun cambioDePrecioYDisponibilidadEnUnSoloAviso() {
		val r = leer(producto(precio = 100.0, minimo = 80.0, disponible = false), 90.0, disponible = true)
		val a = r.avisos.single()
		assertEquals(TipoAviso.BAJADA, a.tipo)
		assertEquals(
			"Robot: de 100,00 € a 90,00 € en Amazon (−10,00 €, −10 %). Robot vuelve a estar disponible en Amazon a 90,00 €.",
			a.mensaje,
		)
	}

	@Test
	fun tresErroresSeguidos() {
		var p = producto(precio = 100.0)
		val mensajes = mutableListOf<List<AvisoNuevo>>()
		repeat(4) {
			val r = LogicaAvisos.aplicarError(p, MensajesError.SIN_PRECIO, todos, ahora, "Amazon")
			mensajes += r.avisos
			p = r.producto
		}
		assertTrue(mensajes[0].isEmpty())
		assertTrue(mensajes[1].isEmpty())
		val a = mensajes[2].single()
		assertEquals(TipoAviso.ERROR, a.tipo)
		assertEquals("No se puede leer el precio", a.titulo)
		assertEquals("Robot (Amazon): ${MensajesError.SIN_PRECIO}", a.mensaje)
		assertTrue("Solo avisa al llegar a 3", mensajes[3].isEmpty())
		assertEquals(4, p.erroresSeguidos)
		assertEquals(100.0, p.precioActual!!, 0.0)
		assertEquals(MensajesError.SIN_PRECIO, p.ultimoError)
		// Sin avisar_errores, nunca
		val r = LogicaAvisos.aplicarError(producto().copy(erroresSeguidos = 2), "x", AjustesAvisos(), ahora, "Amazon")
		assertTrue(r.avisos.isEmpty())
	}

	@Test
	fun estadoDeLaComprobacion() {
		assertEquals(EstadoComprobacion.SIN_COMPROBAR, estadoComprobacion(producto(precio = null)))
		assertEquals(EstadoComprobacion.CORRECTA, estadoComprobacion(producto()))
		assertEquals(EstadoComprobacion.BLOQUEADA, estadoComprobacion(producto().copy(ultimoError = MensajesError.BLOQUEO)))
		assertEquals(EstadoComprobacion.SIN_PRECIO, estadoComprobacion(producto().copy(ultimoError = MensajesError.SIN_PRECIO)))
		assertEquals(EstadoComprobacion.SIN_CONEXION, estadoComprobacion(producto().copy(ultimoError = MensajesError.SIN_CONEXION)))
	}
}
