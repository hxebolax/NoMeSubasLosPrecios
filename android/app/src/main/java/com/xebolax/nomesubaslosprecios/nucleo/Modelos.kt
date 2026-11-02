package com.xebolax.nomesubaslosprecios.nucleo

/*
 * Modelo de datos común con la app de Windows (ESPECIFICACION.md, «Modelo de
 * datos»). Las columnas de SQLite tienen los mismos nombres; aquí van en
 * camelCase. Las fechas son texto ISO 8601 en UTC con «Z».
 */

data class Categoria(
	val id: Long = 0,
	val uuid: String,
	val nombre: String,
	val descripcion: String? = null,
	val orden: Int = 0,
)

data class Tienda(
	val id: Long = 0,
	val uuid: String,
	val nombre: String,
	val dominio: String,
	val selectorPrecio: String? = null,
	val selectorTitulo: String? = null,
	val selectorDisponible: String? = null,
	val notas: String? = null,
	/** auto, directo o navegador (migración 2). */
	val modoDescarga: String = ModoDescarga.AUTO,
)

/** Cómo se descargan las páginas de una tienda (columna tiendas.modo_descarga). */
object ModoDescarga {
	const val AUTO = "auto"
	const val DIRECTO = "directo"
	const val NAVEGADOR = "navegador"
	val TODOS = listOf(AUTO, DIRECTO, NAVEGADOR)
}

data class Producto(
	val id: Long = 0,
	val uuid: String,
	val nombre: String,
	val url: String,
	val tiendaId: Long? = null,
	val categoriaId: Long? = null,
	val grupo: String? = null,
	val moneda: String = "EUR",
	val precioActual: Double? = null,
	val disponible: Boolean = true,
	val precioInicial: Double? = null,
	val precioMinimo: Double? = null,
	val fechaMinimo: String? = null,
	val precioMaximo: Double? = null,
	val fechaMaximo: String? = null,
	val precioAnterior: Double? = null,
	val fechaCambio: String? = null,
	val precioObjetivo: Double? = null,
	val alertaPorcentaje: Double = 0.0,
	val avisarDisponible: Boolean = true,
	val selectorPrecio: String? = null,
	val imagenUrl: String? = null,
	val notas: String? = null,
	val favorito: Boolean = false,
	val activo: Boolean = true,
	val fechaAlta: String? = null,
	val ultimaComprobacion: String? = null,
	val ultimoError: String? = null,
	val erroresSeguidos: Int = 0,
	/** Variante elegida: su sku o su nombre (migración 2). */
	val variante: String? = null,
	/** De dónde salió el último precio («JSON-LD», «plataforma shopify», «elegido por ti»...). */
	val origenPrecio: String? = null,
	/** alta, media o baja. */
	val confianza: String? = null,
	/** Huella del selector elegido por el usuario: importe, texto y atributo, en JSON. */
	val huellaSelector: String? = null,
	/** El precio guardado es un «desde» (variantes sin elegir o rango). */
	val desde: Boolean = false,
)

/** Una fila del historial: solo se guarda cuando cambia el precio o la disponibilidad. */
data class PuntoHistorial(
	val fecha: String,
	val precio: Double?,
	val disponible: Boolean,
)

/** Tipos de aviso (columna avisos.tipo). */
object TipoAviso {
	const val OBJETIVO = "objetivo"
	const val MINIMO = "minimo"
	const val BAJADA = "bajada"
	const val SUBIDA = "subida"
	const val DISPONIBLE = "disponible"
	const val AGOTADO = "agotado"
	const val ERROR = "error"
}

data class Aviso(
	val id: Long = 0,
	val productoId: Long? = null,
	val fecha: String,
	val tipo: String,
	val titulo: String,
	val mensaje: String,
	val leido: Boolean = false,
)

/**
 * Ajustes que afectan a la comprobación y a los avisos (claves de la
 * especificación). La app Android los lee de SharedPreferences.
 */
