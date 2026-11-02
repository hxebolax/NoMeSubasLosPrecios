package com.xebolax.nomesubaslosprecios.nucleo

/** Cálculos de ofertas y orden de la lista (lógica pura). */
object Ofertas {

	private const val SIETE_DIAS_MS = 7L * 24 * 60 * 60 * 1000

	/** % que bajó respecto al precio anterior (positivo si bajó; 0 si no bajó o no se sabe). */
	fun porcentajeBajada(p: Producto): Double {
		val actual = p.precioActual ?: return 0.0
		val anterior = p.precioAnterior ?: return 0.0
		if (anterior <= 0.0 || actual >= anterior) return 0.0
		return (anterior - actual) / anterior * 100.0
	}

	/** ¿Precio en el deseado o por debajo? */
	fun objetivoAlcanzado(p: Producto): Boolean {
		val actual = p.precioActual ?: return false
		val objetivo = p.precioObjetivo ?: return false
		return actual <= objetivo
	}

	/** ¿En su mínimo histórico, habiendo estado antes más caro? */
	fun enMinimo(p: Producto): Boolean {
		val actual = p.precioActual ?: return false
		val minimo = p.precioMinimo ?: return false
		val maximo = p.precioMaximo ?: return false
		return actual <= minimo && maximo > minimo
	}

	/**
	 * Sección Ofertas: por debajo del anterior en los últimos 7 días, en su
	 * mínimo histórico o en el precio deseado o por debajo.
	 */
	fun esOferta(p: Producto, ahoraMs: Long = System.currentTimeMillis()): Boolean {
		if (p.precioActual == null || !p.disponible) return false
		val bajoReciente = porcentajeBajada(p) > 0.0 && (Fechas.ms(p.fechaCambio)?.let { ahoraMs - it <= SIETE_DIAS_MS } ?: false)
		return bajoReciente || enMinimo(p) || objetivoAlcanzado(p)
	}
}
