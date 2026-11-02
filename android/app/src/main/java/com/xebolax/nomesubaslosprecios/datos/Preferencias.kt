package com.xebolax.nomesubaslosprecios.datos

import android.content.Context
import android.content.SharedPreferences
import androidx.preference.PreferenceManager
import com.xebolax.nomesubaslosprecios.nucleo.AjustesAvisos
import com.xebolax.nomesubaslosprecios.nucleo.Intercambio

/**
 * Ajustes de la app con las claves de la especificación (y solo_wifi, propio
 * de Android). Los ListPreference y EditTextPreference guardan texto y los
 * deslizadores, enteros: aquí se leen sea cual sea el tipo guardado.
 */
class Preferencias(contexto: Context) {

	val p: SharedPreferences = PreferenceManager.getDefaultSharedPreferences(contexto)

	companion object {
		const val INTERVALO_HORAS = "intervalo_horas"
		const val COMPROBAR_AL_INICIAR = "comprobar_al_iniciar"
		const val AVISAR_BAJADAS = "avisar_bajadas"
		const val AVISAR_SUBIDAS = "avisar_subidas"
		const val AVISAR_OBJETIVO = "avisar_objetivo"
		const val AVISAR_MINIMO = "avisar_minimo"
		const val AVISAR_DISPONIBLE = "avisar_disponible"
		const val AVISAR_AGOTADO = "avisar_agotado"
		const val AVISAR_ERRORES = "avisar_errores"
		const val CAMBIO_MINIMO_PORCENTAJE = "cambio_minimo_porcentaje"
		const val PAUSA_ENTRE_PETICIONES = "pausa_entre_peticiones"
		const val TIEMPO_ESPERA = "tiempo_espera"
		const val CONSERVAR_AVISOS_DIAS = "conservar_avisos_dias"
		const val BUSCAR_ACTUALIZACIONES = "buscar_actualizaciones"
		const val SOLO_WIFI = "solo_wifi"

		/** Claves que se guardan como texto (ListPreference y EditTextPreference). */
		private val COMO_TEXTO = setOf(INTERVALO_HORAS, CONSERVAR_AVISOS_DIAS, CAMBIO_MINIMO_PORCENTAJE)
		/** Claves que se guardan como entero (deslizadores). */
		private val COMO_ENTERO = setOf(PAUSA_ENTRE_PETICIONES, TIEMPO_ESPERA)

		val INTERVALOS = listOf(1, 2, 3, 6, 12, 24)

		private const val ORDEN = "orden_lista"
		private const val FILTROS = "filtros_lista"
		private const val ULTIMA_GENERAL = "ultima_comprobacion_general"
		private const val PERMISO_EXPLICADO = "permiso_notificaciones_explicado"
	}

	private fun entero(clave: String, porDefecto: Int): Int = when (val v = p.all[clave]) {
		is Int -> v
		is Long -> v.toInt()
		is Float -> v.toInt()
		is String -> v.trim().toIntOrNull() ?: v.trim().replace(',', '.').toDoubleOrNull()?.toInt() ?: porDefecto
		else -> porDefecto
	}

	private fun real(clave: String, porDefecto: Double): Double = when (val v = p.all[clave]) {
		is Int -> v.toDouble()
		is Long -> v.toDouble()
		is Float -> v.toDouble()
		is String -> v.trim().replace(',', '.').toDoubleOrNull() ?: porDefecto
		else -> porDefecto
	}

	private fun booleano(clave: String, porDefecto: Boolean): Boolean = (p.all[clave] as? Boolean) ?: porDefecto

	val intervaloHoras: Int get() = entero(INTERVALO_HORAS, 6).let { v -> if (v in INTERVALOS) v else 6 }
	val comprobarAlIniciar: Boolean get() = booleano(COMPROBAR_AL_INICIAR, true)
	val pausaEntrePeticiones: Int get() = entero(PAUSA_ENTRE_PETICIONES, 3).coerceIn(0, 120)
	val tiempoEspera: Int get() = entero(TIEMPO_ESPERA, 25).coerceIn(5, 120)
	val conservarAvisosDias: Int get() = entero(CONSERVAR_AVISOS_DIAS, 90).coerceAtLeast(0)
	val buscarActualizaciones: Boolean get() = booleano(BUSCAR_ACTUALIZACIONES, true)
	val soloWifi: Boolean get() = booleano(SOLO_WIFI, false)

