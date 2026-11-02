package com.xebolax.nomesubaslosprecios.nucleo

import org.jsoup.nodes.Document
import org.jsoup.nodes.Element
import org.jsoup.select.Selector

/**
 * Selector CSS estable para el elemento que elige el usuario, y su validación
 * (EXTRACTOR_GENERICO.md, 7.2 y 7.3; traducido de selector_css.py).
 */
object SelectorCss {

	private val RE_GENERADO = Regex(
		"^(?:css|sc|jsx|emotion|e|tw|svelte|astro|chakra|mui|Mui[A-Za-z]*|makeStyles|styled|ng-tns|ember|v|data-v)-[A-Za-z0-9_-]*\\d[A-Za-z0-9_-]*$" +
			"|^[A-Za-z][\\w-]*_{1,2}(?=[A-Za-z0-9-]*\\d)[A-Za-z0-9-]{5,}$" +
			"|^_?(?=[a-zA-Z]*\\d)(?=\\d*[a-zA-Z])[a-zA-Z0-9]{5,8}$" +
			"|[:\\[\\]/!@]" +
			"|\\d{3,}",
	)
	private val RE_ESTADO = Regex(
		"^(?:is-|has-|js-is-|active|selected|current-?item|open|closed|hover|focus|visible|hidden|loaded|lazy|show|fade|in|d-|col-|row|flex|grid|mt-|mb-|ml-|mr-|pt-|pb-|p-|m-|text-|font-|bg-|w-|h-|swiper-slide|slick-)",
		RegexOption.IGNORE_CASE,
	)
	private val ATRIBUTOS_ESTABLES = listOf(
		"itemprop", "data-price-type", "data-test", "data-testid", "data-test-id", "data-qa", "data-cy", "data-role", "data-element",
		"data-hook", "data-automation", "data-ui", "name",
	)
	private val RE_TROZOS = Regex("[-_]+|(?<=[a-z])(?=[A-Z])")
	private val RE_CONSONANTES = Regex("[^aeiouy0-9]{5,}")

	fun palabraEstable(nombre: String?): Boolean {
		if (nombre == null || nombre.length < 3 || nombre.length > 60) return false
		if (RE_GENERADO.containsMatchIn(nombre) || RE_ESTADO.containsMatchIn(nombre)) return false
		return nombre.split(RE_TROZOS).none { it.isNotEmpty() && RE_CONSONANTES.containsMatchIn(it.lowercase()) }
	}

	private fun escapar(v: String) = v.replace("\\", "\\\\").replace("\"", "\\\"")

	private fun clasesEstables(e: Element) = e.classNames().filter { palabraEstable(it) }

	private fun idEstable(e: Element): String? = e.id().takeIf { it.isNotEmpty() && palabraEstable(it) && Regex("[A-Za-z][\\w-]*").matches(it) }

	private fun partesDe(e: Element): List<String> {
		val out = mutableListOf<String>()
		for (a in ATRIBUTOS_ESTABLES) {
			val v = e.attr(a)
			if (v.isNotEmpty() && v.length < 60 && palabraEstable(v.replace(" ", "-"))) out += "${e.tagName()}[$a=\"${escapar(v)}\"]"
		}
		idEstable(e)?.let { out += "#$it" }
		val cs = clasesEstables(e)
		cs.forEach { out += "${e.tagName()}.$it" }
		for (k in cs.indices) for (j in k + 1 until cs.size) out += "${e.tagName()}.${cs[k]}.${cs[j]}"
		return out
	}

	private fun seleccionar(doc: Element, sel: String): List<Element>? = try {
		doc.select(sel)
	} catch (e: Selector.SelectorParseException) {
		null
	} catch (e: IllegalArgumentException) {
		null
	}

	private fun unico(doc: Element, sel: String, e: Element): Boolean {
		val r = seleccionar(doc, sel) ?: return false
		return r.size == 1 && r[0] === e
	}

	private fun nthOfType(e: Element): String {
		val p = e.parent() ?: return e.tagName()
		val hermanos = p.children().filter { it.tagName() == e.tagName() }
		if (hermanos.size == 1) return e.tagName()
		return "${e.tagName()}:nth-of-type(${hermanos.indexOfFirst { it === e } + 1})"
	}

	/** Atributo del que se lee el valor (si lo hay): así el importe se lee como número de máquina. */
	fun atributoDeValor(e: Element): String? {
		if (e.attr("content").isNotEmpty() && importeDeMaquina(e.attr("content")) != null) return "content"
		return listOf("data-price-amount", "data-price", "data-product-price", "data-price-value").firstOrNull { e.attr(it).isNotEmpty() }
	}

	private fun esRaiz(e: Element?) = e == null || e is Document || e.tagName() == "html" || e.tagName() == "#root"

	/** Selector y atributo (o null) para el elemento, de más a menos preferido. */
	fun generar(e: Element, doc: Document): Pair<String, String?> {
		val atributo = atributoDeValor(e)
		val propias = partesDe(e)
		propias.firstOrNull { unico(doc, it, e) }?.let { return it to atributo }
		var p = e.parent()
		var nivel = 0
		while (!esRaiz(p) && nivel < 8) {
			for (pa in partesDe(p!!).take(6)) for (s in propias + e.tagName()) {
				val sel = "$pa $s"
				if (unico(doc, sel, e)) return sel to atributo
			}
			p = p.parent()
			nivel++
		}
		p = e.parent()
		val tramo = mutableListOf(nthOfType(e))
		nivel = 0
		while (!esRaiz(p) && p!!.tagName() != "body" && nivel < 5) {
			for (pa in partesDe(p).take(6)) {
				val sel = pa + " > " + tramo.joinToString(" > ")
				if (unico(doc, sel, e)) return sel to atributo
			}
			tramo.add(0, nthOfType(p))
			p = p.parent()
			nivel++
		}
		for (s in propias) {
			val r = seleccionar(doc, s) ?: continue
			if (r.isNotEmpty() && r[0] === e) return s to atributo
		}
		val ruta = mutableListOf<String>()
		var q: Element? = e
		while (q != null && !esRaiz(q) && q.tagName() != "body") {
			val i = idEstable(q)
			if (i != null && q !== e) {
				ruta += "#$i"
				break
			}
			ruta += nthOfType(q)
			q = q.parent()
		}
		var sel = ruta.reversed().joinToString(" > ")
		if (!sel.startsWith("#")) sel = "body > $sel"
		return sel to atributo
	}

	/** Importe de un elemento: el atributo (número de máquina) o el texto (con los precios partidos unidos). */
	fun importeDe(e: Element, atributo: String?): Double? =
		if (atributo != null) importeDeMaquina(e.attr(atributo)) else analizarImporte(Extractor.textoImporte(e))

	/** Válido si devuelve un único elemento y su importe es el esperado. */
	fun validar(doc: Element, selector: String, atributo: String?, esperado: Double): Boolean {
		val r = seleccionar(doc, selector) ?: return false
		if (r.size != 1) return false
		return importeDe(r[0], atributo) == esperado
	}
}
