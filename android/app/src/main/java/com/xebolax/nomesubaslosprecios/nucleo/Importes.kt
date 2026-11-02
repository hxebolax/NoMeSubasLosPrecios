package com.xebolax.nomesubaslosprecios.nucleo

import java.math.BigDecimal
import java.math.RoundingMode

/*
 * Lectura y escritura de importes. Lógica pura (sin Android) para probarla en
 * la JVM con los vectores comunes de compartido/pruebas/importes.json, los
 * mismos que usa la app de Windows (analizar_importe e importe_de_maquina).
 */

/** Dígitos con separadores: punto, coma o apóstrofo; o un espacio (normal, duro o fino) seguido de exactamente 3 dígitos. */
private val NUMERO = Regex("\\d+(?:[.,'’]\\d+|[ \\u00A0\\u202F]\\d{3}(?!\\d))*")

/** Formato de máquina: «1299.99», «12.5», «1299». */
private val MAQUINA = Regex("^\\d+(\\.\\d{1,2})?$")

/** Redondea a 2 decimales (mitad hacia arriba), como se guardan los importes. */
fun redondear(valor: Double): Double = BigDecimal(valor.toString()).setScale(2, RoundingMode.HALF_UP).toDouble()

/**
 * Saca el primer importe de un texto escrito por personas («1.299,99 €»,
 * «£1,049.00», «1 299,99 €», «PVP 2.499 €»). Devuelve null si no hay
 * importe o es cero o negativo. Reglas en ESPECIFICACION.md, «Importes de texto».
 */
fun analizarImporte(texto: String?): Double? {
	if (texto.isNullOrEmpty()) return null
	val coincidencia = NUMERO.find(texto)?.value ?: return null
	// Espacios y apóstrofos son siempre separadores de miles
	var numero = coincidencia.filter { it != ' ' && it != ' ' && it != ' ' && it != '\'' && it != '’' }
	val ultimoPunto = numero.lastIndexOf('.')
	val ultimaComa = numero.lastIndexOf(',')
	numero = when {
		ultimoPunto >= 0 && ultimaComa >= 0 -> {
			// El que aparece el último es el decimal
			if (ultimoPunto > ultimaComa) numero.replace(",", "")
			else numero.replace(".", "").replace(',', '.')
		}
		ultimoPunto >= 0 || ultimaComa >= 0 -> {
			val separador = if (ultimoPunto >= 0) '.' else ','
			val veces = numero.count { it == separador }
			val tras = numero.length - numero.lastIndexOf(separador) - 1
			if (veces > 1 || tras == 3) numero.replace(separador.toString(), "")
			else numero.replace(separador, '.')
		}
		else -> numero
	}
	val valor = numero.toBigDecimalOrNull() ?: return null
	val redondeado = valor.setScale(2, RoundingMode.HALF_UP)
	if (redondeado.signum() <= 0) return null
	return redondeado.toDouble()
}

/**
 * Importe que viene de un dato pensado para máquinas (texto del JSON-LD,
 * atributo content de un metadato, atributo pedido por una regla): «1299.99»
 * se lee con punto decimal; cualquier otra cosa, con analizarImporte.
 */
fun importeDeMaquina(texto: String?): Double? {
	val limpio = texto?.trim() ?: return null
	if (MAQUINA.matches(limpio)) {
		val valor = limpio.toBigDecimal().setScale(2, RoundingMode.HALF_UP)
		return if (valor.signum() > 0) valor.toDouble() else null
	}
	return analizarImporte(limpio)
}

/** Símbolo con el que se escribe cada moneda conocida; las demás, con su código. */
fun simboloMoneda(moneda: String?): String = when (moneda?.uppercase()) {
	null, "", "EUR" -> "€"
	"USD" -> "$"
	"GBP" -> "£"
	else -> moneda.uppercase()
}

/** «1.299,99» (sin moneda): miles con punto y dos decimales con coma. */
fun formatearNumero(valor: Double, decimales: Int = 2): String {
	val bd = BigDecimal(valor.toString()).abs().setScale(decimales, RoundingMode.HALF_UP)
	val texto = bd.toPlainString()
	val entero = texto.substringBefore('.')
	val fraccion = if (decimales > 0) texto.substringAfter('.', "") else ""
	val conMiles = StringBuilder()
	entero.reversed().forEachIndexed { i, c ->
		if (i > 0 && i % 3 == 0) conMiles.append('.')
		conMiles.append(c)
	}
	val signo = if (valor < 0 && bd.signum() != 0) "-" else ""
	return signo + conMiles.reverse().toString() + if (fraccion.isNotEmpty()) ",$fraccion" else ""
}

/** «1.299,99 €»: el formato español que el lector de pantalla lee bien (nunca «€1299.99»). */
fun formatearImporte(valor: Double?, moneda: String? = "EUR"): String {
	if (valor == null) return ""
	return formatearNumero(valor) + " " + simboloMoneda(moneda)
}

/** «7,5» o «10» (una decimal con coma; sin decimal si es entero). Sin el signo de por ciento. */
fun formatearPorcentaje(valor: Double): String {
	val bd = BigDecimal(valor.toString()).abs().setScale(1, RoundingMode.HALF_UP)
	val texto = if (bd.stripTrailingZeros().scale() <= 0) bd.setScale(0, RoundingMode.UNNECESSARY).toPlainString()
	else bd.toPlainString().replace('.', ',')
	return texto
}

/** Cambio en % de p0 a p1: (p1 − p0) / p0 × 100. */
fun cambioPorcentaje(p0: Double, p1: Double): Double = if (p0 == 0.0) 0.0 else (p1 - p0) / p0 * 100.0

/** Moneda por el símbolo de un texto (€ EUR, $ USD, £ GBP) o null si no hay ninguno. */
fun monedaPorSimbolo(texto: String?): String? {
	if (texto.isNullOrEmpty()) return null
	return when {
		texto.contains('€') || texto.contains("EUR", ignoreCase = false) -> "EUR"
		texto.contains('£') || texto.contains("GBP") -> "GBP"
		texto.contains('$') || texto.contains("USD") -> "USD"
		else -> null
	}
}
