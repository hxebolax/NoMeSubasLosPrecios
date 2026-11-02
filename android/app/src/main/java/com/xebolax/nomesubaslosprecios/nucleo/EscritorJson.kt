package com.xebolax.nomesubaslosprecios.nucleo

import java.math.BigDecimal

/**
 * JSON con sangría de 2 espacios y las claves en el orden en que se meten
 * (LinkedHashMap), como pide FORMATO_INTERCAMBIO.md. org.json no garantiza
 * el orden de las claves, por eso se escribe a mano.
 */
object EscritorJson {

	fun escribir(valor: Any?): String = StringBuilder().also { escribir(valor, it, 0) }.append('\n').toString()

	private fun sangria(sb: StringBuilder, nivel: Int) {
		repeat(nivel * 2) { sb.append(' ') }
	}

	private fun escribir(valor: Any?, sb: StringBuilder, nivel: Int) {
		when (valor) {
			null -> sb.append("null")
			is String -> cadena(valor, sb)
			is Boolean -> sb.append(valor)
			is Int, is Long -> sb.append(valor.toString())
			is Double -> sb.append(numero(valor))
			is Float -> sb.append(numero(valor.toDouble()))
			is Map<*, *> -> {
				if (valor.isEmpty()) {
					sb.append("{}")
					return
				}
				sb.append("{\n")
				var primero = true
				for ((k, v) in valor) {
					if (!primero) sb.append(",\n")
					primero = false
					sangria(sb, nivel + 1)
					cadena(k.toString(), sb)
					sb.append(": ")
					escribir(v, sb, nivel + 1)
				}
				sb.append('\n')
				sangria(sb, nivel)
				sb.append('}')
			}
			is List<*> -> {
				if (valor.isEmpty()) {
					sb.append("[]")
					return
				}
				sb.append("[\n")
				valor.forEachIndexed { i, v ->
					if (i > 0) sb.append(",\n")
					sangria(sb, nivel + 1)
					escribir(v, sb, nivel + 1)
				}
				sb.append('\n')
				sangria(sb, nivel)
				sb.append(']')
			}
			else -> cadena(valor.toString(), sb)
		}
	}

	/** Número con punto decimal y sin notación científica («399.0», «349.9»). */
	fun numero(d: Double): String {
		if (d.isNaN() || d.isInfinite()) return "null"
		val texto = BigDecimal(d.toString()).stripTrailingZeros().toPlainString()
		return if (texto.contains('.')) texto else "$texto.0"
	}

	private fun cadena(s: String, sb: StringBuilder) {
		sb.append('"')
		for (c in s) {
			when (c) {
				'"' -> sb.append("\\\"")
				'\\' -> sb.append("\\\\")
				'\n' -> sb.append("\\n")
				'\r' -> sb.append("\\r")
				'\t' -> sb.append("\\t")
				'\b' -> sb.append("\\b")
				'\u000C' -> sb.append("\\f")
				else -> if (c < ' ' || c == ' ' || c == ' ') sb.append("\\u%04x".format(c.code)) else sb.append(c)
			}
		}
		sb.append('"')
	}
}
