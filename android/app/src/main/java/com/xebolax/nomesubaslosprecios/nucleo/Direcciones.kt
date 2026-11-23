package com.xebolax.nomesubaslosprecios.nucleo

/*
 * Limpieza de direcciones y dominio de la tienda (ESPECIFICACION.md,
 * «Direcciones»). Vectores comunes en compartido/pruebas/direcciones.json.
 */

/** Parámetros de seguimiento que se quitan (comparación exacta). */
private val PARAMETROS_SEGUIMIENTO = setOf(
	"gclid", "fbclid", "ref", "ref_", "tag", "psc", "smid", "spla", "th", "_encoding", "qid", "sr", "keywords",
	"crid", "sprefix", "dib", "dib_tag", "linkcode", "linkid", "srsltid", "suid",
)

/** Prefijos de parámetros de seguimiento. */
private val PREFIJOS_SEGUIMIENTO = listOf("utm_", "pd_rd_", "pf_rd_")

private val ESQUEMA = Regex("^[a-zA-Z][a-zA-Z0-9+.-]*://")

/** ASIN de Amazon en /dp/, /gp/product/ o /gp/aw/d/. */
private val ASIN = Regex("/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)", RegexOption.IGNORE_CASE)

private val URL_EN_TEXTO = Regex("https?://[^\\s<>\"']+", RegexOption.IGNORE_CASE)

private fun esSeguimiento(nombre: String): Boolean {
	val n = nombre.lowercase()
	return n in PARAMETROS_SEGUIMIENTO || PREFIJOS_SEGUIMIENTO.any { n.startsWith(it) }
}

/** Partes de una dirección sin interpretar la codificación (para no cambiar nada que no haga falta). */
private data class Partes(val esquema: String, val host: String, val resto: String, val consulta: String?)

private fun partir(url: String): Partes {
	val esquema = url.substringBefore("://")
	val tras = url.substringAfter("://")
	val finHost = tras.indexOfFirst { it == '/' || it == '?' }.let { if (it < 0) tras.length else it }
	val host = tras.substring(0, finHost)
	val despues = tras.substring(finHost)
	val consulta = if (despues.contains('?')) despues.substringAfter('?') else null
	val ruta = despues.substringBefore('?')
	return Partes(esquema, host, ruta, consulta)
}

/**
 * Dirección limpia que se guarda: sin espacios, con https:// si no tenía
 * esquema, sin parámetros de seguimiento ni fragmento, el host en minúsculas
 * y, en Amazon, reducida a https://www.amazon.<tld>/dp/<ASIN>.
 */
fun limpiarUrl(entrada: String): String {
	var url = entrada.trim()
	if (url.isEmpty()) return url
	if (!ESQUEMA.containsMatchIn(url)) url = "https://$url"
	url = url.substringBefore('#')
	val partes = partir(url)
	// El host en minúsculas (usuario y puerto, si los hay, se conservan tal cual salvo el caso)
	val host = partes.host.lowercase()
	val dominio = dominioDeHost(host)
	if (esAmazon(dominio)) {
		ASIN.find(partes.resto)?.let { return "https://www.$dominio/dp/${it.groupValues[1].uppercase()}" }
	}
	val consulta = partes.consulta
		?.split('&')
		?.filter { it.isNotEmpty() && !esSeguimiento(it.substringBefore('=')) }
		?.joinToString("&")
		.orEmpty()
	return "${partes.esquema.lowercase()}://$host${partes.resto}" + if (consulta.isNotEmpty()) "?$consulta" else ""
}

private fun dominioDeHost(host: String): String {
	var h = host.substringAfterLast('@').substringBefore(':').lowercase().trimEnd('.')
	if (h.startsWith("www.")) h = h.removePrefix("www.")
	else if (h.startsWith("m.")) h = h.removePrefix("m.")
	return h
}

/** Dominio de la tienda: el host en minúsculas sin «www.» ni «m.» («amazon.es»). */
fun dominioDe(url: String): String {
	var u = url.trim()
	if (!ESQUEMA.containsMatchIn(u)) u = "https://$u"
	return dominioDeHost(partir(u.substringBefore('#')).host)
}

/** ¿Es un dominio de Amazon (amazon.es, amazon.co.uk, amazon.com.mx...)? */
fun esAmazon(dominio: String): Boolean = Regex("^amazon\\.[a-z.]+$").matches(dominio)

/** Sufijos públicos de dos niveles que reconoce la especificación común. */
val SUFIJOS_DOBLES = setOf(
	"co.uk", "org.uk", "com.mx", "com.ar", "com.br", "com.au", "co.jp", "com.es", "nom.es", "org.es", "com.pt", "com.tr", "co.nz", "co.za",
)

/**
 * Nombre de una tienda que no está en tiendas.json: la etiqueta que va justo
 * antes del sufijo público, con la primera letra en mayúscula
 * («tiendaejemplo.es» → «Tiendaejemplo»; «informatica.ejemplo.es» y
 * «tienda.ejemplo.co.uk» → «Ejemplo»).
 */
fun nombreTiendaPorDominio(dominio: String): String {
	val partes = dominio.lowercase().split('.').filter { it.isNotEmpty() }
	val base = when {
		partes.isEmpty() -> dominio
		partes.size < 2 -> partes[0]
		partes.size > 2 && partes.takeLast(2).joinToString(".") in SUFIJOS_DOBLES -> partes[partes.size - 3]
		else -> partes[partes.size - 2]
	}
	return base.replaceFirstChar { it.uppercase() }
}

/** La primera dirección web de un texto compartido («Mira esto: https://...»), o null. */
fun primeraUrl(texto: String?): String? {
	if (texto.isNullOrBlank()) return null
	return URL_EN_TEXTO.find(texto)?.value?.trimEnd('.', ',', ')', ';', '!', '?')
}

/** ¿Parece una dirección web que se pueda comprobar? */
fun pareceUrl(texto: String): Boolean {
	val limpia = limpiarUrl(texto)
	if (!limpia.startsWith("http://") && !limpia.startsWith("https://")) return false
	val dominio = dominioDe(limpia)
	return dominio.contains('.') && !dominio.contains(' ') && dominio.length >= 4
}
