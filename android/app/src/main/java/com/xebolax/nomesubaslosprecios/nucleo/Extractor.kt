package com.xebolax.nomesubaslosprecios.nucleo

import org.jsoup.Jsoup
import org.jsoup.nodes.Document
import org.jsoup.nodes.Element
import org.jsoup.parser.Parser
import org.jsoup.select.Elements
import org.jsoup.select.Selector
import java.text.Normalizer
import kotlin.math.abs

/** Selectores CSS que escribe el usuario (el del producto y los de su tienda), que ganan a tiendas.json, y la variante elegida. */
data class SelectoresUsuario(
	val precioProducto: String? = null,
	val precioTienda: String? = null,
	val tituloTienda: String? = null,
	val disponibleTienda: String? = null,
	/** Importe de la huella del selector elegido por el usuario (para detectar que se ha roto). */
	val huellaImporte: Double? = null,
	/** Atributo de la huella del que se lee el importe (null o vacío: el texto del elemento). */
	val huellaAtributo: String? = null,
	/** Variante elegida (sku, id o nombre). */
	val variante: String? = null,
)

/** Lo que saca una estrategia. Los campos que no sabe, a null. */
data class Parcial(
	val origen: OrigenPrecio,
	val precio: Double? = null,
	/** Texto de donde salió el precio (para deducir la moneda por el símbolo). */
	val textoPrecio: String? = null,
	val moneda: String? = null,
	val nombre: String? = null,
	val imagen: String? = null,
	val disponible: Boolean? = null,
	/** «plataforma shopify» u otro texto más preciso que el del origen. */
	val origenTexto: String? = null,
	val confianza: String = Confianza.ALTA,
	val desde: Boolean = false,
	val variantes: List<VarianteEncontrada> = emptyList(),
	val candidatos: List<Candidato> = emptyList(),
	/** El JSON-LD dice que la página es una categoría (ItemList o CollectionPage) sin producto. */
	val categoria: Boolean = false,
)

/** Resultado de la extracción de una página. error es null si se puede guardar (hay precio o se sabe que está agotado). */
data class ResultadoExtraccion(
	val precio: Double?,
	val moneda: String,
	val nombre: String?,
	val imagen: String?,
	val disponible: Boolean?,
	val bloqueo: Boolean,
	val error: String?,
	/** De dónde salió el precio (null si no hay precio). */
	val origen: OrigenPrecio?,
	/** Lo que sacó cada estrategia, en orden (para «Probar» los selectores). */
	val parciales: List<Parcial>,
	val confianza: String? = null,
	val desde: Boolean = false,
	val variantes: List<VarianteEncontrada> = emptyList(),
	/** Candidatos visibles para «Elegir el precio en la página». */
	val candidatos: List<Candidato> = emptyList(),
	val origenTexto: String? = origen?.texto,
	/** La página analizada (para elegir el precio y generar el selector). */
	val documento: Document? = null,
)

/** Lo que necesitan las estrategias: la página ya analizada y las reglas de su tienda. */
class ContextoExtraccion(
	val documento: Document,
	val html: String,
	val url: String,
	val dominio: String,
	val reglas: ReglasTienda?,
	val selectores: SelectoresUsuario,
	val nombreTienda: String,
	val registro: (String, Throwable?) -> Unit,
)

/**
 * Una forma de sacar los datos de una página. El extractor es una lista
 * ordenada de estrategias: para añadir otra basta con meterla en su sitio.
 */
interface Estrategia {
	val origen: OrigenPrecio
	fun extraer(c: ContextoExtraccion): Parcial?
}

/** Ayudantes comunes de las estrategias. */
internal object Html {

	/** Busca sin romper con un selector mal escrito por el usuario. */
	fun seleccionar(c: ContextoExtraccion, css: String): Elements = try {
		c.documento.select(css)
	} catch (e: Selector.SelectorParseException) {
		c.registro("Selector CSS no válido: $css", e)
		Elements()
	} catch (e: IllegalArgumentException) {
		c.registro("Selector CSS no válido: $css", e)
		Elements()
	}

	fun normalizar(texto: String?): String? = texto?.replace(Regex("[\\s\\u00A0\\u202F]+"), " ")?.trim()?.ifEmpty { null }

