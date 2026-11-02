package com.xebolax.nomesubaslosprecios.nucleo

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.jsoup.Jsoup
import java.io.File

/**
 * Extractor genérico (pasos 7 a 12): los vectores sintéticos de
 * compartido/referencia_extractor/pruebas_sinteticas.py traducidos, los
 * selectores CSS estables y, si ya existe, compartido/pruebas/extractor_generico.json.
 */
class ExtractorGenericoTest {

	private val boton = "<form><button type=\"submit\" name=\"add\">Añadir al carrito</button></form>"

	private data class Caso(val nombre: String, val url: String?, val html: String, val esperado: Double?)

	private val casos = listOf(
		Caso(
			"Shopify var meta en céntimos, variante de la URL", "https://t.es/products/camiseta?variant=222",
			"<script src=\"//cdn.shopify.com/x.js\"></script><script>var meta = {\"product\":{\"id\":1,\"variants\":[{\"id\":111,\"price\":2999},{\"id\":222,\"price\":3499}]},\"page\":{\"pageType\":\"product\"}};\nfor (var attr in meta) {}</script><h1>Camiseta</h1>",
			34.99,
		),
		Caso(
			"Shopify data-selected-variant (Dawn)", "https://t.es/products/taza",
			"<link href=\"//cdn.shopify.com/s.css\"><h1>Taza</h1><script type=\"application/json\" data-selected-variant>{\"id\":5,\"price\":1250,\"compare_at_price\":1500}</script>$boton",
			12.5,
		),
		Caso(
			"Magento 2 Luma: finalPrice del bloque principal, no oldPrice ni relacionados", null,
			"<script type=\"text/x-magento-init\">{}</script><div class=\"product-info-main\"><h1>Bolso</h1><div class=\"price-box\" data-role=\"priceBox\">" +
				"<span class=\"special-price\"><span data-price-amount=\"59.9\" data-price-type=\"finalPrice\" class=\"price-wrapper\"><span class=\"price\">59,90 €</span></span></span>" +
				"<span class=\"old-price\"><span data-price-amount=\"79.9\" data-price-type=\"oldPrice\" class=\"price-wrapper\"><span class=\"price\">79,90 €</span></span></span></div>$boton</div>" +
				"<div class=\"block related\"><span data-price-amount=\"9.9\" data-price-type=\"finalPrice\"></span></div>",
			59.9,
		),
		Caso(
			"WooCommerce variaciones con atributo en la URL", "https://t.es/producto/cafe/?attribute_pa_peso=1kg",
			"<div class=\"woocommerce\"><h1 class=\"product_title\">Café</h1><p class=\"price\"><span class=\"woocommerce-Price-amount\">12,00 €</span> – <span class=\"woocommerce-Price-amount\">40,00 €</span></p>" +
				"<form class=\"variations_form\" data-product_variations='[{\"attributes\":{\"attribute_pa_peso\":\"250g\"},\"display_price\":12,\"is_in_stock\":true},{\"attributes\":{\"attribute_pa_peso\":\"1kg\"},\"display_price\":40,\"is_in_stock\":true}]'>$boton</form></div>",
			40.0,
		),
		Caso(
			"PrestaShop 1.6 #our_price_display", null,
			"<script>var prestashop = {}; var productPrice = 19.95;</script><h1>Pienso</h1><span id=\"our_price_display\" class=\"price\" itemprop=\"price\" content=\"19.95\">19,95 €</span>$boton",
			19.95,
		),
		Caso(
			"Salesforce Commerce Cloud .sales .value[content]", null,
			"<link href=\"/on/demandware.static/x.css\"><div class=\"product-detail\" data-pid=\"ABC\"><h1>Gafas</h1><div class=\"prices\"><div class=\"price\"><span class=\"strike-through list\"><span class=\"value\" content=\"69.99\">69,99 €</span></span>" +
				"<span class=\"sales\"><span class=\"value\" content=\"48.99\">48,99 €</span></span></div></div>$boton</div>",
			48.99,
		),
		Caso(
			"VTEX antiguo: skuJson en céntimos (solo SKU disponibles)", null,
			"<script src=\"https://x.vteximg.com.br/a.js\"></script><script>var skuJson_0 = {\"productId\":1,\"name\":\"Zapatilla\",\"skus\":[{\"sku\":1,\"available\":false,\"bestPrice\":4990},{\"sku\":2,\"available\":true,\"bestPrice\":5990}]};</script><h1>Zapatilla</h1>",
			59.9,
		),
		Caso(
			"VTEX IO: __STATE__ commertialOffer.Price", null,
			"<template data-type=\"json\" data-varname=\"__STATE__\"><script>{\"Product:sku-1\":{\"productName\":\"Sofá\"},\"\$Product:sku-1.items.0.sellers.0.commertialOffer\":{\"Price\":299.0,\"ListPrice\":349.0,\"AvailableQuantity\":5}}</script></template><h1>Sofá</h1>",
			299.0,
		),
		Caso(
			"BigCommerce BCData con IVA", null,
			"<script>var BCData = {\"product_attributes\":{\"sku\":\"X\",\"price\":{\"with_tax\":{\"formatted\":\"121,00 €\",\"value\":121,\"currency\":\"EUR\"},\"without_tax\":{\"value\":100}}}};</script><h1>Lámpara</h1>",
			121.0,
		),
		Caso(
			"Next.js __NEXT_DATA__ con el producto (nombre = h1)", null,
			"<script id=\"__NEXT_DATA__\" type=\"application/json\">{\"props\":{\"pageProps\":{\"product\":{\"name\":\"Silla nórdica roble\",\"price\":{\"current\":89.95,\"old\":119.95},\"related\":[{\"name\":\"Mesa\",\"price\":{\"current\":199}}]}}}}</script><h1>Silla nórdica roble</h1>",
			89.95,
		),
		Caso(
			"Nuxt 3 __NUXT_DATA__ (devalue)", null,
			"<script type=\"application/json\" id=\"__NUXT_DATA__\">[{\"data\":1},{\"producto\":2},{\"name\":3,\"price\":4},\"Mochila urbana gris\",45.5]</script><h1>Mochila urbana gris</h1>",
			45.5,
		),
		Caso(
			"Solo analítica: GA4 view_item + píxel de Facebook coinciden", null,
			"<h1>Altavoz</h1><script>dataLayer.push({\"event\":\"view_item\",\"ecommerce\":{\"currency\":\"EUR\",\"value\":79.0,\"items\":[{\"item_id\":\"A1\",\"price\":79.0}]}});" +
				"fbq(\"track\",\"ViewContent\",{\"value\":79.0,\"currency\":\"EUR\"});</script>",
			79.0,
		),
		Caso(
			"Trampa: cuota mensual al lado del precio", null,
			"<main><h1>Portátil</h1><div class=\"product-price\">599,00 €</div><div class=\"financing\">o 24,96 €/mes en 24 cuotas</div>$boton</main>",
			599.0,
		),
		Caso(
			"Trampa: precio por kilo", null,
			"<main><h1>Queso curado 300 g</h1><span class=\"price\">3,75 €</span> <small class=\"unit\">12,50 €/kg</small>$boton</main>",
			3.75,
		),
		Caso(
			"Trampa: precio sin IVA y con IVA (B2B)", null,
			"<main><h1>Taladro</h1><div class=\"price-excl\">99,00 € + IVA</div><div class=\"price-incl\">119,79 € IVA incluido</div>$boton</main>",
			119.79,
		),
		Caso(
			"Trampa: tachado con clase .old y oferta", null,
			"<main><h1>Robot</h1><span class=\"price old\">249,00 €</span><span class=\"price\">199,00 €</span><span class=\"badge\">Ahorra 50,00 €</span>$boton</main>",
			199.0,
		),
		Caso(
			"Trampa: página de categoría (muchos productos) -> no debe dar precio", null,
			"<h1>Zapatillas</h1>" + (0 until 8).joinToString("") { i ->
				"<div class=\"product-card\"><a href=\"/p$i\">Modelo $i</a><span class=\"price\">${40 + i},99 €</span><button>Añadir al carrito</button></div>"
			},
			null,
		),
		Caso(
			"Trampa: envío gratis como único importe visible", null,
			"<main><h1>Planta</h1><p class=\"shipping\">Envío gratis a partir de 49 €</p>$boton</main>",
			null,
		),
		Caso(
			"twitter:label1 = Precio (Yoast WooCommerce SEO) coincide con el visible", null,
			"<meta name=\"twitter:label1\" content=\"Precio\"><meta name=\"twitter:data1\" content=\"24,90 €\"><main><h1>Libro</h1><p><span class=\"amount\">24,90 €</span></p>$boton</main>",
			24.9,
		),
	)

