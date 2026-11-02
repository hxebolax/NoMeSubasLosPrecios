package com.xebolax.nomesubaslosprecios.ui

import android.content.Context
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.nucleo.EstadoComprobacion
import com.xebolax.nomesubaslosprecios.nucleo.Fechas
import com.xebolax.nomesubaslosprecios.nucleo.Ofertas
import com.xebolax.nomesubaslosprecios.nucleo.Producto
import com.xebolax.nomesubaslosprecios.nucleo.ProductoConNombres
import com.xebolax.nomesubaslosprecios.nucleo.cambioPorcentaje
import com.xebolax.nomesubaslosprecios.nucleo.estadoComprobacion
import com.xebolax.nomesubaslosprecios.nucleo.formatearImporte
import com.xebolax.nomesubaslosprecios.nucleo.formatearPorcentaje
import kotlin.math.abs

/*
 * Textos que se leen en la lista y en los detalles. Cada fila lo dice todo
 * en una línea, con el estado primero (ESPECIFICACION.md, «Lista de productos»).
 */

fun Context.precioTexto(p: Producto): String = when {
	p.precioActual == null -> getString(R.string.sin_precio_leido)
	p.desde -> getString(R.string.desde, formatearImporte(p.precioActual, p.moneda))
	else -> formatearImporte(p.precioActual, p.moneda)
}

/** Estado de la última comprobación, siempre distinguible (bloqueada nunca se confunde con agotado). */
fun Context.textoComprobacion(p: Producto): String = when (estadoComprobacion(p)) {
	EstadoComprobacion.SIN_COMPROBAR -> getString(R.string.estado_sin_comprobar)
	EstadoComprobacion.CORRECTA -> getString(R.string.estado_correcta)
	EstadoComprobacion.SIN_PRECIO -> getString(R.string.estado_sin_precio)
	EstadoComprobacion.BLOQUEADA -> getString(R.string.estado_bloqueada)
	EstadoComprobacion.SIN_CONEXION -> getString(R.string.estado_sin_conexion)
	EstadoComprobacion.OTRO_ERROR -> getString(R.string.estado_error)
}

/** «En pausa», «Agotado», «Bloqueado por la tienda», «En oferta»...: lo que se dice antes del nombre. */
fun Context.estadosFila(p: Producto): List<String> {
	val estados = mutableListOf<String>()
	if (!p.activo) estados += getString(R.string.estado_en_pausa)
	when (estadoComprobacion(p)) {
		EstadoComprobacion.BLOQUEADA -> estados += getString(R.string.estado_bloqueada)
		EstadoComprobacion.SIN_PRECIO -> estados += getString(R.string.estado_sin_precio)
		EstadoComprobacion.SIN_CONEXION -> estados += getString(R.string.estado_sin_conexion)
		EstadoComprobacion.OTRO_ERROR -> estados += getString(R.string.estado_error)
		else -> Unit
	}
	if (!p.disponible) estados += getString(R.string.estado_agotado)
	else if (p.activo && Ofertas.esOferta(p)) estados += getString(R.string.estado_en_oferta)
	return estados
}

/** «bajó 10,00 € (7 %)», «subió 5,00 € (3 %)» o «sin cambios»; y «precio deseado alcanzado» si toca. */
fun Context.textoCambio(p: Producto): String {
	val actual = p.precioActual
	val anterior = p.precioAnterior
	val cambio = if (actual != null && anterior != null && anterior > 0 && actual != anterior) {
		val diferencia = formatearImporte(abs(actual - anterior), p.moneda)
		val pct = formatearPorcentaje(cambioPorcentaje(anterior, actual))
		if (actual < anterior) getString(R.string.cambio_bajo, diferencia, pct) else getString(R.string.cambio_subio, diferencia, pct)
	} else getString(R.string.cambio_sin_cambios)
	return if (Ofertas.objetivoAlcanzado(p)) cambio + ", " + getString(R.string.objetivo_alcanzado_corto) else cambio
}

/** La línea completa de una fila: «[estado,] nombre, precio, cambio, tienda, categoría[, extra]». */
fun Context.textoFila(pc: ProductoConNombres, extra: String? = null): String {
	val p = pc.producto
	val partes = estadosFila(p) + listOf(
		p.nombre.ifBlank { p.url },
		precioTexto(p),
		textoCambio(p),
		pc.tienda,
		pc.categoria ?: getString(R.string.sin_categoria),
	) + listOfNotNull(extra)
	return partes.joinToString(", ")
}

/** Primera línea visible de la fila: estado y nombre. */
fun Context.tituloFila(pc: ProductoConNombres): String =
	(estadosFila(pc.producto) + pc.producto.nombre.ifBlank { pc.producto.url }).joinToString(", ")

/** Segunda línea visible: precio, cambio, tienda y categoría. */
fun Context.detalleFila(pc: ProductoConNombres, extra: String? = null): String =
	(listOf(precioTexto(pc.producto), textoCambio(pc.producto), pc.tienda, pc.categoria ?: getString(R.string.sin_categoria)) + listOfNotNull(extra))
		.joinToString(", ")

/**
 * Resumen hablado de los detalles: «Ahora 129,99 €. Mínimo 119,00 € el 3 de
 * octubre. Máximo 149,00 €. Está un 9,2 % por encima del mínimo.»
 */
fun Context.resumenHablado(p: Producto): String {
	val actual = p.precioActual ?: return getString(R.string.resumen_sin_precio)
	val partes = mutableListOf(getString(R.string.resumen_ahora, formatearImporte(actual, p.moneda)))
	if (!p.disponible) partes += getString(R.string.resumen_agotado)
	p.precioMinimo?.let { min ->
		val fecha = Fechas.diaHablado(p.fechaMinimo)
		partes += if (fecha.isNotEmpty()) getString(R.string.resumen_minimo_fecha, formatearImporte(min, p.moneda), fecha)
		else getString(R.string.resumen_minimo, formatearImporte(min, p.moneda))
	}
	p.precioMaximo?.let { partes += getString(R.string.resumen_maximo, formatearImporte(it, p.moneda)) }
	val min = p.precioMinimo
	if (min != null && min > 0) {
		partes += if (actual <= min) getString(R.string.resumen_en_minimo)
		else getString(R.string.resumen_sobre_minimo, formatearPorcentaje(cambioPorcentaje(min, actual)))
	}
	if (Ofertas.objetivoAlcanzado(p)) partes += getString(R.string.resumen_objetivo)
	return partes.joinToString(" ")
}