	/** Primer importe válido de una regla: el atributo pedido (formato de máquina) o el texto (con los precios partidos unidos). */
	fun importe(c: ContextoExtraccion, regla: ReglaCss, conAtributos: Boolean = false): Pair<Double, String>? {
		for (e in seleccionar(c, regla.css)) {
			if (regla.atributo != null) {
				val t = e.attr(regla.atributo)
				importeDeMaquina(t)?.let { return it to t }
				continue
			}
			val texto = Extractor.textoImporte(e)
			analizarImporte(texto)?.let { return it to texto }
			if (conAtributos) {
				// Selector del usuario sobre un elemento sin texto (meta, input...): sus atributos de valor
				for (a in listOf("content", "data-price-amount", "data-price", "value")) {
					numeroDeMaquina(e.attr(a).ifEmpty { null })?.let { return it to e.attr(a) }
				}
			}
		}
		return null
	}

	fun texto(c: ContextoExtraccion, regla: ReglaCss): String? {
		for (e in seleccionar(c, regla.css)) {
			val t = normalizar(if (regla.atributo != null) e.attr(regla.atributo) else e.text())
			if (t != null) return t
		}
		return null
	}

	fun imagen(c: ContextoExtraccion, regla: ReglaCss): String? {
		val atributo = regla.atributo ?: "src"
		for (e in seleccionar(c, regla.css)) {
			val valor = e.absUrl(atributo).ifEmpty { e.attr(atributo) }.trim()
			if (valor.isNotEmpty()) return valor
		}
		return null
	}

	fun metas(c: ContextoExtraccion, nombre: String, atributo: String = "property"): List<Element> =
		c.documento.getElementsByTag("meta").filter { it.attr(atributo).equals(nombre, ignoreCase = true) }

	fun meta(c: ContextoExtraccion, nombre: String, atributo: String = "property"): List<String> = metas(c, nombre, atributo).map { it.attr("content") }

	fun absoluta(c: ContextoExtraccion, url: String?): String? {
		val u = url?.trim()?.ifEmpty { null } ?: return null
		if (u.startsWith("http://") || u.startsWith("https://")) return u
		return try {
			java.net.URI(c.url).resolve(u).toString()
		} catch (e: Exception) {
			c.registro("Dirección de imagen no válida: $u", e)
			u
		}
	}

	/** Textos genéricos de «agotado» para el selector de disponibilidad que escribe el usuario. */
	val AGOTADO_GENERICO = listOf("agotado", "no disponible", "sin stock", "out of stock", "sold out", "unavailable", "currently unavailable")

	private val DISPONIBLE = setOf("instock", "limitedavailability", "onlineonly", "preorder", "presale", "instoreonly")
	private val AGOTADO = setOf("outofstock", "soldout", "discontinued")

	/** Disponibilidad de schema.org por el final del texto, sin distinguir mayúsculas. */
	fun disponibilidadSchema(valor: Any?): Boolean? {
		val texto = (valor as? String)?.trim()?.substringAfterLast('/')?.lowercase() ?: return null
		return when (texto) {
			in DISPONIBLE -> true
			in AGOTADO -> false
			else -> null
		}
	}
}

/** 1. selector_precio del producto. */
object EstrategiaSelectorProducto : Estrategia {
	override val origen = OrigenPrecio.SELECTOR_PRODUCTO
	override fun extraer(c: ContextoExtraccion): Parcial? {
		val css = c.selectores.precioProducto?.trim()?.ifEmpty { null } ?: return null
		val (valor, texto) = Html.importe(c, ReglaCss(css, c.selectores.huellaAtributo?.ifEmpty { null }), conAtributos = true) ?: return null
		return Parcial(origen, precio = valor, textoPrecio = texto)
	}
}

/** 2. Selectores de la tienda que escribe el usuario (precio, título y disponibilidad). */
object EstrategiaSelectorTienda : Estrategia {
	override val origen = OrigenPrecio.SELECTOR_TIENDA
	override fun extraer(c: ContextoExtraccion): Parcial? {
		val s = c.selectores
		val precio = s.precioTienda?.trim()?.ifEmpty { null }?.let { Html.importe(c, ReglaCss(it), conAtributos = true) }
		val nombre = s.tituloTienda?.trim()?.ifEmpty { null }?.let { Html.texto(c, ReglaCss(it)) }
		val disponible = s.disponibleTienda?.trim()?.ifEmpty { null }?.let { css ->
			val e = Html.seleccionar(c, css).firstOrNull() ?: return@let null
			val t = e.text().lowercase()
			Html.AGOTADO_GENERICO.none { t.contains(it) }
		}
		if (precio == null && nombre == null && disponible == null) return null
		return Parcial(origen, precio = precio?.first, textoPrecio = precio?.second, nombre = nombre, disponible = disponible)
	}
}

