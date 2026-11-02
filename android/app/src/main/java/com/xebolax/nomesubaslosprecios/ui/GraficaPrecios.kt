package com.xebolax.nomesubaslosprecios.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.util.AttributeSet
import android.view.View
import com.google.android.material.color.MaterialColors
import com.xebolax.nomesubaslosprecios.nucleo.Fechas
import com.xebolax.nomesubaslosprecios.nucleo.PuntoHistorial
import com.xebolax.nomesubaslosprecios.nucleo.formatearImporte

/**
 * Gráfica de línea del precio en el tiempo. Es decorativa para el lector de
 * pantalla (importantForAccessibility = no): el resumen hablado y la lista
 * del historial ya dicen todo lo que muestra.
 */
class GraficaPrecios @JvmOverloads constructor(contexto: Context, atributos: AttributeSet? = null) : View(contexto, atributos) {

	private var puntos: List<Pair<Long, Double>> = emptyList()
	private var moneda = "EUR"
	private val densidad = resources.displayMetrics.density

	private val linea = Paint(Paint.ANTI_ALIAS_FLAG).apply {
		style = Paint.Style.STROKE
		strokeWidth = 3 * densidad
		strokeJoin = Paint.Join.ROUND
		color = MaterialColors.getColor(this@GraficaPrecios, com.google.android.material.R.attr.colorPrimary)
	}
	private val ejes = Paint(Paint.ANTI_ALIAS_FLAG).apply {
		style = Paint.Style.STROKE
		strokeWidth = densidad
		color = MaterialColors.getColor(this@GraficaPrecios, com.google.android.material.R.attr.colorOutline)
	}
	private val punto = Paint(Paint.ANTI_ALIAS_FLAG).apply {
		style = Paint.Style.FILL
		color = linea.color
	}
	private val texto = Paint(Paint.ANTI_ALIAS_FLAG).apply {
		textSize = 12 * resources.displayMetrics.scaledDensity
		color = MaterialColors.getColor(this@GraficaPrecios, com.google.android.material.R.attr.colorOnSurfaceVariant)
	}

	init {
		importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_NO
	}

	fun mostrar(historial: List<PuntoHistorial>, moneda: String) {
		this.moneda = moneda
		puntos = historial.mapNotNull { h -> val ms = Fechas.ms(h.fecha); if (ms != null && h.precio != null) ms to h.precio else null }
		invalidate()
	}

	override fun onDraw(lienzo: Canvas) {
		super.onDraw(lienzo)
		if (puntos.isEmpty()) return
		val margenIzq = texto.measureText(formatearImporte(puntos.maxOf { it.second }, moneda)) + 8 * densidad
		val margen = 12 * densidad
		val ancho = width - margenIzq - margen
		val alto = height - 2 * margen
		if (ancho <= 0 || alto <= 0) return
		val min = puntos.minOf { it.second }
		val max = puntos.maxOf { it.second }
		val rango = (max - min).takeIf { it > 0 } ?: 1.0
		val t0 = puntos.first().first
		// Si solo hay un punto o todos son del mismo momento, la línea va hasta el borde derecho (hasta hoy)
		val t1 = maxOf(puntos.last().first, System.currentTimeMillis())
		val dt = (t1 - t0).takeIf { it > 0 } ?: 1L
		fun x(t: Long) = margenIzq + (t - t0).toFloat() / dt * ancho
		fun y(v: Double) = margen + alto - ((v - min) / rango * alto).toFloat()
		lienzo.drawLine(margenIzq, margen, margenIzq, margen + alto, ejes)
		lienzo.drawLine(margenIzq, margen + alto, margenIzq + ancho, margen + alto, ejes)
		lienzo.drawText(formatearImporte(max, moneda), 0f, margen + texto.textSize / 2, texto)
		lienzo.drawText(formatearImporte(min, moneda), 0f, margen + alto, texto)
		// Escalones: el precio se mantiene hasta el siguiente cambio
		val camino = Path()
		puntos.forEachIndexed { i, (t, v) ->
			if (i == 0) camino.moveTo(x(t), y(v))
			else {
				camino.lineTo(x(t), y(puntos[i - 1].second))
				camino.lineTo(x(t), y(v))
			}
		}
		camino.lineTo(x(t1), y(puntos.last().second))
		lienzo.drawPath(camino, linea)
		puntos.forEach { (t, v) -> lienzo.drawCircle(x(t), y(v), 4 * densidad, punto) }
	}
}
