package com.xebolax.nomesubaslosprecios.nucleo

import org.jsoup.nodes.DataNode
import org.jsoup.nodes.Document
import org.jsoup.nodes.Element
import org.jsoup.nodes.Node
import org.jsoup.nodes.TextNode
import org.jsoup.parser.Parser
import java.net.URLDecoder
import java.util.IdentityHashMap
import kotlin.math.abs

/** Un importe candidato a ser el precio, con su puntuación y por qué. */
class Candidato(
	val valor: Double,
	val origen: String,
	var puntos: Double = 0.0,
	val texto: String = "",
	val elemento: Element? = null,
	val motivos: MutableList<String> = mutableListOf(),
) {
	/** Familia de un candidato oculto (estado, dataLayer, gtag, fbq...), para contar fuentes independientes. */
	val familia: String get() = origen.substringBefore(' ')
}

/** Lo que decide el extractor genérico (pasos 7 a 12 de EXTRACTOR_GENERICO.md). */
data class DecisionGenerica(
	val precio: Double?,
	/** «plataforma shopify», «análisis de la página»... */
	val origen: String?,
	val confianza: String?,
	val desde: Boolean,
	/** Candidatos visibles ordenados por puntos (para que elija el usuario). */
	val candidatos: List<Candidato>,
	val plataformas: List<String>,
	val variantes: List<VarianteEncontrada> = emptyList(),
)

/** Una variante del producto (talla, color...) con su precio. clave: sku, id o nombre. */
data class VarianteEncontrada(val clave: String, val nombre: String, val precio: Double?, val disponible: Boolean?)

/**
 * Extractor genérico: plataforma, estado incrustado, analítica, heurística
 * visible con puntuación y decisión con UMBRAL = 8, MARGEN = 3 y
 * UMBRAL_UNICO = 5 (EXTRACTOR_GENERICO.md, traducido del prototipo de
 * compartido/referencia_extractor/extractor_generico.py).
 */
object ExtractorGenerico {

	const val UMBRAL = 8.0
	const val MARGEN = 3.0
	const val BONO_COINCIDE = 3.0
	const val UMBRAL_UNICO = 5.0

	private fun r(p: String, ic: Boolean = true) = regexUnicode(p, ic)

	private val FIRMAS = listOf(
		"shopify" to Regex("cdn\\.shopify\\.com|ShopifyAnalytics|Shopify\\.shop\\s*="),
		"woocommerce" to Regex("woocommerce-Price-amount|wp-content/plugins/woocommerce|class=\"[^\"]*woocommerce"),
		"prestashop" to Regex("var prestashop\\s*=|prestashop\\s*=\\s*\\{|/modules/ps_|PrestaShop"),
		"magento" to Regex("x-magento-init|data-mage-init|Magento_[A-Z]|mage/cookies"),
		"sfcc" to Regex("/on/demandware\\.|demandware\\.static|dwvar_"),
		"vtex" to Regex("vteximg\\.com|vtexassets\\.com|data-varname=\"__STATE__\"|skuJson_\\d|vtex\\.events"),
		"bigcommerce" to Regex("BCData\\s*=|cdn\\d*\\.bigcommerce\\.com"),
		"shopware" to Regex("Shopware|sw-plugin|data-shopware"),
		"wix" to Regex("static\\.wixstatic\\.com|wix-warmup-data"),
		"next" to Regex("id=\"__NEXT_DATA__\""),
		"nuxt" to Regex("__NUXT__|id=\"__NUXT_DATA__\""),
	)

	fun detectarPlataformas(html: String): List<String> = FIRMAS.filter { it.second.containsMatchIn(html) }.map { it.first }

	// --- Expresiones de la heurística (apartado 6) ------------------------------------------------

	private const val MONEDA = "(?:€|EUR|eur|euros?|\\$|USD|£|GBP)"
	private const val NUM = "\\d{1,3}(?:[.\\s\\u00A0\\u202F]\\d{3})*(?:[.,]\\d{1,2})?|\\d+(?:[.,]\\d{1,2})?"
	val RE_PRECIO_TEXTO = r("(?:$MONEDA\\s*(?:$NUM)|(?:$NUM)\\s*,?-?\\s*$MONEDA)", ic = false)
	val RE_CLASE_PRECIO = r("price|precio|prezzo|preco|preis|prix|amount|importe|pvp|cost|tarifa|money")
	private val RE_CLASE_ACTUAL = r("current|final|sale|special|actual|now|offer|oferta|promo|selling|our[-_]?price|regular-price__current|price--main|main-price|product-price")
	val RE_CLASE_TACHADO = r("old|was|before|regular(?!-price__current)|compare|tachad|anterior|strike|crossed|rrp|pvpr|list-?price|original|antes|precio-?base|price-?before|discount-from")
	private val RE_ZONA_AJENA = r("related|relacionad|recommend|recomend|upsell|up-sell|cross-?sell|carousel|carrusel|slider|swiper|similar|recent|viewed|vistos|also|tambien|bundle|accesor|complement|footer|header|navbar|menu|minicart|mini-cart|cart-drawer|widget_shopping_cart|sidebar|newsletter|popup|modal|banner|product-tile|product-item(?!-info)|product-card|miniature|grid-product|product-list|productos-|products-grid|tile|frequently|compra-junto|pack")
	private val RE_DESDE = r("\\b(desde|a partir de|from|ab|starting at)\\b")
	private val RE_CUOTA = r("/\\s*mes|al mes|mensual|cuotas?|financ|plazos|meses|month|/mo\\b|aplazame|sequra|klarna|pagantis|paypal en 3|en \\d+ pagos")
	private val RE_AHORRO = r("ahorr|descuento|dto\\.?|save|you save|-\\s*\\d+\\s*%|\\d+\\s*%\\s*(dto|off)|rebaja de")
	private val RE_ENVIO = r("env[ií]o|gastos|shipping|entrega|portes|gratis a partir|pedidos? superiores?|free delivery")
	private val RE_UNIDAD = r("/\\s*(kg|g|l|ml|m2|m²|m|100\\s*g|100\\s*ml|lavado|dosis|litro|kilo|cápsula|capsula)\\b|por (kilo|litro|lavado|dosis|cápsula)|precio (por kilo|por litro|unitario)|\\bunit price|€\\s*/\\s*(kg|l|m)")
	private val RE_UNIDAD_DEBIL = r("/\\s*(ud|u|unidad|uds)\\b|por unidad")
	private val RE_ANTES = r("precio original|precio anterior|precio de venta recomendado|pvp ?rec|pvpr|antes:?\\s|\\bwas\\b|\\brrp\\b|original price|regular price|precio habitual|precio sin descuento")
	private val RE_ETIQUETA_PRECIO = r("\\b(precio|p\\.?v\\.?p\\.?|price|importe)\\s*:")
	private val RE_ACTUAL_TXT = r("precio actual|current price|ahora:?\\s|now:?\\s|precio final|tu precio")
	private val RE_SIN_IVA = r("sin iva|iva no incl|\\+\\s*iva|excl\\.?\\s*(iva|vat|tax)|tax excl|base imponible|antes de impuestos|vat excl|pretax|sin impuestos")
	private val RE_CON_IVA = r("iva incl|con iva|impuestos incl|vat incl|tax incl|igic incl")
	private val RE_BOTON_CARRITO = r("a[ñn]adir al carrito|a[ñn]adir a la cesta|a[ñn]adir a la bolsa|comprar ahora|comprar\\b|add to (cart|bag|basket)|buy now|añadir$|reservar")
	private val RE_CLASE_BOTON = r("add-to-cart|addtocart|add_to_cart|btn-cart|tocart|buy-button")
	private val RE_CABECERA = r("site|masthead|main-header|page-header|top-?bar|cabecera")
	private val RE_DOS_DECIMALES = Regex("\\d[.,]\\d{2}\\b")
	private val RE_TROZO_DECIMAL = Regex("^[.,]\\s?\\d")
	private val RE_NUMERO_ATRIBUTO = Regex("\\s*\\d+(?:[.,]\\d+)?\\s*")