/** 3. Reglas de tiendas.json para el dominio. */
object EstrategiaReglasTienda : Estrategia {
	override val origen = OrigenPrecio.REGLA_TIENDA
	override fun extraer(c: ContextoExtraccion): Parcial? {
		val r = c.reglas ?: return null
		val precio = r.precio.firstNotNullOfOrNull { Html.importe(c, it) }
		val nombre = r.titulo.firstNotNullOfOrNull { Html.texto(c, it) }
		val imagen = r.imagen.firstNotNullOfOrNull { Html.imagen(c, it) }
		var disponible: Boolean? = null
		for (regla in r.disponible) {
			val e = Html.seleccionar(c, regla.css).firstOrNull() ?: continue
			val t = e.text().lowercase()
			disponible = regla.agotado.none { it.isEmpty() || t.contains(it) }
			break
		}
		return Parcial(origen, precio = precio?.first, textoPrecio = precio?.second, nombre = nombre, imagen = imagen, disponible = disponible)
	}
}

/**
 * 4. JSON-LD, recorrido entero y recursivo: el primer Product (o ProductGroup,
 * Book...) con precio; variantes por la URL o la elegida; ofertas en stock
 * primero; sin los productos relacionados.
 */
object EstrategiaJsonLd : Estrategia {
	override val origen = OrigenPrecio.JSON_LD

	private val TIPOS = setOf("product", "productgroup", "book", "individualproduct", "productmodel", "vehicle")
	private val RELACIONADOS = setOf("itemlistelement", "isrelatedto", "issimilarto", "hasvariant")

	private class Oferta(val precio: Double?, val moneda: String?, val disponible: Boolean?, val url: String?, val nombre: String?, val sku: String?)

	private class Evaluacion(
		val precio: Double?, val moneda: String?, val disponible: Boolean?, val desde: Boolean, val variantes: List<VarianteEncontrada>,
	)

	fun tipos(o: Map<String, Any?>): List<String> = when (val t = o.sinMayusculas("@type")) {
		is String -> listOf(t)
		is List<*> -> t.mapNotNull { it as? String }
		else -> emptyList()
	}.map { it.substringAfterLast('/').lowercase() }

	private fun esProducto(o: Map<String, Any?>) = tipos(o).any { it in TIPOS }

	private fun buscar(valor: Any?, salida: MutableList<Map<String, Any?>>, dentro: Boolean, categoria: BooleanArray) {
		when (valor) {
			is Map<*, *> -> {
				@Suppress("UNCHECKED_CAST")
				val o = valor as Map<String, Any?>
				val t = tipos(o)
				if (t.any { it == "itemlist" || it == "collectionpage" }) categoria[0] = true
				val producto = t.any { it in TIPOS }
				if (producto && !dentro) salida += o
				for ((k, v) in o) {
					val kl = k.lowercase()
					val relacionado = dentro || kl in RELACIONADOS || (kl == "offers" && producto) || t.contains("itemlist")
					buscar(v, salida, relacionado, categoria)
				}
			}
			is List<*> -> valor.forEach { buscar(it, salida, dentro, categoria) }
		}
	}

	private fun primero(valor: Any?): Map<String, Any?>? {
		@Suppress("UNCHECKED_CAST")
		return when (valor) {
			is Map<*, *> -> valor as Map<String, Any?>
			is List<*> -> valor.firstOrNull { it is Map<*, *> } as? Map<String, Any?>
			else -> null
		}
	}

	fun importe(valor: Any?): Double? = when (valor) {
		is Number -> valor.toDouble().takeIf { it > 0 && !it.isNaN() }?.let { redondear(it) }
		is String -> importeDeMaquina(valor)
		else -> null
	}

	private fun texto(v: Any?): String? = (v as? String)?.trim()?.ifEmpty { null } ?: (v as? Number)?.let { if (it.toDouble() == Math.floor(it.toDouble())) it.toLong().toString() else it.toString() }