	@Test
	fun vectoresSinteticosDelPrototipo() {
		val fallos = mutableListOf<String>()
		for (c in casos) {
			val doc = Jsoup.parse(c.html, c.url ?: "https://t.es/")
			val d = ExtractorGenerico.extraer(c.html, doc, c.url)
			if (d.precio != c.esperado) fallos += "${c.nombre}: ${d.precio} (${d.origen}), se esperaba ${c.esperado}"
		}
		assertTrue("Vectores que fallan (${fallos.size} de ${casos.size}):\n" + fallos.joinToString("\n"), fallos.isEmpty())
	}

	@Test
	fun vectoresConElExtractorCompleto() {
		// Con los pasos 1 a 6 delante, ninguno de estos vectores debe cambiar de resultado
		val fallos = mutableListOf<String>()
		for (c in casos) {
			val r = Extractor.extraer(c.html, c.url ?: "https://t.es/producto", ReglasTiendas.VACIAS)
			if (r.precio != c.esperado) fallos += "${c.nombre}: ${r.precio} (${r.origenTexto}), se esperaba ${c.esperado}"
		}
		assertTrue("Vectores que fallan:\n" + fallos.joinToString("\n"), fallos.isEmpty())
	}

	@Test
	fun sinPrecioSeguroHayCandidatosParaElegir() {
		val c = casos.first { it.esperado == null && it.nombre.contains("categoría") }
		val r = Extractor.extraer(c.html, "https://t.es/zapatillas", ReglasTiendas.VACIAS)
		assertEquals(null, r.precio)
		assertEquals(MensajesError.NO_DECIDIDO, r.error)
		val opciones = ExtractorGenerico.opcionesParaElegir(r.candidatos)
		assertTrue(opciones.isNotEmpty())
		assertTrue(opciones.size <= 8)
		assertTrue(opciones[0].first.contains("€"))
	}

