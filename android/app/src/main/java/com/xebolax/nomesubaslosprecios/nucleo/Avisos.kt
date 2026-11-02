package com.xebolax.nomesubaslosprecios.nucleo

import kotlin.math.abs

/** Lo leído en una comprobación correcta (con precio, o agotado sin precio). */
data class Lectura(
	val precio: Double?,
	val disponible: Boolean,
	val nombre: String? = null,
	val imagen: String? = null,
	val moneda: String? = null,
	/** De dónde salió el precio y con qué confianza (se guardan en el producto). */
	val origen: String? = null,
	val confianza: String? = null,
	/** El precio es un «desde» (variantes sin elegir o rango). */
	val desde: Boolean = false,
)

/** Aviso que hay que guardar y notificar (sin id ni producto todavía). */
data class AvisoNuevo(val tipo: String, val titulo: String, val mensaje: String)

/** Resultado de aplicar una comprobación a un producto: el producto al día, la fila de historial (si hay) y los avisos. */
data class ResultadoComprobacion(
	val producto: Producto,
	val historial: PuntoHistorial?,
	val avisos: List<AvisoNuevo>,
	/** ¿Cambió el precio o la disponibilidad? */
	val cambio: Boolean,
)

/**
 * Lógica de la comprobación y de los avisos (ESPECIFICACION.md,
 * «Comprobación y avisos»). Pura: recibe el producto, lo leído y los
 * ajustes, y devuelve el producto al día, la fila de historial y los avisos
 * con los textos exactos de la especificación.
 */
object LogicaAvisos {

	const val TITULO_OBJETIVO = "¡Precio deseado alcanzado!"
	const val TITULO_MINIMO = "Mínimo histórico"
	const val TITULO_BAJADA = "Ha bajado de precio"
	const val TITULO_SUBIDA = "¡Te han subido el precio!"
	const val TITULO_DISPONIBLE = "Vuelve a estar disponible"
	const val TITULO_AGOTADO = "Agotado"
	const val TITULO_ERROR = "No se puede leer el precio"

	/** Errores seguidos que provocan el aviso de tipo error. */
	const val ERRORES_PARA_AVISAR = 3

	private const val MENOS = "−"

	fun textoObjetivo(nombre: String, p1: Double, tienda: String, objetivo: Double, moneda: String) =
		"$nombre: ${formatearImporte(p1, moneda)} en $tienda (querías ${formatearImporte(objetivo, moneda)} o menos)."

	fun textoMinimo(nombre: String, p1: Double, tienda: String, p0: Double, moneda: String) =
		"$nombre: ${formatearImporte(p1, moneda)} en $tienda, el precio más bajo visto (antes ${formatearImporte(p0, moneda)})."

	fun textoBajada(nombre: String, p0: Double, p1: Double, tienda: String, moneda: String) =
		"$nombre: de ${formatearImporte(p0, moneda)} a ${formatearImporte(p1, moneda)} en $tienda " +
			"($MENOS${formatearImporte(abs(p0 - p1), moneda)}, $MENOS${formatearPorcentaje(cambioPorcentaje(p0, p1))} %)."

	fun textoSubida(nombre: String, p0: Double, p1: Double, tienda: String, moneda: String) =
		"$nombre: de ${formatearImporte(p0, moneda)} a ${formatearImporte(p1, moneda)} en $tienda " +
			"(+${formatearImporte(abs(p1 - p0), moneda)}, +${formatearPorcentaje(cambioPorcentaje(p0, p1))} %)."

	fun textoDisponible(nombre: String, tienda: String, p1: Double?, moneda: String) =
		if (p1 != null) "$nombre vuelve a estar disponible en $tienda a ${formatearImporte(p1, moneda)}."
		else "$nombre vuelve a estar disponible en $tienda."

	fun textoAgotado(nombre: String, tienda: String) = "$nombre se ha agotado en $tienda."

	fun textoError(nombre: String, tienda: String, error: String) = "$nombre ($tienda): $error"

	/** Una comprobación que ha fallado: solo se tocan el error, el contador y la fecha. */
	fun aplicarError(p: Producto, mensaje: String, ajustes: AjustesAvisos, ahora: String, tienda: String): ResultadoComprobacion {
		val errores = p.erroresSeguidos + 1
		val nuevo = p.copy(ultimoError = mensaje, erroresSeguidos = errores, ultimaComprobacion = ahora)
		val avisos = if (ajustes.avisarErrores && errores == ERRORES_PARA_AVISAR)
			listOf(AvisoNuevo(TipoAviso.ERROR, TITULO_ERROR, textoError(nombreDe(nuevo), tienda, mensaje)))
		else emptyList()
		return ResultadoComprobacion(nuevo, null, avisos, cambio = false)
	}

	private fun nombreDe(p: Producto) = p.nombre.ifBlank { p.url }