	private fun ofertas(valor: Any?, salida: MutableList<Oferta>) {
		when (valor) {
			is List<*> -> valor.forEach { ofertas(it, salida) }
			is Map<*, *> -> {
				@Suppress("UNCHECKED_CAST")
				val o = valor as Map<String, Any?>
				// Precio de socio (IKEA Family...): no es el precio
				val especificacion = primero(o.sinMayusculas("priceSpecification"))?.takeIf { it.sinMayusculas("validForMemberTier") == null }
				val precio = importe(o.sinMayusculas("price")) ?: importe(o.sinMayusculas("lowPrice")) ?: importe(especificacion?.sinMayusculas("price"))
				val moneda = (texto(o.sinMayusculas("priceCurrency")) ?: texto(especificacion?.sinMayusculas("priceCurrency")))?.uppercase()
				salida += Oferta(
					precio, moneda, Html.disponibilidadSchema(o.sinMayusculas("availability")), texto(o.sinMayusculas("url")),
					texto(o.sinMayusculas("name")), texto(o.sinMayusculas("sku")),
				)
				if (o.sinMayusculas("offers") != null) ofertas(o.sinMayusculas("offers"), salida)
			}
		}
	}

	/** De varias ofertas sin variantes: las válidas, las que están en stock primero, y la menor. */
	private fun mejor(lista: List<Oferta>): Oferta? {
		val validas = lista.filter { it.precio != null }
		return (validas.filter { it.disponible == true }.ifEmpty { validas }).minByOrNull { it.precio!! }
	}

	private fun mismaUrl(a: String?, b: String): Boolean = a != null && (a == b || limpiarUrl(a).trimEnd('/') == limpiarUrl(b).trimEnd('/'))

	/** ¿La variante corresponde a la dirección o a la variante elegida? */
	private fun casa(v: Map<String, Any?>, ofertasV: List<Oferta>, url: String, elegida: String?): Boolean {
		val claves = listOfNotNull(texto(v.sinMayusculas("sku")), texto(v.sinMayusculas("productID"))) +
			v.entries.filter { it.key.lowercase().startsWith("gtin") }.mapNotNull { texto(it.value) }
		if (elegida != null) return elegida in claves || elegida == texto(v.sinMayusculas("name"))
		if (mismaUrl(texto(v.sinMayusculas("url")), url) || ofertasV.any { mismaUrl(it.url, url) }) return true
		return claves.any { it.length >= 3 && url.contains(it) }
	}

	private fun evaluar(p: Map<String, Any?>, url: String, elegida: String?): Evaluacion {
		@Suppress("UNCHECKED_CAST")
		val variantes = (p.sinMayusculas("hasVariant") as? List<*>)?.mapNotNull { it as? Map<String, Any?> }.orEmpty()
		val propias = mutableListOf<Oferta>().also { ofertas(p.sinMayusculas("offers"), it) }
		fun deOferta(o: Oferta?, lista: List<Oferta>) =
			Evaluacion(o?.precio, o?.moneda ?: lista.firstNotNullOfOrNull { it.moneda }, o?.disponible ?: lista.firstNotNullOfOrNull { it.disponible }, false, emptyList())
		if (variantes.isNotEmpty()) {
			val conOfertas = variantes.map { v -> v to mutableListOf<Oferta>().also { ofertas(v.sinMayusculas("offers"), it) } }
			val lista = conOfertas.map { (v, os) ->
				val o = mejor(os)
				VarianteEncontrada(
					texto(v.sinMayusculas("sku")) ?: texto(v.sinMayusculas("name")) ?: texto(v.sinMayusculas("url")) ?: "?",
					texto(v.sinMayusculas("name")) ?: texto(v.sinMayusculas("sku")) ?: "?", o?.precio, o?.disponible,
				)
			}
			conOfertas.firstOrNull { (v, os) -> casa(v, os, url, elegida) }?.let { (_, os) -> return deOferta(mejor(os), os).let { Evaluacion(it.precio, it.moneda, it.disponible, false, lista) } }
			mejor(propias)?.let { return Evaluacion(it.precio, it.moneda, it.disponible, false, lista) }
			val precios = lista.mapNotNull { it.precio }
			if (precios.isEmpty()) return Evaluacion(null, null, null, false, lista)
			val moneda = conOfertas.flatMap { it.second }.firstNotNullOfOrNull { it.moneda }
			val disponible = lista.any { it.disponible == true }.takeIf { it } ?: lista.firstNotNullOfOrNull { it.disponible }
			return Evaluacion(precios.min(), moneda, disponible, precios.toSet().size > 1, lista)
		}
		// Ofertas con direcciones distintas: son variantes
		val urls = propias.mapNotNull { it.url }.toSet()
		if (urls.size > 1) {
			val lista = propias.filter { it.precio != null }.map { VarianteEncontrada(it.sku ?: it.nombre ?: it.url ?: "?", it.nombre ?: it.sku ?: it.url ?: "?", it.precio, it.disponible) }
			val elegidaO = propias.firstOrNull { o -> if (elegida != null) elegida == o.sku || elegida == o.nombre || elegida == o.url else mismaUrl(o.url, url) }
			if (elegidaO != null) return Evaluacion(elegidaO.precio, elegidaO.moneda, elegidaO.disponible, false, lista)
			val precios = lista.mapNotNull { it.precio }
			val m = mejor(propias)
			return Evaluacion(m?.precio, m?.moneda, m?.disponible ?: propias.firstNotNullOfOrNull { it.disponible }, precios.toSet().size > 1, lista)
		}
		return deOferta(mejor(propias), propias)
	}