	private val ETIQUETAS_FUERA = setOf("script", "style", "noscript", "template", "svg", "head", "iframe", "select", "option", "button", "label", "title")
	private val ETIQUETAS_SIN_TEXTO = setOf("script", "style", "noscript", "template", "svg", "head")

	fun norm(t: String?): String = (t ?: "").replace(Regex("[\\s\\u00A0\\u202F]+"), " ").trim()

	/** Texto de un elemento, como get_text(" ") del prototipo. */
	private fun texto(e: Element): String = norm(e.text())

	private fun textoCorto(e: Element, limite: Int = 48): String? = texto(e).takeIf { it.isNotEmpty() && it.length <= limite }

	private fun ancestros(e: Element, n: Int = 50): List<Element> {
		val out = ArrayList<Element>()
		var p = e.parent()
		while (p != null && p !is Document && out.size < n) {
			out += p
			p = p.parent()
		}
		return out
	}

	private fun clases(e: Element): String = e.classNames().joinToString(" ")

	private fun atributosTexto(e: Element): String {
		val partes = mutableListOf(e.id(), clases(e), e.attr("itemprop"))
		for (a in e.attributes()) if (a.key.startsWith("data-")) {
			if (a.value.length < 60) partes += "${a.key}=${a.value}"
			partes += a.key
		}
		return partes.joinToString(" ")
	}

	fun tachado(e: Element): Boolean {
		for (a in listOf(e) + ancestros(e, 4)) {
			if (a.tagName() in setOf("del", "s", "strike")) return true
			if (RE_CLASE_TACHADO.containsMatchIn(clases(a) + " " + a.id())) return true
			if (a.attr("style").contains("line-through")) return true
			if (a.attr("data-price-type") in setOf("oldPrice", "basePrice")) return true
		}
		return false
	}

	private fun esCabeceraDelSitio(h: Element): Boolean =
		h.selectFirst("nav") != null || RE_CABECERA.containsMatchIn(clases(h) + " " + h.id()) || h.parent()?.tagName() == "body"

	private fun esZonaAjena(a: Element, ancestrosH1: Set<Element>): Boolean {
		if (a.tagName() in setOf("body", "html", "main", "#root") || a in ancestrosH1) return false
		if (a.tagName() in setOf("footer", "nav", "aside")) return true
		if (a.tagName() == "header" && esCabeceraDelSitio(a)) return true
		val fichas = a.classNames().toList() + listOfNotNull(a.id().ifEmpty { null })
		return fichas.any { RE_ZONA_AJENA.containsMatchIn(it) }
	}

	private fun identidad(lista: Collection<Element>): MutableSet<Element> =
		java.util.Collections.newSetFromMap(IdentityHashMap<Element, Boolean>()).apply { addAll(lista) }

	// --- Paso 7: plataforma ------------------------------------------------------------------------

	private fun parametros(url: String?): Map<String, String> {
		val q = url?.substringAfter('?', "")?.substringBefore('#') ?: return emptyMap()
		if (q.isEmpty()) return emptyMap()
		return q.split('&').filter { it.isNotEmpty() }.associate { p ->
			val k = p.substringBefore('=')
			val v = p.substringAfter('=', "")
			decodificar(k) to decodificar(v)
		}
	}

	private fun decodificar(t: String) = try {
		URLDecoder.decode(t, "UTF-8")
	} catch (e: IllegalArgumentException) {
		t
	}

	private fun mapa(v: Any?): Map<String, Any?>? {
		@Suppress("UNCHECKED_CAST")
		return v as? Map<String, Any?>
	}

	private fun esEntero(v: Any?) = v is Int || v is Long || (v is Number && v.toDouble() == Math.floor(v.toDouble()))

	private fun centimos(v: Any?): Double? = (v as? Number)?.toDouble()?.takeIf { it > 0 }?.let { redondear(it / 100) }