	/** Una comprobación correcta: precios, historial y, como mucho, un aviso por producto. */
	fun aplicarLectura(p: Producto, lectura: Lectura, ajustes: AjustesAvisos, ahora: String, tienda: String): ResultadoComprobacion {
		var n = p.copy(ultimoError = "", erroresSeguidos = 0, ultimaComprobacion = ahora)
		if (n.nombre.isBlank() && !lectura.nombre.isNullOrBlank()) n = n.copy(nombre = lectura.nombre)
		if (!lectura.imagen.isNullOrBlank() && lectura.imagen != n.imagenUrl) n = n.copy(imagenUrl = lectura.imagen)
		if (!lectura.moneda.isNullOrBlank()) n = n.copy(moneda = lectura.moneda)
		if (lectura.precio != null) n = n.copy(origenPrecio = lectura.origen ?: n.origenPrecio, confianza = lectura.confianza ?: n.confianza, desde = lectura.desde)
		val moneda = n.moneda
		val nombre = nombreDe(n)

		val p0 = p.precioActual?.let { redondear(it) }
		val p1 = lectura.precio?.let { redondear(it) }
		val d0 = p.disponible
		val d1 = lectura.disponible
		val avisos = mutableListOf<AvisoNuevo>()
		var fila: PuntoHistorial? = null
		var cambio = false

		if (p0 == null && p1 != null) {
			// Primera lectura
			n = n.copy(
				precioActual = p1, disponible = d1,
				precioInicial = p1, precioMinimo = p1, fechaMinimo = ahora, precioMaximo = p1, fechaMaximo = ahora,
			)
			fila = PuntoHistorial(ahora, p1, d1)
			cambio = true
			val objetivo = n.precioObjetivo
			if (objetivo != null && p1 <= objetivo && ajustes.avisarObjetivo) {
				avisos += AvisoNuevo(TipoAviso.OBJETIVO, TITULO_OBJETIVO, textoObjetivo(nombre, p1, tienda, objetivo, moneda))
			}
			return ResultadoComprobacion(n, fila, avisos, cambio)
		}

		if (p0 == null) {
			// Sin precio nunca leído y agotado: se guarda la disponibilidad (fila en la primera comprobación o si cambia)
			n = n.copy(disponible = d1)
			if (p.ultimaComprobacion == null || d0 != d1) {
				fila = PuntoHistorial(ahora, null, d1)
				cambio = d0 != d1
			}
			return ResultadoComprobacion(n, fila, avisos, cambio)
		}

		// Desde aquí hay un precio anterior. Sin precio nuevo (agotado), se conserva el último conocido
		val precioNuevo = p1 ?: p0
		val cambioPrecio = p1 != null && p1 != p0
		val cambioDisponible = d1 != d0
		n = n.copy(disponible = d1, precioActual = precioNuevo)
		if (cambioPrecio || cambioDisponible) {
			fila = PuntoHistorial(ahora, precioNuevo, d1)
			cambio = true
		}

		var avisoPrecio: AvisoNuevo? = null
		if (cambioPrecio) {
			val nuevo = p1!!
			val minimoAnterior = p.precioMinimo ?: p0
			val maximoAnterior = p.precioMaximo ?: p0
			n = n.copy(precioAnterior = p0, fechaCambio = ahora)
			if (nuevo < minimoAnterior) n = n.copy(precioMinimo = nuevo, fechaMinimo = ahora)
			if (nuevo > maximoAnterior) n = n.copy(precioMaximo = nuevo, fechaMaximo = ahora)
			if (n.precioInicial == null) n = n.copy(precioInicial = p0)
			// Redondeado a millonésimas: que un 5 % justo no se quede en 4,9999999
			val porcentaje = Math.round(cambioPorcentaje(p0, nuevo) * 1_000_000.0) / 1_000_000.0
			if (abs(porcentaje) >= ajustes.cambioMinimoPorcentaje) {
				val objetivo = p.precioObjetivo
				avisoPrecio = when {
					objetivo != null && nuevo <= objetivo && p0 > objetivo && ajustes.avisarObjetivo ->
						AvisoNuevo(TipoAviso.OBJETIVO, TITULO_OBJETIVO, textoObjetivo(nombre, nuevo, tienda, objetivo, moneda))
					nuevo < minimoAnterior && ajustes.avisarMinimo ->
						AvisoNuevo(TipoAviso.MINIMO, TITULO_MINIMO, textoMinimo(nombre, nuevo, tienda, p0, moneda))
					nuevo < p0 && ajustes.avisarBajadas && (p.alertaPorcentaje <= 0.0 || -porcentaje >= p.alertaPorcentaje) ->
						AvisoNuevo(TipoAviso.BAJADA, TITULO_BAJADA, textoBajada(nombre, p0, nuevo, tienda, moneda))
					nuevo > p0 && ajustes.avisarSubidas ->
						AvisoNuevo(TipoAviso.SUBIDA, TITULO_SUBIDA, textoSubida(nombre, p0, nuevo, tienda, moneda))
					else -> null
				}
			}
		}

		var avisoDisponible: AvisoNuevo? = null
		if (cambioDisponible) {
			avisoDisponible = if (d1 && ajustes.avisarDisponible && p.avisarDisponible)
				AvisoNuevo(TipoAviso.DISPONIBLE, TITULO_DISPONIBLE, textoDisponible(nombre, tienda, precioNuevo, moneda))
			else if (!d1 && ajustes.avisarAgotado)
				AvisoNuevo(TipoAviso.AGOTADO, TITULO_AGOTADO, textoAgotado(nombre, tienda))
			else null
		}

		when {
			// Un solo aviso: el de disponibilidad va en el mismo mensaje que el del precio
			avisoPrecio != null && avisoDisponible != null ->
				avisos += avisoPrecio.copy(mensaje = avisoPrecio.mensaje + " " + avisoDisponible.mensaje)
			avisoPrecio != null -> avisos += avisoPrecio
			avisoDisponible != null -> avisos += avisoDisponible
		}
		return ResultadoComprobacion(n, fila, avisos, cambio)
	}

	/** Resumen cuando una comprobación da más de 3 avisos: «5 productos han cambiado de precio». */
	fun textoResumen(cantidad: Int) = if (cantidad == 1) "1 producto ha cambiado de precio" else "$cantidad productos han cambiado de precio"
}