	private fun imagen(c: ContextoExtraccion, valor: Any?): String? = when (valor) {
		is String -> Html.absoluta(c, valor)
		is List<*> -> valor.firstNotNullOfOrNull { imagen(c, it) }
		is Map<*, *> -> Html.absoluta(c, ((valor["url"] ?: valor["contentUrl"]) as? String))
		else -> null
	}

	override fun extraer(c: ContextoExtraccion): Parcial? {
		val productos = mutableListOf<Map<String, Any?>>()
		val categoria = BooleanArray(1)
		for (script in c.documento.select("script[type~=(?i)application/ld\\+json]")) {
			val texto = script.data().trim()
			if (texto.isEmpty()) continue
			val datos = leerJson(texto)
			if (datos == null) {
				// Un JSON-LD mal formado se ignora: no rompe la extracción
				c.registro("JSON-LD mal formado en ${c.url}", null)
				continue
			}
			buscar(datos, productos, false, categoria)
		}
		if (productos.isEmpty()) return if (categoria[0]) Parcial(origen, categoria = true) else null
		var elegido: Map<String, Any?>? = null
		var ev: Evaluacion? = null
		for (p in productos) {
			val e = evaluar(p, c.url, c.selectores.variante)
			if (e.precio != null) {
				elegido = p
				ev = e
				break
			}
		}
		val producto = elegido ?: productos.first()
		val evaluacion = ev ?: evaluar(producto, c.url, c.selectores.variante)
		// El nombre, del ProductGroup antes que de la variante; con las entidades HTML decodificadas
		val nombre = Html.normalizar((producto.sinMayusculas("name") as? String)?.let { Parser.unescapeEntities(it, false) })
		return Parcial(
			origen,
			precio = evaluacion.precio,
			moneda = evaluacion.moneda,
			nombre = nombre,
			imagen = imagen(c, producto.sinMayusculas("image")),
			disponible = evaluacion.disponible,
			desde = evaluacion.desde,
			variantes = evaluacion.variantes,
		)
	}
}

/** 5. Metadatos (nunca product:pretax_price:amount; los de 0 y los tachados se saltan), og:title, og:image y disponibilidad. */
object EstrategiaMetadatos : Estrategia {
	override val origen = OrigenPrecio.METADATOS

	private val DISPONIBLE = setOf("instock", "in stock", "available for order", "preorder")
	private val AGOTADO = setOf("oos", "out of stock")