	@Test
	fun selectoresEstables() {
		val html = "<div class=\"css-1x2y3z product-main\"><h1 class=\"sc-abc123\">X</h1>" +
			"<div class=\"Price_wrapper__3x9Yz\"><span class=\"Price_price__a1B2c current-price\" data-test=\"product-price\">19,99 €</span></div>" +
			"<div class=\"price\"><span>29,99 €</span></div></div>" +
			"<ul class=\"related\"><li><span class=\"Price_price__a1B2c\">5,00 €</span></li></ul>"
		val doc = Jsoup.parse(html)
		val el = doc.selectFirst("[data-test=product-price]")!!
		val (sel, atr) = SelectorCss.generar(el, doc)
		assertTrue("Selector no válido: $sel", SelectorCss.validar(doc, sel, atr, 19.99))
		val el2 = doc.selectFirst(".price span")!!
		val (sel2, atr2) = SelectorCss.generar(el2, doc)
		assertTrue("Selector no válido: $sel2", SelectorCss.validar(doc, sel2, atr2, 29.99))
		for (n in listOf("css-1x2y3z", "sc-abc123", "Price_price__a1B2c", "jsx-2847563", "md:text-lg", "is-active")) {
			assertFalse("$n no debería ser estable", SelectorCss.palabraEstable(n))
		}
		for (n in listOf("product-price", "current-price", "price__current", "js-product-price", "woocommerce-Price-amount")) {
			assertTrue("$n debería ser estable", SelectorCss.palabraEstable(n))
		}
	}