	private fun plataformaShopify(html: String, doc: Document, url: String?, variantes: MutableList<VarianteEncontrada>): List<Candidato> {
		val res = mutableListOf<Candidato>()
		val varId = parametros(url)["variant"]
		val metas = jsonTras(html, Regex("var\\s+meta\\s*=\\s*(?=\\{)")) + jsonTras(html, Regex("ShopifyAnalytics\\.meta\\s*=\\s*(?=\\{)"))
		for (meta in metas) {
			val prod = mapa(mapa(meta)?.get("product")) ?: continue
			val vs = (prod["variants"] as? List<*>)?.mapNotNull { mapa(it) }?.takeIf { it.isNotEmpty() } ?: continue
			if (variantes.isEmpty()) vs.forEach { v ->
				val clave = v["id"]?.toString() ?: return@forEach
				val nombre = (v["public_title"] ?: v["name"] ?: v["title"] ?: clave).toString()
				variantes += VarianteEncontrada(clave, nombre, centimos(v["price"]), null)
			}
			val elegidas = vs.filter { varId != null && idTexto(it["id"]) == varId }.ifEmpty { vs }
			val precios = elegidas.mapNotNull { centimos(it["price"]) }.toSortedSet()
			if (precios.isNotEmpty()) res += Candidato(precios.first(), "shopify meta (céntimos)", motivos = mutableListOf(if (precios.size > 1) "desde" else "variante única o elegida"))
		}
		for (s in doc.getElementsByTag("script")) {
			if (!(s.hasAttr("data-selected-variant") || s.hasAttr("data-product-json") || s.id().startsWith("ProductJson"))) continue
			val d = mapa(leerJson(s.data())) ?: continue
			val p: Any? = if (d.containsKey("variants")) {
				val vs = (d["variants"] as? List<*>)?.mapNotNull { mapa(it) }.orEmpty()
				val elegidas = vs.filter { varId == null || idTexto(it["id"]) == varId }.ifEmpty { vs }
				elegidas.mapNotNull { (it["price"] as? Number)?.takeIf { n -> esEntero(n) } }.minByOrNull { it.toDouble() }
			} else d["price"]
			if (p is Number && esEntero(p) && p.toDouble() > 0) res += Candidato(redondear(p.toDouble() / 100), "shopify product-json (céntimos)")
		}
		return res
	}

	private fun idTexto(v: Any?): String? = when (v) {
		null -> null
		is Number -> if (esEntero(v)) v.toLong().toString() else v.toString()
		else -> v.toString()
	}

	private fun bloquePrincipalWoo(doc: Document): Element? {
		for (sel in listOf(
			"div.product .summary", "div[id^=product-] .summary", ".single-product-wrapper .summary", ".product-summary", ".wd-single-price",
			".elementor-widget-woocommerce-product-price", ".elementor-widget-wd_single_product_price",
		)) doc.selectFirst(sel)?.let { return it }
		return null
	}

	private fun precioWooEn(bloque: Element): Pair<Double?, String> {
		val caja = if (bloque.hasClass("price")) bloque else (bloque.selectFirst("p.price, span.price") ?: bloque)
		val ins = caja.select("ins .woocommerce-Price-amount")
		val cantidades = ins.ifEmpty { caja.select(".woocommerce-Price-amount").filter { a -> a.parents().none { it.tagName() == "del" } } }
		val vals = cantidades.mapNotNull { analizarImporte(it.text()) }
		if (vals.isEmpty()) return null to ""
		return vals.min() to if (vals.toSet().size > 1) "rango desde" else ""
	}

	private fun plataformaWoo(doc: Document, url: String?, variantes: MutableList<VarianteEncontrada>): List<Candidato> {
		val res = mutableListOf<Candidato>()
		doc.selectFirst("form.variations_form[data-product_variations]")?.let { form ->
			val variaciones = (leerJson(form.attr("data-product_variations")) as? List<*>)?.mapNotNull { mapa(it) }
			if (!variaciones.isNullOrEmpty()) {
				val q = parametros(url)
				fun atributos(v: Map<String, Any?>) = mapa(v["attributes"]).orEmpty()
				if (variantes.isEmpty()) variaciones.forEach { v ->
					val nombre = atributos(v).values.mapNotNull { it?.toString()?.ifEmpty { null } }.joinToString(", ").ifEmpty { v["variation_id"]?.toString() ?: "?" }
					variantes += VarianteEncontrada(idTexto(v["variation_id"]) ?: nombre, nombre, numeroDeMaquina(v["display_price"]), v["is_in_stock"] as? Boolean)
				}
				val elegidas = variaciones.filter { v ->
					val at = atributos(v)
					q.isNotEmpty() && at.all { (k, valor) -> q[k] == null || q[k] == valor?.toString() || q[k] == "" || valor?.toString() == "" } && at.keys.any { it in q }
				}
				val pool = elegidas.ifEmpty { variaciones }
				val disponibles = pool.filter { (it["is_in_stock"] as? Boolean) ?: true }.ifEmpty { pool }
				val precios = disponibles.mapNotNull { numeroDeMaquina(it["display_price"]) }.toSortedSet()
				if (precios.isNotEmpty()) res += Candidato(
					precios.first(), "woocommerce variaciones",
					motivos = mutableListOf(if (elegidas.isNotEmpty()) "variante de la URL" else if (precios.size > 1) "desde" else "todas iguales"),
				)
			}
		}
		val titulo = doc.selectFirst("h1.product_title, .product_title, h1.entry-title") ?: doc.selectFirst("h1")
		var b: Element? = null
		if (titulo != null) {
			val ancT = identidad(listOf(titulo) + ancestros(titulo))
			val todos = doc.allElements
			val inicio = todos.indexOf(titulo)
			var n = 0
			for (i in inicio + 1 until todos.size) {
				val e = todos[i]
				if (!e.hasClass("price")) continue
				if (n++ > 30) break
				if (e.tagName() in setOf("p", "span", "div") && e.selectFirst(".woocommerce-Price-amount") != null &&
					ancestros(e).none { esZonaAjena(it, ancT) }
				) {
					b = e
					break
				}
			}
		}
		if (b == null) b = bloquePrincipalWoo(doc)
		if (b != null) {
			val (v, nota) = precioWooEn(b)
			if (v != null) res += Candidato(v, "woocommerce .summary .price", motivos = if (nota.isNotEmpty()) mutableListOf(nota) else mutableListOf())
		}
		return res
	}

	private fun plataformaPrestashop(html: String, doc: Document): List<Candidato> {
		val res = mutableListOf<Candidato>()
		doc.selectFirst("#product-details[data-product]")?.let { d ->
			val datos = mapa(leerJson(d.attr("data-product")))
			val v = datos?.let { numeroDeMaquina(it["price_amount"]) ?: analizarImporte(it["price"]?.toString()) }
			if (v != null) res += Candidato(v, "prestashop data-product price_amount")
		}
		doc.selectFirst(".product-prices .current-price [content], .current-price-value[content], .current-price [itemprop=price][content]")?.let { e ->
			numeroDeMaquina(e.attr("content"))?.let { res += Candidato(it, "prestashop .current-price content") }
		}
		doc.selectFirst("#our_price_display")?.let { e ->
			val v = if (e.attr("content").isNotEmpty()) numeroDeMaquina(e.attr("content")) else analizarImporte(e.text())
			if (v != null) res += Candidato(v, "prestashop 1.6 #our_price_display")
		}
		Regex("var\\s+productPrice\\s*=\\s*['\"]?([\\d.]+)").find(html)?.let { m ->
			numeroDeMaquina(m.groupValues[1])?.let { res += Candidato(it, "prestashop 1.6 productPrice") }
		}
		return res
	}

