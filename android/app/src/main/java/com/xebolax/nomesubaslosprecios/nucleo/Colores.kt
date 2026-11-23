package com.xebolax.nomesubaslosprecios.nucleo

/*
 * Colores de la lista (1.1.0): paleta y qué color lleva cada producto o aviso.
 * Lógica pura (sin Android), probada en la JVM. La especificación común está en
 * compartido/ESPECIFICACION.md, «Colores de la lista»: Windows usa la misma
 * paleta, los mismos identificadores y la misma regla (app/services/colores.py).
 *
 * El color nunca es la única pista: la fila ya empieza por su estado («En
 * oferta», «Agotado»...) y dice «bajó» o «subió».
 */

/** Qué estado se colorea. id es el sufijo de la clave de ajustes (color_bajada...). */
enum class TipoColor(val id: String, val porDefecto: String) {
	BAJADA("bajada", "verde"),
	SUBIDA("subida", "rojo"),
	OBJETIVO("objetivo", "azul"),
	PROBLEMA("problema", "gris");

	/** Clave de ajustes: color_bajada, color_subida, color_objetivo, color_problema. */
	val clave: String get() = "color_$id"
}

/** Qué se colorea: el fondo de la fila o las letras. */
enum class ModoColores(val id: String) {
	FONDO("fondo"),
	TEXTO("texto");

	companion object {
		val POR_DEFECTO = FONDO

		/** Un valor desconocido se lee como el de por defecto. */
		fun de(id: String?): ModoColores = entries.firstOrNull { it.id == id } ?: POR_DEFECTO
	}
}

/**
 * Un color de la paleta (ARGB). fondo y texto, con el tema claro; fondoOscuro y
 * textoClaro, con el oscuro. null en «ninguno» (Sin color).
 */
data class ColorPaleta(
	val id: String,
	val nombre: String,
	val fondo: Int?,
	val texto: Int?,
	val fondoOscuro: Int?,
	val textoClaro: Int?,
) {
	val sinColor: Boolean get() = fondo == null

	/** Color que toca según el modo y el tema; null = los colores normales. */
	fun pintura(modo: ModoColores, temaOscuro: Boolean): Int? = when (modo) {
		ModoColores.FONDO -> if (temaOscuro) fondoOscuro else fondo
		ModoColores.TEXTO -> if (temaOscuro) textoClaro else texto
	}
}

object Colores {

	const val NINGUNO = "ninguno"

	private const val SIETE_DIAS_MS = 7L * 24 * 60 * 60 * 1000

	/** «#C8E6C9» → 0xFFC8E6C9. */
	fun hex(texto: String): Int = (0xFF000000L or texto.removePrefix("#").toLong(16)).toInt()

	private fun c(id: String, nombre: String, fondo: String, texto: String, fondoOscuro: String, textoClaro: String) =
		ColorPaleta(id, nombre, hex(fondo), hex(texto), hex(fondoOscuro), hex(textoClaro))

	/** La paleta de la especificación, en su orden. */
	val PALETA: List<ColorPaleta> = listOf(
		ColorPaleta(NINGUNO, "Sin color", null, null, null, null),
		c("verde", "Verde", "#C8E6C9", "#1B5E20", "#1E4620", "#A5D6A7"),
		c("azul", "Azul", "#BBDEFB", "#0D47A1", "#0D3260", "#90CAF9"),
		c("celeste", "Celeste", "#B3E5FC", "#01579B", "#0A3D5C", "#81D4FA"),
		c("turquesa", "Turquesa", "#B2DFDB", "#004D40", "#0B3D38", "#80CBC4"),
		c("morado", "Morado", "#E1BEE7", "#4A148C", "#3B1D4A", "#CE93D8"),
		c("rosa", "Rosa", "#F8BBD0", "#880E4F", "#4A1830", "#F48FB1"),
		c("rojo", "Rojo", "#FFCDD2", "#B71C1C", "#5C1A1A", "#EF9A9A"),
		c("naranja", "Naranja", "#FFE0B2", "#BF360C", "#5A3210", "#FFCC80"),
		c("amarillo", "Amarillo", "#FFF9C4", "#7A5C00", "#4D4410", "#FFF59D"),
		c("marron", "Marrón", "#D7CCC8", "#4E342E", "#3E2C26", "#BCAAA4"),
		c("gris", "Gris", "#E0E0E0", "#424242", "#3A3A3A", "#BDBDBD"),
	)

