package com.xebolax.nomesubaslosprecios.nucleo

import java.text.ParseException
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Fechas en texto ISO 8601 en UTC con «Z» (2026-11-02T20:15:00Z), como las
 * guardan las dos apps. Sin java.time para no necesitar desugaring con minSdk 24.
 */
object Fechas {

	private val UTC: TimeZone = TimeZone.getTimeZone("UTC")
	private val MESES = listOf(
		"enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
	)

	private fun formato(patron: String) = SimpleDateFormat(patron, Locale.ROOT).apply { timeZone = UTC; isLenient = false }

	fun iso(ms: Long): String = formato("yyyy-MM-dd'T'HH:mm:ss'Z'").format(Date(ms))

	fun ahora(): String = iso(System.currentTimeMillis())

	/** Milisegundos de una fecha ISO (también con fracción de segundo o con desfase), o null si no se entiende. */
	fun ms(texto: String?): Long? {
		val t = texto?.trim()?.ifEmpty { null } ?: return null
		val patrones = listOf("yyyy-MM-dd'T'HH:mm:ss'Z'", "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", "yyyy-MM-dd'T'HH:mm:ssXXX", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", "yyyy-MM-dd")
		for (p in patrones) {
			try {
				return formato(p).parse(t)?.time
			} catch (e: ParseException) {
				// Se prueba el siguiente formato
				continue
			}
		}
		return null
	}

	/** «3 de octubre» (con el año si no es el actual), en la hora local. */
	fun diaHablado(texto: String?, zona: TimeZone = TimeZone.getDefault()): String {
		val ms = ms(texto) ?: return ""
		val c = Calendar.getInstance(zona).apply { timeInMillis = ms }
		val hoy = Calendar.getInstance(zona)
		val base = "${c.get(Calendar.DAY_OF_MONTH)} de ${MESES[c.get(Calendar.MONTH)]}"
		return if (c.get(Calendar.YEAR) == hoy.get(Calendar.YEAR)) base else "$base de ${c.get(Calendar.YEAR)}"
	}

	/** «3 de octubre a las 14:05», en la hora local. */
	fun fechaHora(texto: String?, zona: TimeZone = TimeZone.getDefault()): String {
		val ms = ms(texto) ?: return ""
		val c = Calendar.getInstance(zona).apply { timeInMillis = ms }
		return diaHablado(texto, zona) + " a las %02d:%02d".format(c.get(Calendar.HOUR_OF_DAY), c.get(Calendar.MINUTE))
	}

	/** AAAA-MM-DD de hoy en la hora local (para el nombre del archivo exportado). */
	fun hoyParaArchivo(): String = SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(Date())
}