data class AjustesAvisos(
	val avisarBajadas: Boolean = true,
	val avisarSubidas: Boolean = true,
	val avisarObjetivo: Boolean = true,
	val avisarMinimo: Boolean = true,
	val avisarDisponible: Boolean = true,
	val avisarAgotado: Boolean = false,
	val avisarErrores: Boolean = false,
	val cambioMinimoPorcentaje: Double = 0.0,
)

/** Mensajes de error comunes con la app de Windows (también sirven para saber el estado de la última comprobación). */
object MensajesError {
	const val BLOQUEO = "La tienda ha pedido comprobar que no eres un robot. Se volverá a intentar en la próxima comprobación."
	const val SIN_PRECIO = "No se encontró el precio en la página. Puede que la tienda haya cambiado su diseño: prueba con un selector propio en Editar."
	const val SIN_CONEXION = "No hay conexión a internet o no se encuentra la tienda. Se volverá a intentar en la próxima comprobación."
	const val TIEMPO_AGOTADO = "La tienda ha tardado demasiado en responder. Se volverá a intentar en la próxima comprobación."
	const val NO_DECIDIDO = "No se pudo decidir cuál es el precio. Abre el producto y elige el precio correcto."
	const val SELECTOR_ROTO = "La posición del precio en la página ha cambiado. Vuelve a elegir el precio en Editar."
	const val CATEGORIA = "El producto ya no existe: la tienda redirige a una categoría."
	const val NO_ENCONTRADA = "La página del producto no existe (error 404). Puede que la tienda la haya quitado o cambiado de dirección."
	fun codigo(codigo: Int) = "La tienda ha respondido con un error (código $codigo). Se volverá a intentar en la próxima comprobación."
}

/** Estado de la última comprobación, que se distingue siempre en la lista y en los detalles. */
enum class EstadoComprobacion { SIN_COMPROBAR, CORRECTA, SIN_PRECIO, BLOQUEADA, SIN_CONEXION, OTRO_ERROR }

/** El estado sale del último error guardado (sin columnas nuevas: así es igual en las dos apps). */
fun estadoComprobacion(p: Producto): EstadoComprobacion {
	val error = p.ultimoError
	return when {
		p.ultimaComprobacion == null && error.isNullOrBlank() -> EstadoComprobacion.SIN_COMPROBAR
		error.isNullOrBlank() -> EstadoComprobacion.CORRECTA
		error == MensajesError.BLOQUEO || error.contains("robot", ignoreCase = true) -> EstadoComprobacion.BLOQUEADA
		error == MensajesError.SIN_PRECIO || error.startsWith("No se encontró el precio") || error == MensajesError.NO_DECIDIDO ||
			error == MensajesError.SELECTOR_ROTO -> EstadoComprobacion.SIN_PRECIO
		error == MensajesError.SIN_CONEXION || error == MensajesError.TIEMPO_AGOTADO ||
			error.contains("conexión", ignoreCase = true) -> EstadoComprobacion.SIN_CONEXION
		else -> EstadoComprobacion.OTRO_ERROR
	}
}

/** Origen del precio leído (se guarda en productos.origen_precio y se muestra en detalles). */
enum class OrigenPrecio(val texto: String) {
	SELECTOR_PRODUCTO("selector del producto"),
	SELECTOR_TIENDA("selector de la tienda"),
	REGLA_TIENDA("regla de la tienda"),
	API("API de la tienda"),
	JSON_LD("JSON-LD"),
	METADATOS("metadatos"),
	MICRODATOS("microdatos"),
	PLATAFORMA("plataforma"),
	ANALISIS("análisis de la página"),
	ELEGIDO("elegido por ti"),
	TITULO_PAGINA("título de la página"),
}

/** Confianza del precio (productos.confianza). */
object Confianza {
	const val ALTA = "alta"
	const val MEDIA = "media"
	const val BAJA = "baja"
}