	private fun plataformaMagento(html: String, doc: Document): List<Candidato> {
		val res = mutableListOf<Candidato>()
		doc.selectFirst(".product-info-main, .product-info-price, #maincontent .product-info-main")?.let { principal ->
			for (e in principal.select("[data-price-type=finalPrice][data-price-amount]")) {
				if (e.parents().any { p -> p.classNames().any { Regex("old-price|tier").containsMatchIn(it) } }) continue
				val v = numeroDeMaquina(e.attr("data-price-amount")) ?: continue
				res += Candidato(v, "magento finalPrice (bloque principal)")
				break
			}
		}
		jsonTras(html, Regex("\"jsonConfig\"\\s*:\\s*(?=\\{)")).firstOrNull()?.let { cfg ->
			val op = mapa(mapa(cfg)?.get("optionPrices"))
			if (op != null) {
				val precios = op.values.mapNotNull { numeroDeMaquina(mapa(mapa(it)?.get("finalPrice"))?.get("amount")) }.toSortedSet()
				if (precios.isNotEmpty()) res += Candidato(precios.first(), "magento jsonConfig optionPrices", motivos = mutableListOf(if (precios.size > 1) "desde" else ""))
			}
		}
		return res
	}

	private fun plataformaSfcc(doc: Document): List<Candidato> {
		val bloque = doc.selectFirst(".product-detail[data-pid], .pdp-main, .product-detail, #product-content") ?: return emptyList()
		val e = bloque.selectFirst(".prices .price .sales .value[content], .prices .sales .value[content], .price-sales") ?: return emptyList()
		val v = if (e.attr("content").isNotEmpty()) numeroDeMaquina(e.attr("content")) else analizarImporte(e.text())
		return listOfNotNull(v?.let { Candidato(it, "sfcc .prices .sales .value") })
	}

	private fun plataformaVtex(html: String, doc: Document): List<Candidato> {
		val res = mutableListOf<Candidato>()
		for (sku in jsonTras(html, Regex("var\\s+skuJson_\\d+\\s*=\\s*(?=\\{)"))) {
			val precios = (mapa(sku)?.get("skus") as? List<*>).orEmpty().mapNotNull { mapa(it) }
				.filter { it["available"] == true }.mapNotNull { centimos(it["bestPrice"]) }.toSortedSet()
			if (precios.isNotEmpty()) res += Candidato(precios.first(), "vtex skuJson bestPrice (céntimos)")
		}
		for (d in jsonTras(html, Regex("vtex\\.events\\.addData\\(\\s*(?=\\{)"))) {
			numeroDeMaquina(mapa(d)?.get("productPriceTo"))?.let { res += Candidato(it, "vtex addData productPriceTo") }
		}
		doc.selectFirst("template[data-varname=__STATE__]")?.let { t ->
			val cuerpo = t.selectFirst("script")?.data()?.ifEmpty { null } ?: t.html()
			val a = cuerpo.indexOf('{')
			val b = cuerpo.lastIndexOf('}')
			val estado = if (a >= 0 && b > a) mapa(leerJson(cuerpo.substring(a, b + 1))) else null
			val precios = estado.orEmpty().filter { (k, o) -> o is Map<*, *> && k.contains("commertialOffer") && ((mapa(o)?.get("AvailableQuantity") as? Number)?.toDouble() ?: 1.0) > 0 }
				.mapNotNull { numeroDeMaquina(mapa(it.value)?.get("Price")) }
			if (precios.isNotEmpty()) res += Candidato(precios.min(), "vtex __STATE__ commertialOffer.Price")
		}
		return res
	}

	private fun plataformaBigcommerce(html: String): List<Candidato> {
		val res = mutableListOf<Candidato>()
		for (d in jsonTras(html, Regex("var\\s+BCData\\s*=\\s*(?=\\{)"))) {
			val p = mapa(mapa(mapa(d)?.get("product_attributes"))?.get("price")) ?: continue
			val conIva = mapa(p["with_tax"])
			val v = numeroDeMaquina((conIva ?: mapa(p["without_tax"]))?.get("value")) ?: continue
			res += Candidato(v, if (conIva != null) "bigcommerce BCData price.with_tax" else "bigcommerce BCData sin IVA")
		}
		return res
	}

	private fun plataforma(nombre: String, html: String, doc: Document, url: String?, variantes: MutableList<VarianteEncontrada>): List<Candidato> = when (nombre) {
		"shopify" -> plataformaShopify(html, doc, url, variantes)
		"woocommerce" -> plataformaWoo(doc, url, variantes)
		"prestashop" -> plataformaPrestashop(html, doc)
		"magento" -> plataformaMagento(html, doc)
		"sfcc" -> plataformaSfcc(doc)
		"vtex" -> plataformaVtex(html, doc)
		"bigcommerce" -> plataformaBigcommerce(html)
		else -> emptyList()
	}

	// --- Paso 8: estado de la aplicación --------------------------------------------------------------

	private val CLAVES_PRECIO = listOf("price", "Price", "salePrice", "sellingPrice", "finalPrice", "currentPrice", "priceValue", "special_price", "final_price", "precio", "pvp", "amount")
	private val CLAVES_NOMBRE = listOf("name", "Name", "title", "productName", "nombre")
	private val RE_CENTIMOS = Regex("(?i)(price|precio).*(cents|centimos)$")

	private fun precioDeObjeto(d: Map<String, Any?>): Double? {
		for (k in CLAVES_PRECIO) {
			if (!d.containsKey(k)) continue
			val v = d[k]
			if (v is Map<*, *>) {
				if (v.containsKey("centAmount")) return centimos(v["centAmount"])
				for (kk in listOf("amount", "value", "current", "final", "sale", "price")) {
					if (v.containsKey(kk) && v[kk] !is Map<*, *> && v[kk] !is List<*>) return numeroDeMaquina(v[kk])
				}
				continue
			}
			if (v is Number || v is String) return numeroDeMaquina(v)
		}
		for ((k, v) in d) if (RE_CENTIMOS.containsMatchIn(k) && v is Number && esEntero(v) && v.toDouble() > 0) return redondear(v.toDouble() / 100)
		return null
	}