	val IDS: List<String> = PALETA.map { it.id }

	private val POR_ID = PALETA.associateBy { it.id }

	/** Color de la paleta; un identificador desconocido vale el de por defecto del tipo (o ninguno). */
	fun color(id: String?, tipo: TipoColor? = null): ColorPaleta =
		POR_ID[id] ?: POR_ID.getValue(tipo?.porDefecto ?: NINGUNO)

	/**
	 * Qué color lleva un producto (null = ninguno), el primero que se cumpla:
	 * 1. En pausa: ninguno. 2. Última comprobación mal o agotado: problema.
	 * 3. Pendiente: ninguno. 4. Precio deseado alcanzado: objetivo.
	 * 5. En oferta (la regla de la sección Ofertas): bajada.
	 * 6. Subió y el cambio fue en los últimos 7 días: subida.
	 */
	fun tipoColor(p: Producto, ahoraMs: Long = System.currentTimeMillis()): TipoColor? {
		if (!p.activo) return null
		val estado = estadoComprobacion(p)
		if (estado == EstadoComprobacion.BLOQUEADA || estado == EstadoComprobacion.SIN_PRECIO ||
			estado == EstadoComprobacion.SIN_CONEXION || estado == EstadoComprobacion.OTRO_ERROR
		) return TipoColor.PROBLEMA
		if (!p.disponible) return TipoColor.PROBLEMA
		if (estado == EstadoComprobacion.SIN_COMPROBAR) return null
		if (Ofertas.objetivoAlcanzado(p)) return TipoColor.OBJETIVO
		if (Ofertas.esOferta(p, ahoraMs)) return TipoColor.BAJADA
		val actual = p.precioActual
		val anterior = p.precioAnterior
		val cambio = Fechas.ms(p.fechaCambio)
		if (actual != null && anterior != null && anterior > 0.0 && actual > anterior && cambio != null && ahoraMs - cambio <= SIETE_DIAS_MS) {
			return TipoColor.SUBIDA
		}
		return null
	}

	/** Color de un aviso según su tipo (tabla avisos); «disponible» y los desconocidos no llevan. */
	fun tipoColorAviso(tipo: String?): TipoColor? = when (tipo) {
		"objetivo" -> TipoColor.OBJETIVO
		"minimo", "bajada" -> TipoColor.BAJADA
		"subida" -> TipoColor.SUBIDA
		"agotado", "error" -> TipoColor.PROBLEMA
		else -> null
	}
}

/** Los ajustes de colores ya leídos y comprobados. */
data class AjustesColores(
	val activos: Boolean = true,
	val modo: ModoColores = ModoColores.POR_DEFECTO,
	/** Identificador elegido para cada tipo (los que falten, el de por defecto). */
	val elegidos: Map<TipoColor, String> = emptyMap(),
) {
	/** Color que toca a un tipo (null si no se colorea: desactivado, sin tipo o «Sin color»). */
	fun colorDe(tipo: TipoColor?): ColorPaleta? {
		if (!activos || tipo == null) return null
		return Colores.color(elegidos[tipo] ?: tipo.porDefecto, tipo).takeUnless { it.sinColor }
	}

	/** Fondo (modo fondo) o color de las letras (modo texto) para una fila; null = los normales. */
	fun pintura(tipo: TipoColor?, temaOscuro: Boolean): Int? = colorDe(tipo)?.pintura(modo, temaOscuro)
}
