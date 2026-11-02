package com.xebolax.nomesubaslosprecios.nucleo

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import org.json.JSONTokener
import java.math.BigDecimal
import java.math.RoundingMode

/*
 * Ayudantes de JSON para la extracción: se pasa todo a Map y List de Kotlin
 * (más cómodos de recorrer), se extraen objetos {...} de dentro de JavaScript
 * contando llaves y se leen números «de máquina». Lógica pura.
 */

/** JSONObject/JSONArray a LinkedHashMap/List (JSONObject.NULL pasa a null). */
fun aKotlin(v: Any?): Any? = when (v) {
	null, JSONObject.NULL -> null
	is JSONObject -> LinkedHashMap<String, Any?>().also { m -> for (k in v.keys()) m[k] = aKotlin(v.opt(k)) }
	is JSONArray -> (0 until v.length()).map { aKotlin(v.opt(it)) }
	else -> v
}

/** Lee un JSON (objeto, lista o valor). null si no es JSON válido. */
fun leerJson(texto: String?): Any? {
	val t = texto?.trim()?.removePrefix("﻿") ?: return null
	if (t.isEmpty()) return null
	return try {
		val tok = JSONTokener(t)
		val v = tok.nextValue()
		// Nada más que espacios detrás: si sobra algo, no era un único JSON
		if (tok.more() && tok.nextClean() != 0.toChar()) return null
		aKotlin(v)
	} catch (e: JSONException) {
		null
	} catch (e: RuntimeException) {
		null
	}
}

/** Como leerJson, pero para objetos literales sencillos de JavaScript (claves sin comillas, comillas simples, comas finales). */
fun cargarJsonFlexible(bloque: String): Any? {
	leerJson(bloque)?.let { return it }
	var t = Regex("(?<=[{,])\\s*([A-Za-z_$][\\w$]*)\\s*:").replace(bloque) { "\"${it.groupValues[1]}\":" }
	t = Regex("'([^'\\\\]*(?:\\\\.[^'\\\\]*)*)'").replace(t) { m ->
		"\"" + m.groupValues[1].replace("\\'", "'").replace("\"", "\\\"") + "\""
	}
	t = Regex(",\\s*([}\\]])").replace(t) { it.groupValues[1] }
	return leerJson(t)
}

/** El texto de {...} o [...] que empieza en texto[inicio], respetando las cadenas. null si no se cierra. */
fun objetoEquilibrado(texto: String, inicio: Int): String? {
	if (inicio !in texto.indices || (texto[inicio] != '{' && texto[inicio] != '[')) return null
	var pila = 0
	var enCadena: Char? = null
	var escape = false
	val fin = minOf(texto.length, inicio + 3_000_000)
	for (i in inicio until fin) {
		val c = texto[i]
		if (enCadena != null) {
			if (escape) escape = false
			else if (c == '\\') escape = true
			else if (c == enCadena) enCadena = null
			continue
		}
		when (c) {
			'"', '\'', '`' -> enCadena = c
			'{', '[' -> pila++
			'}', ']' -> {
				pila--
				if (pila < 0) return null
				if (pila == 0) return texto.substring(inicio, i + 1)
			}
		}
	}
	return null
}

/** Los objetos JSON que siguen a cada coincidencia del patrón (que acaba justo antes de «{» o «[»). */
fun jsonTras(texto: String, patron: Regex): List<Any> {
	val salida = mutableListOf<Any>()
	for (m in patron.findAll(texto)) {
		var j = m.range.last + 1
		while (j < texto.length && texto[j] in " \t\r\n") j++
		val bloque = objetoEquilibrado(texto, j) ?: continue
		cargarJsonFlexible(bloque)?.let { salida += it }
	}
	return salida
}

/** Cada mapa del árbol, con su ruta. */
fun recorrerJson(obj: Any?, ruta: List<String> = emptyList(), salida: MutableList<Pair<List<String>, Map<String, Any?>>> = mutableListOf()): List<Pair<List<String>, Map<String, Any?>>> {
	when (obj) {
		is Map<*, *> -> {
			@Suppress("UNCHECKED_CAST")
			salida += ruta to (obj as Map<String, Any?>)
			for ((k, v) in obj) recorrerJson(v, ruta + k.toString(), salida)
		}
		is List<*> -> obj.forEachIndexed { i, v -> recorrerJson(v, ruta + i.toString(), salida) }
	}
	return salida
}

/**
 * Número de un campo de máquina (JSON, data-price-amount, content): más
 * estricto que importeDeMaquina, «12.990» es 12,99. EXTRACTOR_GENERICO.md, 8.1.
 */
fun numeroDeMaquina(v: Any?): Double? {
	when (v) {
		null, is Boolean -> return null
		is Number -> {
			val d = v.toDouble()
			return if (d > 0 && !d.isNaN() && !d.isInfinite()) BigDecimal(d.toString()).setScale(2, RoundingMode.HALF_UP).toDouble().takeIf { it > 0 } else null
		}
	}
	val t = v.toString().trim()
	if (Regex("\\d+(?:\\.\\d+)?").matches(t)) {
		val f = BigDecimal(t).setScale(2, RoundingMode.HALF_UP)
		return if (f.signum() > 0) f.toDouble() else null
	}
	return importeDeMaquina(t)
}

/**
 * Expresión regular con \s, \w y \b de Unicode (como Python), igual en
 * Android y en la JVM: el motor ICU de Android ya es Unicode y NO acepta la
 * opción (?U) (lanza PatternSyntaxException); la JVM la necesita.
 */
private val enAndroid: Boolean = System.getProperty("java.vm.name").orEmpty().contains("Dalvik", ignoreCase = true) ||
	System.getProperty("java.vendor").orEmpty().contains("Android", ignoreCase = true)

fun regexUnicode(patron: String, sinMayusculas: Boolean = false): Regex {
	val p = if (enAndroid) patron else "(?U)$patron"
	return if (sinMayusculas) Regex(p, RegexOption.IGNORE_CASE) else Regex(p)
}

/** Valor de una clave sin distinguir mayúsculas («Price» o «price»). */
fun Map<String, Any?>.sinMayusculas(clave: String): Any? = this[clave] ?: entries.firstOrNull { it.key.equals(clave, ignoreCase = true) }?.value