	private data class ProductoOculto(val valor: Double, val nombre: String, val parecido: Double, val ruta: String)

	private val RE_PALABRA = regexUnicode("\\w{4,}")

	private fun productosEnJson(datos: Any?, nombreRef: String): List<ProductoOculto> {
		val ref = RE_PALABRA.findAll(nombreRef.lowercase()).map { it.value }.toSet()
		val vistos = mutableListOf<ProductoOculto>()
		for ((ruta, d) in recorrerJson(datos)) {
			val nombre = CLAVES_NOMBRE.firstNotNullOfOrNull { d[it] as? String } ?: continue
			val v = precioDeObjeto(d) ?: continue
			val palabras = RE_PALABRA.findAll(nombre.lowercase()).map { it.value }.toSet()
			val parecido = if (ref.isNotEmpty()) (palabras intersect ref).size.toDouble() / maxOf(1, palabras.size) else 0.0
			vistos += ProductoOculto(v, nombre, parecido, ruta.takeLast(3).joinToString("/"))
		}
		return vistos
	}

	/** Nuxt 3 («devalue»): una lista plana donde los enteros son referencias a otras posiciones. */
	fun devalueNuxt(arr: List<*>): Any? {
		val cache = HashMap<Int, Any?>()
		fun res(i: Any?, prof: Int): Any? {
			val n = (i as? Number)?.takeIf { esEntero(it) }?.toInt() ?: return null
			if (prof > 60 || n < 0 || n >= arr.size) return null
			if (cache.containsKey(n)) return cache[n]
			return when (val v = arr[n]) {
				is Map<*, *> -> {
					val out = LinkedHashMap<String, Any?>()
					cache[n] = out
					for ((k, ref) in v) out[k.toString()] = res(ref, prof + 1)
					out
				}
				is List<*> -> {
					if (v.isNotEmpty() && v[0] is String && v[0] in setOf("Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef")) {
						if (v.size > 1) res(v[1], prof + 1) else null
					} else {
						val out = ArrayList<Any?>()
						cache[n] = out
						v.forEach { out += res(it, prof + 1) }
						out
					}
				}
				else -> v
			}
		}
		return res(0, 0)
	}

	private fun bloquesDeEstado(html: String, doc: Document): List<Pair<String, Any?>> {
		val bloques = mutableListOf<Pair<String, Any?>>()
		for (s in doc.getElementsByTag("script")) {
			val tipo = s.attr("type").lowercase()
			val sid = s.id()
			val txt = s.data()
			if (sid == "__NEXT_DATA__" || (tipo == "application/json" && txt.length > 50)) {
				var d = leerJson(txt) ?: continue
				if (sid == "__NUXT_DATA__" && d is List<*>) d = devalueNuxt(d) ?: continue
				bloques += sid.ifEmpty { "application/json" } to d
			}
		}
		for (nombre in listOf("__INITIAL_STATE__", "__PRELOADED_STATE__", "__APOLLO_STATE__", "__APP_STATE__", "__STORE__")) {
			for (d in jsonTras(html, Regex("window\\.$nombre\\s*=\\s*(?=[{\\[])")) + jsonTras(html, Regex("window\\[['\"]$nombre['\"]]\\s*=\\s*(?=[{\\[])"))) {
				bloques += nombre to d
			}
		}
		val patron = Regex("(?:\\b(?:var|let|const)\\s+|window\\.)([A-Za-z_$]*(?:[Pp]roduct|[Pp]roducto|[Ii]tem|[Pp]dp|[Ss]ku|[Oo]ffer)[A-Za-z0-9_$]*)\\s*=\\s*(?=\\{)")
		for (m in patron.findAll(html)) {
			val bloque = objetoEquilibrado(html, m.range.last + 1) ?: continue
			if (bloque.length >= 2_000_000) continue
			cargarJsonFlexible(bloque)?.let { bloques += "var ${m.groupValues[1]}" to it }
		}
		return bloques
	}

	// --- Paso 9: analítica ----------------------------------------------------------------------------

	private fun senalesAnalitica(html: String, doc: Document): List<Candidato> {
		val res = mutableListOf<Candidato>()
		for (m in Regex("['\"]?event['\"]?\\s*:\\s*['\"]view_item['\"]").findAll(html)) {
			var ini = html.lastIndexOf('{', m.range.first)
			var bloque: String? = null
			repeat(6) {
				if (bloque != null) return@repeat
				val b = if (ini >= 0) objetoEquilibrado(html, ini) else null
				if (b != null && ini + b.length > m.range.last + 1) bloque = b
				else ini = if (ini > 0) html.lastIndexOf('{', ini - 1) else -1
			}
			val obj = mapa(bloque?.let { cargarJsonFlexible(it) }) ?: continue
			val items = mapa(obj["ecommerce"])?.get("items") as? List<*>
			val it0 = mapa(items?.firstOrNull()) ?: continue
			if (it0.containsKey("price_tax_inc")) numeroDeMaquina(it0["price_tax_inc"])?.let { res += Candidato(it, "dataLayer view_item price_tax_inc") }
			numeroDeMaquina(it0["price"])?.let { res += Candidato(it, "dataLayer view_item items[0].price", motivos = mutableListOf("puede ir sin IVA")) }
		}
		for (d in jsonTras(html, Regex("gtag\\(\\s*['\"]event['\"]\\s*,\\s*['\"]view_item['\"]\\s*,\\s*(?=\\{)"))) {
			val dm = mapa(d) ?: continue
			val it0 = mapa((dm["items"] as? List<*>)?.firstOrNull())
			(numeroDeMaquina(it0?.get("price")) ?: numeroDeMaquina(dm["value"]))?.let { res += Candidato(it, "gtag view_item") }
		}
		for (d in jsonTras(html, Regex("['\"]?detail['\"]?\\s*:\\s*(?=\\{\\s*['\"]?(?:actionField|products))"))) {
			val p0 = mapa((mapa(d)?.get("products") as? List<*>)?.firstOrNull()) ?: continue
			numeroDeMaquina(p0["price"])?.let { res += Candidato(it, "dataLayer UA detail.products[0].price", motivos = mutableListOf("puede ir sin IVA")) }
		}
		for (d in jsonTras(html, Regex("fbq\\(\\s*['\"]track['\"]\\s*,\\s*['\"]ViewContent['\"]\\s*,\\s*(?=\\{)"))) {
			numeroDeMaquina(mapa(d)?.get("value"))?.let { res += Candidato(it, "fbq ViewContent value") }
		}
		for (m in Regex("facebook\\.com/tr\\?[^\"'<>\\s]*ev=ViewContent[^\"'<>\\s]*").findAll(html)) {
			val q = parametros(Parser.unescapeEntities(m.value, true))
			val v = numeroDeMaquina(q["cd[value]"] ?: q["cd[product_price]"])
			if (v != null) {
				res += Candidato(v, "fbq noscript cd[value]")
				break
			}
		}
		Regex("\"name\"\\s*:\\s*\"ViewContent\".{0,600}?\"value\"\\s*:\\s*\"?([\\d.]+)", RegexOption.DOT_MATCHES_ALL).find(html)?.let { m ->
			numeroDeMaquina(m.groupValues[1])?.let { res += Candidato(it, "PixelYourSite ViewContent value") }
		}
		for (d in jsonTras(html, Regex("['\"]Viewed Product['\"]\\s*,\\s*(?=\\{)"))) {
			val dm = mapa(d) ?: continue
			numeroDeMaquina(dm["Price"] ?: dm["Value"])?.let { res += Candidato(it, "Klaviyo Viewed Product") }
		}
		Regex("['\"]?ecomm_totalvalue['\"]?\\s*:\\s*['\"]?(\\d+(?:\\.\\d+)?)").find(html)?.let { m ->
			numeroDeMaquina(m.groupValues[1])?.let { res += Candidato(it, "google_tag_params ecomm_totalvalue") }
		}
		for (i in 1..2) {
			val lab = doc.getElementsByTag("meta").firstOrNull { it.attr("name") == "twitter:label$i" }
			val dat = doc.getElementsByTag("meta").firstOrNull { it.attr("name") == "twitter:data$i" }
			if (lab != null && dat != null && regexUnicode("\\s*(precio|price|prix|preço|prezzo)\\s*", true).matches(lab.attr("content"))) {
				analizarImporte(dat.attr("content"))?.let { res += Candidato(it, "twitter:data$i (label Precio)") }
			}
		}
		return res
	}