	override fun extraer(c: ContextoExtraccion): Parcial? {
		val candidatos = Html.metas(c, "product:price:amount") + Html.metas(c, "og:price:amount") +
			Html.metas(c, "price", "itemprop").filter { !ExtractorGenerico.tachado(it) }
		var precio: Double? = null
		var textoPrecio: String? = null
		for (m in candidatos) {
			val t = m.attr("content")
			val v = importeDeMaquina(t)
			if (v != null) {
				precio = v
				textoPrecio = t
				break
			}
		}
		val moneda = (Html.meta(c, "product:price:currency") + Html.meta(c, "og:price:currency"))
			.map { it.trim().uppercase() }.firstOrNull { it.isNotEmpty() }
		val nombre = Html.meta(c, "og:title").firstNotNullOfOrNull { Html.normalizar(it) }
		val imagen = Html.meta(c, "og:image").firstNotNullOfOrNull { Html.absoluta(c, it) }
		val disponible = (Html.meta(c, "product:availability") + Html.meta(c, "og:availability")).firstNotNullOfOrNull { valor ->
			val v = valor.trim().lowercase()
			val final = v.substringAfterLast('/')
			when {
				v in DISPONIBLE || final == "instock" -> true
				v in AGOTADO || final == "outofstock" -> false
				else -> null
			}
		}
		if (precio == null && moneda == null && nombre == null && imagen == null && disponible == null) return null
		return Parcial(origen, precio = precio, textoPrecio = textoPrecio, moneda = moneda, nombre = nombre, imagen = imagen, disponible = disponible)
	}
}

/** 6. Microdatos: el primer itemprop="price" (su content o su texto) y la disponibilidad por itemprop="availability". */
object EstrategiaMicrodatos : Estrategia {
	override val origen = OrigenPrecio.MICRODATOS
	override fun extraer(c: ContextoExtraccion): Parcial? {
		val disponible = c.documento.select("[itemprop=availability]").firstNotNullOfOrNull { e ->
			Html.disponibilidadSchema(e.attr("href").ifEmpty { e.attr("content") }.ifEmpty { e.text() })
		}
		val e: Element? = c.documento.selectFirst("[itemprop=price]")
		var valor: Double? = null
		var texto: String? = null
		if (e != null) {
			if (e.hasAttr("content")) {
				texto = e.attr("content")
				valor = importeDeMaquina(texto)
			} else {
				texto = Extractor.textoImporte(e)
				valor = analizarImporte(texto)
			}
		}
		if (valor == null && disponible == null) return null
		return Parcial(origen, precio = valor, textoPrecio = texto, disponible = disponible)
	}
}

/** 7 a 12. Plataforma, estado incrustado, analítica y heurística visible (ExtractorGenerico). */
object EstrategiaGenerica : Estrategia {
	override val origen = OrigenPrecio.ANALISIS
	override fun extraer(c: ContextoExtraccion): Parcial {
		val d = ExtractorGenerico.extraer(c.html, c.documento, c.url, c.registro)
		val origenReal = if (d.origen?.startsWith(OrigenPrecio.PLATAFORMA.texto) == true) OrigenPrecio.PLATAFORMA else OrigenPrecio.ANALISIS
		val texto = d.candidatos.firstOrNull { it.valor == d.precio }?.texto
		return Parcial(
			origenReal, precio = d.precio, textoPrecio = texto, origenTexto = d.origen, confianza = d.confianza ?: Confianza.MEDIA,
			desde = d.desde, variantes = d.variantes, candidatos = d.candidatos,
		)
	}
}

/** Último recurso para el nombre: el título de la página sin el sufijo de la tienda. */
object EstrategiaTituloPagina : Estrategia {
	override val origen = OrigenPrecio.TITULO_PAGINA

	private val SEPARADORES = listOf(" | ", " - ", " – ", " — ")

	/** Para comparar «Informática Ejemplo» con «Informatica.ejemplo»: sin tildes, sin signos y en minúsculas. */
	private fun comparable(texto: String): String =
		Normalizer.normalize(texto, Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "").lowercase().filter { it.isLetterOrDigit() }

	/** Quita « | Tienda» o « - Tienda» si el sufijo es la tienda (por su nombre o por su dominio, sin tildes ni signos). */
	fun sinSufijo(titulo: String, tiendas: Collection<String>): String {
		val objetivos = tiendas.map { comparable(it) }.filter { it.isNotEmpty() }.toSet()
		if (objetivos.isEmpty()) return titulo
		for (s in SEPARADORES) {
			val i = titulo.lastIndexOf(s)
			if (i > 0 && comparable(titulo.substring(i + s.length)) in objetivos) return titulo.substring(0, i).trim()
		}
		return titulo
	}

	fun sinSufijo(titulo: String, tienda: String): String = sinSufijo(titulo, listOf(tienda))