	@Test
	fun selectorElegidoConHuella() {
		val html = "<main><h1>Robot</h1><span class=\"precio-actual\">199,00 €</span>$boton</main>"
		val bien = Extractor.extraer(html, "https://t.es/p", ReglasTiendas.VACIAS, SelectoresUsuario(precioProducto = "span.precio-actual", huellaImporte = 199.0))
		assertEquals(199.0, bien.precio!!, 0.0)
		val roto = Extractor.extraer(html, "https://t.es/p", ReglasTiendas.VACIAS, SelectoresUsuario(precioProducto = "span.no-existe", huellaImporte = 99.0))
		assertEquals(null, roto.precio)
		assertEquals(MensajesError.SELECTOR_ROTO, roto.error)
	}

	@Test
	fun preciosPartidosYNumeroDeMaquina() {
		val doc = Jsoup.parse("<span class=\"p\">74 <span>,</span> 99 €</span><span class=\"q\">109<sup>,95</sup> €</span>")
		assertEquals(74.99, analizarImporte(Extractor.textoImporte(doc.selectFirst(".p")!!))!!, 0.0)
		assertEquals(109.95, analizarImporte(Extractor.textoImporte(doc.selectFirst(".q")!!))!!, 0.0)
		assertEquals(12.99, numeroDeMaquina("12.990")!!, 0.0)
		assertEquals(19.95, numeroDeMaquina("19.950000")!!, 0.0)
		assertEquals(59.9, numeroDeMaquina("59.9")!!, 0.0)
		assertEquals(null, numeroDeMaquina(0))
		assertEquals(1299.0, numeroDeMaquina("1.299,00")!!, 0.0)
	}

	@Test
	fun jsonLdCorrecciones() {
		// @type en minúsculas, clave «Price» con mayúscula, producto relacionado ignorado y oferta en stock preferida
		val html = """<script type="application/ld+json">{"@type":"product","name":"Libro &ntilde;o&ntilde;o","offers":[
			{"@type":"Offer","Price":"9.99","availability":"OutOfStock"},{"@type":"Offer","price":"12.50","availability":"InStock"}],
			"isRelatedTo":{"@type":"Product","name":"Otro","offers":{"price":1}}}</script>"""
		val r = Extractor.extraer(html, "https://t.es/libro", ReglasTiendas.VACIAS)
		assertEquals(12.5, r.precio!!, 0.0)
		assertEquals("Libro ñoño", r.nombre)
		// ProductGroup con variantes: la de la URL; sin elegir y con precios distintos, «desde» la menor
		val grupo = """<script type="application/ld+json">{"@type":"ProductGroup","name":"Camiseta","hasVariant":[
			{"@type":"Product","name":"Camiseta S","sku":"CAM-S","offers":{"price":10,"url":"https://t.es/camiseta?talla=s"}},
			{"@type":"Product","name":"Camiseta L","sku":"CAM-L","offers":{"price":14,"url":"https://t.es/camiseta?talla=l"}}]}</script>"""
		val l = Extractor.extraer(grupo, "https://t.es/camiseta?talla=l", ReglasTiendas.VACIAS)
		assertEquals(14.0, l.precio!!, 0.0)
		assertEquals("Camiseta", l.nombre)
		val sin = Extractor.extraer(grupo, "https://t.es/camiseta", ReglasTiendas.VACIAS)
		assertEquals(10.0, sin.precio!!, 0.0)
		assertTrue(sin.desde)
		assertEquals(2, sin.variantes.size)
		val elegida = Extractor.extraer(grupo, "https://t.es/camiseta", ReglasTiendas.VACIAS, SelectoresUsuario(variante = "CAM-L"))
		assertEquals(14.0, elegida.precio!!, 0.0)
		assertFalse(elegida.desde)
		// Categoría
		val cat = Extractor.extraer("""<script type="application/ld+json">{"@type":"ItemList","itemListElement":[{"@type":"Product","name":"A","offers":{"price":5}}]}</script>""", "https://t.es/c", ReglasTiendas.VACIAS)
		assertEquals(MensajesError.CATEGORIA, cat.error)
	}