	val ajustesAvisos: AjustesAvisos
		get() = AjustesAvisos(
			avisarBajadas = booleano(AVISAR_BAJADAS, true),
			avisarSubidas = booleano(AVISAR_SUBIDAS, true),
			avisarObjetivo = booleano(AVISAR_OBJETIVO, true),
			avisarMinimo = booleano(AVISAR_MINIMO, true),
			avisarDisponible = booleano(AVISAR_DISPONIBLE, true),
			avisarAgotado = booleano(AVISAR_AGOTADO, false),
			avisarErrores = booleano(AVISAR_ERRORES, false),
			cambioMinimoPorcentaje = real(CAMBIO_MINIMO_PORCENTAJE, 0.0).coerceAtLeast(0.0),
		)

	/** Orden elegido de la lista (se recuerda). */
	var orden: String
		get() = p.getString(ORDEN, "nombre") ?: "nombre"
		set(v) = p.edit().putString(ORDEN, v).apply()

	/** Filtros rápidos activos: activos, error, agotados. */
	var filtros: Set<String>
		get() = p.getStringSet(FILTROS, emptySet()).orEmpty()
		set(v) = p.edit().putStringSet(FILTROS, v).apply()

	/** Cuándo terminó la última comprobación de todos los productos (ms). */
	var ultimaComprobacionGeneral: Long
		get() = p.getLong(ULTIMA_GENERAL, 0L)
		set(v) = p.edit().putLong(ULTIMA_GENERAL, v).apply()

	var permisoExplicado: Boolean
		get() = p.getBoolean(PERMISO_EXPLICADO, false)
		set(v) = p.edit().putBoolean(PERMISO_EXPLICADO, v).apply()

	/** Ajustes para exportar, con los tipos de la especificación. */
	fun exportar(): Map<String, Any?> = linkedMapOf(
		INTERVALO_HORAS to intervaloHoras,
		COMPROBAR_AL_INICIAR to comprobarAlIniciar,
		AVISAR_BAJADAS to ajustesAvisos.avisarBajadas,
		AVISAR_SUBIDAS to ajustesAvisos.avisarSubidas,
		AVISAR_OBJETIVO to ajustesAvisos.avisarObjetivo,
		AVISAR_MINIMO to ajustesAvisos.avisarMinimo,
		AVISAR_DISPONIBLE to ajustesAvisos.avisarDisponible,
		AVISAR_AGOTADO to ajustesAvisos.avisarAgotado,
		AVISAR_ERRORES to ajustesAvisos.avisarErrores,
		CAMBIO_MINIMO_PORCENTAJE to ajustesAvisos.cambioMinimoPorcentaje,
		PAUSA_ENTRE_PETICIONES to pausaEntrePeticiones,
		TIEMPO_ESPERA to tiempoEspera,
		CONSERVAR_AVISOS_DIAS to conservarAvisosDias,
		BUSCAR_ACTUALIZACIONES to buscarActualizaciones,
		SOLO_WIFI to soloWifi,
	)

	/** Aplica los ajustes de un archivo importado (solo las claves conocidas y con el tipo que espera cada control). */
	fun importar(ajustes: Map<String, Any?>) {
		val e = p.edit()
		for ((clave, valor) in ajustes) {
			if (clave !in Intercambio.CLAVES_AJUSTES || valor == null) continue
			when {
				clave in COMO_TEXTO -> when (valor) {
					is Number -> e.putString(clave, if (clave == CAMBIO_MINIMO_PORCENTAJE) valor.toDouble().toString().removeSuffix(".0") else valor.toInt().toString())
					is String -> e.putString(clave, valor)
				}
				clave in COMO_ENTERO -> (valor as? Number)?.let { e.putInt(clave, it.toInt()) }
				valor is Boolean -> e.putBoolean(clave, valor)
			}
		}
		e.apply()
	}
}