	override fun extraer(c: ContextoExtraccion): Parcial? {
		val titulo = Html.normalizar(c.documento.title()) ?: return null
		val partes = c.dominio.split('.').filter { it.isNotEmpty() }
		val candidatos = mutableSetOf(c.nombreTienda, c.dominio)
		c.reglas?.nombre?.let { candidatos += it }
		if (partes.size > 1) {
			candidatos += partes.dropLast(1).joinToString(".")
			candidatos += partes.dropLast(1)
		}
		return Parcial(origen, nombre = sinSufijo(titulo, candidatos))
	}
}

/**
 * Extracción del precio, el nombre, la moneda, la imagen y la disponibilidad
 * de una página de producto, en el orden de ESPECIFICACION.md («Extracción
 * del precio» y «Extracción ampliada»). Lógica pura (Jsoup y org.json),
 * probada en la JVM con compartido/pruebas.
 */
object Extractor {

	/** Las estrategias en el orden en que se prueba el precio: se usa el primer precio válido. */
	val estrategias: List<Estrategia> = listOf(
		EstrategiaSelectorProducto,
		EstrategiaSelectorTienda,
		EstrategiaReglasTienda,
		EstrategiaJsonLd,
		EstrategiaMetadatos,
		EstrategiaMicrodatos,
		EstrategiaGenerica,
		EstrategiaTituloPagina,
	)

	/** Orden de la disponibilidad: lo del usuario, JSON-LD, metadatos, microdatos y la regla de la tienda. */
	private val ORDEN_DISPONIBLE = listOf(
		OrigenPrecio.SELECTOR_TIENDA, OrigenPrecio.JSON_LD, OrigenPrecio.METADATOS, OrigenPrecio.MICRODATOS, OrigenPrecio.REGLA_TIENDA,
	)

	private val RE_TITULO_NO_PRODUCTO =
		regexUnicode("^\\s*(buscador|b[uú]squeda|resultados?\\b|search\\b|buscar\\b|p[aá]gina no encontrada|404\\b|not found\\b)", true)

	private val RE_PARTIDO = Regex("(\\d)\\s*([.,])\\s*(\\d{2})(?!\\d)")

	/** Texto de un elemento para leer un importe: sus partes unidas sin separador y los precios partidos juntados («74 , 99 €» → «74,99 €»). */
	fun textoImporte(e: Element): String {
		val t = e.wholeText().replace(Regex("[\\s\\u00A0\\u202F]+"), " ").trim()
		return RE_PARTIDO.replace(t) { m -> m.groupValues[1] + m.groupValues[2] + m.groupValues[3] }
	}

	fun analizar(html: String, url: String): Document = Jsoup.parse(html, url)

