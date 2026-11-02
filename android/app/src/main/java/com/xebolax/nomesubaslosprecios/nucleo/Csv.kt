package com.xebolax.nomesubaslosprecios.nucleo

/** Producto con los nombres de su tienda y su categoría (para la lista y el CSV). */
data class ProductoConNombres(
	val producto: Producto,
	val tienda: String,
	val categoria: String?,
)

/**
 * Exportación a CSV para hojas de cálculo: separador «;», decimales con coma
 * y UTF-8 con BOM para que Excel lo abra bien. Solo productos; no se importa.
 */
object Csv {

	private val CABECERA = listOf(
		"Nombre", "Tienda", "Categoría", "Grupo", "Precio actual", "Moneda", "Disponible", "Precio inicial", "Precio mínimo",
		"Fecha del mínimo", "Precio máximo", "Precio anterior", "Precio deseado", "Alerta por bajada (%)", "Favorito", "Activo",
		"Última comprobación", "Último error", "Dirección", "Notas",
	)

	private fun celda(texto: String?): String {
		val t = texto.orEmpty()
		return if (t.any { it == ';' || it == '"' || it == '\n' || it == '\r' }) "\"" + t.replace("\"", "\"\"") + "\"" else t
	}

	private fun decimal(valor: Double?): String = valor?.let { formatearNumero(it).replace(".", "") }.orEmpty()

	private fun siNo(valor: Boolean) = if (valor) "Sí" else "No"

	fun escribir(productos: List<ProductoConNombres>): String {
		val sb = StringBuilder("﻿")
		sb.append(CABECERA.joinToString(";") { celda(it) }).append("\r\n")
		for (pc in productos) {
			val p = pc.producto
			val fila = listOf(
				p.nombre, pc.tienda, pc.categoria, p.grupo, decimal(p.precioActual), p.moneda, siNo(p.disponible), decimal(p.precioInicial),
				decimal(p.precioMinimo), p.fechaMinimo, decimal(p.precioMaximo), decimal(p.precioAnterior), decimal(p.precioObjetivo),
				formatearPorcentaje(p.alertaPorcentaje), siNo(p.favorito), siNo(p.activo), p.ultimaComprobacion, p.ultimoError, p.url, p.notas,
			)
			sb.append(fila.joinToString(";") { celda(it) }).append("\r\n")
		}
		return sb.toString()
	}
}