	// --- Paso 10: heurística visible -------------------------------------------------------------------

	class Anclas(val h1: Element?, val boton: Element?, val principal: Element?)

	private fun localizarAnclas(doc: Document, orden: Map<Element, Int>): Anclas {
		var h1: Element? = null
		for (h in doc.getElementsByTag("h1")) {
			if (h.parents().any { it.tagName() == "nav" || it.tagName() == "footer" } || texto(h).isEmpty()) continue
			val cab = h.parents().firstOrNull { it.tagName() == "header" }
			if (cab != null && esCabeceraDelSitio(cab)) continue
			h1 = h
			break
		}
		if (h1 == null) h1 = doc.selectFirst(".product_title, .product-title, .product-name, [itemprop=name]")
		val ancH1 = if (h1 != null) identidad(listOf(h1) + ancestros(h1)) else identidad(emptyList())
		val posH1 = h1?.let { orden[it] } ?: 0
		val botones = mutableListOf<Element>()
		for (b in doc.select("button, input, a")) {
			val t = norm(if (b.tagName() != "input") b.text() else b.attr("value"))
			val cls = clases(b) + " " + b.attr("name") + " " + b.id() + " " + b.attr("data-button-action")
			if ((RE_BOTON_CARRITO.containsMatchIn(t) && t.length < 40) || RE_CLASE_BOTON.containsMatchIn(cls)) {
				if (ancestros(b).any { esZonaAjena(it, ancH1) }) continue
				botones += b
			}
		}
		val boton = botones.firstOrNull { (orden[it] ?: 0) > posH1 } ?: botones.firstOrNull()
		var principal: Element? = null
		if (h1 != null && boton != null) {
			val ancB = identidad(listOf(boton) + ancestros(boton))
			principal = (listOf(h1) + ancestros(h1)).firstOrNull { it in ancB }
			if (principal != null && principal.tagName() in setOf("html", "body", "#root")) principal = null
		}
		return Anclas(h1, boton, principal)
	}

	private fun textoNodo(n: Node): String = when (n) {
		is TextNode -> n.text()
		is DataNode -> ""
		is Element -> if (n.tagName() in ETIQUETAS_SIN_TEXTO) "" else n.text()
		else -> ""
	}

	/** Texto justo antes y justo después del elemento, sin cruzar otro importe (apartado 6.3). */
	fun contextoAdyacente(el: Element, limite: Int = 40, niveles: Int = 3): Pair<String, String> {
		var nodo: Element = el
		var antes = ""
		var despues = ""
		repeat(niveles) {
			val partesA = ArrayList<String>()
			var h: Node? = nodo.previousSibling()
			while (h != null) {
				val tx = norm(textoNodo(h))
				if (tx.isNotEmpty()) {
					if (RE_PRECIO_TEXTO.containsMatchIn(tx)) break
					partesA.add(0, tx)
					if (partesA.sumOf { it.length } >= limite) break
				}
				h = h.previousSibling()
			}
			antes = norm(partesA.joinToString(" ")).takeLast(limite)
			val partesD = ArrayList<String>()
			h = nodo.nextSibling()
			while (h != null) {
				val tx = norm(textoNodo(h))
				if (tx.isNotEmpty()) {
					if (RE_PRECIO_TEXTO.containsMatchIn(tx)) break
					partesD.add(tx)
					if (partesD.sumOf { it.length } >= limite) break
				}
				h = h.nextSibling()
			}
			despues = norm(partesD.joinToString(" ")).take(limite)
			val padre = nodo.parent()
			if (antes.isNotEmpty() || despues.isNotEmpty() || padre == null || padre is Document) return antes to despues
			nodo = padre
		}
		return antes to despues
	}

	private fun dentroDeFuera(e: Element): Boolean = e.tagName() in ETIQUETAS_FUERA || e.parents().any { it.tagName() in ETIQUETAS_FUERA }