	/**
	 * Extrae los datos de una página. codigoHttp sirve para las reglas de
	 * bloqueo (202 sin precio, 400 con texto de bloqueo). registro recibe los
	 * avisos de depuración (JSON-LD mal formado, selector no válido).
	 */
	fun extraer(
		html: String,
		url: String,
		reglas: ReglasTiendas,
		selectores: SelectoresUsuario = SelectoresUsuario(),
		nombreTienda: String? = null,
		codigoHttp: Int = 200,
		registro: (String, Throwable?) -> Unit = { _, _ -> },
	): ResultadoExtraccion {
		val dominio = dominioDe(url)
		val regla = reglas.para(dominio)
		val documento = analizar(html, url)
		val contexto = ContextoExtraccion(
			documento = documento,
			html = html,
			url = url,
			dominio = dominio,
			reglas = regla,
			selectores = selectores,
			nombreTienda = nombreTienda ?: regla?.nombre ?: nombreTiendaPorDominio(dominio),
			registro = registro,
		)
		val parciales = mutableListOf<Parcial>()
		for (e in estrategias) {
			// El extractor genérico solo hace falta si nadie ha dado precio (y no es una categoría)
			if (e === EstrategiaGenerica && (parciales.any { it.precio != null } || parciales.any { it.categoria })) continue
			try {
				e.extraer(contexto)?.let { parciales += it }
			} catch (ex: RuntimeException) {
				// Una estrategia que falla no impide las demás
				registro("La estrategia ${e.origen.texto} falló en $url", ex)
			}
		}
		// La tienda redirige al buscador o a «página no encontrada» (fichas retiradas): nunca un precio de otro artículo
		if (RE_TITULO_NO_PRODUCTO.containsMatchIn(documento.title())) {
			return ResultadoExtraccion(
				precio = null, moneda = "EUR", nombre = null, imagen = null, disponible = null, bloqueo = false,
				error = MensajesError.CATEGORIA, origen = null, parciales = parciales, documento = documento,
			)
		}
		var conPrecio = parciales.firstOrNull { it.precio != null }
		var errorSelector = false
		// Selector elegido por el usuario con huella: si se rompe, nunca se guarda un precio dudoso
		val huella = selectores.huellaImporte
		if (huella != null && !selectores.precioProducto.isNullOrBlank()) {
			val propio = parciales.firstOrNull { it.origen == OrigenPrecio.SELECTOR_PRODUCTO }?.precio
			if (propio == null || abs(propio - huella) / huella > 0.7) {
				val auto = parciales.firstOrNull { it.origen != OrigenPrecio.SELECTOR_PRODUCTO && it.precio != null }
				if (auto?.precio == null || auto.precio != huella) errorSelector = true
				conPrecio = if (errorSelector) null else auto
			}
		}
		var precio = conPrecio?.precio
		var desde = conPrecio?.desde ?: false
		val variantes = conPrecio?.variantes?.ifEmpty { null } ?: parciales.firstNotNullOfOrNull { it.variantes.ifEmpty { null } }.orEmpty()
		// Variante elegida por el usuario
		val elegida = selectores.variante
		if (elegida != null && desde) {
			variantes.firstOrNull { it.clave == elegida || it.nombre == elegida }?.precio?.let {
				precio = it
				desde = false
			}
		}
		val nombre = parciales.firstNotNullOfOrNull { it.nombre }
		val imagen = parciales.firstNotNullOfOrNull { it.imagen }
		val moneda = parciales.firstNotNullOfOrNull { it.moneda } ?: monedaPorSimbolo(conPrecio?.textoPrecio) ?: "EUR"
		var disponible = ORDEN_DISPONIBLE.firstNotNullOfOrNull { origen -> parciales.firstOrNull { it.origen == origen }?.disponible }
		if (disponible == null && precio != null) disponible = true
		val candidatos = parciales.firstOrNull { it.origen == OrigenPrecio.ANALISIS || it.origen == OrigenPrecio.PLATAFORMA }?.candidatos.orEmpty()

		var bloqueo = false
		var error: String? = null
		if (precio == null) {
			if (disponible == null || codigoHttp == 202) {
				// Solo sin precio ni disponibilidad: así un «Access Denied» en una página normal no da un falso bloqueo
				val textos = (regla?.bloqueo.orEmpty() + reglas.bloqueoGeneral).filter { it.isNotBlank() }
				val hayTexto = textos.any { html.contains(it, ignoreCase = true) }
				bloqueo = codigoHttp == 202 || hayTexto
			}
			if (codigoHttp == 400) {
				bloqueo = regla?.bloqueo.orEmpty().any { it.isNotBlank() && html.contains(it, ignoreCase = true) }
				if (!bloqueo) error = MensajesError.codigo(400)
			}
			when {
				bloqueo -> {
					error = MensajesError.BLOQUEO
					disponible = null
				}
				error != null -> disponible = null
				errorSelector -> error = MensajesError.SELECTOR_ROTO
				parciales.any { it.categoria } -> error = MensajesError.CATEGORIA
				disponible != false -> error = if (candidatos.isNotEmpty()) MensajesError.NO_DECIDIDO else MensajesError.SIN_PRECIO
			}
		}
		return ResultadoExtraccion(
			precio = precio,
			moneda = moneda,
			nombre = nombre,
			imagen = imagen,
			disponible = disponible,
			bloqueo = bloqueo,
			error = error,
			origen = if (precio != null) conPrecio?.origen else null,
			parciales = parciales,
			confianza = if (precio != null) conPrecio?.confianza else null,
			desde = precio != null && desde,
			variantes = variantes,
			candidatos = candidatos,
			origenTexto = when {
				precio == null -> null
				// El selector del producto que eligió el usuario en «Elegir el precio en la página»
				conPrecio?.origen == OrigenPrecio.SELECTOR_PRODUCTO && huella != null -> OrigenPrecio.ELEGIDO.texto
				else -> conPrecio?.origenTexto ?: conPrecio?.origen?.texto
			},
			documento = documento,
		)
	}
}
