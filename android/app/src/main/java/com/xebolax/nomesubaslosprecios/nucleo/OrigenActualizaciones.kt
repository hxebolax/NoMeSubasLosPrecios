package com.xebolax.nomesubaslosprecios.nucleo

/*
 * Origen de las actualizaciones (1.2.0, ESPECIFICACION.md, «Actualizaciones»):
 * de qué version.json se lee la versión publicada. Lógica pura, probada en la
 * JVM. El APK se descarga siempre de la misma carpeta que su version.json, y su
 * tamaño, SHA-256 y firma se comprueban igual venga de donde venga.
 */
object OrigenActualizaciones {

	const val SERVIDOR = "servidor"
	const val GITHUB = "github"
	const val AMBOS = "ambos"
	const val PERSONALIZADA = "personalizada"

	/** Valores admitidos de origen_actualizaciones, en el orden de la pantalla. */
	val VALORES = listOf(SERVIDOR, GITHUB, AMBOS, PERSONALIZADA)

	/** version.json de Android en la última release de GitHub (la redirección a GitHub es https → https). */
	const val MANIFIESTO_GITHUB = "https://github.com/hxebolax/NoMeSubasLosPrecios/releases/latest/download/version.json"

	private val RE_LOCAL = Regex("^http://(localhost|127\\.0\\.0\\.1)(:\\d+)?(/.*)?$", RegexOption.IGNORE_CASE)
	private val RE_HTTPS = Regex("^https://[^/\\s]+(/.*)?$", RegexOption.IGNORE_CASE)

	/** Un origen desconocido se lee como el servidor del autor. */
	fun origen(valor: String?): String = valor?.trim()?.lowercase()?.takeIf { it in VALORES } ?: SERVIDOR

	/**
	 * Carpeta de una dirección personalizada, terminada en «/»: se quitan los
	 * espacios y un final «/windows/version.json» o «/version.json». Solo https://
	 * (y http://localhost o http://127.0.0.1, para pruebas). Si no vale, "".
	 */
	fun basePersonalizada(texto: String?): String {
		var t = texto?.trim().orEmpty()
		if (t.isEmpty()) return ""
		if (!RE_HTTPS.matches(t) && !RE_LOCAL.matches(t)) return ""
		for (final in listOf("/windows/version.json", "/version.json")) {
			if (t.endsWith(final, ignoreCase = true)) {
				t = t.dropLast(final.length)
				break
			}
		}
		if (!t.endsWith("/")) t += "/"
		// Tras quitar el final tiene que seguir habiendo un servidor
		return if (RE_HTTPS.matches(t) || RE_LOCAL.matches(t)) t else ""
	}

	/**
	 * version.json que se consultan, en orden de preferencia (con empate de
	 * versión gana el primero). servidor es el del autor («.../version.json»).
	 * Una dirección personalizada no válida se cambia por el servidor del autor.
	 */
	fun manifiestos(origen: String?, url: String?, servidor: String): List<String> = when (origen(origen)) {
		GITHUB -> listOf(MANIFIESTO_GITHUB)
		AMBOS -> listOf(servidor, MANIFIESTO_GITHUB)
		PERSONALIZADA -> basePersonalizada(url).let { base -> if (base.isEmpty()) listOf(servidor) else listOf(base + "version.json") }
		else -> listOf(servidor)
	}

	/** Carpeta de un version.json (con «/» al final): de ahí se descarga el APK. */
	fun carpeta(manifiesto: String): String = manifiesto.substringBefore('?').substringBeforeLast('/') + "/"
}