	/** Los candidatos visibles con su puntuación (apartado 6.4). */
	fun candidatosVisibles(doc: Document): Pair<List<Candidato>, Anclas> {
		val todos = doc.allElements.filter { it !is Document }
		val orden = IdentityHashMap<Element, Int>().apply { todos.forEachIndexed { i, e -> put(e, i) } }
		val anclas = localizarAnclas(doc, orden)
		val (h1, boton, principal) = Triple(anclas.h1, anclas.boton, anclas.principal)
		val total = maxOf(1, todos.size)
		val posH1 = h1?.let { orden[it] }
		val posBoton = boton?.let { orden[it] }
		val tamPrincipal = principal?.allElements?.size?.minus(1) ?: 0
		val principalUtil = principal != null && (tamPrincipal < 0.5 * total || total < 300)
		val ancH1 = if (h1 != null) identidad(listOf(h1) + ancestros(h1)) else identidad(emptyList())

		data class Bruto(val el: Element, val valor: Double, val t: String, val conMoneda: Boolean)
		val brutos = mutableListOf<Bruto>()
		for (el in todos) {
			if (dentroDeFuera(el)) continue
			val t = textoCorto(el)
			var valorAttr: Double? = null
			for (a in listOf("data-price-amount", "data-price", "data-product-price", "data-price-value")) {
				val v = el.attr(a)
				if (v.isNotEmpty() && RE_NUMERO_ATRIBUTO.matches(v)) {
					valorAttr = numeroDeMaquina(v.trim().replace(',', '.'))
					break
				}
			}
			if (el.attr("itemprop") == "price" && el.attr("content").isNotEmpty()) valorAttr = numeroDeMaquina(el.attr("content"))
			if (t == null && valorAttr == null) continue
			if (t != null && RE_TROZO_DECIMAL.containsMatchIn(t)) continue
			val m = t?.let { RE_PRECIO_TEXTO.find(it) }
			val clasePrecio = RE_CLASE_PRECIO.containsMatchIn(atributosTexto(el))
			if (m == null && valorAttr == null && !(clasePrecio && t != null && RE_DOS_DECIMALES.containsMatchIn(t))) continue
			val valor = valorAttr ?: analizarImporte(m?.value ?: t) ?: continue
			if (valor > 1_000_000) continue
			// Se queda el elemento más profundo: si un descendiente da el mismo importe, este sobra
			if (valorAttr == null && el.allElements.drop(1).any { h ->
					h.tagName() !in ETIQUETAS_FUERA && textoCorto(h)?.let { th -> RE_PRECIO_TEXTO.find(th)?.let { analizarImporte(it.value) } } == valor
				}
			) continue
			brutos += Bruto(el, valor, t ?: "", m != null)
		}

		val cands = mutableListOf<Candidato>()
		for ((el, valor, t, conMoneda) in brutos) {
			var p = 0.0
			val motivos = mutableListOf<String>()
			val anc = ancestros(el, 60)
			val cerca = listOf(el) + anc.take(3)
			val attrsCerca = cerca.joinToString(" ") { atributosTexto(it) }
			val (antes, despues) = contextoAdyacente(el)
			val propioYAntes = antes.takeLast(40) + " | " + t
			val propioYDespues = t + " | " + despues.take(40)
			val alrededor = antes.takeLast(40) + " | " + t + " | " + despues.take(40)
			if (conMoneda) { p += 2; motivos += "moneda +2" }
			if (RE_CLASE_PRECIO.containsMatchIn(attrsCerca)) {
				p += 2; motivos += "clase precio +2"
				if (RE_CLASE_ACTUAL.containsMatchIn(attrsCerca) && !RE_CLASE_TACHADO.containsMatchIn(attrsCerca)) { p += 1; motivos += "clase actual/final +1" }
			}
			if (el.attr("itemprop") == "price" || el.attr("data-price-amount").isNotEmpty() || el.parents().any { it.attr("data-price-type") == "finalPrice" }) {
				p += 2; motivos += "itemprop/data-price +2"
			}
			val dentroPrincipal = principalUtil && anc.any { it === principal }
			if (dentroPrincipal) { p += 4; motivos += "bloque principal +4" }
			val pos = orden[el] ?: 0
			if (posH1 != null) {
				val d = abs(pos - posH1)
				val extra = maxOf(0.0, 2.0 * (1 - d / 300.0))
				if (extra > 0) { p += extra; motivos += "cerca del h1 +%.1f".format(extra) }
				if (pos < posH1 - 400) { p -= 2; motivos += "muy por encima del h1 -2" }
			}
			if (posBoton != null) {
				val d = abs(pos - posBoton)
				val extra = maxOf(0.0, 2.0 * (1 - d / 150.0))
				if (extra > 0) { p += extra; motivos += "cerca de comprar +%.1f".format(extra) }
			}
			val esTachado = tachado(el)
			if (esTachado) { p -= 6; motivos += "tachado -6" }
			if (RE_ANTES.containsMatchIn(propioYAntes) && !esTachado) { p -= 6; motivos += "tachado (texto «antes/original») -6" }
			if (RE_ACTUAL_TXT.containsMatchIn(propioYAntes)) { p += 1; motivos += "«precio actual» +1" }
			else if (RE_ETIQUETA_PRECIO.containsMatchIn(propioYAntes)) { p += 1; motivos += "etiqueta «Precio/PVP» +1" }
			if (!dentroPrincipal && anc.any { esZonaAjena(it, ancH1) }) { p -= 5; motivos += "zona ajena (relacionados, carrusel, cabecera...) -5" }
			if (RE_CUOTA.containsMatchIn(alrededor)) { p -= 6; motivos += "cuota/financiación -6" }
			if (RE_AHORRO.containsMatchIn(propioYAntes)) { p -= 5; motivos += "ahorro/descuento -5" }
			if (RE_ENVIO.containsMatchIn(propioYAntes)) { p -= 5; motivos += "envío -5" }
			if (RE_UNIDAD.containsMatchIn(t) || RE_UNIDAD.containsMatchIn(despues.take(15))) { p -= 5; motivos += "precio por kilo/litro -5" }
			else if (RE_UNIDAD_DEBIL.containsMatchIn(t)) { p -= 1; motivos += "«por unidad» -1" }
			if (RE_SIN_IVA.containsMatchIn(alrededor)) { p -= 4; motivos += "sin IVA -4" }
			else if (RE_CON_IVA.containsMatchIn(propioYDespues)) { p += 1; motivos += "IVA incluido +1" }
			if (RE_DESDE.containsMatchIn(antes.takeLast(25) + " " + t.take(12))) { p -= 2; motivos += "desde -2" }
			cands += Candidato(valor, "visible", p, t, el, motivos)
		}
		return cands to Anclas(h1, boton, if (principalUtil) principal else null)
	}

