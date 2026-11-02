package com.xebolax.nomesubaslosprecios.nucleo

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Extracción con las páginas comunes (compartido/pruebas/paginas.json) y las reglas de compartido/recursos/tiendas.json. */
class ExtractorTest {

	@Test
	fun paginasComunes() {
		val lista = JSONObject(Comun.leer("paginas.json")).getJSONArray("paginas")
		assertTrue(lista.length() > 0)
		val fallos = mutableListOf<String>()
		for (i in 0 until lista.length()) {
			val caso = lista.getJSONObject(i)
			val archivo = caso.getString("archivo")
			val html = File(Comun.pruebas, "paginas/$archivo").readText(Charsets.UTF_8)
			val r = Extractor.extraer(html, caso.getString("url"), Comun.reglas)
			fun comprobar(campo: String, esperado: Any?, obtenido: Any?) {
				if (esperado != obtenido) fallos += "$archivo: $campo = $obtenido, se esperaba $esperado"
			}
			if (caso.has("precio")) comprobar("precio", if (caso.isNull("precio")) null else caso.getDouble("precio"), r.precio)
			if (caso.has("moneda")) comprobar("moneda", caso.getString("moneda"), r.moneda)
			if (caso.has("nombre")) comprobar("nombre", caso.getString("nombre"), r.nombre)
			if (caso.has("imagen")) comprobar("imagen", caso.getString("imagen"), r.imagen)
			if (caso.has("disponible")) comprobar("disponible", if (caso.isNull("disponible")) null else caso.getBoolean("disponible"), r.disponible)
			if (caso.has("bloqueo")) comprobar("bloqueo", caso.getBoolean("bloqueo"), r.bloqueo)
			if (caso.optBoolean("categoria", false)) comprobar("categoría", MensajesError.CATEGORIA, r.error)
			comprobar("error", caso.optBoolean("error", false), r.error != null)
		}
		assertTrue("Páginas que no coinciden:\n" + fallos.joinToString("\n"), fallos.isEmpty())
	}

	@Test
	fun selectoresDelUsuarioGanan() {
		val html = File(Comun.pruebas, "paginas/jsonld_producto.html").readText(Charsets.UTF_8)
		val r = Extractor.extraer(html, "https://www.tiendaejemplo.es/p/x200", Comun.reglas, SelectoresUsuario(precioProducto = "span.precio"))
		assertEquals(129.99, r.precio!!, 0.0)
		assertEquals(OrigenPrecio.SELECTOR_PRODUCTO, r.origen)
		val malo = Extractor.extraer(html, "https://www.tiendaejemplo.es/p/x200", Comun.reglas, SelectoresUsuario(precioProducto = "span[[["))
		assertEquals(OrigenPrecio.JSON_LD, malo.origen)
	}

	@Test
	fun jsonLdRecursivoYOfertasDeCero() {
		val html = """<html><head><script type="application/ld+json">
			{"@type":"BuyAction","object":{"@type":"Product","name":"Tele","offers":{"@type":"AggregateOffer","offers":[
			{"@type":"Offer","price":0,"priceCurrency":"EUR"},{"@type":"Offer","priceSpecification":[{"price":"499.00","priceCurrency":"EUR"}],"availability":"InStock"}]}}}
			</script></head></html>"""
		val r = Extractor.extraer(html, "https://www.mediamarkt.es/es/product/x.html", Comun.reglas)
		assertEquals(499.0, r.precio!!, 0.0)
		assertEquals("Tele", r.nombre)
		assertEquals(true, r.disponible)
	}

	@Test
	fun respuesta202SinPrecioEsBloqueo() {
		val r = Extractor.extraer("<html><body></body></html>", "https://www.amazon.es/dp/B0EJEMPLO9", Comun.reglas, codigoHttp = 202)
		assertTrue(r.bloqueo)
		assertEquals(MensajesError.BLOQUEO, r.error)
	}
}