	@Test
	fun metadatosYBloqueo() {
		// pretax nunca; og a 0 se salta; meta itemprop tachado se salta; disponibilidad por microdatos
		val html = """<meta property="product:pretax_price:amount" content="10"><meta property="og:price:amount" content="0">
			<del><meta itemprop="price" content="20"></del><meta itemprop="price" content="12.10"><link itemprop="availability" href="https://schema.org/OutOfStock">"""
		val r = Extractor.extraer(html, "https://t.es/p", ReglasTiendas.VACIAS)
		assertEquals(12.1, r.precio!!, 0.0)
		assertEquals(false, r.disponible)
		// «captcha» suelto no es bloqueo
		val captcha = Extractor.extraer("<html><body><div class=\"g-recaptcha\">captcha</div></body></html>", "https://t.es/p", Comun.reglas)
		assertFalse(captcha.bloqueo)
	}

	@Test
	fun apiDeLaTienda() {
		val mercadona = Comun.reglas.para("tienda.mercadona.es")?.api
		assertNotNull("tiendas.json debería tener la API de Mercadona", mercadona)
		assertEquals("https://tienda.mercadona.es/api/products/12345/", mercadona!!.urlPara("https://tienda.mercadona.es/product/12345/leche"))
		val r = mercadona.extraer("""{"display_name":"Leche","published":true,"price_instructions":{"unit_price":"1.25"},"photos":[{"regular":"https://x/f.jpg"}]}""")!!
		assertEquals(1.25, r.precio!!, 0.0)
		assertEquals("Leche", r.nombre)
		assertEquals("https://x/f.jpg", r.imagen)
		assertEquals(true, r.disponible)
		val datos = leerJson("""{"priceData":{"prices":[{"id":"PRICE","value":{"centAmount":2.5}},{"id":"OFFER_PRICE","value":{"centAmount":1.99}}]}}""")
		assertEquals(1.99, (ApiTienda.valorEn(datos, "priceData.prices[id=OFFER_PRICE].value.centAmount") as Number).toDouble(), 0.0)
	}

	/** Vectores comunes con Windows: compartido/pruebas/extractor_generico.json. */
	@Test
	fun vectoresComunes() {
		val archivo = File(Comun.pruebas, "extractor_generico.json")
		assertTrue("Falta $archivo", archivo.exists())
		val raiz = JSONObject(archivo.readText(Charsets.UTF_8))
		val lista: JSONArray = raiz.optJSONArray("casos") ?: raiz.keys().asSequence().map { raiz.opt(it) }.filterIsInstance<JSONArray>().first()
		assertTrue(lista.length() > 0)
		val fallos = mutableListOf<String>()
		for (i in 0 until lista.length()) {
			val c = lista.getJSONObject(i)
			val nombre = c.optString("nombre", "caso $i")
			val r = Extractor.extraer(c.getString("html"), c.optString("url").ifEmpty { "https://tiendaejemplo.es/p/1" }, Comun.reglas)
			fun comprobar(campo: String, esperado: Any?, obtenido: Any?) {
				if (esperado != obtenido) fallos += "$nombre: $campo = $obtenido, se esperaba $esperado"
			}
			comprobar("precio", if (c.isNull("precio")) null else c.getDouble("precio"), r.precio)
			if (c.has("origen") && !c.isNull("origen")) comprobar("origen", c.getString("origen"), r.origenTexto)
			when (c.optString("decision")) {
				"acepta" -> comprobar("decisión", true, r.precio != null)
				"pregunta" -> comprobar("decisión (candidatos)", true, r.precio == null && r.candidatos.isNotEmpty())
				"error" -> comprobar("decisión (error)", true, r.error != null)
			}
			if (c.has("desde")) comprobar("desde", c.getBoolean("desde"), r.desde)
			if (c.has("disponible") && !c.isNull("disponible")) comprobar("disponible", c.getBoolean("disponible"), r.disponible)
			if (c.has("bloqueo")) comprobar("bloqueo", c.getBoolean("bloqueo"), r.bloqueo)
			if (c.has("categoria") && c.getBoolean("categoria")) comprobar("categoría", MensajesError.CATEGORIA, r.error)
			if (c.has("nombre_producto")) comprobar("nombre", c.getString("nombre_producto"), r.nombre)
		}
		assertTrue("Vectores comunes que fallan:\n" + fallos.joinToString("\n"), fallos.isEmpty())
	}
}