	// --- Pasos 7 a 12 juntos ------------------------------------------------------------------------------

	/** Los pasos 7 a 12 sobre una página ya analizada. variantes recibe las variantes que se encuentren. */
	fun extraer(html: String, doc: Document, url: String?, registro: (String, Throwable?) -> Unit = { _, _ -> }): DecisionGenerica {
		val plataformas = detectarPlataformas(html)
		val variantes = mutableListOf<VarianteEncontrada>()
		// 7. Plataforma
		for (plat in plataformas) {
			val cs = try {
				plataforma(plat, html, doc, url, variantes)
			} catch (e: RuntimeException) {
				registro("Extractor de la plataforma $plat falló", e)
				emptyList()
			}
			val c = cs.firstOrNull() ?: continue
			return DecisionGenerica(c.valor, "${OrigenPrecio.PLATAFORMA.texto} $plat", Confianza.ALTA, desde = c.motivos.any { it.contains("desde") }, candidatos = emptyList(), plataformas = plataformas, variantes = variantes)
		}
		// 8 y 9. Ocultos
		var titulo = doc.getElementsByTag("meta").firstOrNull { it.attr("property") == "og:title" }?.attr("content").orEmpty()
		doc.selectFirst("h1")?.let { titulo += " " + texto(it) }
		val ocultos = mutableListOf<Candidato>()
		for ((nombre, datos) in try {
			bloquesDeEstado(html, doc)
		} catch (e: RuntimeException) {
			registro("No se pudo leer el estado incrustado", e)
			emptyList()
		}) {
			val buenos = productosEnJson(datos, titulo).filter { it.parecido >= 0.5 }
			for (b in buenos.take(5)) ocultos += Candidato(b.valor, "estado $nombre (${b.ruta})", motivos = mutableListOf("nombre coincide %d%%".format(Math.round(b.parecido * 100))))
		}
		ocultos += try {
			senalesAnalitica(html, doc)
		} catch (e: RuntimeException) {
			registro("No se pudo leer la analítica", e)
			emptyList()
		}
		val valoresOcultos = LinkedHashMap<Double, MutableSet<String>>()
		for (c in ocultos) valoresOcultos.getOrPut(c.valor) { mutableSetOf() } += c.familia

		// 10. Visibles
		val (vis, anclas) = candidatosVisibles(doc)
		for (c in vis) {
			val familias = valoresOcultos[c.valor] ?: continue
			val bono = BONO_COINCIDE + if (familias.size > 1) 1 else 0
			c.puntos += bono
			c.motivos += "coincide con datos ocultos +${bono.toInt()}"
		}
		val ordenados = vis.sortedByDescending { it.puntos }
		fun decision(precio: Double?, origen: String?, confianza: String?) =
			DecisionGenerica(precio, origen, confianza, desde = false, candidatos = ordenados, plataformas = plataformas, variantes = variantes)

		// 11. Decisión
		if (ordenados.isNotEmpty()) {
			val mejor = ordenados[0]
			val otro = ordenados.drop(1).firstOrNull { it.valor != mejor.valor }
			val margen = mejor.puntos - (otro?.puntos ?: 0.0)
			if (mejor.puntos >= UMBRAL && (otro == null || margen >= MARGEN)) return decision(mejor.valor, OrigenPrecio.ANALISIS.texto, Confianza.MEDIA)
			val positivos = ordenados.filter { it.puntos > 0 }.map { it.valor }.toSet()
			if (positivos.size == 1 && mejor.puntos >= UMBRAL_UNICO && anclas.boton != null && mejor.motivos.none { it.contains("-") }) {
				return decision(mejor.valor, OrigenPrecio.ANALISIS.texto, Confianza.BAJA)
			}
		}
		if (valoresOcultos.size == 1) {
			val (v, familias) = valoresOcultos.entries.first()
			if (familias.size >= 2) return decision(v, OrigenPrecio.ANALISIS.texto, Confianza.MEDIA)
		}
		val seguros = ocultos.filter { c ->
			c.origen.startsWith("estado") && c.motivos.any { it.startsWith("nombre coincide") && it.substringAfterLast(' ').trimEnd('%').toIntOrNull()?.let { n -> n >= 80 } == true }
		}.map { it.valor }.toSet()
		val mejorVis = ordenados.firstOrNull()?.puntos ?: 0.0
		if (seguros.size == 1 && mejorVis < UMBRAL) return decision(seguros.first(), OrigenPrecio.ANALISIS.texto, Confianza.MEDIA)
		// 12. Pregunta al usuario
		return decision(null, null, null)
	}

	/** Texto de una opción para el lector de pantalla (apartado 7.1): «39,99 € — junto al botón de compra — "…"». */
	fun describir(c: Candidato, moneda: String = "EUR"): String {
		val m = c.motivos.joinToString(" ")
		val partes = mutableListOf<String>()
		if ("tachado" in m) partes += "tachado"
		if ("bloque principal" in m || "cerca de comprar" in m) partes += "junto al botón de compra"
		if ("zona ajena" in m) partes += "en otra zona (relacionados, carrusel o pie)"
		if ("cuota" in m) partes += "cuota o financiación"
		if ("kilo/litro" in m) partes += "precio por kilo o litro"
		if ("envío" in m) partes += "envío"
		if ("sin IVA" in m) partes += "sin IVA"
		if ("desde -2" in m) partes += "desde"
		if ("coincide con datos ocultos" in m) partes += "coincide con los datos internos de la página"
		val texto = c.texto.take(80)
		return formatearImporte(c.valor, moneda) + (if (partes.isNotEmpty()) " — " + partes.joinToString(", ") else "") +
			(if (texto.isNotEmpty()) " — «$texto»" else "")
	}

	/** Opciones para «Elegir el precio en la página»: agrupadas por importe y tipo de contexto, como mucho 8, por puntos. */
	fun opcionesParaElegir(candidatos: List<Candidato>, moneda: String = "EUR"): List<Pair<String, Candidato>> {
		val vistos = HashSet<String>()
		val salida = mutableListOf<Pair<String, Candidato>>()
		for (c in candidatos.sortedByDescending { it.puntos }) {
			if (c.elemento == null) continue
			val desc = describir(c, moneda)
			val tipo = c.valor.toString() + "|" + desc.substringAfter(" — ", "").substringBefore(" — «")
			if (!vistos.add(tipo)) continue
			salida += desc to c
			if (salida.size >= 8) break
		}
		return salida
	}
}
